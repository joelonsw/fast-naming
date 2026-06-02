"""
LLM 클라이언트 및 작명 생성 모듈
확장 가능한 Multi-Provider 구조
"""

import json
import logging
from typing import List, Dict, Any

from state import ContestInfo, Submission
from llm_clients import create_generation_clients, get_rate_limit_delay
from contest_intelligence import build_contest_profile, build_example_insights, prioritize_strategies

logger = logging.getLogger(__name__)


# ============================================================
# 창의적 전략 정의
# ============================================================

CREATIVE_STRATEGIES = [
    {
        "name": "Keyword Combination",
        "description": "핵심 키워드 조합",
        "prompt_injection": """
**전략: 핵심 키워드 조합**
- 주최사의 핵심 정체성과 가치에 집중하세요.
- 공모전 설명에서 핵심 단어들을 추출하세요.
- 추출한 키워드들을 창의적으로 결합하여 작명하세요.
"""
    },
    {
        "name": "Metaphor & Analogy",
        "description": "은유와 비유",
        "prompt_injection": """
**전략: 은유와 비유**
- 공모전 주제가 무엇과 비슷한지 생각하세요. (등대? 도약대? 캔버스?)
- 은유적 상징을 활용하여 감성을 자극하는 작명을 만드세요.
"""
    },
    {
        "name": "Benefit-Oriented",
        "description": "혜택 중심",
        "prompt_injection": """
**전략: 혜택 중심 접근**
- 사용자가 얻게 될 가치나 혜택에만 집중하세요.
- 슬로건만 들어도 긍정적 결과가 떠오르도록 만드세요.
"""
    },
    {
        "name": "Wordplay & Wit",
        "description": "언어유희와 재치",
        "prompt_injection": """
**전략: 언어유희와 재치**
- 재치 있는 말장난, 중의적 표현, 기발한 줄임말을 활용하세요.
- 기억에 오래 남는 매력적인 작명을 만드세요.
"""
    },
    {
        "name": "Future Vision",
        "description": "미래 비전",
        "prompt_injection": """
**전략: 미래 비전 제시**
- 주최사가 만들고자 하는 이상적인 미래를 상상하세요.
- '혁신', '발전', '도약' 등 미래 지향적 느낌을 주세요.
"""
    },
    {
        "name": "Simple & Direct",
        "description": "단순함과 직관성",
        "prompt_injection": """
**전략: 단순함과 직관성**
- 불필요한 수식어를 제거하고 본질에 집중하세요.
- 짧고 간결하며 누구나 쉽게 기억할 수 있어야 합니다.
"""
    },
    {
        "name": "Korean Wordplay",
        "description": "한국어 언어유희",
        "prompt_injection": """
**전략: 한국어 언어유희**
- 두운(頭韻): 같은 자음으로 시작하는 단어들 조합 (예: "빛나는 비전", "꿈꾸는 군산")
- 각운(脚韻): 같은 모음으로 끝나는 단어들 조합
- 의성어/의태어: 생동감 있는 표현 (예: "붕붕", "반짝반짝")
- 줄임말/합성어: 새로운 조어 (예: "마플" = 마린플레이)
- 한글의 아름다움을 살린 표현을 사용하세요.
"""
    },
    {
        "name": "Korean Cultural Reference",
        "description": "한국 문화 레퍼런스",
        "prompt_injection": """
**전략: 한국 문화 레퍼런스**
- 사자성어나 고사성어를 현대적으로 재해석
- 한국 전통 문화 요소 (한, 정, 흥, 멋) 활용
- 지역 특색 반영 (해당 지역의 역사, 특산물, 명소)
- MZ세대가 공감할 수 있는 트렌드 표현 활용
"""
    },
    # === 신규 전략 4개 (1등 달성용) ===
    {
        "name": "Winner Perspective",
        "description": "수상자 관점",
        "prompt_injection": """
**전략: 수상자 관점 (역할극)**
당신은 이미 이 공모전에서 1등을 수상한 작가입니다.
- 심사위원들이 왜 당신의 작품을 선택했는지 설명하면서
- 그 작품이 무엇이었는지 공개하세요
- 다른 작품들을 제치고 선정된 결정적 이유를 담으세요
"""
    },
    {
        "name": "Rhyme & Rhythm",
        "description": "운율과 리듬감",
        "prompt_injection": """
**전략: 운율과 리듬감**
- 4음절, 7음절 등 읽기 좋은 리듬을 만드세요
- 반복, 대구, 점층 구조를 활용하세요
- 소리 내어 읽었을 때 귀에 꼽히는 작명을 만드세요
- 예: "함께 떠나요, 함께 자라요", "컨네면 컨네"
"""
    },
    {
        "name": "Emotional Impact",
        "description": "감정적 울림",
        "prompt_injection": """
**전략: 감정적 울림**
- 보는 순간 감동이나 설렘을 주는 작명을 만드세요
- 희망, 사랑, 껼림, 감사 등 보편적 감정을 자극하세요
- 심사위원의 마음을 움직이는 선정적 요소를 넣으세요
- 예: "당신의 꼀에 날개를", "오늘이 내일을 만든다"
"""
    },
    {
        "name": "Neologism Creation",
        "description": "신조어 창작",
        "prompt_injection": """
**전략: 신조어 창작**
- 기존에 없는 완전히 새로운 단어를 만드세요
- 두 단어를 합성하거나 발음을 변형하여 독창적인 이름을 만드세요
- 상표 등록이 가능할 정도로 독특해야 합니다
- 예: "컧럭터" (게 + 캐릭터), "맬스플레인" (맨들 + 설명), "코린이"(코렜 린스)
"""
    },
]


