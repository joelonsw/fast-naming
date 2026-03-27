"""
작명 정제 및 다양성 강화 모듈
- 중복 제거 (Levenshtein 거리)
- 다양성 강화 (전략별 최소 1개 보장)
- 반복 정제 (TOP 10 → 개선 → TOP 3)
"""

import asyncio
import logging
from typing import List, Dict, Set
from difflib import SequenceMatcher
from collections import defaultdict

from state import Submission
from contest_intelligence import build_contest_profile
from llm_clients import create_primary_client, get_rate_limit_delay

logger = logging.getLogger(__name__)


def calculate_similarity(s1: str, s2: str) -> float:
    """두 문자열 간 유사도 계산 (0~1)"""
    return SequenceMatcher(None, s1, s2).ratio()


def remove_duplicates(
    submissions: List[Submission],
    similarity_threshold: float = 0.7,
) -> List[Submission]:
    """유사한 작명 중복 제거
    
    Args:
        submissions: 작명 목록
        similarity_threshold: 유사도 임계값 (이상이면 중복으로 간주)
        
    Returns:
        중복 제거된 작명 목록
    """
    if not submissions:
        return []
    
    unique = []
    seen_names: List[str] = []
    
    for sub in submissions:
        name = sub['name']
        is_duplicate = False
        
        for seen in seen_names:
            if calculate_similarity(name, seen) >= similarity_threshold:
                is_duplicate = True
                logger.debug(f"🔄 중복 제거: '{name}' ('{seen}'와 유사)")
                break
        
        if not is_duplicate:
            unique.append(sub)
            seen_names.append(name)
    
    removed_count = len(submissions) - len(unique)
    if removed_count > 0:
        logger.info(f"🧹 {removed_count}개 유사 작명 중복 제거 (임계값: {similarity_threshold})")
    
    return unique


def ensure_strategy_diversity(
    submissions: List[Submission],
    top_n: int = 10,
) -> List[Submission]:
    """각 전략에서 최소 1개는 TOP N에 포함되도록 보장
    
    Args:
        submissions: 점수순 정렬된 작명 목록
        top_n: 상위 N개
        
    Returns:
        다양성이 보장된 TOP N
    """
    if not submissions:
        return []
    
    # 전략별로 그룹화
    by_strategy: Dict[str, List[Submission]] = defaultdict(list)
    for sub in submissions:
        strategy = sub.get('strategy', 'Unknown')
        by_strategy[strategy].append(sub)
    
    # 각 전략별 최고 점수 1개씩 선택
    selected: List[Submission] = []
    selected_names: Set[str] = set()
    
    for strategy, subs in by_strategy.items():
        if subs:
            best = max(subs, key=lambda x: x.get('score', 0) or 0)
            if best['name'] not in selected_names:
                selected.append(best)
                selected_names.add(best['name'])
    
    # 나머지 슬롯은 점수순으로 채움
    remaining_slots = top_n - len(selected)
    if remaining_slots > 0:
        for sub in submissions:
            if len(selected) >= top_n:
                break
            if sub['name'] not in selected_names:
                selected.append(sub)
                selected_names.add(sub['name'])
    
    # 점수순 재정렬
    selected.sort(key=lambda x: x.get('score', 0) or 0, reverse=True)
    
    logger.info(f"🎯 전략 다양성 보장: {len(by_strategy)}개 전략에서 TOP {len(selected)} 선정")
    
    return selected


