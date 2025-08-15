
"""
LLM Clients for multiple providers (GitHub AI, Groq, Google Gemini)
This module provides unified interfaces for different LLM providers.
"""


import os
import json
import random
import logging
from typing import List, Dict, Any, Optional, Union
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Groq imports
from groq import Groq

# GitHub AI imports
try:
    from azure.ai.inference import ChatCompletionsClient
    from azure.ai.inference.models import SystemMessage, UserMessage
    from azure.core.credentials import AzureKeyCredential
    GITHUB_AI_AVAILABLE = True
except ImportError:
    GITHUB_AI_AVAILABLE = False

# Google Gemini imports
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Together AI imports
try:
    from together import Together
    TOGETHER_AVAILABLE = True
except ImportError:
    TOGETHER_AVAILABLE = False


class LLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Generate response from LLM."""
        pass


class GroqClient(LLMClient):
    """Groq LLM client."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable must be set")
        self.client = Groq(api_key=self.api_key)
    
    def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Generate response using Groq."""
        try:
            model = kwargs.get("model", "openai/gpt-oss-120b")
            temperature = kwargs.get("temperature", 1.0)
            max_tokens = kwargs.get("max_tokens", 8192)
            top_p = kwargs.get("top_p", 1.0)
            reasoning_effort = kwargs.get("reasoning_effort", "medium")
            
            logger.info(f"🚀 Groq API 호출: model={model}, temp={temperature}, top_p={top_p}")
            
            # reasoning_effort를 지원하는 모델만 해당 파라미터 사용
            request_params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_completion_tokens": max_tokens,
                "top_p": top_p,
                "stream": False
            }
            
            # reasoning_effort를 지원하는 모델에만 추가
            if model == "openai/gpt-oss-120b":
                request_params["reasoning_effort"] = reasoning_effort
            
            completion = self.client.chat.completions.create(**request_params)
            
            response = completion.choices[0].message.content
            logger.info(f"✅ Groq API 응답 수신: {len(response)}자")
            return response
            
        except Exception as e:
            logger.error(f"❌ Groq API 오류: {str(e)}")
            raise Exception(f"Groq generation failed: {str(e)}")


class GitHubAIClient(LLMClient):
    """GitHub AI LLM client."""
    
    def __init__(self, api_key: Optional[str] = None):
        if not GITHUB_AI_AVAILABLE:
            raise ImportError("GitHub AI dependencies not available. Install azure-ai-inference")
        
        self.api_key = api_key or os.getenv("GITHUB_TOKEN")
        if not self.api_key:
            raise ValueError("GITHUB_TOKEN environment variable must be set")
        
        self.endpoint = "https://models.github.ai/inference"
        self.client = ChatCompletionsClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.api_key)
        )
    
    def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Generate response using GitHub AI."""
        try:
            model = kwargs.get("model", "openai/gpt-5")
            
            response = self.client.complete(
                messages=[
                    SystemMessage(system_prompt),
                    UserMessage(user_prompt)
                ],
                model=model
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"GitHub AI generation failed: {str(e)}")


class GeminiClient(LLMClient):
    """Google Gemini LLM client."""
    
    def __init__(self, api_key: Optional[str] = None):
        if not GEMINI_AVAILABLE:
            raise ImportError("Gemini dependencies not available. Install google-generativeai")
        
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable must be set")
        
        genai.configure(api_key=self.api_key)
    
    def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Generate response using Google Gemini."""
        try:
            model_name = kwargs.get("model", "gemini-2.5-flash")
            model = genai.GenerativeModel(model_name)
            
            # Combine system and user prompts for Gemini
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            raise Exception(f"Gemini generation failed: {str(e)}")


class TogetherClient(LLMClient):
    """Together AI LLM client."""
    
    def __init__(self, api_key: Optional[str] = None):
        if not TOGETHER_AVAILABLE:
            raise ImportError("Together AI dependencies not available. Install `together`")
        
        self.api_key = api_key or os.getenv("TOGETHER_API_KEY")
        if not self.api_key:
            raise ValueError("TOGETHER_API_KEY environment variable must be set")
        
        self.client = Together(api_key=self.api_key)
    
    def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Generate response using Together AI."""
        try:
            model = kwargs.get("model", "lgai/exaone-deep-32b")
            temperature = kwargs.get("temperature", 1.0)
            max_tokens = kwargs.get("max_tokens", 8192)
            top_p = kwargs.get("top_p", 1.0)
            
            logger.info(f"🚀 Together AI API 호출: model={model}, temp={temperature}, top_p={top_p}")
            
            # Combine system and user prompts
            # Together API uses a similar message format to OpenAI
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )
            
            content = response.choices[0].message.content
            logger.info(f"✅ Together AI API 응답 수신: {len(content)}자")
            return content
            
        except Exception as e:
            logger.error(f"❌ Together AI API 오류: {str(e)}")
            raise Exception(f"Together AI generation failed: {str(e)}")


