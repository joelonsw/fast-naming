import json
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime
import google.generativeai as genai
from groq import Groq

logger = logging.getLogger(__name__)

class ContestEvaluator:
    def __init__(self):
        """Initialize the contest evaluator with LLM clients."""
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.gemini_client = genai.GenerativeModel('gemini-2.5-flash')
        
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
            # Try to extract JSON from the response
            import re
            
            # Look for JSON pattern
            json_match = re.search(r'\{[^{}]*"contestCriteria"[^{}]*\{[^{}]*\}', response)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                return data.get("contestCriteria", {})
            
            # If no JSON found, try to extract just the criteria part
            criteria_match = re.search(r'"contestCriteria":\s*\{[^{}]*\}', response)
            if criteria_match:
                criteria_str = "{" + criteria_match.group() + "}"
                data = json.loads(criteria_str)
                return data.get("contestCriteria", {})
            
            # Fallback: try to parse the entire response as JSON
            data = json.loads(response)
            return data.get("contestCriteria", {})
            
        except Exception as e:
            logger.error(f"❌ 평가 기준 파싱 실패: {str(e)}")
            # Return default criteria
            return {
                "창의성": 25,
                "적합성": 25,
                "완성도": 25,
                "기억하기 쉬움": 25
            }

    def evaluate_submissions(self, contest_title: str, contest_content: str, 
                            submissions: List[Dict], criteria: Optional[Dict[str, int]] = None) -> List[Dict]:
        """Evaluate submissions using Gemini 2.5 flash model."""
        try:
            logger.info(f"🎯 작명 평가 시작: {len(submissions)}개 작명")
            
            # Generate criteria if not provided
            if not criteria:
                criteria = self.generate_criteria(contest_title, contest_content)
            
            # Prepare submissions for evaluation
            submissions_text = self._format_submissions_for_evaluation(submissions)

            # 👇 user_prompt에 시스템 프롬프트의 역할을 부여합니다.
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

    guidelines:
    1. 전체 submission에 대해 공평한 기준으로 채점을 진행합니다. 
    2. 채점된 submission 중 점수가 높은 20개를 선정합니다. 동일 점수일 경우, 무작위로 선정합니다.
    3. 점수가 높은 순서래도 위의 expected_json 형식에 맞춰 결과를 반환합니다. 
    """

            # Call Gemini API
            response = self.gemini_client.generate_content(user_prompt)
            result = response.text
            
            print(result)
            
            # Parse evaluation results
            evaluated_submissions = self._parse_evaluation_response(result, submissions)
            
            # Sort by total score (highest first)
            evaluated_submissions.sort(key=lambda x: x.get('total_score', 0), reverse=True)
            
            logger.info(f"📊 평가 완료: {len(evaluated_submissions)}개 작명 정렬됨")
            
            return evaluated_submissions
            
        except Exception as e:
            logger.error(f"❌ 작명 평가 실패: {str(e)}")
            # Return original submissions with default scores
            return self._add_default_scores(submissions)

    def evaluate_submissions_gpt(self, contest_title: str, contest_content: str, 
                        submissions: List[Dict], criteria: Optional[Dict[str, int]] = None) -> List[Dict]:
        try:
            logger.info(f"🎯 작명 평가 시작: {len(submissions)}개 작명")
            
            # Generate criteria if not provided
            if not criteria:
                criteria = self.generate_criteria(contest_title, contest_content)
            
            # Prepare submissions for evaluation
            submissions_text = self._format_submissions_for_evaluation(submissions)
            
            system_prompt = f"""당신은 {contest_title}의 심사위원입니다. 
    {contest_content}를 참고하여, 공모전의 공정한 평가를 진행하세요.
    """

            # --- 👇 여기부터 들여쓰기를 수정합니다 ---
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
                reasoning_effort="medium",
                top_p=1,
                response_format= {"type": "json_object"}
            )

            result = completion.choices[0].message.content
            print(result)
            # logger.info(f"✅ 작명 평가 완료: {len(result)}자")
            
            # Parse evaluation results
            evaluated_submissions = self._parse_evaluation_response(result, submissions)
            
            # Sort by total score (highest first)
            evaluated_submissions.sort(key=lambda x: x.get('total_score', 0), reverse=True)
            
            logger.info(f"📊 평가 완료: {len(evaluated_submissions)}개 작명 정렬됨")
            
            return evaluated_submissions
            # --- 👆 여기까지 들여쓰기를 수정합니다 ---
            
        except Exception as e:
            logger.error(f"❌ 작명 평가 실패: {str(e)}")
            # Return original submissions with default scores
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
            
            # Use a more robust regex to find the 'evaluations' array
            json_match = re.search(r'\{[^{}]*"evaluations"\s*:\s*\[(.+?)\]\s*\}', response, re.DOTALL)
            if not json_match:
                # Fallback to parsing the entire response
                data = json.loads(response)
                evaluations = data.get("evaluations", [])
            else:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                evaluations = data.get("evaluations", [])
            
            # Merge with original submissions
            result = []
            for i, evaluation in enumerate(evaluations):
                if i < len(original_submissions):
                    submission = original_submissions[i].copy()
                    # Ensure scores and total score are correctly updated
                    submission.update({
                        "score": evaluation.get("score", {}),
                        "total_score": evaluation.get("total_score", 0),
                        "comments": evaluation.get("comments", "")
                    })
                    result.append(submission)
                else:
                    result.append(evaluation)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 평가 결과 파싱 실패: {str(e)}")
            return self._add_default_scores(original_submissions)
        
    def _add_default_scores(self, submissions: List[Dict]) -> List[Dict]:
        """Add default scores to submissions when evaluation fails."""
        for submission in submissions:
            submission['score'] = {
                "창의성": 20,
                "적합성": 25,
                "완성도": 25,
                "기억하기 쉬움": 30
            }
            submission['total_score'] = 100
            submission['comments'] = "기본 평가 점수"
        
        return submissions
    
    def save_evaluation_result(self, result_number: int, evaluated_submissions: List[Dict], 
                             criteria: Dict[str, int], contest_data: Dict) -> str:
        """Save evaluation results to score file."""
        try:
            # Create result directory if it doesn't exist
            os.makedirs("result", exist_ok=True)
            
            # Generate score file name
            score_file = f"result/score{result_number:04d}.json"
            
            # Prepare data for saving
            evaluation_data = {
                "contest_data": contest_data,
                "evaluation_criteria": criteria,
                "evaluation_timestamp": datetime.now().isoformat(),
                "total_submissions": len(evaluated_submissions),
                "submissions": evaluated_submissions
            }
            
            # Save to file
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