async def refine_top_submissions(
    contest,
    top_submissions: List[Submission],
    groq_client,
) -> List[Submission]:
    """TOP 작명들을 분석하고 개선된 버전 생성"""
    import json
    import re
    
    logger.info(f"✨ TOP {len(top_submissions)}개 작명 정제 시작")
    client = create_primary_client(temperature=0.8, max_tokens=2048)
    contest_profile = build_contest_profile(contest)

    if not client:
        logger.error("❌ 정제용 LLM이 없습니다")
        return []
    logger.info("🛠️ 정제 모델: %s/%s", client.provider_name, client.model_name)
    
    top_text = ""
    for i, sub in enumerate(top_submissions, 1):
        score = sub.get('score', 0) or 0
        top_text += f"{i}. {sub['name']} (점수: {score})\n   → {sub['description']}\n\n"
    
    prompt = f"""당신은 대한민국 최고의 네이미스트입니다.

아래는 "{contest['title']}" 공모전의 현재 TOP 작명들입니다:

{top_text}

위 작명들을 분석하고, 각각의 장점을 결합하여 더 나은 작명 3개를 만드세요.

개선 방향:
1. 한국어 언어유희 (두운, 각운, 의성어/의태어) 활용
2. 기억하기 쉬운 짧은 형태
3. 공모전 주제와 더 강한 연결성
4. 독창성과 차별화

반드시 다음 JSON 형식으로만 응답하세요:
```json
[
    {{"submission": "개선된 작명1", "description": "개선 이유"}},
    {{"submission": "개선된 작명2", "description": "개선 이유"}},
    {{"submission": "개선된 작명3", "description": "개선 이유"}}
]
```
"""
    
    try:
        system_prompt = f"""당신은 대한민국 최고의 네이미스트입니다. 더 나은 후보를 만들 때는 한국어 감각과 수상 가능성을 동시에 고려하세요.
{contest_profile.get("prompt_boost", "")}"""
        response = await client.generate(system_prompt, prompt)
        
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_match:
            refined = json.loads(json_match.group(1))
        else:
            refined = json.loads(response.strip())
        
        refined_submissions = []
        for item in refined:
            sub = Submission(
                name=item['submission'],
                description=f"[정제됨] {item['description']}",
                strategy="Refined",
                provider=client.provider_name,
                model=client.model_name,
                score=None,
                criteria_scores=None,
            )
            refined_submissions.append(sub)
        
        logger.info(f"✅ {len(refined_submissions)}개 정제된 작명 생성됨")
        await asyncio.sleep(get_rate_limit_delay(client.provider_name))
        
        return refined_submissions
        
    except Exception as e:
        logger.error(f"❌ 정제 실패: {e}")
        return []


# ============================================================
# Tournament Selection System (1등 달성용)
# ============================================================

async def tournament_selection(
    contest,
    submissions: List[Submission],
    final_count: int = 5,
) -> List[Submission]:
    """토너먼트 방식으로 최종 후보 선정
    
    Round 1: 점수 기준 상위 20개+
    Round 2: 전략 다양성 보장
    Round 3: 1:1 대결을 통한 최종 선정
    """
    logger.info(f"🏆 토너먼트 선정 시작 ({len(submissions)}개 → {final_count}개)")
    
    if len(submissions) <= final_count:
        return submissions
    
    # Round 1: 상위 20개 선정
    round1 = sorted(submissions, key=lambda x: x.get('score', 0) or 0, reverse=True)[:20]
    logger.info(f"   Round 1: {len(submissions)} → {len(round1)}개 (점수 기준)")
    
    # Round 2: 전략 다양성 보장
    round2 = ensure_strategy_diversity(round1, top_n=10)
    logger.info(f"   Round 2: {len(round1)} → {len(round2)}개 (전략 다양성)")
    
    # Round 3: 1:1 대결 토너먼트
    finalists = await _run_head_to_head_tournament(contest, round2, final_count)
    logger.info(f"   Round 3: {len(round2)} → {len(finalists)}개 (1:1 토너먼트)")
    
    return finalists


