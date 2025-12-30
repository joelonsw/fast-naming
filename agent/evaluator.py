"""
작명 평가 모듈 - Multi-Agent 평가 시스템
3개 LLM 교차 평가 + Self-Critique 메커니즘
"""

import os
import json
import asyncio
import logging
import httpx
from typing import List, Dict, Optional, Tuple
from statistics import mean, stdev

from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from state import ContestInfo, Submission

logger = logging.getLogger(__name__)


# ============================================================
# Multi-Agent 평가 시스템
# ============================================================

class MultiAgentEvaluator:
    """
    Multi-Agent 평가 시스템
    - 3개 LLM (Groq, Gemini, GitHub AI) 교차 평가
    - Self-Critique 메커니즘
    - 합의 기반 최종 점수 산출
    """
    
    def __init__(self):
        self.groq = ChatGroq(
            model="openai/gpt-oss-120b",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.3,
        )
        
        self.gemini = None
        if os.getenv("GEMINI_API_KEY"):
            self.gemini = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash-lite",
                google_api_key=os.getenv("GEMINI_API_KEY"),
                temperature=0.3,
            )
        
        self.github_token = os.getenv("AI_GITHUB_TOKEN")
    
    async def _evaluate_with_groq(
        self, 
        contest: ContestInfo, 
        submissions: List[Submission],
        criteria: Dict[str, int],
    ) -> Dict[int, float]:
        """Groq로 평가"""
        
        submissions_text = "\n".join([
            f"{i}. {s['name']}" for i, s in enumerate(submissions, 1)
        ])
        
        prompt = f"""당신은 "{contest['title']}" 공모전의 엄격한 심사위원입니다.

<평가 기준>
{json.dumps(criteria, ensure_ascii=False)}
</평가 기준>

<출품작>
{submissions_text}
</출품작>

각 출품작에 0~100점을 부여하세요. 반드시 JSON으로 응답:
```json
{{"1": 점수, "2": 점수, ...}}
```"""
        
        try:
            response = await self.groq.ainvoke([HumanMessage(content=prompt)])
            import re
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response.content)
            if json_match:
                scores = json.loads(json_match.group(1))
            else:
                scores = json.loads(response.content.strip())
            
            await asyncio.sleep(2)
            return {int(k): float(v) for k, v in scores.items()}
        except Exception as e:
            logger.error(f"Groq 평가 실패: {e}")
            return {}
    
    async def _evaluate_with_gemini(
        self, 
        contest: ContestInfo, 
        submissions: List[Submission],
        criteria: Dict[str, int],
    ) -> Dict[int, float]:
        """Gemini로 평가"""
        
        if not self.gemini:
            return {}
        
        submissions_text = "\n".join([
            f"{i}. {s['name']}" for i, s in enumerate(submissions, 1)
        ])
        
        prompt = f"""당신은 "{contest['title']}" 공모전의 창의성 전문 심사위원입니다.
창의성과 독창성에 특히 주목하세요.

<평가 기준>
{json.dumps(criteria, ensure_ascii=False)}
</평가 기준>

<출품작>
{submissions_text}
</출품작>

각 출품작에 0~100점을 부여하세요. 반드시 JSON으로 응답:
```json
{{"1": 점수, "2": 점수, ...}}
```"""
        
        try:
            response = await self.gemini.ainvoke([HumanMessage(content=prompt)])
            import re
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response.content)
            if json_match:
                scores = json.loads(json_match.group(1))
            else:
                scores = json.loads(response.content.strip())
            
            await asyncio.sleep(10)  # Gemini rate limit
            return {int(k): float(v) for k, v in scores.items()}
        except Exception as e:
            logger.error(f"Gemini 평가 실패: {e}")
            return {}
    
    async def _evaluate_with_github(
        self, 
        contest: ContestInfo, 
        submissions: List[Submission],
        criteria: Dict[str, int],
    ) -> Dict[int, float]:
        """GitHub AI로 평가"""
        
        if not self.github_token:
            return {}
        
        submissions_text = "\n".join([
            f"{i}. {s['name']}" for i, s in enumerate(submissions, 1)
        ])
        
        prompt = f"""당신은 "{contest['title']}" 공모전의 실용성 전문 심사위원입니다.
기억용이성과 실용성에 특히 주목하세요.

<평가 기준>
{json.dumps(criteria, ensure_ascii=False)}
</평가 기준>

<출품작>
{submissions_text}
</출품작>

각 출품작에 0~100점을 부여하세요. 반드시 JSON으로 응답:
{{"1": 점수, "2": 점수, ...}}"""
        
        try:
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "openai/gpt-4.1-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://models.github.ai/inference/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if response.status_code == 429:
                    return {}
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                import re
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    scores = json.loads(json_match.group())
                    await asyncio.sleep(10)
                    return {int(k): float(v) for k, v in scores.items()}
        except Exception as e:
            logger.error(f"GitHub AI 평가 실패: {e}")
        return {}
    
    async def cross_evaluate(
        self,
        contest: ContestInfo,
        submissions: List[Submission],
        criteria: Dict[str, int],
    ) -> List[Submission]:
        """3개 LLM 교차 평가 및 합의 도출"""
        
        logger.info(f"🔄 Multi-Agent 교차 평가 시작 ({len(submissions)}개)")
        
        # 병렬 평가 (순차 실행으로 변경 - rate limit)
        groq_scores = await self._evaluate_with_groq(contest, submissions, criteria)
        gemini_scores = await self._evaluate_with_gemini(contest, submissions, criteria)
        github_scores = await self._evaluate_with_github(contest, submissions, criteria)
        
        # 점수 합산
        active_evaluators = sum([
            bool(groq_scores), 
            bool(gemini_scores), 
            bool(github_scores)
        ])
        
        logger.info(f"📊 {active_evaluators}개 LLM 평가 완료")
        
        for i, sub in enumerate(submissions, 1):
            scores = []
            if i in groq_scores:
                scores.append(groq_scores[i])
            if i in gemini_scores:
                scores.append(gemini_scores[i])
            if i in github_scores:
                scores.append(github_scores[i])
            
            if scores:
                # 가중 평균 (편차가 큰 경우 중앙값 사용)
                if len(scores) >= 2 and max(scores) - min(scores) > 20:
                    sub['score'] = sorted(scores)[len(scores)//2]
                else:
                    sub['score'] = mean(scores)
                    
                sub['criteria_scores'] = {
                    "multi_agent_scores": scores,
                    "evaluator_count": len(scores),
                }
            else:
                sub['score'] = 0
                sub['criteria_scores'] = {}
        
        return submissions
    
    async def self_critique(
        self,
        contest: ContestInfo,
        submission: Submission,
    ) -> Tuple[float, str]:
        """자기 비판을 통한 품질 검증"""
        
        prompt = f"""당신은 "{contest['title']}" 공모전의 최종 심사위원입니다.

다음 작명에 대해 비판적으로 평가하세요:
- 작명: {submission['name']}
- 설명: {submission['description']}

<공모전 내용>
{contest['content'][:500]}
</공모전 내용>

다음 관점에서 분석하세요:
1. 이 작명의 가장 큰 약점은?
2. 심사위원이 탈락시킬 이유가 있다면?
3. 1등을 할 수 있는지 솔직히 평가

반드시 JSON 형식으로 응답:
```json
{{
    "weaknesses": "약점 설명",
    "rejection_risk": "탈락 가능성 (high/medium/low)",
    "improvement_suggestion": "개선 제안",
    "final_score": 0~100
}}
```"""
        
        try:
            response = await self.groq.ainvoke([HumanMessage(content=prompt)])
            import re
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response.content)
            if json_match:
                critique = json.loads(json_match.group(1))
            else:
                critique = json.loads(response.content.strip())
            
            await asyncio.sleep(2)
            
            return (
                critique.get('final_score', 0),
                critique.get('improvement_suggestion', ''),
            )
        except Exception as e:
            logger.error(f"Self-critique 실패: {e}")
            return (0, "")


