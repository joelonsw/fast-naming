

"""
Async LLM Clients for multiple providers (GitHub AI, Groq, Google Gemini)
This module provides unified interfaces for different LLM providers with async support.
"""

import os
import json
import random
import logging
import asyncio
from typing import List, Dict, Any, Optional

from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Groq imports
from groq import AsyncGroq

# GitHub AI imports
try:
    from azure.ai.inference.aio import ChatCompletionsClient
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
    from together import AsyncTogether
    TOGETHER_AVAILABLE = True
except ImportError:
    TOGETHER_AVAILABLE = False


class AsyncLLMClient(ABC):
    """Abstract base class for async LLM clients."""

    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Generate response from LLM asynchronously."""
        pass


class AsyncGroqClient(AsyncLLMClient):
    """Async Groq LLM client."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable must be set")
        self.client = AsyncGroq(api_key=self.api_key)

    async def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Generate response using Groq asynchronously."""
        try:
            model = kwargs.get("model", "openai/gpt-oss-120b")
            temperature = kwargs.get("temperature", 1.0)
            max_tokens = kwargs.get("max_tokens", 8192)
            top_p = kwargs.get("top_p", 1.0)
            reasoning_effort = kwargs.get("reasoning_effort", "medium")

            logger.info(f"🚀 Groq API 호출: model={model}, temp={temperature}, top_p={top_p}")

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

            if model == "openai/gpt-oss-120b":
                request_params["reasoning_effort"] = reasoning_effort

            if model != "llama-3.3-70b-versatile":
                request_params["response_format"] = {"type": "json_object"}

            completion = await self.client.chat.completions.create(**request_params)

            response = completion.choices[0].message.content
            logger.info(f"✅ Groq API 응답 수신: {len(response)}자")
            return response

        except Exception as e:
            logger.error(f"❌ Groq API 오류: {str(e)}")
            raise Exception(f"Groq generation failed: {str(e)}")


class AsyncGitHubAIClient(AsyncLLMClient):
    """Async GitHub AI LLM client."""

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

    async def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Generate response using GitHub AI asynchronously."""
        try:
            model = kwargs.get("model", "microsoft/Phi-4")

            response = await self.client.complete(
                messages=[
                    SystemMessage(system_prompt),
                    UserMessage(user_prompt)
                ],
                model=model
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"GitHub AI generation failed: {str(e)}")


