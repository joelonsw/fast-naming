import json
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime
import google.generativeai as genai
from groq import Groq
# google.generativeai.types에서 HarmCategory와 HarmBlockThreshold를 임포트합니다.
from google.generativeai.types import HarmCategory, HarmBlockThreshold

logger = logging.getLogger(__name__)

class ContestEvaluator:
    def __init__(self):
        """Initialize the contest evaluator with LLM clients."""
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        # 클라이언트 초기화 시 genai.GenerativeModel의 인자가 올바른 모델명이어야 합니다.
        # 'gemini-2.5-pro'가 아닌 'gemini-1.5-pro-latest' 또는 사용 가능한 다른 모델을 사용하세요.
        self.gemini_client = genai.GenerativeModel('gemini-2.5-pro')
        
    def generate_criteria(self, contest_title: str, contest_content: str) -> Dict[str, int]:
        """Generate evaluation criteria using Groq GPT-OSS-120B model."""
        try:
            logger.info(f"🔍 평가 기준 생성 시작: {contest_title}")
            
            system_prompt = f"""당신은 {contest_title}의 심사위원입니다. 
{contest_content}를 참고하여, 공모전의 공정한 평가기준을 마련하세요.
"""

            user_prompt = f"""당신은 {contest_title}의 심사위원입니다. 
{contest_content}를 참고하여, 공모전의 공정한 평가기준을 마련하세요.
평가 기준은 4가지로 마련하며, 각 평가기준의 총합은 100이 되어야 합니다.
다음과 같이 json으로 생성하여 반환하세요.

"contestCriteria": {{
    "배점기준1": 10,
    "배점기준2": 20,
    "배점기준3": 30,
    "배점기준4": 40,
}}"""

            completion = self.groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                max_completion_tokens=1000,
                top_p=1
            )
            
            response = completion.choices[0].message.content
            logger.info(f"✅ 평가 기준 생성 완료: {len(response)}자")
            
            # Parse JSON response
            criteria = self._parse_criteria_response(response)
            logger.info(f"📊 생성된 평가 기준: {criteria}")
            
            return criteria
            
        except Exception as e:
            logger.error(f"❌ 평가 기준 생성 실패: {str(e)}")
            # Fallback to default criteria
            return {
                "창의성": 25,
                "적합성": 25,
                "완성도": 25,
                "기억하기 쉬움": 25
            }
    
    def _parse_criteria_response(self, response: str) -> Dict[str, int]:
        """Parse the criteria response from LLM."""
        try:
            import re
            
            json_match = re.search(r'\{[^{}]*"contestCriteria"[^{}]*\{[^{}]*\}', response)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                return data.get("contestCriteria", {})
            
            criteria_match = re.search(r'"contestCriteria":\s*\{[^{}]*\}', response)
            if criteria_match:
                criteria_str = "{" + criteria_match.group() + "}"
                data = json.loads(criteria_str)
                return data.get("contestCriteria", {})
            
            data = json.loads(response)
            return data.get("contestCriteria", {})
            
        except Exception as e:
            logger.error(f"❌ 평가 기준 파싱 실패: {str(e)}")
            return {
                "창의성": 25,
                "적합성": 25,
                "완성도": 25,
                "기억하기 쉬움": 25
            }

    def evaluate_submissions(self, contest_title: str, contest_content: str, 
                            submissions: List[Dict], criteria: Optional[Dict[str, int]] = None) -> List[Dict]:
        """Evaluate submissions using Gemini model."""
        try:
            logger.info(f"🎯 작명 평가 시작: {len(submissions)}개 작명")
            
            if not criteria:
                criteria = self.generate_criteria(contest_title, contest_content)
            
            submissions_text = self._format_submissions_for_evaluation(submissions)

            user_prompt = f"""당신은 {contest_title}의 심사위원입니다.
    다음은 공모전 내용입니다.
    <contest_content>
    {contest_content}
    </contest_content>
    
    이 공모전의 출품작들을 평가해야 합니다. 다음 출품작에 대해 위의 평가 기준에 따라 채점한 뒤, 점수가 높은 20개 작품을 반환하세요.
    각 submission에 대해 아래의 평가 기준에 따라 점수를 매겨주세요.
    <score_criteria>
    {json.dumps(criteria, ensure_ascii=False, indent=2)}
    </score_criteria>
    <submissions>
    {submissions_text}
    </submissions>

    각 평가 항목에 대한 점수와 함께 총점을 계산하고, 각 작품에 대한 평가 코멘트를 20자 내외로 작성해주세요.
    각 평가 항목에 대한 총점은 100점입니다.

    <expected_json>
    {{
        "evaluations": [
            {{
                "submission": "작명 내용",
                "score": {json.dumps({k: 0 for k in criteria.keys()})},
                "total_score": int,
                "comments": "평가 코멘트"
            }},
            // ... (for other submissions)
        ]
    }}
    </expected_json>

    guidelines:
    1. 전체 submission에 대해 공평한 기준으로 채점을 진행합니다. 항목별로 합리적인 기준으로 채점을 진행해야 합니다. 
    2. 채점된 submission 중 총점이 높은 20개를 선정합니다. 동일 점수일 경우, 무작위로 선정합니다.
    3. 점수가 높은 순서대로 위의 expected_json 형식에 맞춰 결과를 반환합니다. 
    """

            # Call Gemini API
            response = self.gemini_client.generate_content(user_prompt)
            print(response)
            
            # --- ▼ [핵심 수정] API 응답이 비어있는지 확인하는 방어 코드 추가 ▼ ---
            if not response.parts:
                logger.error("❌ Gemini API가 빈 응답을 반환했습니다. Safety Filter에 의해 차단되었을 수 있습니다.")
                # 응답 거부 사유를 로그로 남겨 디버깅에 활용
                logger.error(f"응답 피드백(거부 사유): {response.prompt_feedback}")
                # 평가 실패 시, 기본 점수를 부여하여 프로그램을 정상적으로 이어감
                return self._add_default_scores(submissions)
            # --- ▲ [핵심 수정] 여기까지 ▲ ---
            
            result = response.text
            
            evaluated_submissions = self._parse_evaluation_response(result, submissions)
            evaluated_submissions.sort(key=lambda x: x.get('total_score', 0), reverse=True)
            
            logger.info(f"📊 평가 완료: {len(evaluated_submissions)}개 작명 정렬됨")
            
            return evaluated_submissions
            
        except Exception as e:
            logger.error(f"❌ 작명 평가 중 예외 발생: {str(e)}")
            return self._add_default_scores(submissions)

    def evaluate_submissions_gpt(self, contest_title: str, contest_content: str, 
                        submissions: List[Dict], criteria: Optional[Dict[str, int]] = None) -> List[Dict]:
        try:
            logger.info(f"🎯 작명 평가 시작: {len(submissions)}개 작명")
            
            if not criteria:
                criteria = self.generate_criteria(contest_title, contest_content)
            
            submissions_text = self._format_submissions_for_evaluation(submissions)
            
            system_prompt = f"""당신은 {contest_title}의 심사위원입니다. 
    {contest_content}를 참고하여, 공모전의 공정한 평가를 진행하세요.
    """

            user_prompt = f"""다음 {contest_title}에 출품한 작품들에 대해 평가를 진행하세요.
    <submissions>
    {submissions_text}
    </submissions>

    각 submission에 대해 위의 평가 기준에 따라 점수를 매겨주세요. 
    <score_criteria>
    {json.dumps(criteria, ensure_ascii=False, indent=2)}
    <score_criteria/>
    각 평가 항목에 대한 점수와 함께 총점을 계산하고, 각 작품에 대한 평가 코멘트를 30자 내외로 작성해주세요.
    각 평가 항목에 대한 총점은 100점입니다. 

    <expected_json>
    {{
        "evaluations": [
            {{
                "submission": "작명 내용",
                "description": "설명",
                "score": {json.dumps({k: 0 for k in criteria.keys()})},
                "total_score": int,
                "comments": "평가 코멘트"
            }},
            // ... (for other submissions)
        ]
    }}
    </expected_json>
    """

            completion = self.groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=1,
                max_completion_tokens=8000,
                top_p=1,
                response_format= {"type": "json_object"}
            )

            result = completion.choices[0].message.content
            
            evaluated_submissions = self._parse_evaluation_response(result, submissions)
            evaluated_submissions.sort(key=lambda x: x.get('total_score', 0), reverse=True)
            
            logger.info(f"📊 평가 완료: {len(evaluated_submissions)}개 작명 정렬됨")
            
            return evaluated_submissions
            
        except Exception as e:
            logger.error(f"❌ 작명 평가 실패: {str(e)}")
            return self._add_default_scores(submissions)

    def _format_submissions_for_evaluation(self, submissions: List[Dict]) -> str:
        """Format submissions for LLM evaluation."""
        formatted = []
        for i, submission in enumerate(submissions, 1):
            formatted.append(f"""    {{
      "submission": "{submission.get('submission', '')}",
      "description": "{submission.get('description', '')}",
    }}""")
        
        return "  " + ",\n".join(formatted)

    def _parse_evaluation_response(self, response: str, original_submissions: List[Dict]) -> List[Dict]:
        """Parse the evaluation response from LLM and merge with original submissions."""
        try:
            import re
            
            json_match = re.search(r'\{[^{}]*"evaluations"\s*:\s*\[(.+?)\]\s*\}', response, re.DOTALL)
            if not json_match:
                data = json.loads(response)
                evaluations = data.get("evaluations", [])
            else:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                evaluations = data.get("evaluations", [])
            
            result = []
            for i, evaluation in enumerate(evaluations):
                # 원본 제출물 목록의 길이를 초과하지 않도록 확인
                if i < len(original_submissions):
                    submission = original_submissions[i].copy()
                    submission.update({
                        "score": evaluation.get("score", {}),
                        "total_score": evaluation.get("total_score", 0),
                        "comments": evaluation.get("comments", "")
                    })
                    result.append(submission)
                else:
                    result.append(evaluation) # 원본이 없는 경우, 평가 결과만 추가
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 평가 결과 파싱 실패: {str(e)}")
            return self._add_default_scores(original_submissions)
        
    def _add_default_scores(self, submissions: List[Dict]) -> List[Dict]:
        """Add default scores to submissions when evaluation fails."""
        for submission in submissions:
            submission['score'] = {
                "창의성": 0,
                "적합성": 0,
                "완성도": 0,
                "기억하기 쉬움": 0
            }
            submission['total_score'] = 0
            submission['comments'] = "API 평가 실패 또는 안전 문제로 인한 기본값"
        
        return submissions
    
    def save_evaluation_result(self, result_number: int, evaluated_submissions: List[Dict], 
                             criteria: Dict[str, int], contest_data: Dict) -> str:
        """Save evaluation results to score file."""
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

def create_contest_evaluator() -> ContestEvaluator:
    """Create and return a contest evaluator instance."""
    return ContestEvaluator()