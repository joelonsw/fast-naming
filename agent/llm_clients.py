"""
Shared LLM client utilities for the agent pipeline.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)

HF_DEFAULT_PRIMARY_MODEL = "Qwen/Qwen2.5-72B-Instruct"
HF_DEFAULT_FALLBACK_MODELS = [
    "meta-llama/Llama-3.3-70B-Instruct",
]


def _parse_csv_env(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def get_huggingface_api_key() -> Optional[str]:
    return os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN")


def get_huggingface_primary_model() -> str:
    return os.getenv("HF_NAMING_MODEL", HF_DEFAULT_PRIMARY_MODEL).strip()


def get_huggingface_fallback_models() -> List[str]:
    configured = _parse_csv_env(os.getenv("HF_NAMING_FALLBACK_MODELS"))
    return configured or HF_DEFAULT_FALLBACK_MODELS.copy()


def get_huggingface_provider() -> str:
    return os.getenv("HF_PROVIDER", "auto").strip() or "auto"


def get_configured_provider_names() -> List[str]:
    providers = []

    if get_huggingface_api_key():
        providers.append("huggingface")
    if os.getenv("GROQ_API_KEY"):
        providers.append("groq")
    if os.getenv("GEMINI_API_KEY"):
        providers.append("gemini")
    if os.getenv("AI_GITHUB_TOKEN"):
        providers.append("github")

    return providers


def get_rate_limit_delay(provider_name: str) -> int:
    return {
        "gemini": 10,
        "groq": 2,
        "github": 10,
        "huggingface": 1,
    }.get(provider_name, 1)


class LLMClient(ABC):
    """Shared async chat interface."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        pass


class GeminiClient(LLMClient):
    _circuit_broken = False  # 클래스 레벨 회로 차단기 플래그

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash", temperature: float = 0.9):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._model_name = model
        self.client = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=self.api_key,
            temperature=temperature,
            max_retries=1,  # SDK 내부 재시도를 1회로 차단하여 지연 시간 누적 방지
        )

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        import asyncio
        
        # 회로가 이미 차단되어 있다면 Gemini를 아예 건너뛰고 바로 Fallback 실행
        if GeminiClient._circuit_broken:
            logger.info("⚡ [Gemini 회로 차단] 429 쿼타 고갈 상태이므로 즉시 Fallback 우회합니다.")
            return await self._fallback_generate(system_prompt, user_prompt)

        retries = [2, 8]  # 대기 시간 초 (최대 2회 재시도)
        
        for attempt, delay in enumerate(retries, 1):
            try:
                response = await self.client.ainvoke(
                    [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=user_prompt),
                    ]
                )
                return response.content
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    logger.warning(
                        "⚠️ [Gemini 429 Quota 초과] %d차 재시도 대기 (%d초)... (에러: %s)",
                        attempt,
                        delay,
                        err_str[:60]
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
        
        # 2회 재시도를 모두 실패한 경우 Fallback 기동 및 회로 차단
        result = await self._fallback_generate(system_prompt, user_prompt)
        GeminiClient._circuit_broken = True  # 다음 호출부터 즉시 우회하도록 차단 설정
        return result

    async def _fallback_generate(self, system_prompt: str, user_prompt: str) -> str:
        logger.warning("🚨 [Gemini 429 임계 초과] Fallback 모델로 즉시 우회 호출합니다.")
        
        # 1순위 Fallback: GitHub AI (gpt-4o-mini)
        if os.getenv("AI_GITHUB_TOKEN"):
            try:
                logger.info("👉 Fallback 1순위 기동: GitHub AI (gpt-4o-mini)")
                fallback_client = GitHubAIClient(model="gpt-4o-mini", temperature=0.9)
                return await fallback_client.generate(system_prompt, user_prompt)
            except Exception as e:
                logger.error("🚨 Fallback 1순위 (gpt-4o-mini) 호출 실패: %s", e)
        
        # 2순위 Fallback: Hugging Face Router (Qwen2.5-72B-Instruct)
        if get_huggingface_api_key() and not HuggingFaceClient._disabled:
            try:
                logger.info("👉 Fallback 2순위 기동: Hugging Face (Qwen/Qwen2.5-72B-Instruct)")
                fallback_client = HuggingFaceClient(model="Qwen/Qwen2.5-72B-Instruct", temperature=0.8)
                return await fallback_client.generate(system_prompt, user_prompt)
            except Exception as e:
                logger.error("🚨 Fallback 2순위 (Qwen2.5-72B) 호출 실패: %s", e)
                
        raise RuntimeError("Gemini 429 초과로 인한 모든 Fallback 모델 우회 호출도 실패하였거나 활성 API 키가 없습니다.")


class GroqClient(LLMClient):
    def __init__(self, api_key: Optional[str] = None, model: str = "openai/gpt-oss-120b", temperature: float = 0.9):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self._model_name = model
        self.client = ChatGroq(
            model=model,
            api_key=self.api_key,
            temperature=temperature,
        )

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = await self.client.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        return response.content


class GitHubAIClient(LLMClient):
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini", temperature: float = 0.9):
        self.api_key = api_key or os.getenv("AI_GITHUB_TOKEN")
        self._model_name = model
        self.temperature = temperature
        self.endpoint = "https://models.github.ai/inference/chat/completions"

    @property
    def provider_name(self) -> str:
        return "github"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.endpoint, headers=headers, json=payload)
            if response.status_code == 429:
                raise Exception("Rate limit exceeded (429) - skipping")
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


