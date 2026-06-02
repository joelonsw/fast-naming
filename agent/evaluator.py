"""
작명 평가 모듈 - Multi-Agent 평가 시스템
3개 LLM 교차 평가 + Self-Critique 메커니즘
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Tuple
from statistics import mean

from state import ContestInfo, Submission
from contest_intelligence import assess_submission_fit, build_contest_profile
from llm_clients import (
    GitHubAIClient,
    GeminiClient,
    GroqClient,
    HuggingFaceClient,
    LLMClient,
    create_primary_client,
    get_huggingface_api_key,
    get_rate_limit_delay,
)

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
        self.evaluators: List[Tuple[str, str, LLMClient]] = []

        if get_huggingface_api_key():
            self.evaluators.append((
                "huggingface",
                "균형감과 언어 완성도를 보는 오픈소스 LLM 심사위원",
                HuggingFaceClient(temperature=0.2, max_tokens=2048),
            ))

        if os.getenv("GROQ_API_KEY"):
            self.evaluators.append((
                "groq",
                "실전 수상 가능성과 적합성을 보는 심사위원",
                GroqClient(model="openai/gpt-oss-120b", temperature=0.2),
            ))

        if os.getenv("GEMINI_API_KEY"):
            self.evaluators.append((
                "gemini",
                "창의성과 독창성을 특히 엄격하게 보는 심사위원",
                GeminiClient(model="gemini-2.5-flash", temperature=0.2),
            ))

        if os.getenv("AI_GITHUB_TOKEN"):
            self.evaluators.append((
                "github",
                "기억용이성과 실용성을 특히 엄격하게 보는 심사위원",
                GitHubAIClient(model="gpt-4o", temperature=0.2),
            ))

        logger.info(
            "🧪 Multi-Agent evaluators: %s",
            ", ".join(f"{name}/{client.model_name}" for name, _, client in self.evaluators) or "없음",
        )

    async def _evaluate_with_client(
        self, 
        client: LLMClient,
        perspective: str,
        contest: ContestInfo, 
        submissions: List[Submission],
        criteria: Dict[str, int],
    ) -> Dict[int, float]:
        """공통 클라이언트로 평가"""
        
        submissions_text = "\n".join([
            f"{i}. {s['name']}" for i, s in enumerate(submissions, 1)
        ])
        contest_profile = build_contest_profile(contest)
        
        system_prompt = f"""당신은 "{contest['title']}" 공모전의 심사위원입니다.
{perspective}
{contest_profile.get("prompt_boost", "")}
반드시 엄격하고 현실적으로 채점하세요."""

        prompt = f"""다음 출품작들을 공정하게 평가하세요.

<평가 기준>
{json.dumps(criteria, ensure_ascii=False)}

* 중요 채점 세부 규칙 (1등 수상 및 상표권 확보 기준):
  - **진부함 및 단순합성 징벌적 감점**: '참', '바른', '뜰', '마루', '아람', '도담', '소담', '초록', '자연', '에코', '그린', '늘', '봄', '온', '누리' 등 네이밍 공모전에 단골로 쓰이는 어근의 1차원적 합성어(예: 참바른뜰, 초록아람, 자연마루, 스마트링크 등)는 **독창성/창의성(또는 참신함 관련 심사기준)에서 반드시 50점 이하의 낙제점**을 부여하십시오.
  - 위와 같은 상투적인 작명은 다른 심사 기준(적합성, 발음성 등)이 아무리 우수하더라도 **최종 종합 합산 총점을 50점 이하로 대폭 감점하여 채점**해야 합니다. 무난한 안전지향형 작명은 1등 수상이 절대로 불가능하며, 상표 등록도 불가능하기 때문입니다.
</평가 기준>

<출품작>
{submissions_text}
</출품작>

각 출품작에 0~100점을 부여하세요. 반드시 JSON으로 응답:
```json
{{"1": 점수, "2": 점수, ...}}
```"""
        
        try:
            response = await client.generate(system_prompt, prompt)
            import re
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                scores = json.loads(json_match.group(1))
            else:
                scores = json.loads(response.strip())
            
            await asyncio.sleep(get_rate_limit_delay(client.provider_name))
            return {int(k): float(v) for k, v in scores.items()}
        except Exception as e:
            logger.error("%s 평가 실패: %s", client.provider_name, e)
            return {}
    
    async def cross_evaluate(
        self,
        contest: ContestInfo,
        submissions: List[Submission],
        criteria: Dict[str, int],
    ) -> List[Submission]:
        """3개 LLM 교차 평가 및 합의 도출"""
        
        logger.info(f"🔄 Multi-Agent 교차 평가 시작 ({len(submissions)}개)")
        
        evaluator_scores: Dict[str, Dict[int, float]] = {}

        for provider_name, perspective, client in self.evaluators:
            scores = await self._evaluate_with_client(
                client=client,
                perspective=perspective,
                contest=contest,
                submissions=submissions,
                criteria=criteria,
            )
            if scores:
                evaluator_scores[provider_name] = scores

        active_evaluators = len(evaluator_scores)
        
        logger.info(f"📊 {active_evaluators}개 LLM 평가 완료")
        
        for i, sub in enumerate(submissions, 1):
            scores = []
            active_names = []

            for provider_name, provider_scores in evaluator_scores.items():
                if i in provider_scores:
                    scores.append(provider_scores[i])
                    active_names.append(provider_name)
            
            if scores:
                # 가중 평균 (편차가 큰 경우 중앙값 사용)
                if len(scores) >= 2 and max(scores) - min(scores) > 20:
                    sub['score'] = sorted(scores)[len(scores)//2]
                else:
                    sub['score'] = mean(scores)
                    
                sub['criteria_scores'] = {
                    "multi_agent_scores": scores,
                    "evaluators": active_names,
                    "evaluator_count": len(scores),
                }
            else:
                sub['score'] = 0
                sub['criteria_scores'] = {}
        
        return submissions


def apply_fit_adjustments(
    contest: ContestInfo,
    submissions: List[Submission],
) -> List[Submission]:
    for sub in submissions:
        if sub.get("score") is None:
            continue

        fit = assess_submission_fit(contest, sub)
        original_score = sub.get("score", 0) or 0
        adjusted_score = max(0.0, min(100.0, original_score + fit["adjustment"]))
        sub["score"] = adjusted_score

        criteria_scores = sub.get("criteria_scores") or {}
        criteria_scores["fit_adjustment"] = fit["adjustment"]
        criteria_scores["fit_reasons"] = fit["reasons"]
        criteria_scores["fit_keyword_hits"] = fit["keyword_hits"]
        criteria_scores["fit_domain_hits"] = fit["domain_hits"]
        sub["criteria_scores"] = criteria_scores

    return submissions
    
    async def self_critique(
        self,
        contest: ContestInfo,
        submission: Submission,
    ) -> Tuple[float, str]:
        """자기 비판을 통한 품질 검증"""

        critic = create_primary_client(temperature=0.2, max_tokens=1024)
        if not critic:
            return (0, "")
        
        system_prompt = f"""당신은 "{contest['title']}" 공모전의 최종 심사위원입니다.