# ============================================================
# 기존 API 호환 함수들
# ============================================================

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
"""
    
    try:
        messages = [HumanMessage(content=prompt)]
        response = await groq.ainvoke(messages)
        
        import re
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response.content)
        if json_match:
            criteria = json.loads(json_match.group(1))
        else:
            criteria = json.loads(response.content.strip())
        
        total = sum(criteria.values())
        if total != 100:
            logger.warning(f"평가 기준 총합 {total}점")
        
        logger.info(f"✅ 평가 기준 생성 완료: {criteria}")
        await asyncio.sleep(2)
        
        return criteria
        
    except Exception as e:
        logger.error(f"❌ 평가 기준 생성 실패: {e}")
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
    use_multi_agent: bool = True,
) -> List[Submission]:
    """작명들을 평가 (Multi-Agent 또는 단일 LLM)"""
    
    if not submissions:
        return []
    
    if use_multi_agent:
        evaluator = MultiAgentEvaluator()
        return await evaluator.cross_evaluate(contest, submissions, criteria)
    
    # 기존 단일 LLM 평가 (fallback)
    logger.info(f"🎯 {len(submissions)}개 작명 평가 시작 (단일 LLM)")
    
    groq = ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.3,
    )
    
    submissions_text = ""
    for i, sub in enumerate(submissions, 1):
        submissions_text += f"{i}. {sub['name']}\n   설명: {sub['description']}\n\n"
    
    prompt = f"""당신은 "{contest['title']}" 공모전의 심사위원입니다.

<평가 기준>
{json.dumps(criteria, ensure_ascii=False, indent=2)}
</평가 기준>

<출품작 목록>
{submissions_text}
</출품작 목록>

각 출품작을 평가하세요. JSON 형식으로 응답:
```json
[{{"index": 1, "total_score": 85}}, ...]
```"""
    
    try:
        response = await groq.ainvoke([HumanMessage(content=prompt)])
        
        import re
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response.content)
        if json_match:
            evaluations = json.loads(json_match.group(1))
        else:
            evaluations = json.loads(response.content.strip())
        
        eval_map = {e['index']: e for e in evaluations}
        
        for i, sub in enumerate(submissions, 1):
            if i in eval_map:
                sub['score'] = eval_map[i].get('total_score', 0)
                sub['criteria_scores'] = eval_map[i].get('scores', {})
        
        logger.info(f"✅ 평가 완료")
        await asyncio.sleep(2)
        
        return submissions
        
    except Exception as e:
        logger.error(f"❌ 평가 실패: {e}")
        for sub in submissions:
            sub['score'] = 0
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
            content="새로운 AI 서비스의 이름을 공모합니다.",
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