class HuggingFaceClient(LLMClient):
    """OpenAI-compatible Hugging Face router client with model fallback."""
    _disabled = False  # 클래스 레벨 비활성화 플래그 (402, 401, 403 등 빌링/인증 오류 대응)

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        provider: Optional[str] = None,
        temperature: float = 0.8,
        max_tokens: int = 2048,
    ):
        self.api_key = api_key or get_huggingface_api_key()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.provider = provider or get_huggingface_provider()
        primary_model = model or get_huggingface_primary_model()
        fallbacks = fallback_models or get_huggingface_fallback_models()

        unique_candidates: List[str] = []
        for candidate in [primary_model, *fallbacks]:
            if candidate and candidate not in unique_candidates:
                unique_candidates.append(candidate)

        self.model_candidates = unique_candidates
        self._model_name = unique_candidates[0]
        self.endpoint = "https://router.huggingface.co/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return "huggingface"

    @property
    def model_name(self) -> str:
        return self._model_name

    def _compose_model_name(self, model_name: str) -> str:
        if self.provider in ("", "auto", None):
            return model_name
        if ":" in model_name:
            return model_name
        return f"{model_name}:{self.provider}"

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if HuggingFaceClient._disabled:
            logger.info("⚡ [Hugging Face 비활성화] 빌링/인증 오류 상태이므로 즉시 Fallback 우회합니다.")
            return await self._fallback_generate(system_prompt, user_prompt)

        if not self.api_key:
            raise ValueError("HUGGINGFACE_API_KEY 또는 HF_TOKEN이 필요합니다")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=90.0) as client:
            for candidate in self.model_candidates:
                payload = {
                    "model": self._compose_model_name(candidate),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                }

                try:
                    response = await client.post(self.endpoint, headers=headers, json=payload)

                    if response.status_code in (401, 402, 403):
                        logger.error(
                            "🚨 Hugging Face 인증/빌링 에러 발생 (%d): %s", 
                            response.status_code, 
                            response.text
                        )
                        HuggingFaceClient._disabled = True
                        return await self._fallback_generate(system_prompt, user_prompt)

                    if response.status_code in (429, 500, 502, 503, 504):
                        raise httpx.HTTPStatusError(
                            f"Hugging Face temporary error ({response.status_code})",
                            request=response.request,
                            response=response,
                        )

                    response.raise_for_status()
                    data = response.json()
                    self._model_name = candidate
                    return data["choices"][0]["message"]["content"]
                except Exception as e:
                    err_str = str(e)
                    if "401" in err_str or "402" in err_str or "403" in err_str:
                        logger.error("🚨 Hugging Face 인증/빌링 에러 감지: %s", err_str)
                        HuggingFaceClient._disabled = True
                        return await self._fallback_generate(system_prompt, user_prompt)

                    last_error = e
                    logger.warning(
                        "Hugging Face model failed, trying next candidate: %s (%s)",
                        candidate,
                        e,
                    )

        # 모든 후보 실패 시 Fallback 호출 및 비활성화
        HuggingFaceClient._disabled = True
        return await self._fallback_generate(system_prompt, user_prompt)

    async def _fallback_generate(self, system_prompt: str, user_prompt: str) -> str:
        logger.warning("🚨 [Hugging Face 임계 초과] Fallback 모델로 즉시 우회 호출합니다.")
        
        # 1순위 Fallback: GitHub AI (gpt-4o-mini)
        if os.getenv("AI_GITHUB_TOKEN"):
            try:
                logger.info("👉 Fallback 1순위 기동: GitHub AI (gpt-4o-mini)")
                fallback_client = GitHubAIClient(model="gpt-4o-mini", temperature=self.temperature)
                return await fallback_client.generate(system_prompt, user_prompt)
            except Exception as e:
                logger.error("🚨 Fallback 1순위 (gpt-4o-mini) 호출 실패: %s", e)
        
        # 2순위 Fallback: Gemini (gemini-2.5-flash)
        if os.getenv("GEMINI_API_KEY") and not GeminiClient._circuit_broken:
            try:
                logger.info("👉 Fallback 2순위 기동: Gemini (gemini-2.5-flash)")
                fallback_client = GeminiClient(model="gemini-2.5-flash", temperature=self.temperature)
                return await fallback_client.generate(system_prompt, user_prompt)
            except Exception as e:
                logger.error("🚨 Fallback 2순위 (Gemini) 호출 실패: %s", e)
                
        # 3순위 Fallback: Groq (openai/gpt-oss-120b)
        if os.getenv("GROQ_API_KEY"):
            try:
                logger.info("👉 Fallback 3순위 기동: Groq (openai/gpt-oss-120b)")
                fallback_client = GroqClient(model="openai/gpt-oss-120b", temperature=self.temperature)
                return await fallback_client.generate(system_prompt, user_prompt)
            except Exception as e:
                logger.error("🚨 Fallback 3순위 (Groq) 호출 실패: %s", e)
                
        raise RuntimeError("Hugging Face 에러로 인한 모든 Fallback 모델 우회 호출도 실패하였거나 활성 API 키가 없습니다.")