async def _run_head_to_head_tournament(
    contest,
    submissions: List[Submission],
    final_count: int,
) -> List[Submission]:
    """1:1 대결을 통한 토너먼트"""
    import json
    import re
    
    if len(submissions) <= final_count:
        return submissions
    
    client = create_primary_client(temperature=0.3, max_tokens=1024)
    if not client:
        logger.warning("토너먼트용 LLM이 없어 점수 기반 결과를 유지합니다")
        return submissions[:final_count]
    contest_profile = build_contest_profile(contest)
    logger.info("⚔️ 토너먼트 모델: %s/%s", client.provider_name, client.model_name)
    
    # 상위 5개 vs 나머지에서 대결
    top = submissions[:final_count]
    challengers = submissions[final_count:]
    
    for challenger in challengers[:3]:  # 최대 3개만 도전
        weakest_top = min(top, key=lambda x: x.get('score', 0) or 0)
        
        prompt = f"""다음 두 작명 중 "{contest['title']}" 공모전에서 1등할 가능성이 더 높은 것을 선택하세요.

A: {weakest_top['name']}
B: {challenger['name']}

반드시 JSON으로 응답: {{"winner": "A" 또는 "B", "reason": "선택 이유"}}"""
        
        try:
            system_prompt = f"""당신은 "{contest['title']}" 공모전의 최종 심사위원입니다.
{contest_profile.get("prompt_boost", "")}
둘 중 실제 수상 가능성이 더 높은 후보만 선택하세요."""
            response = await client.generate(system_prompt, prompt)
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                result = json.loads(json_match.group())
                if result.get('winner') == 'B':
                    top.remove(weakest_top)
                    top.append(challenger)
                    logger.info(f"   🔄 교체: '{weakest_top['name']}' → '{challenger['name']}'")
            
            await asyncio.sleep(get_rate_limit_delay(client.provider_name))
        except Exception as e:
            logger.error(f"대결 실패: {e}")
    
    return top


async def final_polish(
    contest,
    top_submissions: List[Submission],
) -> List[Submission]:
    """최종 후보 폴리싱 - 1등 달성을 위한 마지막 다듬기"""
    import json
    import re
    
    logger.info(f"💎 최종 폴리싱 시작 ({len(top_submissions)}개)")
    client = create_primary_client(temperature=0.5, max_tokens=2048)
    if not client:
        logger.warning("폴리싱용 LLM이 없어 원본 후보를 그대로 사용합니다")
        return top_submissions
    contest_profile = build_contest_profile(contest)
    logger.info("💎 폴리싱 모델: %s/%s", client.provider_name, client.model_name)
    
    polished = []
    
    for sub in top_submissions[:3]:  # TOP 3만 폴리싱
        prompt = f"""당신은 "{contest['title']}" 공모전 심사위원입니다.

다음 작명을 1등으로 만들기 위해 미세하게 다듬으세요:
- 현재 작명: {sub['name']}
- 설명: {sub['description']}

중요한 점은, 단순히 수정 이유만 말하는 것이 아니라 **공모전 주최측에 직접 제출할 수 있는 완벽하고 설득력 있는 '작명 배경 및 의미(Naming Reason)'를 작성해야 한다는 것입니다.**
보는 순간 1등이 확신되는 감동적이고 매력적인 설명이어야 합니다.

다음 중 하나를 선택하세요:
1. 현재 작명이 이미 완벽하면 그대로 유지하되 제출용 설명만 다듬기
2. 미세한 수정이 필요하면 개선된 버전 제안 및 제출용 설명 작성

반드시 JSON으로 응답:
```json
{{
    "final_name": "최종 작명 (수정 또는 원본 유지)",
    "final_description": "공모전 제출용으로 바로 복사붙여넣기 할 수 있는 완벽한 '작명 배경 및 의미' (2~3문장)",
    "polished": true/false,
    "polish_reason": "무엇을 왜 수정했는지 심사위원 관점의 분석 이유"
}}
```"""
        
        try:
            system_prompt = f"""당신은 "{contest['title']}" 공모전 심사위원입니다.
{contest_profile.get("prompt_boost", "")}
수정은 최소화하되 제출용 설명은 바로 쓸 수 있을 정도로 다듬으세요."""
            response = await client.generate(system_prompt, prompt)
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                result = json.loads(response.strip())
            
            if result.get('polished'):
                polished_sub = Submission(
                    name=result['final_name'],
                    description=f"{result.get('final_description', result.get('polish_reason', ''))}\n\n*[폴리싱됨] 심사위원 노트: {result.get('polish_reason', '')} | 원본: {sub['name']}*",
                    strategy=f"{sub['strategy']}-Polished",
                    provider=sub['provider'],
                    model=sub['model'],
                    score=sub.get('score'),
                    criteria_scores=sub.get('criteria_scores'),
                )
                polished.append(polished_sub)
                logger.info(f"   ✨ '{sub['name']}' → '{result['final_name']}'")
            else:
                polished.append(sub)
                logger.info(f"   ✅ '{sub['name']}' 유지")
            
            await asyncio.sleep(get_rate_limit_delay(client.provider_name))
            
        except Exception as e:
            logger.error(f"폴리싱 실패: {e}")
            polished.append(sub)
    
    # 나머지는 그대로 추가
    polished.extend(top_submissions[3:])
    
    return polished


