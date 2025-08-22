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
    """
    Evaluator that enriches context by using a pre-fetched host organization's persona
    and processes submissions in batches for improved reliability.
    """

    def __init__(self):
        """Initialize the contest evaluator with LLM clients."""
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.gemini_client = genai.GenerativeModel(
            'gemini-2.5-pro',
            safety_settings={
                'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
                'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
                'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
                'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE'
            }
        )

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
            # Provide a sensible default if generation fails
            return {"브랜드 적합성": 35, "창의성": 25, "기억용이성": 20, "활용성": 20}

    async def evaluate_submissions(self, contest_data: Dict, submissions: List[Dict], organization_persona: str) -> (List[Dict], Dict[str, int]):
        """
        Evaluate submissions in batches using Gemini, enriched with a pre-fetched persona context.
        """
        try:
            contest_title = contest_data.get('contestTitle', '')
            contest_content = contest_data.get('contestContent', '')
            criteria = contest_data.get('contestCriteria')

            logger.info(f"🎯 작명 평가 시작: {len(submissions)}개 작명 (배치 처리)")

            if not criteria:
                criteria = await self.generate_criteria(contest_title, contest_content, organization_persona)

            # --- BATCH PROCESSING LOGIC ---
            batch_size = 40  # Process 40 submissions at a time. Adjust if necessary.
            all_evaluated_submissions = []
            
            for i in range(0, len(submissions), batch_size):
                batch_submissions = submissions[i:i + batch_size]
                logger.info(f"⚙️ 배치 처리 중: {i+1}-{min(i + batch_size, len(submissions))} / {len(submissions)}")
                
                submissions_text = self._format_submissions_for_evaluation(batch_submissions)

                # This prompt is now tailored for evaluating a single batch
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

<이번에 평가할 출품작 목록>
{submissions_text}
</이번에 평가할 출품작 목록>

**평가 지침:**
1. 각 출품작에 대해 <평가 기준>에 따라 점수를 엄격하게 매겨주세요.
2. <주최 기관 분석 정보>를 반드시 참고하여, 기관의 성향과 비전에 부합하는지를 점수에 반영하세요.
3. **이번에 제공된 모든 출품작**을 빠짐없이 평가해주세요.
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
                generation_config = genai.types.GenerationConfig(
                    max_output_tokens=16384,
                    response_mime_type="application/json"
                )

                try:
                    response = await self.gemini_client.generate_content_async(
                        user_prompt,
                        generation_config=generation_config
                    )
                    response_text = response.text
                    evaluated_batch = self._parse_evaluation_response(response_text, batch_submissions)
                    all_evaluated_submissions.extend(evaluated_batch)
                except ValueError:
                    logger.error(
                        f"❌ 배치 {i//batch_size + 1} 평가 실패: Gemini 응답이 비어 있습니다. Finish reason: %s",
                        response.candidates[0].finish_reason if response.candidates else "N/A"
                    )
                    all_evaluated_submissions.extend(self._add_default_scores(batch_submissions))
                except Exception as batch_e:
                    logger.error(f"❌ 배치 {i//batch_size + 1} 처리 중 오류 발생: {str(batch_e)}")
                    all_evaluated_submissions.extend(self._add_default_scores(batch_submissions))
                
                # --- ADD THIS LINE ---
                # Pause for 31 seconds to respect the 2 RPM free tier limit
                if i + batch_size < len(submissions): # Don't sleep after the last batch
                    logger.info("⏳ 31초 대기 (API 속도 제한 준수)")
                    await asyncio.sleep(31)
            # --- END BATCH PROCESSING LOGIC ---

            # Sort all results from all batches together to get the final ranking
            all_evaluated_submissions.sort(key=lambda x: x.get('total_score', 0), reverse=True)
            logger.info(f"📊 평가 완료: {len(all_evaluated_submissions)}개 작명 정렬됨")
            
            return all_evaluated_submissions, criteria
            
        except Exception as e:
            logger.error(f"❌ 작명 평가 전체 프로세스 실패: {str(e)}", exc_info=True)
            return self._add_default_scores(submissions), criteria if 'criteria' in locals() else {}

    def _format_submissions_for_evaluation(self, submissions: List[Dict]) -> str:
        """Formats a list of submission dicts into a JSON string for the prompt."""
        return json.dumps([{"submission": s.get('submission'), "description": s.get('description')} for s in submissions], ensure_ascii=False, indent=2)

    def _parse_evaluation_response(self, response: str, original_submissions: List[Dict]) -> List[Dict]:
        """Parses the JSON response from the LLM and maps it back to the original submission data."""
        try:
            logger.info("Parsing evaluation response...")
            # Handle cases where the response might be wrapped in markdown
            match = re.search(r'```json\s*(.*)\s*```', response, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                json_str = response
            
            data = json.loads(json_str)
            evaluations = data.get("evaluations", [])
            
            # Create a map for easy lookup of original submission data
            submission_map = {s['submission']: s for s in original_submissions}
            
            result = []
            for eval_data in evaluations:
                original_sub = submission_map.get(eval_data['submission'])
                if original_sub:
                    # Safely convert total_score to an integer
                    try:
                        total_score = int(eval_data.get("total_score", 0))
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
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"❌ 평가 결과 파싱 실패: {str(e)}. Response was: {response[:200]}...")
            return self._add_default_scores(original_submissions)

    def _add_default_scores(self, submissions: List[Dict]) -> List[Dict]:
        """Adds default error values to submissions when an evaluation fails."""
        for sub in submissions:
            sub['score'] = {}
            sub['total_score'] = 0
            sub['comments'] = "평가 중 오류 발생"
        return submissions

    def save_evaluation_result(self, result_number: int, evaluated_submissions: List[Dict], 
                             criteria: Dict[str, int], contest_data: Dict) -> str:
        """Saves the complete evaluation data to a JSON file."""
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
    """Factory function to create an instance of the evaluator."""
    return EvaluatorWithSearch()