class AsyncGeminiClient(AsyncLLMClient):
    """Async Google Gemini LLM client."""

    def __init__(self, api_key: Optional[str] = None):
        if not GEMINI_AVAILABLE:
            raise ImportError("Gemini dependencies not available. Install google-generativeai")

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable must be set")

        genai.configure(api_key=self.api_key)

    async def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Generate response using Google Gemini asynchronously."""
        try:
            model_name = kwargs.get("model", "gemini-2.5-flash")
            model = genai.GenerativeModel(model_name)

            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            response = await model.generate_content_async(full_prompt)
            return response.text
        except Exception as e:
            raise Exception(f"Gemini generation failed: {str(e)}")


class AsyncTogetherClient(AsyncLLMClient):
    """Async Together AI LLM client."""

    def __init__(self, api_key: Optional[str] = None):
        if not TOGETHER_AVAILABLE:
            raise ImportError("Together AI dependencies not available. Install `together`")

        self.api_key = api_key or os.getenv("TOGETHER_API_KEY")
        if not self.api_key:
            raise ValueError("TOGETHER_API_KEY environment variable must be set")

        self.client = AsyncTogether(api_key=self.api_key)

    async def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Generate response using Together AI asynchronously."""
        try:
            model = kwargs.get("model", "lgai/exaone-deep-32b")
            temperature = kwargs.get("temperature", 1.0)
            max_tokens = kwargs.get("max_tokens", 8192)
            top_p = kwargs.get("top_p", 1.0)

            logger.info(f"🚀 Together AI API 호출: model={model}, temp={temperature}, top_p={top_p}")

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = await self.client.chat.completions.create(
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


class AsyncLLMOrchestrator:
    """Orchestrator for managing multiple async LLM clients and generating contest submissions."""

    def __init__(self):
        logger.info("🔧 AsyncLLMOrchestrator 초기화 시작")
        self.clients = {}
        self._initialize_clients()
        logger.info("✅ AsyncLLMOrchestrator 초기화 완료")

    def _initialize_clients(self):
        """Initialize available async LLM clients."""
        logger.info("🔧 Async LLM 클라이언트 초기화 시작")

        try:
            self.clients["groq"] = {
                "client": AsyncGroqClient(),
                "models": [
                    "openai/gpt-oss-120b",
                    "llama-3.3-70b-versatile",
                    "qwen/qwen3-32b"
                ]
            }
            logger.info("✅ Groq 클라이언트 초기화 성공")
        except Exception as e:
            logger.error(f"❌ Groq 클라이언트 초기화 실패: {e}")

        logger.info("⚠️ GitHub AI 클라이언트 비활성화 (속도 제한 문제)")

        try:
            self.clients["gemini"] = {
                "client": AsyncGeminiClient(),
                "models": ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemma-3-27b-it"]
            }
            logger.info("✅ Gemini 클라이언트 초기화 성공")
        except Exception as e:
            logger.error(f"❌ Gemini 클라이언트 초기화 실패: {e}")

        try:
            self.clients["together"] = {
                "client": AsyncTogetherClient(),
                "models": ["lgai/exaone-3-5-32b-instruct"]
            }
            logger.info("✅ Together AI 클라이언트 초기화 성공")
        except Exception as e:
            logger.error(f"❌ Together AI 클라이언트 초기화 실패: {e}")

        try:
            self.clients["github"] = {
                "client": AsyncGitHubAIClient(),
                "models": ["microsoft/Phi-4"]
            }
            logger.info("✅ github AI 클라이언트 초기화 성공")
        except Exception as e:
            logger.error(f"❌ github AI 클라이언트 초기화 실패: {e}")

        logger.info(f"📊 초기화된 클라이언트: {list(self.clients.keys())}")

    async def generate_submissions(
        self,
        contest_data: Dict[str, Any],
        successful_examples: List[Dict[str, str]],
        num_iterations: int = 5
    ) -> List[Dict[str, Any]]:
        """Generate contest submissions using multiple async LLM providers."""
        logger.info("🎯 Async LLM 작명 생성 시작")
        logger.info(f"📊 설정: {len(self.clients)}개 제공자, {num_iterations}회 반복")

        tasks = []
        # temperature_variations = [0.85, 0.925, 1, 1.075, 1.15]
        temperature_variations = [0.9, 0.95, 1, 1.05, 1.1]

        for provider_name, provider_info in self.clients.items():
            client = provider_info["client"]
            models = provider_info["models"]
            for model in models:
                for i in range(num_iterations):
                    temperature = temperature_variations[i % len(temperature_variations)]
                    # top_p = top_p_variations[i % len(top_p_variations)]
                    top_p = 0.99999
                    task = self._generate_single_submission(
                        client,
                        provider_name,
                        model,
                        i,
                        temperature,
                        top_p,
                        contest_data,
                        successful_examples
                    )
                    tasks.append(task)

        results = await asyncio.gather(*tasks)
        all_submissions = [item for sublist in results for item in sublist]

        logger.info(f"🎉 Async LLM 작명 생성 완료! 총 작명: {len(all_submissions)}개")
        return all_submissions

    async def _generate_single_submission(
        self,
        client: AsyncLLMClient,
        provider_name: str,
        model: str,
        iteration: int,
        temperature: float,
        top_p: float,
        contest_data: Dict[str, Any],
        successful_examples: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """Generate a single submission asynchronously."""
        try:
            logger.info(f"🔄 {provider_name}/{model} - 반복 {iteration+1} (temp={temperature}, top_p={top_p})")

            system_prompt = self._create_system_prompt(contest_data)
            user_prompt = self._create_user_prompt(contest_data, successful_examples)

            response = await client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                temperature=temperature,
                top_p=top_p,
                max_tokens=8192
            )

            submissions = self._parse_response(response)
            valid_submissions = self._validate_submissions(submissions)

            for submission in valid_submissions:
                submission.update({
                    "provider": provider_name,
                    "model": model,
                    "temperature": temperature,
                    "top_p": top_p,
                    "iteration": iteration + 1
                })
            
            logger.info(f"✅ {provider_name}/{model} - 반복 {iteration+1} 성공: {len(valid_submissions)}개 작명 생성")
            return valid_submissions

        except Exception as e:
            logger.error(f"❌ {provider_name}/{model} - 반복 {iteration+1} 실패: {e}")
            return []

    def _create_system_prompt(self, contest_data: Dict[str, Any]) -> str:
        return '''당신은 대한민국 최고의 네이미스트입니다.
당신은 주최측이 원하는 네이밍을 무조건 제공하는 네이미스트입니다.
반드시 JSON 형식으로만 응답해야 합니다.'''

    def _create_user_prompt(self, contest_data: Dict[str, Any], successful_examples: List[Dict[str, str]]) -> str:
        selected_examples = random.sample(successful_examples, min(1, len(successful_examples)))

        prompt = f"{contest_data['contestTitle']}에 참여하여 수상 확률이 가장 높은 3가지 {contest_data['contestType']}을 만드세요.\n\n"
        prompt += f"<contest_description>\n{contest_data['contestContent']}\n</contest_description>\n\n"
        prompt += "앞서 비슷한 유형의 공모전에서 수상한 작품들을 참고하세요.\n"

        for i, example in enumerate(selected_examples, 1):
            prompt += f"<sample_input{i}>\n{example['contestTitle']}\n</sample_input{i}>\n"
            prompt += f"<ideal_output{i}>\n{example['contestWinner']}\n</ideal_output{i}>\n"
            prompt += f"<strength{i}>\n{example['strength']}\n</strength{i}>\n\n"

        prompt += "guidelines:\n"
        prompt += f"1. {contest_data['contestTitle']}에서 수상할 작품 10가지를 브레인스토밍하세요.\n"
        prompt += f"2. 10가지 브레인스토밍 된 작품 중에 제일 퀄리티가 좋은 작품 3가지를 선택하세요.\n"
        prompt += f"3. submission에 하나의 {contest_data['contestType']}만 포함해야 합니다.\n"
        prompt += f"4. description에 해당 {contest_data['contestType']}을 생성한 이유와 특징을 설명해야 합니다.\n\n"
        prompt += "반드시 다음 JSON 형식으로만 응답하세요:\n"
        prompt += f'''```json
[
    {{
        "submission": "하나의 {contest_data['contestType']}",
        "description": "해당 작명을 생성한 이유와 특징 설명"
    }},
    {{
        "submission": "하나의 {contest_data['contestType']}",
        "description": "해당 작명을 생성한 이유와 특징 설명"
    }},
    {{
        "submission": "하나의 {contest_data['contestType']}",
        "description": "해당 작명을 생성한 이유와 특징 설명"
    }}
]
```'''
        return prompt

    def _parse_response(self, response: str) -> List[Dict[str, str]]:
        logger.info(f"🔍 응답 파싱 시작: {len(response)}자")
        try:
            if response.strip().startswith('['):
                logger.info("✅ 직접 JSON 배열 파싱 성공")
                return json.loads(response)
            elif response.strip().startswith('{'):
                logger.info("✅ 직접 JSON 객체 파싱 성공")
                return [json.loads(response)]

            import re
            json_block_match = re.search(r'```json\s*(\[.*?\])\s*```', response, re.DOTALL)
            if json_block_match:
                logger.info("✅ 코드 블록에서 JSON 추출 성공")
                return json.loads(json_block_match.group(1))

            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                logger.info("✅ 정규식으로 JSON 배열 추출 성공")
                return json.loads(json_match.group())

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

            logger.warning("⚠️ JSON 파싱 실패, 텍스트에서 슬로건 추출 시도")
            submissions = self._extract_submissions_from_text(response)
            if submissions:
                return submissions

            logger.error("❌ 모든 파싱 방법 실패")
            return [{'submission': '파싱 실패', 'description': f'원본 응답: {response[:200]}...'}]

        except Exception as e:
            logger.error(f"❌ JSON 파싱 오류: {e}")
            return [{'submission': '파싱 오류', 'description': f'오류: {str(e)}'}]

    def _extract_submissions_from_text(self, response: str) -> List[Dict[str, str]]:
        submissions = []
        lines = response.strip().split('\n')
        current_submission = None
        import re
        for line in lines:
            line = line.strip()
            if re.match(r'^[\d\-\*. ]+', line) and len(line) > 5:
                if current_submission:
                    submissions.append(current_submission)
                submission_text = re.sub(r'^[\d\-\*.\s]+', '', line).strip()
                if submission_text:
                    current_submission = {
                        'submission': submission_text,
                        'description': f'텍스트에서 추출된 슬로건: {submission_text}'
                    }
        if current_submission:
            submissions.append(current_submission)
        return submissions[:3]

    def _validate_submissions(self, submissions: List[Dict[str, str]]) -> List[Dict[str, str]]:
        valid_submissions = []
        for submission in submissions:
            if not isinstance(submission, dict):
                continue
            if 'submission' not in submission or 'description' not in submission:
                continue
            submission_text = submission['submission']
            description_text = submission['description']
            if len(submission_text) > 100:
                import re
                first_sentence = re.split(r'[.!?]', submission_text)[0].strip()
                if first_sentence:
                    submission_text = first_sentence + '.'
                else:
                    submission_text = submission_text[:50] + '...'
            if len(description_text) < 10:
                description_text = f"생성된 슬로건: {submission_text}"
            valid_submissions.append({
                'submission': submission_text,
                'description': description_text
            })
        logger.info(f"🔍 검증 결과: {len(submissions)}개 중 {len(valid_submissions)}개 유효")
        return valid_submissions


def create_async_llm_orchestrator() -> AsyncLLMOrchestrator:
    """Create and return an async LLM orchestrator instance."""
    return AsyncLLMOrchestrator()
