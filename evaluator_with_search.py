import json
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

# Re-using the same LLM clients as the original evaluator
import google.generativeai as genai
from groq import Groq
import re

logger = logging.getLogger(__name__)

class EvaluatorWithSearch:
    """Evaluator that enriches context by using a pre-fetched host organization's persona."""

    def __init__(self):
        """Initialize the contest evaluator with LLM clients."""
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.gemini_client = genai.GenerativeModel('gemini-2.5-pro')

    async def generate_criteria(self, contest_title: str, contest_content: str, organization_persona: str) -> Dict[str, int]:
        """Generate evaluation criteria using Groq, enriched with persona context."""
        try:
            logger.info(f"🔍 평가 기준 생성 시작 (페르소나 기반): {contest_title}")
            
            system_prompt = f"""당신은 {contest_title}의 심사위원장입니다. 주최 기관의 특성을 깊이 이해하고, 그에 맞는 심사 기준을 만들어야 합니다."""

            user_prompt = f"""공모전 내용과 아래의 주최 기관 정보를 참고하여, 가장 공정한 평가 기준 4가지를 만드세요. 각 기준의 배점 합은 100이 되어야 합니다.

<공모전 내용>
{contest_content}
</공모전 내용>

<주최 기관 분석 정보>
{organization_persona}
</주최 기관 분석 정보>

반드시 다음 JSON 형식으로만 반환하세요:
```json
{{
    "contestCriteria": {{
        "배점기준1": 25,
        "배점기준2": 25,
        "배점기준3": 25,
        "배점기준4": 25
    }}
}}
```"""

            completion = self.groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                max_completion_tokens=1000,
                top_p=1,
                response_format={"type": "json_object"}
            )
            
            response = completion.choices[0].message.content
            criteria = json.loads(response).get("contestCriteria", {})
            logger.info(f"📊 생성된 평가 기준: {criteria}")
            return criteria
            
        except Exception as e:
            logger.error(f"❌ 평가 기준 생성 실패: {str(e)}")
            return {"창의성": 25, "브랜드 적합성": 35, "기억용이성": 20, "활용성": 20}

    async def evaluate_submissions(self, contest_data: Dict, submissions: List[Dict], organization_persona: str) -> (List[Dict], Dict[str, int]):
        """Evaluate submissions using Gemini, enriched with a pre-fetched persona context."""
        try:
            contest_title = contest_data.get('contestTitle', '')
            contest_content = contest_data.get('contestContent', '')
            criteria = contest_data.get('contestCriteria')

            logger.info(f"🎯 작명 평가 시작: {len(submissions)}개 작명")

            # Generate criteria if not provided, using the persona
            if not criteria:
                criteria = await self.generate_criteria(contest_title, contest_content, organization_persona)
            
            submissions_text = self._format_submissions_for_evaluation(submissions)

            user_prompt = f"""당신은 {contest_title}의 전문 심사위원입니다. 아래 정보를 바탕으로 출품작을 평가하세요.

<주최 기관 분석 정보>
{organization_persona}
</주최 기관 분석 정보>

<공모전 내용>
{contest_content}
</공모전 내용>

<평가 기준>
{json.dumps(criteria, ensure_ascii=False, indent=2)}
</평가 기준>

<출품작 목록>
{submissions_text}
</출품작 목록>

**평가 지침:**
1. 각 출품작에 대해 <평가 기준>에 따라 점수를 엄격하게 매겨주세요.
2. <주최 기관 분석 정보>를 반드시 참고하여, 기관의 성향과 비전에 부합하는지를 점수에 반영하세요.
3. 총점이 높은 순서대로 상위 20개의 작품을 선정하세요.
4. 각 작품에 대한 평가 코멘트를 20자 내외로 작성해주세요.

**출력 형식:**
반드시 아래 JSON 형식에 맞춰 결과를 반환합니다.
```json
{{
    "evaluations": [
        {{
            "submission": "작명 내용",
            "description": "설명",
            "score": {{ "기준1": "점수", "기준2": "점수" }},
            "total_score": "총점",
            "comments": "평가 코멘트"
        }}
    ]
}}
```
"""

            response = self.gemini_client.generate_content(user_prompt)
            evaluated_submissions = self._parse_evaluation_response(response.text, submissions)
            
            evaluated_submissions.sort(key=lambda x: x.get('total_score', 0), reverse=True)
            logger.info(f"📊 평가 완료: {len(evaluated_submissions)}개 작명 정렬됨")
            
            return evaluated_submissions, criteria
            
        except Exception as e:
            logger.error(f"❌ 작명 평가 실패: {str(e)}", exc_info=True)
            return self._add_default_scores(submissions), {}

    def _format_submissions_for_evaluation(self, submissions: List[Dict]) -> str:
        return json.dumps([{"submission": s.get('submission'), "description": s.get('description')} for s in submissions], ensure_ascii=False, indent=2)

    def _parse_evaluation_response(self, response: str, original_submissions: List[Dict]) -> List[Dict]:
        try:
            logger.info("Parsing evaluation response...")
            match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                json_str = response
            
            data = json.loads(json_str)
            evaluations = data.get("evaluations", [])
            
            submission_map = {s['submission']: s for s in original_submissions}
            
            result = []
            for eval_data in evaluations:
                original_sub = submission_map.get(eval_data['submission'])
                if original_sub:
                    # Ensure total_score is an integer
                    total_score = eval_data.get("total_score", 0)
                    try:
                        total_score = int(total_score)
                    except (ValueError, TypeError):
                        total_score = 0

                    original_sub.update({
                        "score": eval_data.get("score", {}),
                        "total_score": total_score,
                        "comments": eval_data.get("comments", "")
                    })
                    result.append(original_sub)
            
            logger.info(f"Successfully parsed {len(result)} evaluations.")
            return result
        except Exception as e:
            logger.error(f"❌ 평가 결과 파싱 실패: {str(e)}")
            return self._add_default_scores(original_submissions)

    def _add_default_scores(self, submissions: List[Dict]) -> List[Dict]:
        for sub in submissions:
            sub['score'] = {}
            sub['total_score'] = 0
            sub['comments'] = "평가 중 오류 발생"
        return submissions

    def save_evaluation_result(self, result_number: int, evaluated_submissions: List[Dict], 
                             criteria: Dict[str, int], contest_data: Dict) -> str:
        try:
            os.makedirs("result", exist_ok=True)
            score_file = f"result/score{result_number:04d}.json"
            evaluation_data = {
                "contest_data": contest_data,
                "evaluation_criteria": criteria,
                "evaluation_timestamp": datetime.now().isoformat(),
                "total_submissions": len(evaluated_submissions),
                "submissions": evaluated_submissions
            }
            with open(score_file, 'w', encoding='utf-8') as f:
                json.dump(evaluation_data, f, ensure_ascii=False, indent=2)
            logger.info(f"💾 평가 결과 저장 완료: {score_file}")
            return score_file
        except Exception as e:
            logger.error(f"❌ 평가 결과 저장 실패: {str(e)}")
            raise

def create_evaluator_with_search() -> EvaluatorWithSearch:
    """Create and return an instance of the search-enhanced evaluator."""
    return EvaluatorWithSearch()