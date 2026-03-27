"""
Contest-specific heuristics to improve prompt fit and reranking quality.
"""

import re
from collections import Counter
from typing import Any, Dict, List, Tuple

from state import ContestInfo, Submission

KOREAN_STOPWORDS = {
    "공모전", "네이밍", "슬로건", "명칭", "이름", "브랜드", "서비스", "제품", "사업", "프로젝트",
    "주최", "주관", "기관", "대한", "관련", "위한", "통한", "모집", "선정", "개최", "참여", "응모",
    "제출", "운영", "활용", "기반", "지원", "대상", "내용", "분야", "소개", "및", "또는",
    "with", "the", "and", "for", "from", "your", "name", "brand",
}

GENERIC_TERMS = {
    "미래", "혁신", "도약", "행복", "희망", "비전", "함께", "세상", "내일", "가능성", "성장",
    "드림", "비전", "스마트", "글로벌", "새로운", "우리", "모두", "플러스", "더", "굿",
}

DOMAIN_KEYWORDS = {
    "tourism": ["관광", "여행", "투어", "축제", "문화", "방문", "체험", "휴양", "도시", "야행"],
    "environment": ["환경", "그린", "에코", "친환경", "탄소", "기후", "자원순환", "재활용"],
    "tech": ["ai", "디지털", "데이터", "플랫폼", "스마트", "it", "tech", "클라우드", "앱", "모빌리티"],
    "youth": ["청년", "청소년", "미래세대", "학생", "캠퍼스", "진로", "창업", "도전"],
    "public": ["시민", "국민", "공공", "행정", "복지", "안전", "상생", "소통", "정책"],
    "local": ["지역", "마을", "도시", "군", "구", "로컬", "상권", "특산물"],
    "finance": ["금융", "은행", "보험", "투자", "핀테크", "자산"],
    "health": ["건강", "의료", "돌봄", "헬스", "바이오", "치유"],
}

ORGANIZER_PROFILES = [
    {
        "name": "local-government",
        "keywords": ["시청", "군청", "구청", "도청", "교육청", "서울시", "부산", "울산", "제주", "전북", "성북구"],
        "traits": ["지역 상징성", "시민 공감도", "정책/사업 목적의 직관성"],
        "avoid": ["과도한 영문 조어", "민간 브랜드 같은 가벼운 톤"],
        "example_bias": ["도시브랜드", "공공와이파이", "안심귀가", "교육청", "관광"],
    },
    {
        "name": "public-agency",
        "keywords": ["공사", "공단", "재단", "진흥원", "공공", "행정안전부", "한국관광공사", "건강보험공단", "도로공사"],
        "traits": ["신뢰감", "기능 명확성", "공익성", "친근한 접근성"],
        "avoid": ["추상적 감성어 위주 구성", "근거 없는 화려함"],
        "example_bias": ["안전", "복지", "관광", "공공서비스", "정책"],
    },
    {
        "name": "education",
        "keywords": ["대학교", "대학", "학교", "캠퍼스", "학원"],
        "traits": ["도전/성장", "젊은 에너지", "비전 제시", "학문적 품격"],
        "avoid": ["너무 상업적인 카피", "과도한 줄임말"],
        "example_bias": ["개교", "비전", "학생", "청년"],
    },
    {
        "name": "finance",
        "keywords": ["은행", "카드", "보험", "증권", "금융"],
        "traits": ["신뢰감", "세련미", "브랜드 확장성", "짧고 강한 기억성"],
        "avoid": ["장황한 문장", "과도한 말장난"],
        "example_bias": ["비전", "서비스", "브랜드", "캠페인"],
    },
    {
        "name": "tech-brand",
        "keywords": ["삼성", "lg", "네이버", "카카오", "ai", "전자", "모빌리티", "플랫폼"],
        "traits": ["미래지향성", "브랜드화 가능성", "차별적 조어", "확장 가능한 톤"],
        "avoid": ["관공서식 문체", "너무 보수적인 일반명사"],
        "example_bias": ["ai", "플랫폼", "서비스", "가전", "통합"],
    },
]


def _normalize_token(token: str) -> str:
    return token.strip().lower()


def extract_keywords(text: str, limit: int = 10) -> List[str]:
    if not text:
        return []

    tokens = re.findall(r"[가-힣A-Za-z][가-힣A-Za-z0-9+-]{1,}", text.lower())
    counter: Counter[str] = Counter()

    for token in tokens:
        normalized = _normalize_token(token)
        if normalized in KOREAN_STOPWORDS:
            continue
        if len(normalized) <= 1:
            continue
        counter[normalized] += 1

    return [token for token, _ in counter.most_common(limit)]