def create_generation_clients() -> List[LLMClient]:
    clients: List[LLMClient] = []

    if get_huggingface_api_key():
        try:
            clients.append(HuggingFaceClient())
            logger.info("✅ Hugging Face 클라이언트 초기화 성공 (%s)", get_huggingface_primary_model())
        except Exception as e:
            logger.error("❌ Hugging Face 클라이언트 초기화 실패: %s", e)

    if os.getenv("GEMINI_API_KEY"):
        try:
            clients.append(GeminiClient())
            logger.info("✅ Gemini 클라이언트 초기화 성공")
        except Exception as e:
            logger.error("❌ Gemini 클라이언트 초기화 실패: %s", e)

    if os.getenv("GROQ_API_KEY"):
        for model in ("openai/gpt-oss-120b", "llama-3.3-70b-versatile"):
            try:
                clients.append(GroqClient(model=model))
                logger.info("✅ Groq 클라이언트 초기화 성공 (%s)", model)
            except Exception as e:
                logger.error("❌ Groq 클라이언트 초기화 실패 (%s): %s", model, e)

    if os.getenv("AI_GITHUB_TOKEN"):
        try:
            clients.append(GitHubAIClient(model="gpt-4o-mini"))
            logger.info("✅ GitHub AI 클라이언트 초기화 성공 (gpt-4o-mini)")
        except Exception as e:
            logger.error("❌ GitHub AI 클라이언트 초기화 실패: %s", e)

    return clients


def create_primary_client(temperature: float = 0.3, max_tokens: int = 2048) -> Optional[LLMClient]:
    if get_huggingface_api_key():
        return HuggingFaceClient(temperature=temperature, max_tokens=max_tokens)

    if os.getenv("GROQ_API_KEY"):
        return GroqClient(model="openai/gpt-oss-120b", temperature=temperature)

    if os.getenv("GEMINI_API_KEY"):
        return GeminiClient(model="gemini-2.5-flash", temperature=temperature)

    if os.getenv("AI_GITHUB_TOKEN"):
        return GitHubAIClient(model="gpt-4o-mini", temperature=temperature)

    return None