# 공모전 유형별 특화 프롬프트
CONTEST_TYPE_PROMPTS = {
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


# ============================================================
# 프롬프트 생성
# ============================================================

def create_system_prompt(contest: ContestInfo, contest_profile: Dict[str, Any]) -> str:
    """Chain-of-Thought 시스템 프롬프트 생성"""
    return f'''당신은 대한민국 최고의 네이미스트이며, 수많은 공모전에서 1등을 수상한 경험이 있습니다.
당신은 주최측이 원하는 {contest["contest_type"]}을 무조건 제공하는 네이미스트입니다.

**Chain-of-Thought 접근법을 사용하세요:**
1. 먼저, 공모전의 핵심 요구사항을 분석하세요.
2. 다음으로, 주최기관의 특성과 가치를 파악하세요.
3. 대상 청중(심사위원)이 선호할 스타일을 고려하세요.
4. 역대 수상작의 공통 패턴을 참고하세요.
5. 위 분석을 바탕으로 최적의 작명 3개를 도출하세요.

추가로 아래 공모전 인텔리전스를 반드시 반영하세요.
{contest_profile.get("prompt_boost", "")}

반드시 JSON 형식으로만 응답해야 합니다.'''


def create_user_prompt(
    contest: ContestInfo, 
    examples: List[Dict[str, str]], 
    strategy: Dict[str, Any],
    contest_profile: Dict[str, Any],
) -> str:
    """사용자 프롬프트 생성"""

    selected_examples = examples[:3] if examples else []
    example_insights = build_example_insights(selected_examples)
    
    # 공모전 유형 명시적 지시
    contest_type = contest['contest_type']
    type_instruction = ""
    if contest_type == "슬로건":
        type_instruction = """
**중요: 이 공모전은 '슬로건' 공모전입니다!**
- 슬로건은 짧고 기억에 남는 문구입니다 (예: "함께 만드는 행복한 미래")
- 네이밍(이름)이 아닌 홍보 문구/캐치프레이즈를 만들어야 합니다
- 보통 한 문장 또는 짧은 문구 형태입니다
"""
    elif contest_type == "네이밍":
        type_instruction = """
**중요: 이 공모전은 '네이밍' 공모전입니다!**
- 네이밍은 이름/명칭입니다 (예: "스마트라이프", "드림파크")
- 슬로건(문구)이 아닌 브랜드명/서비스명/제품명을 만들어야 합니다
- 보통 1~4단어의 이름 형태입니다
"""
    
    prompt = f"{contest['title']}에 참여하여 수상 확률이 가장 높은 3가지 {contest_type}을 만드세요.\n\n"
    
    # 유형 명시적 지시 추가
    if type_instruction:
        prompt += type_instruction + "\n"
    
    # 공모전 유형별 특화 프롬프트 추가
    held_by_type = contest.get('held_by_type', '')
    if held_by_type in CONTEST_TYPE_PROMPTS:
        prompt += CONTEST_TYPE_PROMPTS[held_by_type] + "\n"
    
    # 전략 주입
    prompt += strategy["prompt_injection"] + "\n\n"
    prompt += contest_profile.get("prompt_boost", "") + "\n"
    
    prompt += f"<contest_description>\n{contest['content'][:2000]}\n</contest_description>\n\n"
    
    if selected_examples:
        prompt += "앞서 비슷한 유형의 공모전에서 수상한 작품들을 참고하세요.\n"
        for i, example in enumerate(selected_examples, 1):
            prompt += f"<sample_input{i}>\n{example.get('contestTitle', '')}\n</sample_input{i}>\n"
            prompt += f"<ideal_output{i}>\n{example.get('contestWinner', '')}\n</ideal_output{i}>\n"
            prompt += f"<strength{i}>\n{example.get('strength', '')}\n</strength{i}>\n\n"
        prompt += example_insights + "\n"

    prompt += """
[💡 현대 1등 수상작들의 세련된 조어/작명 트렌드 예시]
1. **순우리말 + 한글/한자 뜻의 하이브리드 조합 (스토리가 느껴짐)**
   - 예: '라온숨' ('즐거운'의 순우리말 '라온' + 자연의 살아있음/호흡을 뜻하는 '숨')
   - 예: '시우아람' (때맞춰 내리는 단비 '시우' + 탐스럽게 잘 익은 농산물 '아람')
2. **함축적 은유 및 유기적 조어 (기존 보통명사 나열 타파)**
   - 예: 단순히 '그린마켓', '초록뜰' 대신 -> '초록아람', '하루자연', '이음뜰' 처럼 참신하게 구성.
   - 예: '스마트링크', '한길테크' 등 1차원적 결합 대신 -> '링크로(Link-Ro)', '온웨이(OnWay)' 등 음성학적으로 부드럽고 상표권 출원이 용이한 세련된 조어 설계.
"""

    prompt += f"""guidelines:
1. 공모전 요구사항을 모두 준수해야 합니다.
2. 주최기관에서 좋아할 작명이어야 합니다.
3. 독창적이고 기억에 남는 작명을 만드세요.
4. 한국어의 아름다움과 리듬감을 살리세요.
5. 심사위원이 '이건 1등이다!'라고 느낄 만한 작품을 만드세요.
6. **반드시 '{contest_type}' 형식으로 생성하세요!**
7. **진부한 어근 단순합성 금지 (절대 규칙)**: '참/바른/뜰/마루/아람/도담/소담/초록/자연/에코/그린/늘/봄/온/누리/하늘' 등 네이밍 공모전 단골 단어들을 1차원적으로 단순 조합(예: 참바른뜰, 초록아람, 자연마루 등)하는 행위는 심사위원 채점 시 즉시 50점 이하로 강제 탈락(과락)됩니다. 식상한 단어의 붙여넣기를 멈추고, 완전히 새로운 유니크한 신조어, 은유법, 뉘앙스가 세련된 조어를 설계하여 차별화하십시오.

반드시 다음 JSON 형식으로만 응답하세요:
```json
[
    {{
        "submission": "{contest_type} 내용",
        "description": "해당 작명을 생성한 이유와 특징 설명"
    }},
    {{
        "submission": "{contest_type} 내용",
        "description": "해당 작명을 생성한 이유와 특징 설명"
    }},
    {{
        "submission": "{contest_type} 내용",
        "description": "해당 작명을 생성한 이유와 특징 설명"
    }}
]
```"""
    
    return prompt


# ============================================================
# 응답 파싱
# ============================================================

def parse_llm_response(response: str) -> List[Dict[str, str]]:
    """LLM 응답에서 작명 추출"""
    import re
    
    try:
        # JSON 블록 추출
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_match:
            json_str = json_match.group(1)
        elif response.strip().startswith('['):
            json_str = response.strip()
        else:
            # JSON 배열 찾기
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                json_str = json_match.group()
            else:
                logger.warning("JSON 파싱 실패, 빈 결과 반환")
                return []
        
        submissions = json.loads(json_str)
        
        # 유효성 검증
        valid_submissions = []
        for sub in submissions:
            if isinstance(sub, dict) and 'submission' in sub:
                valid_submissions.append({
                    'submission': sub.get('submission', ''),
                    'description': sub.get('description', ''),
                })
        
        return valid_submissions
        
    except Exception as e:
        logger.error(f"응답 파싱 실패: {e}")
        return []


# ============================================================
# 작명 생성 메인 함수
# ============================================================

async def generate_submissions(
    contest: ContestInfo,
    examples: List[Dict[str, str]],
    strategies: List[Dict[str, Any]] = None,
) -> List[Submission]:
    """다중 LLM과 다중 전략으로 작명 생성"""
    import asyncio
    
    strategies = strategies or CREATIVE_STRATEGIES
    strategies = prioritize_strategies(strategies, contest)
    contest_profile = build_contest_profile(contest)
    clients = create_generation_clients()
    
    if not clients:
        logger.error("사용 가능한 LLM 클라이언트가 없습니다!")
        return []
    
    all_submissions: List[Submission] = []
    system_prompt = create_system_prompt(contest, contest_profile)

    logger.info(
        "🧭 공모전 인텔리전스 | 키워드=%s | 분야=%s | 추천전략=%s",
        ", ".join(contest_profile.get("keywords", [])[:6]) or "없음",
        ", ".join(contest_profile.get("domain_tags", [])) or "일반",
        ", ".join(contest_profile.get("recommended_strategies", [])[:5]) or "기본",
    )
    
    for strategy in strategies:
        for client in clients:
            try:
                logger.info(f"🔄 {client.provider_name}/{client.model_name} - 전략: {strategy['name']}")
                
                user_prompt = create_user_prompt(contest, examples, strategy, contest_profile)
                response = await client.generate(system_prompt, user_prompt)
                
                parsed = parse_llm_response(response)
                
                for item in parsed:
                    submission = Submission(
                        name=item['submission'],
                        description=item['description'],
                        strategy=strategy['name'],
                        provider=client.provider_name,
                        model=client.model_name,
                        score=None,
                        criteria_scores=None,
                    )
                    all_submissions.append(submission)
                
                logger.info(f"✅ {len(parsed)}개 작명 생성됨")
                
                # Rate limit 대응
                delay = get_rate_limit_delay(client.provider_name)
                if delay > 0:
                    logger.info("⏳ %s rate limit 대응: %s초 대기...", client.provider_name, delay)
                    await asyncio.sleep(delay)
                
            except Exception as e:
                logger.error(f"❌ {client.provider_name} 생성 실패: {e}")
    
    logger.info(f"🎉 총 {len(all_submissions)}개 작명 생성 완료")
    return all_submissions


# 테스트용
if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    
    async def main():
        test_contest = ContestInfo(
            title="테스트 공모전",
            content="테스트 공모전 설명입니다.",
            held_by="테스트 기관",
            contest_type="네이밍",
            held_by_type="공공기관",
            url="https://example.com",
            submission_method="이메일",
            deadline="2024-12-31",
            d_day="D-10",
        )
        
        submissions = await generate_submissions(
            contest=test_contest,
            examples=[],
            strategies=CREATIVE_STRATEGIES[:2],  # 테스트용으로 2개만
        )
        
        for s in submissions:
            print(f"\n[{s['strategy']}] {s['name']}")
            print(f"  → {s['description']}")
    
    asyncio.run(main())