def infer_domain_tags(text: str) -> List[str]:
    text_lower = text.lower()
    matched = []

    for tag, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword.lower() in text_lower for keyword in keywords):
            matched.append(tag)

    return matched


def detect_organizer_profile(held_by: str, content: str) -> Dict[str, Any]:
    combined = f"{held_by} {content[:800]}".lower()

    for profile in ORGANIZER_PROFILES:
        if any(keyword.lower() in combined for keyword in profile["keywords"]):
            return profile

    return {
        "name": "general",
        "traits": ["직관성", "기억성", "주제 적합성"],
        "avoid": ["generic 표현", "주제와 무관한 추상어"],
        "example_bias": [],
    }


def build_contest_profile(contest: ContestInfo) -> Dict[str, Any]:
    combined = " ".join([
        contest.get("title", ""),
        contest.get("held_by", ""),
        contest.get("content", "")[:1800],
    ])
    keywords = extract_keywords(combined, limit=12)
    domain_tags = infer_domain_tags(combined)
    organizer_profile = detect_organizer_profile(contest.get("held_by", ""), contest.get("content", ""))

    preferred_traits = []
    if contest.get("held_by_type") == "공공기관":
        preferred_traits.extend(["신뢰감", "공공성", "보편적 공감", "정책/서비스 연결성"])
    elif contest.get("held_by_type") == "사기업":
        preferred_traits.extend(["브랜드화 가능성", "기억용이성", "트렌디함", "차별화"])
    elif contest.get("held_by_type") == "학교":
        preferred_traits.extend(["젊은 감각", "밝은 톤", "성장/도전 메시지"])

    if contest.get("contest_type") == "네이밍":
        preferred_traits.extend(["짧은 발화성", "명칭 적합성", "상표화 가능성"])
    else:
        preferred_traits.extend(["문장 리듬감", "메시지 명확성", "구호성"])

    recommended_strategies = ["Keyword Combination", "Simple & Direct"]
    if "local" in domain_tags or "tourism" in domain_tags:
        recommended_strategies.extend(["Korean Cultural Reference", "Metaphor & Analogy"])
    if "tech" in domain_tags:
        recommended_strategies.extend(["Future Vision", "Neologism Creation"])
    if contest.get("contest_type") == "슬로건":
        recommended_strategies.extend(["Benefit-Oriented", "Rhyme & Rhythm", "Emotional Impact"])
    else:
        recommended_strategies.extend(["Wordplay & Wit", "Neologism Creation"])

    risk_patterns = [
        "주제와 무관한 추상어 남발",
        "기관명/사업 목적과 연결되지 않는 generic 표현",
        "네이밍 공모전인데 문장형 슬로건 생성",
        "슬로건 공모전인데 브랜드명처럼 짧은 조어만 생성",
    ]

    profile = {
        "keywords": keywords,
        "domain_tags": domain_tags,
        "preferred_traits": preferred_traits,
        "recommended_strategies": list(dict.fromkeys(recommended_strategies)),
        "risk_patterns": risk_patterns,
        "organizer_profile": organizer_profile,
    }
    profile["prompt_boost"] = build_prompt_boost(profile)
    return profile


def build_prompt_boost(profile: Dict[str, Any]) -> str:
    keywords = ", ".join(profile.get("keywords", [])[:8]) or "핵심 키워드 없음"
    domains = ", ".join(profile.get("domain_tags", [])) or "일반"
    traits = ", ".join(profile.get("preferred_traits", [])[:6]) or "기억에 남는 완성도"
    risks = "; ".join(profile.get("risk_patterns", [])[:4])
    organizer = profile.get("organizer_profile", {})
    organizer_name = organizer.get("name", "general")
    organizer_traits = ", ".join(organizer.get("traits", [])[:4]) or "직관성"
    organizer_avoid = ", ".join(organizer.get("avoid", [])[:3]) or "generic 표현"

    return f"""
<contest_intelligence>
- 핵심 키워드: {keywords}
- 추정 분야 태그: {domains}
- 심사위원 선호 특성: {traits}
- 주최기관 프로필: {organizer_name}
- 주최기관이 좋아할 요소: {organizer_traits}
- 주최기관 기준 피해야 할 요소: {organizer_avoid}
- 피해야 할 함정: {risks}
</contest_intelligence>
"""


def prioritize_strategies(
    strategies: List[Dict[str, Any]],
    contest: ContestInfo,
) -> List[Dict[str, Any]]:
    profile = build_contest_profile(contest)
    preferred = profile.get("recommended_strategies", [])
    preferred_order = {name: idx for idx, name in enumerate(preferred)}

    return sorted(
        strategies,
        key=lambda item: (preferred_order.get(item["name"], 999), item["name"]),
    )