약점과 탈락 리스크를 숨기지 말고 냉정하게 지적하세요."""

        prompt = f"""다음 작명에 대해 비판적으로 평가하세요:

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
            response = await critic.generate(system_prompt, prompt)
            import re
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                critique = json.loads(json_match.group(1))
            else:
                critique = json.loads(response.strip())
            
            await asyncio.sleep(get_rate_limit_delay(critic.provider_name))
            
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
    """공모전 평가 기준 자동 생성"""
    
    logger.info(f"📊 평가 기준 생성: {contest['title']}")

    client = create_primary_client(temperature=0.5, max_tokens=1024)
    if not client:
        logger.warning("사용 가능한 평가용 LLM이 없어 기본 평가 기준을 사용합니다")
        return {
            "창의성": 25,
            "적합성": 25,
            "기억용이성": 25,
            "완성도": 25,
        }

    logger.info("🧪 평가 기준 생성 모델: %s/%s", client.provider_name, client.model_name)
    
    system_prompt = f"""당신은 "{contest['title']}" 공모전의 심사위원입니다.
{build_contest_profile(contest).get("prompt_boost", "")}
공모전 설명에 맞는 실제 심사 기준을 설계하세요."""

    prompt = f"""<공모전 내용>

{contest['content'][:1500]}
</공모전 내용>

위 공모전의 공정한 평가기준을 4가지로 마련하세요.
이 중 '창의성 및 독창성'(혹은 이에 준하는 참신함 및 차별성 평가 항목)은 반드시 포함해야 하며, 해당 항목의 배점을 100점 중 최소 35점 이상으로 크게 책정하십시오.
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
        response = await client.generate(system_prompt, prompt)
        
        import re
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_match:
            criteria = json.loads(json_match.group(1))
        else:
            criteria = json.loads(response.strip())
        
        total = sum(criteria.values())
        if total != 100:
            logger.warning(f"평가 기준 총합 {total}점")
        
        logger.info(f"✅ 평가 기준 생성 완료: {criteria}")
        await asyncio.sleep(get_rate_limit_delay(client.provider_name))
        
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
        evaluated = await evaluator.cross_evaluate(contest, submissions, criteria)
        return apply_fit_adjustments(contest, evaluated)
    
    # 기존 단일 LLM 평가 (fallback)
    logger.info(f"🎯 {len(submissions)}개 작명 평가 시작 (단일 LLM)")

    client = create_primary_client(temperature=0.2, max_tokens=2048)
    if not client:
        logger.error("평가에 사용할 LLM이 없습니다")
        for sub in submissions:
            sub['score'] = 0
        return submissions

    logger.info("🧪 단일 평가 모델: %s/%s", client.provider_name, client.model_name)
    
    submissions_text = ""
    for i, sub in enumerate(submissions, 1):
        submissions_text += f"{i}. {sub['name']}\n   설명: {sub['description']}\n\n"
    
    system_prompt = f"""당신은 "{contest['title']}" 공모전의 심사위원입니다.
{build_contest_profile(contest).get("prompt_boost", "")}
평가 기준에 맞춰 공정하게 점수를 부여하세요."""

    prompt = f"""<평가 기준>

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
        response = await client.generate(system_prompt, prompt)
        
        import re
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_match:
            evaluations = json.loads(json_match.group(1))
        else:
            evaluations = json.loads(response.strip())
        
        eval_map = {e['index']: e for e in evaluations}
        
        for i, sub in enumerate(submissions, 1):
            if i in eval_map:
                sub['score'] = eval_map[i].get('total_score', 0)
                sub['criteria_scores'] = eval_map[i].get('scores', {})
        
        logger.info(f"✅ 평가 완료")
        await asyncio.sleep(get_rate_limit_delay(client.provider_name))

        return apply_fit_adjustments(contest, submissions)
        
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
