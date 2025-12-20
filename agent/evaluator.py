"""
작명 평가 모듈
Groq openai/gpt-oss-120b 사용으로 Gemini rate limit 회피
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Optional

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from state import ContestInfo, Submission

logger = logging.getLogger(__name__)


async def generate_evaluation_criteria(
    contest: ContestInfo,
) -> Dict[str, int]:
    """공모전 평가 기준 자동 생성 (Groq 사용)"""
    
    logger.info(f"📊 평가 기준 생성: {contest['title']}")
    
    groq = ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.5,
    )
    
    prompt = f"""당신은 "{contest['title']}" 공모전의 심사위원입니다.

<공모전 내용>
{contest['content'][:1500]}
</공모전 내용>

위 공모전의 공정한 평가기준을 4가지로 마련하세요.
각 평가기준의 총합은 100이 되어야 합니다.

반드시 다음 JSON 형식으로만 응답하세요:
```json
{{
    "평가기준1이름": 점수,
    "평가기준2이름": 점수,
    "평가기준3이름": 점수,
    "평가기준4이름": 점수
}}
```

예시:
```json
{{
    "창의성": 30,
    "적합성": 25,
    "기억용이성": 25,
    "완성도": 20
}}
```
"""
    
    try:
        messages = [HumanMessage(content=prompt)]
        response = await groq.ainvoke(messages)
        
        # JSON 파싱
        import re
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response.content)
        if json_match:
            criteria = json.loads(json_match.group(1))
        else:
            criteria = json.loads(response.content.strip())
        
        # 총합 100 확인
        total = sum(criteria.values())
        if total != 100:
            logger.warning(f"평가 기준 총합 {total}점 (100점이 아님)")
        
        logger.info(f"✅ 평가 기준 생성 완료: {criteria}")
        
        # Groq rate limit 대응: 2초 대기
        await asyncio.sleep(2)
        
        return criteria
        
    except Exception as e:
        logger.error(f"❌ 평가 기준 생성 실패: {e}")
        # 기본 평가 기준
        return {
            "창의성": 25,
            "적합성": 25,
            "기억용이성": 25,
            "완성도": 25,
        }


async def evaluate_submissions(
    contest: ContestInfo,
    submissions: List[Submission],
    criteria: Dict[str, int],
) -> List[Submission]:
    """작명들을 평가하고 점수 부여 (Groq 사용)"""
    
    logger.info(f"🎯 {len(submissions)}개 작명 평가 시작")
    
    if not submissions:
        return []
    
    groq = ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.3,  # 평가는 낮은 temperature
    )
    
    # 작명 목록 포맷팅
    submissions_text = ""
    for i, sub in enumerate(submissions, 1):
        submissions_text += f"{i}. {sub['name']}\n   설명: {sub['description']}\n\n"
    
    prompt = f"""당신은 "{contest['title']}" 공모전의 심사위원입니다.

<공모전 내용>
{contest['content'][:1000]}
</공모전 내용>

<평가 기준>
{json.dumps(criteria, ensure_ascii=False, indent=2)}
</평가 기준>

<출품작 목록>
{submissions_text}
</출품작 목록>

위 출품작들을 평가 기준에 따라 채점하세요.
각 출품작에 대해 각 평가 기준별 점수와 총점을 매겨주세요.

반드시 다음 JSON 형식으로 응답하세요:
```json
[
    {{
        "index": 1,
        "name": "작명 내용",
        "scores": {{"창의성": 25, "적합성": 20, ...}},
        "total_score": 85,
        "comment": "평가 코멘트"
    }},
    ...
]
```
"""
    
    try:
        messages = [HumanMessage(content=prompt)]
        response = await groq.ainvoke(messages)
        
        # JSON 파싱
        import re
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response.content)
        if json_match:
            evaluations = json.loads(json_match.group(1))
        else:
            evaluations = json.loads(response.content.strip())
        
        # 평가 결과를 submissions에 반영
        eval_map = {e['index']: e for e in evaluations}
        
        for i, sub in enumerate(submissions, 1):
            if i in eval_map:
                eval_data = eval_map[i]
                sub['score'] = eval_data.get('total_score', 0)
                sub['criteria_scores'] = eval_data.get('scores', {})
        
        logger.info(f"✅ {len(evaluations)}개 작명 평가 완료")
        
        # Groq rate limit 대응: 2초 대기
        await asyncio.sleep(2)
        
        return submissions
        
    except Exception as e:
        logger.error(f"❌ 평가 실패: {e}")
        # 평가 실패시 기본 점수 부여
        for sub in submissions:
            sub['score'] = 0
            sub['criteria_scores'] = {k: 0 for k in criteria.keys()}
        return submissions


def rank_submissions(submissions: List[Submission]) -> List[Submission]:
    """점수 높은 순으로 정렬"""
    return sorted(
        submissions, 
        key=lambda x: x.get('score', 0) or 0, 
        reverse=True
    )


def get_top_n(submissions: List[Submission], n: int = 3) -> List[Submission]:
    """상위 N개 작명 선택"""
    ranked = rank_submissions(submissions)
    return ranked[:n]


# 테스트용
if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    
    async def main():
        test_contest = ContestInfo(
            title="테스트 네이밍 공모전",
            content="새로운 AI 서비스의 이름을 공모합니다. 혁신적이고 기억하기 쉬운 이름을 원합니다.",
            held_by="테스트 기관",
            contest_type="네이밍",
            held_by_type="사기업",
            url="https://example.com",
            submission_method="이메일",
            deadline="2024-12-31",
            d_day="D-10",
        )
        
        criteria = await generate_evaluation_criteria(test_contest)
        print(f"평가 기준: {criteria}")
    
    asyncio.run(main())