class LLMOrchestrator:
    """Orchestrator for managing multiple LLM clients and generating contest submissions."""
    
    def __init__(self):
        logger.info("🔧 LLMOrchestrator 초기화 시작")
        self.clients = {}
        self._initialize_clients()
        logger.info("✅ LLMOrchestrator 초기화 완료")
    
    def _initialize_clients(self):
        """Initialize available LLM clients."""
        logger.info("🔧 LLM 클라이언트 초기화 시작")
        
        # Initialize Groq client
        try:
            self.clients["groq"] = {
                "client": GroqClient(),
                "models": [
                    "openai/gpt-oss-120b", 
                    "deepseek-r1-distill-llama-70b", 
                    "llama-3.3-70b-versatile",
                    "gemma2-9b-it",
                    "qwen/qwen3-32b"
                ]
            }
            logger.info("✅ Groq 클라이언트 초기화 성공")
        except Exception as e:
            logger.error(f"❌ Groq 클라이언트 초기화 실패: {e}")
        
        # GitHub AI 클라이언트 비활성화 (속도 제한 문제로 인해)
        logger.info("⚠️ GitHub AI 클라이언트 비활성화 (속도 제한 문제)")
        
        # Initialize Gemini client
        try:
            self.clients["gemini"] = {
                "client": GeminiClient(),
                "models": ["gemini-2.5-flash"]
            }
            logger.info("✅ Gemini 클라이언트 초기화 성공")
        except Exception as e:
            logger.error(f"❌ Gemini 클라이언트 초기화 실패: {e}")
            
        # Initialize Together AI client
        try:
            self.clients["together"] = {
                "client": TogetherClient(),
                "models": ["lgai/exaone-deep-32b", "lgai/exaone-3-5-32b-instruct"]
            }
            logger.info("✅ Together AI 클라이언트 초기화 성공")
        except Exception as e:
            logger.error(f"❌ Together AI 클라이언트 초기화 실패: {e}")
        
        logger.info(f"📊 초기화된 클라이언트: {list(self.clients.keys())}")
    
    def generate_submissions(
        self,
        contest_data: Dict[str, Any],
        successful_examples: List[Dict[str, str]],
        num_iterations: int = 5
    ) -> List[Dict[str, Any]]:
        """Generate contest submissions using multiple LLM providers."""
        logger.info("🎯 LLM 작명 생성 시작")
        logger.info(f"📊 설정: {len(self.clients)}개 제공자, {num_iterations}회 반복")
        
        all_submissions = []
        
        # Temperature and top_p variations
        temperature_variations = [0.3, 0.5, 0.7, 0.9, 1.0]
        top_p_variations = [0.7, 0.8, 0.9, 0.95, 1.0]
        
        total_attempts = 0
        successful_attempts = 0
        last_logged_model = None
        
        for provider_name, provider_info in self.clients.items():
            logger.info(f"🤖 {provider_name} 제공자 처리 시작")
            client = provider_info["client"]
            models = provider_info["models"]
            
            for model in models:
                logger.info(f"📝 모델 {model} 처리 시작")
                for i in range(num_iterations):
                    total_attempts += 1
                    try:
                        # Use deterministic temperature and top_p based on iteration
                        temperature = temperature_variations[i % len(temperature_variations)]
                        top_p = top_p_variations[i % len(top_p_variations)]
                        
                        logger.info(f"🔄 {provider_name}/{model} - 반복 {i+1}/{num_iterations} (temp={temperature}, top_p={top_p})")
                        
                        # Create prompts
                        system_prompt = self._create_system_prompt(contest_data)
                        user_prompt = self._create_user_prompt(contest_data, successful_examples)
                        
                        # Log prompts only when the model changes
                        if model != last_logged_model:
                            logger.info(f"✨ New prompt for model '{model}':")
                            logger.info(f"SYSTEM PROMPT:\n{system_prompt}")
                            logger.info(f"USER PROMPT:\n{user_prompt}")
                            last_logged_model = model

                        # Generate response
                        response = client.generate(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            model=model,
                            temperature=temperature,
                            top_p=top_p,
                            max_tokens=8192
                        )
                        
                        # Parse response
                        submissions = self._parse_response(response)
                        
                        # Validate submissions
                        valid_submissions = self._validate_submissions(submissions)
                        
                        # Add metadata
                        for submission in valid_submissions:
                            submission.update({
                                "provider": provider_name,
                                "model": model,
                                "temperature": temperature,
                                "top_p": top_p,
                                "iteration": i + 1
                            })
                        
                        all_submissions.extend(valid_submissions)
                        successful_attempts += 1
                        
                        logger.info(f"✅ {provider_name}/{model} - 반복 {i+1} 성공: {len(valid_submissions)}개 작명 생성")
                        
                    except Exception as e:
                        logger.error(f"❌ {provider_name}/{model} - 반복 {i+1} 실패: {e}")
                        continue
        
        logger.info(f"🎉 LLM 작명 생성 완료!")
        logger.info(f"📊 총 시도: {total_attempts}회, 성공: {successful_attempts}회, 총 작명: {len(all_submissions)}개")
        
        return all_submissions
    
    def _create_system_prompt(self, contest_data: Dict[str, Any]) -> str:
        """Create system prompt for contest submission generation."""
        return '''당신은 대한민국 최고의 네이미스트입니다. 
당신은 주최측이 원하는 네이밍을 무조건 제공하는 네이미스트입니다.
반드시 JSON 형식으로만 응답해야 합니다.'''
    
    def _create_user_prompt(self, contest_data: Dict[str, Any], successful_examples: List[Dict[str, str]]) -> str:
        """Create user prompt with few-shot examples."""
        # Select 3 random examples
        selected_examples = random.sample(successful_examples, min(3, len(successful_examples)))
        
        prompt = f"{contest_data['contestTitle']} 공모전에 참여하여 수상 확률이 가장 높은 3가지 {contest_data['contestType']}을 만드세요.\n\n"
        prompt += f"<contest_description>\n{contest_data['contestContent']}\n</contest_description>\n\n"
        
        prompt += "앞서 비슷한 유형의 공모전에서 수상한 작품들을 참고하세요.\n"
        
        for i, example in enumerate(selected_examples, 1):
            prompt += f"<sample_input{i}>\n{example['contestTitle']}\n</sample_input{i}>\n"
            prompt += f"<ideal_output{i}>\n{example['contestWinner']}\n</ideal_output{i}>\n"
            prompt += f"<strength{i}>\n{example['strength']}\n</strength{i}>\n\n"
        
        prompt += "guidelines:\n"
        prompt += f"1. {contest_data['contestContent']}에 있는 요구사항을 모두 준수해야 합니다.\n"
        prompt += f"2. {contest_data['contestHeldBy']}에서 좋아할 작명이여야 합니다.\n"
        prompt += "3. submission은 반드시 한 문장의 슬로건/네이밍만 포함해야 합니다.\n"
        prompt += "4. description은 해당 작명을 생성한 이유와 특징을 설명해야 합니다.\n\n"
        
        prompt += "반드시 다음 JSON 형식으로만 응답하세요:\n"
        prompt += '''```json
[
    {
        "submission": "슬로건/네이밍 한 문장",
        "description": "해당 작명을 생성한 이유와 특징 설명"
    },
    {
        "submission": "슬로건/네이밍 한 문장",
        "description": "해당 작명을 생성한 이유와 특징 설명"
    },
    {
        "submission": "슬로건/네이밍 한 문장",
        "description": "해당 작명을 생성한 이유와 특징 설명"
    }
]
```'''
        
        return prompt
    
    def _parse_response(self, response: str) -> List[Dict[str, str]]:
        """Parse LLM response into structured format."""
        logger.info(f"🔍 응답 파싱 시작: {len(response)}자")
        
        try:
            # 1. 직접 JSON 파싱 시도
            if response.strip().startswith('['):
                logger.info("✅ 직접 JSON 배열 파싱 성공")
                return json.loads(response)
            elif response.strip().startswith('{'):
                logger.info("✅ 직접 JSON 객체 파싱 성공")
                return [json.loads(response)]
            
            # 2. 코드 블록에서 JSON 추출
            import re
            # ```json ... ``` 패턴 찾기
            json_block_match = re.search(r'```json\s*(\[.*?\])\s*```', response, re.DOTALL)
            if json_block_match:
                logger.info("✅ 코드 블록에서 JSON 추출 성공")
                return json.loads(json_block_match.group(1))
            
            # 3. 일반 JSON 배열 패턴 찾기
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                logger.info("✅ 정규식으로 JSON 배열 추출 성공")
                return json.loads(json_match.group())
            
            # 4. 개별 JSON 객체들 찾기
            json_objects = re.findall(r'\{[^{}]*"submission"[^{}]*\}', response, re.DOTALL)
            if json_objects:
                logger.info(f"✅ 개별 JSON 객체 {len(json_objects)}개 추출 성공")
                submissions = []
                for obj_str in json_objects:
                    try:
                        submissions.append(json.loads(obj_str))
                    except:
                        continue
                if submissions:
                    return submissions
            
            # 5. 텍스트에서 슬로건/네이밍 추출 (최후의 수단)
            logger.warning("⚠️ JSON 파싱 실패, 텍스트에서 슬로건 추출 시도")
            submissions = self._extract_submissions_from_text(response)
            if submissions:
                return submissions
            
            # 6. 완전한 실패 시
            logger.error("❌ 모든 파싱 방법 실패")
            return [{'submission': '파싱 실패', 'description': f'원본 응답: {response[:200]}...'}]
            
        except Exception as e:
            logger.error(f"❌ JSON 파싱 오류: {e}")
            return [{'submission': '파싱 오류', 'description': f'오류: {str(e)}'}]
    
    def _extract_submissions_from_text(self, response: str) -> List[Dict[str, str]]:
        """Extract submissions from text when JSON parsing fails."""
        submissions = []
        
        # 줄바꿈으로 분리
        lines = response.strip().split('\n')
        current_submission = None
        
        for line in lines:
            line = line.strip()
            
            # 슬로건/네이밍 패턴 찾기 (번호나 기호로 시작하는 줄)
            if re.match(r'^[\d\-\*\.]+', line) and len(line) > 5:
                if current_submission:
                    submissions.append(current_submission)
                
                # 슬로건 추출 (번호/기호 제거)
                submission_text = re.sub(r'^[\d\-\*\.\s]+', '', line).strip()
                if submission_text:
                    current_submission = {
                        'submission': submission_text,
                        'description': f'텍스트에서 추출된 슬로건: {submission_text}'
                    }
        
        # 마지막 submission 추가
        if current_submission:
            submissions.append(current_submission)
        
        # 3개까지만 반환
        return submissions[:3]
    
    def _validate_submissions(self, submissions: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Validate and clean submissions."""
        valid_submissions = []
        
        for submission in submissions:
            # 필수 필드 확인
            if not isinstance(submission, dict):
                continue
                
            if 'submission' not in submission or 'description' not in submission:
                continue
            
            submission_text = submission['submission']
            description_text = submission['description']
            
            # submission이 너무 길면 잘라내기 (한 문장이어야 함)
            if len(submission_text) > 100:
                # 첫 번째 문장만 추출
                import re
                first_sentence = re.split(r'[.!?]', submission_text)[0].strip()
                if first_sentence:
                    submission_text = first_sentence + '.'
                else:
                    submission_text = submission_text[:50] + '...'
            
            # description이 너무 짧으면 기본값 설정
            if len(description_text) < 10:
                description_text = f"생성된 슬로건: {submission_text}"
            
            valid_submissions.append({
                'submission': submission_text,
                'description': description_text
            })
        
        logger.info(f"🔍 검증 결과: {len(submissions)}개 중 {len(valid_submissions)}개 유효")
        return valid_submissions


# Convenience function
def create_llm_orchestrator() -> LLMOrchestrator:
    """Create and return an LLM orchestrator instance."""
    return LLMOrchestrator()

