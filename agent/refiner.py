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
    """TOP 작명들을 분석하고 개선된 버전 생성
    
    Args:
        contest: 공모전 정보
        top_submissions: TOP N 작명들
        groq_client: Groq 클라이언트
        
    Returns:
        정제된 작명 목록 (원본 + 개선본)
    """
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage
    import os
    import json
    import re
    
    logger.info(f"✨ TOP {len(top_submissions)}개 작명 정제 시작")
    
    # TOP 작명들 텍스트로 변환
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
        groq = ChatGroq(
            model="openai/gpt-oss-120b",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.8,
        )
        
        response = await groq.ainvoke([HumanMessage(content=prompt)])
        
        # JSON 파싱
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response.content)
        if json_match:
            refined = json.loads(json_match.group(1))
        else:
            refined = json.loads(response.content.strip())
        
        # 정제된 작명을 Submission으로 변환
        refined_submissions = []
        for item in refined:
            sub = Submission(
                name=item['submission'],
                description=f"[정제됨] {item['description']}",
                strategy="Refined",
                provider="groq",
                model="openai/gpt-oss-120b",
                score=None,
                criteria_scores=None,
            )
            refined_submissions.append(sub)
        
        logger.info(f"✅ {len(refined_submissions)}개 정제된 작명 생성됨")
        
        # Rate limit 대응
        await asyncio.sleep(3)
        
        return refined_submissions
        
    except Exception as e:
        logger.error(f"❌ 정제 실패: {e}")
        return []


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