def rank_examples_for_contest(
    examples: List[Dict[str, str]],
    contest: ContestInfo,
) -> List[Dict[str, str]]:
    if not examples:
        return []

    contest_tokens = set(extract_keywords(
        " ".join([
            contest.get("title", ""),
            contest.get("held_by", ""),
            contest.get("content", "")[:1000],
        ]),
        limit=20,
    ))
    organizer_profile = detect_organizer_profile(contest.get("held_by", ""), contest.get("content", ""))
    organizer_bias = organizer_profile.get("example_bias", [])
    held_by_lower = contest.get("held_by", "").lower()

    def score_example(example: Dict[str, str]) -> Tuple[int, int]:
        example_text = " ".join([
            example.get("contestTitle", ""),
            example.get("contestWinner", ""),
            example.get("strength", ""),
        ])
        example_tokens = set(extract_keywords(example_text, limit=15))
        overlap = len(contest_tokens & example_tokens)
        strength_bonus = 1 if any(word in example.get("strength", "") for word in ["창의", "위트", "기억", "브랜드"]) else 0
        organizer_bonus = 1 if any(word.lower() in example_text.lower() for word in organizer_bias) else 0
        same_org_bonus = 1 if held_by_lower and held_by_lower[:4] in example_text.lower() else 0
        return (overlap + organizer_bonus + same_org_bonus, strength_bonus + organizer_bonus)

    return sorted(examples, key=score_example, reverse=True)


def build_example_insights(examples: List[Dict[str, str]]) -> str:
    if not examples:
        return ""

    winner_lengths = [len(ex.get("contestWinner", "").replace(" ", "")) for ex in examples if ex.get("contestWinner")]
    top_strengths = extract_keywords(" ".join(ex.get("strength", "") for ex in examples), limit=8)
    top_winner_tokens = extract_keywords(" ".join(ex.get("contestWinner", "") for ex in examples), limit=8)

    average_length = round(sum(winner_lengths) / len(winner_lengths), 1) if winner_lengths else 0

    return f"""
<winner_db_insights>
- 참고 수상작 수: {len(examples)}
- 수상작 평균 길이: {average_length}
- 수상 강점 키워드: {", ".join(top_strengths) or "없음"}
- 수상작 자주 쓰인 표현: {", ".join(top_winner_tokens) or "없음"}
- 위 패턴을 참고하되 그대로 복제하지 말고, 현재 공모전 문맥에 맞게 새롭게 변형하세요.
</winner_db_insights>
"""


def assess_submission_fit(contest: ContestInfo, submission: Submission) -> Dict[str, Any]:
    profile = build_contest_profile(contest)
    text = f"{submission.get('name', '')} {submission.get('description', '')}".lower()
    name = submission.get("name", "")

    keyword_hits = [kw for kw in profile["keywords"][:8] if kw and kw in text]
    domain_hits = [tag for tag in profile["domain_tags"] if any(term in text for term in DOMAIN_KEYWORDS.get(tag, []))]
    generic_hits = [term for term in GENERIC_TERMS if term in text]

    adjustment = 0.0
    reasons: List[str] = []

    if keyword_hits:
        keyword_bonus = min(3.0, len(keyword_hits) * 0.8)
        adjustment += keyword_bonus
        reasons.append(f"핵심 키워드 반영 +{keyword_bonus:.1f}")

    if domain_hits:
        domain_bonus = min(2.0, len(domain_hits) * 0.7)
        adjustment += domain_bonus
        reasons.append(f"분야 적합성 +{domain_bonus:.1f}")

    if contest.get("contest_type") == "네이밍":
        if 2 <= len(name.replace(" ", "")) <= 8:
            adjustment += 1.2
            reasons.append("네이밍 길이 적절 +1.2")
        elif len(name.replace(" ", "")) >= 14:
            adjustment -= 1.5
            reasons.append("네이밍 길이 과다 -1.5")
    else:
        if 8 <= len(name.replace(" ", "")) <= 24:
            adjustment += 1.0
            reasons.append("슬로건 길이 적절 +1.0")
        elif len(name.replace(" ", "")) <= 4:
            adjustment -= 1.2
            reasons.append("슬로건 정보량 부족 -1.2")

    if generic_hits and not keyword_hits:
        penalty = min(3.0, len(generic_hits) * 0.7)
        adjustment -= penalty
        reasons.append(f"generic 표현 과다 -{penalty:.1f}")

    unique_char_ratio = len(set(name.replace(" ", ""))) / max(1, len(name.replace(" ", "")))
    if unique_char_ratio < 0.45:
        adjustment -= 0.8
        reasons.append("반복도 과다 -0.8")

    return {
        "adjustment": round(adjustment, 2),
        "reasons": reasons,
        "keyword_hits": keyword_hits,
        "domain_hits": domain_hits,
    }
