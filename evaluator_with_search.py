import json
import logging
import os
from typing import Dict, List
from datetime import datetime
import asyncio
import google.generativeai as genai
import re

logger = logging.getLogger(__name__)

class EvaluatorWithSearch:
    """
    Evaluates submissions using the Gemini 2.5 Pro model.
    Includes diagnostic steps and uses batching for stability.
    """

    def __init__(self):
        """Initialize the contest evaluator with the Gemini LLM client."""
        self.gemini_client = genai.GenerativeModel(
            'gemini-2.5-pro',
            safety_settings={
                'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
                'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
                'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
                'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE'
            }
        )
        self.generation_config = genai.types.GenerationConfig(temperature=0.7)

    async def _test_api_call(self, component_name: str, test_prompt: str) -> bool:
        """A helper function to test API calls with specific prompt components."""
        try:
            logger.info(f"🩺 진단 시작: '{component_name}' 컴포넌트 테스트")
            response = await self.gemini_client.generate_content_async(test_prompt)
            if not response.parts:
                logger.error(f"❌ 진단 실패: '{component_name}' 테스트에서 모델이 빈 응답을 반환했습니다.")
                return False
            logger.info(f"✅ 진단 통과: '{component_name}' 컴포넌트가 정상적으로 처리되었습니다.")
            return True
        except Exception as e:
            logger.error(f"❌ 진단 중 심각한 오류 발생 ('{component_name}'): {str(e)}")
            return False

    async def generate_criteria(self, contest_title: str, contest_content: str, organization_persona: str) -> Dict[str, int]:
        """Generate evaluation criteria using Gemini, enriched with persona context."""
        try:
            logger.info(f"🔍 평가 기준 생성 시작 (Gemini 2.5 Pro 기반): {contest_title}")
            user_prompt = f"""당신은 {contest_title}의 심사위원장입니다. 주최 기관의 특성을 깊이 이해하고, 그에 맞는 심사 기준을 만들어야 합니다.

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
            response = await self.gemini_client.generate_content_async(user_prompt, generation_config=self.generation_config)
            json_str = self._extract_json_from_response(response)
            criteria = json.loads(json_str).get("contestCriteria", {})
            logger.info(f"📊 생성된 평가 기준: {criteria}")
            return criteria
        except Exception as e:
            logger.error(f"❌ 평가 기준 생성 실패: {str(e)}")
            return {"브랜드 적합성": 35, "창의성": 25, "기억용이성": 20, "활용성": 20}

    async def evaluate_submissions(self, contest_data: Dict, submissions: List[Dict], organization_persona: str) -> (List[Dict], Dict[str, int]):
        """
        Evaluate submissions in batches, with a preceding diagnostic step.
        """
        try:
            contest_title = contest_data.get('contestTitle', '')
            contest_content = contest_data.get('contestContent', '')
            criteria = contest_data.get('contestCriteria')

            logger.info("🕵️‍♂️ API 응답 문제를 진단하기 위해 자동 진단 시퀀스를 시작합니다.")
            if not await self._test_api_call("기본 연결", "Say 'Hello World' in Korean."):
                raise ConnectionError("API 기본 연결 테스트에 실패했습니다. 인증 또는 네트워크를 확인하세요.")
            
            first_batch_text = self._format_submissions_for_evaluation(submissions[:5])
            if not await self._test_api_call("작명 리스트", f"다음은 작명 리스트입니다: {first_batch_text}"):
                raise ValueError("진단 실패: 작명 리스트 내용이 API 문제를 유발하는 것으로 보입니다.")
            
            if not await self._test_api_call("공모전 내용", f"다음은 공모전 내용입니다: {contest_content}"):
                 raise ValueError("진단 실패: 공모전 내용이 API 문제를 유발하는 것으로 보입니다.")

            if not await self._test_api_call("주최 기관 페르소나", f"다음은 주최 기관 정보입니다: {organization_persona}"):
                 raise ValueError("진단 실패: 주최 기관 페르소나 내용이 API 문제를 유발하는 것으로 보입니다.")
            logger.info("✅ 모든 진단 테스트 통과. 본 평가를 시작합니다.")

            if not criteria:
                criteria = await self.generate_criteria(contest_title, contest_content, organization_persona)

            all_evaluated_submissions = []
            batch_size = 40

            for i in range(0, len(submissions), batch_size):
                batch_submissions = submissions[i:i + batch_size]
                logger.info(f"⚙️ 배치 처리 중: {i+1}-{min(i + batch_size, len(submissions))} / {len(submissions)}")
                submissions_text = self._format_submissions_for_evaluation(batch_submissions)
                user_prompt = f"""당신은 {contest_title}의 전문 심사위원입니다. 아래 정보를 바탕으로 모든 출품작을 평가하세요.\n\n<주최 기관 분석 정보>\n{organization_persona}\n</주최 기관 분석 정보>\n\n<공모전 내용>\n{contest_content}\n</공모전 내용>\n\n<평가 기준>\n{json.dumps(criteria, ensure_ascii=False, indent=2)}\n</평가 기준>\n\n<이번에 평가할 출품작 목록>\n{submissions_text}\n</이번에 평가할 출품작 목록>\n\n**평가 지침:**\n1. 각 출품작에 대해 <평가 기준>에 따라 점수를 엄격하게 매겨주세요.\n2. <주최 기관 분석 정보>를 반드시 참고하여, 기관의 성향과 비전에 부합하는지를 점수에 반영하세요.\n3. **제공된 모든 출품작**을 빠짐없이 평가해야 합니다.\n4. 각 작품에 대한 평가 코멘트는 20자 내외의 짧고 핵심적인 내용으로 작성해주세요.\n\n**출력 형식:**\n**중요**: 출력 토큰을 최소화하기 위해, 입력으로 받은 `description`은 제외하고 아래의 JSON 형식에 맞춰 **평가 결과만** 반환합니다.\n```json\n{{\n    "evaluations": [\n        {{\n            "submission": "작명 내용",\n            "score": {{ "기준1": 점수, "기준2": 점수 }},
            "total_score": 총점,\n            "comments": "핵심 평가 코멘트"\n        }}\n    ]\n}}\n```\n"""
                try:
                    response = await self.gemini_client.generate_content_async(user_prompt, generation_config=self.generation_config)
                    json_str = self._extract_json_from_response(response)
                    evaluated_batch = self._parse_evaluation_response(json_str, batch_submissions)
                    all_evaluated_submissions.extend(evaluated_batch)
                except Exception as e:
                    logger.error(f"❌ 배치 {i//batch_size + 1} 처리 중 오류 발생: {str(e)}")
                    self._add_default_scores(batch_submissions)
                    all_evaluated_submissions.extend(batch_submissions)

                if i + batch_size < len(submissions):
                    logger.info("⏳ 15초 대기 (API 속도 제한 준수)")
                    await asyncio.sleep(15)
            
            all_evaluated_submissions.sort(key=lambda x: x.get('total_score', 0), reverse=True)
            logger.info(f"📊 평가 완료: {len(all_evaluated_submissions)}개 작명 정렬됨")
            return all_evaluated_submissions, criteria
        except Exception as e:
            logger.error(f"❌ 작명 평가 전체 프로세스 실패: {str(e)}", exc_info=True)
            return self._add_default_scores(submissions), {} if not criteria else criteria

    def _extract_json_from_response(self, response) -> str:
        if not response.parts:
            logger.warning(f"Model returned empty parts. Finish reason: {response.candidates[0].finish_reason.name if response.candidates else 'N/A'}. Safety ratings: {response.candidates[0].safety_ratings if response.candidates else 'N/A'}")
            raise ValueError("The model returned an empty response.")
        response_text = response.text
        match = re.search(r'```json\s*(.*)\s*```', response_text, re.DOTALL)
        if match:
            return match.group(1)
        return response_text

    def _format_submissions_for_evaluation(self, submissions: List[Dict]) -> str:
        return json.dumps([{"submission": s.get('submission'), "description": s.get('description')} for s in submissions], ensure_ascii=False, indent=2)

    def _parse_evaluation_response(self, json_str: str, original_batch: List[Dict]) -> List[Dict]:
        try:
            logger.info("Parsing evaluation response...")
            data = json.loads(json_str)
            evaluations = data.get("evaluations", [])
            submission_map = {s['submission']: s for s in original_batch}
            for eval_data in evaluations:
                original_sub = submission_map.get(eval_data['submission'])
                if original_sub:
                    try:
                        total_score = int(eval_data.get("total_score", 0))
                    except (ValueError, TypeError):
                        total_score = 0
                    original_sub.update({
                        "score": eval_data.get("score", {}),
                        "total_score": total_score,
                        "comments": eval_data.get("comments", "")
                    })
            evaluated_submissions_set = {e['submission'] for e in evaluations}
            unevaluated_submissions = [s for s in original_batch if s['submission'] not in evaluated_submissions_set]
            if unevaluated_submissions:
                logger.warning(f"모델이 {len(unevaluated_submissions)}개의 작명을 평가하지 않았습니다. 기본 점수를 할당합니다.")
                self._add_default_scores(unevaluated_submissions)
            logger.info(f"Successfully parsed and merged {len(evaluations)} evaluations for this batch.")
            return original_batch
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"❌ 평가 결과 파싱 실패: {str(e)}. Response was: {json_str[:200]}...")
            return self._add_default_scores(original_batch)

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
    """Factory function to create an instance of the evaluator."""
    return EvaluatorWithSearch()