def get_korean_special_strategies() -> List[Dict]:
    """한국어 특화 창의적 전략"""
    return [
        {
            "name": "Korean Wordplay",
            "description": "한국어 언어유희",
            "prompt_injection": """
**전략: 한국어 언어유희**
- 두운(頭韻): 같은 자음으로 시작하는 단어들 조합 (예: "빛나는 비전", "꿈꾸는 군산")
- 각운(脚韻): 같은 모음으로 끝나는 단어들 조합
- 의성어/의태어: 생동감 있는 표현 (예: "붕붕", "반짝반짝")
- 줄임말/합성어: 새로운 조어 (예: "마플" = 마린플레이)
"""
        },
        {
            "name": "Korean Cultural Reference",
            "description": "한국 문화 레퍼런스",
            "prompt_injection": """
**전략: 한국 문화 레퍼런스**
- 한국 전통 문화 요소 활용 (사자성어, 고사성어, 전통 용어)
- 트렌드 용어 활용 (MZ세대 표현, SNS 용어)
- 한국적 정서 반영 (정, 한, 흥, 멋)
- 지역 특색 반영 (해당 지역의 역사, 특산물, 명소)
"""
        },
    ]


def get_contest_type_prompts(held_by_type: str) -> str:
    """공모전 유형별 특화 프롬프트"""
    prompts = {
        "공공기관": """
**주최 유형: 공공기관**
- 공익성과 신뢰감을 주는 표현 사용
- 시민/국민이 공감할 수 있는 메시지
- 지속가능성, 상생, 협력 등 공공 가치 반영
- 너무 상업적이거나 가벼운 표현 지양
""",
        "사기업": """
**주최 유형: 사기업**
- 트렌디하고 세련된 표현 사용
- 마케팅 효과가 있는 기억하기 쉬운 이름
- 브랜드 아이덴티티와 연결 가능한 표현
- 젊고 역동적인 이미지 연출
""",
        "학교": """
**주최 유형: 학교**
- 젊음과 창의성을 표현
- 학생들이 공감할 수 있는 친근한 표현
- 미래지향적이고 희망적인 메시지
- 교육적 가치나 성장의 의미 담기
""",
    }
    return prompts.get(held_by_type, "")


# 테스트용
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 중복 제거 테스트
    test_subs = [
        Submission(name="군산 블루웨이브", description="테스트", strategy="A", provider="test", model="test", score=90, criteria_scores={}),
        Submission(name="군산 블루웨이브 파크", description="테스트", strategy="A", provider="test", model="test", score=85, criteria_scores={}),  # 유사
        Submission(name="해양드림", description="테스트", strategy="B", provider="test", model="test", score=80, criteria_scores={}),
    ]
    
    unique = remove_duplicates(test_subs)
    print(f"중복 제거: {len(test_subs)} → {len(unique)}")
