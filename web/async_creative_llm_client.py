
"""
Async Creative LLM Clients
This module extends the async LLM clients by incorporating diverse creative strategies
for generating a wider spectrum of naming and slogan submissions.
"""

import os
import json
import random
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable

# Import base classes and clients from the original module
from async_llm_client import AsyncLLMClient, AsyncGroqClient, AsyncGitHubAIClient, AsyncGeminiClient, AsyncTogetherClient, AsyncAnthropicClient

logger = logging.getLogger(__name__)

# --- Creative Strategies Definition ---

def strategy_keyword_combination(prompt: str, contest_data: Dict[str, Any]) -> str:
    """전략: 주최사의 이름, 가치, 서비스 등 핵심 키워드를 조합합니다."""
    injection = f"""
    **전략: 핵심 키워드 조합**
    - 주최사 '{contest_data['contestHeldBy']}'의 핵심 정체성과 가치에 집중하세요.
    - 공모전 설명에서 가장 중요한 핵심 단어(키워드)들을 몇 가지 추출하세요.
    - 추출한 키워드들을 창의적으로 결합하여, 새롭고 의미 있는 슬로건이나 이름을 만드세요.
    """
    return f"{injection}\n\n{prompt}"

def strategy_metaphor_analogy(prompt: str, contest_data: Dict[str, Any]) -> str:
    """전략: 감성적 호소를 위해 은유와 비유를 사용합니다."""
    injection = f"""
    **전략: 은유와 비유**
    - 이 공모전의 주제가 무엇과 비슷한지 생각해보세요. 세상을 밝히는 '등대' 인가요? 새로운 시작을 돕는 '도약대' 인가요? 무한한 가능성을 담은 '캔버스' 인가요?
    - 이러한 은유적 상징을 활용하여, 듣는 이의 감성과 상상력을 자극하는 인상적인 슬로건을 만드세요.
    - 직접적으로 설명하기보다, 상징을 통해 메시지를 전달하는 것이 중요합니다.
    """
    return f"{injection}\n\n{prompt}"

def strategy_benefit_oriented(prompt: str, contest_data: Dict[str, Any]) -> str:
    """전략: 최종 사용자가 얻게 될 혜택과 가치에 집중합니다."""
    injection = f"""
    **전략: 혜택 중심 접근**
    - 사용자가 궁극적으로 얻게 될 가치나 혜택이 무엇인지에만 집중하세요. '이 서비스를 통해 어떤 문제를 해결할 수 있는가?', '어떤 즐거움이나 편리함을 얻는가?'를 자문해보세요.
    - 슬로건만 들어도 이러한 긍정적인 결과가 직관적으로 떠오를 수 있도록 만드세요.
    - 철저히 고객의 입장에서, 고객이 듣고 싶어 하는 말을 들려주는 것이 핵심입니다.
    """
    return f"{injection}\n\n{prompt}"

def strategy_wordplay_wit(prompt: str, contest_data: Dict[str, Any]) -> str:
    """전략: 기억에 남도록 언어유희, 중의적 표현, 재치 있는 문구를 사용합니다."""
    injection = f"""
    **전략: 언어유희와 재치**
    - 사람들이 '아!'하고 무릎을 칠 만한 재치 있는 말장난, 여러 의미로 해석될 수 있는 중의적 표현, 기발한 줄임말 등을 활용하세요.
    - 단순히 웃음을 주는 것을 넘어, 서비스의 특징과 연결되어 듣는 이의 기억에 오래 남도록 만드는 것이 목표입니다.
    - 독창성과 한 번 들으면 잊히지 않는 매력이 중요합니다.
    """
    return f"{injection}\n\n{prompt}"

def strategy_future_vision(prompt: str, contest_data: Dict[str, Any]) -> str:
    """전략: 미래 지향적이고 혁신적인 느낌을 전달합니다."""
    injection = f"""
    **전략: 미래 비전 제시**
    - 주최사 '{contest_data['contestHeldBy']}'가 이 서비스를 통해 만들고자 하는 이상적인 미래의 모습을 상상해보세요.
    - '혁신', '발전', '새로운 시대', '도약' 등 미래 지향적인 느낌을 주는 단어들을 사용하여 슬로건을 구성하세요.
    - 듣는 이에게 원대하고 비전 있는 포부를 느끼게 하여, 기대감을 심어주어야 합니다.
    """
    return f"{injection}\n\n{prompt}"

def strategy_simple_direct(prompt: str, contest_data: Dict[str, Any]) -> str:
    """전략: 군더더기 없이 단순하고 명확하게 핵심을 전달합니다."""
    injection = f"""
    **전략: 단순함과 직관성**
    - 모든 전문 용어나 불필요한 수식어를 완전히 제거하고, 가장 본질적인 단 하나의 메시지에만 집중하세요.
    - 누구나 쉽게 말하고, 쓰고, 기억할 수 있어야 합니다.
    - 짧고 간결할수록 강력합니다. 명확성이 이 전략의 핵심입니다.
    """
    return f"{injection}\n\n{prompt}"


CREATIVE_STRATEGIES: List[Dict[str, Any]] = [
    {"name": "Keyword Combination", "modifier": strategy_keyword_combination},
    {"name": "Metaphor & Analogy", "modifier": strategy_metaphor_analogy},
    {"name": "Benefit-Oriented", "modifier": strategy_benefit_oriented},
    {"name": "Wordplay & Wit", "modifier": strategy_wordplay_wit},
    {"name": "Future Vision", "modifier": strategy_future_vision},
    {"name": "Simple & Direct", "modifier": strategy_simple_direct},
]


class AsyncCreativeLLMOrchestrator:
    """
    Orchestrator for managing multiple async LLM clients and generating contest submissions
    using a variety of creative strategies.
    """

    def __init__(self):
        logger.info("🔧 AsyncCreativeLLMOrchestrator 초기화 시작")
        self.clients = {}
        self._initialize_clients()
        logger.info("✅ AsyncCreativeLLMOrchestrator 초기화 완료")

    def _initialize_clients(self):
        """Initialize available async LLM clients."""
        logger.info("🔧 Async LLM 클라이언트 초기화 시작")
        # This part is identical to the original orchestrator
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

        try:
            self.clients["anthropic"] = {
                "client": AsyncAnthropicClient(),
                "models": ["claude-sonnet-4-20250514"]
            }
            logger.info("✅ Anthropic 클라이언트 초기화 성공")
        except Exception as e:
            logger.error(f"❌ Anthropic 클라이언트 초기화 실패: {e}")

        logger.info(f"📊 초기화된 클라이언트: {list(self.clients.keys())}")


    async def generate_submissions(
        self,
        contest_data: Dict[str, Any],
        successful_examples: List[Dict[str, str]],
        num_iterations: int = 1 # Reduced iterations as we multiply by strategies
    ) -> List[Dict[str, Any]]:
        """Generate contest submissions using multiple strategies, providers, and models."""
        logger.info("🎯 Creative Async LLM 작명 생성 시작")
        logger.info(f"📊 설정: {len(self.clients)}개 제공자, {len(CREATIVE_STRATEGIES)}개 전략, {num_iterations}회 반복")

        tasks = []
        ## FIX 1 ##: Corrected the default temperature list to be within the valid 0.0-1.0 range.
        temperature_variations = [0.8, 0.9, 0.95, 1.0] 
        claude_temperature_variations = [0.7, 0.8, 0.9, 0.95, 1.0] 

        # Iterate through strategies in addition to providers and models
        for strategy in CREATIVE_STRATEGIES:
            for provider_name, provider_info in self.clients.items():
                client = provider_info["client"]
                models = provider_info["models"]
                for model in models:
                    for i in range(num_iterations):
                        ## FIX 2 ##: Conditionally choose the temperature list based on the provider.
                        if provider_name == "anthropic":
                            temperature = random.choice(claude_temperature_variations)
                        else:
                            temperature = random.choice(temperature_variations)
                        
                        top_p = 0.99999
                        task = self._generate_single_submission(
                            client=client,
                            provider_name=provider_name,
                            model=model,
                            iteration=i,
                            temperature=temperature,
                            top_p=top_p,
                            contest_data=contest_data,
                            successful_examples=successful_examples,
                            strategy=strategy
                        )
                        tasks.append(task)

        results = await asyncio.gather(*tasks)
        all_submissions = [item for sublist in results for item in sublist]

        logger.info(f"🎉 Creative Async LLM 작명 생성 완료! 총 작명: {len(all_submissions)}개")
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
        successful_examples: List[Dict[str, str]],
        strategy: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate a single submission asynchronously using a specific creative strategy."""
        strategy_name = strategy['name']
        strategy_modifier = strategy['modifier']
        try:
            logger.info(f"🔄 {provider_name}/{model} - 전략: {strategy_name} (temp={temperature})")

            system_prompt = self._create_system_prompt(contest_data)
            # Create the base user prompt
            base_user_prompt = self._create_user_prompt(contest_data, successful_examples)
            # Apply the creative strategy to the prompt
            creative_user_prompt = strategy_modifier(base_user_prompt, contest_data)

            response = await client.generate(
                system_prompt=system_prompt,
                user_prompt=creative_user_prompt,
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
                    "iteration": iteration + 1,
                    "strategy": strategy_name  # Add strategy metadata
                })
            
            logger.info(f"✅ {provider_name}/{model} - 전략: {strategy_name} 성공: {len(valid_submissions)}개 작명 생성")
            return valid_submissions

        except Exception as e:
            logger.error(f"❌ {provider_name}/{model} - 전략: {strategy_name} 실패: {e}")
            return []

    def _create_system_prompt(self, contest_data: Dict[str, Any]) -> str:
        # Identical to original
        return '''당신은 대한민국 최고의 네이미스트입니다.
당신은 주최측이 원하는 네이밍을 무조건 제공하는 네이미스트입니다.
반드시 JSON 형식으로만 응답해야 합니다.'''

    def _create_user_prompt(self, contest_data: Dict[str, Any], successful_examples: List[Dict[str, str]]) -> str:
        # Identical to original, creates the base prompt before strategy modification
        selected_examples = random.sample(successful_examples, min(2, len(successful_examples)))

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
        # This part is identical to the original orchestrator
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
        # This part is identical to the original orchestrator
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
        # This part is identical to the original orchestrator
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

    async def generate_from_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        num_iterations: int = 3 # Fewer iterations for focused refinement
    ) -> List[Dict[str, Any]]:
        """Generates submissions from a direct system and user prompt."""
        logger.info("🎯 Creative Async LLM generation from prompt 시작")
        tasks = []
        ## FIX 3 ##: Corrected this list to be within the valid 0.0-1.0 range.
        temperature_variations = [0.8, 0.9, 1.0]
        claude_temperature_variations = [0.7, 0.85, 1.0] # Added a separate valid list for Claude

        # For refinement, we might not need all strategies, but we can still use the multi-model approach
        for provider_name, provider_info in self.clients.items():
            client = provider_info["client"]
            models = provider_info["models"]
            for model in models:
                for i in range(num_iterations):
                    ## FIX 4 ##: Conditionally choose temperature for the provider.
                    if provider_name == "anthropic":
                        temperature = claude_temperature_variations[i % len(claude_temperature_variations)]
                    else:
                        temperature = temperature_variations[i % len(temperature_variations)]

                    top_p = 0.99999
                    task = self._generate_single_submission_from_prompt(
                        client=client,
                        provider_name=provider_name,
                        model=model,
                        iteration=i,
                        temperature=temperature,
                        top_p=top_p,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt
                    )
                    tasks.append(task)

        results = await asyncio.gather(*tasks)
        all_submissions = [item for sublist in results for item in sublist]

        logger.info(f"🎉 Creative Async LLM generation from prompt 완료! 총 작명: {len(all_submissions)}개")
        return all_submissions

    async def _generate_single_submission_from_prompt(
        self,
        client: AsyncLLMClient,
        provider_name: str,
        model: str,
        iteration: int,
        temperature: float,
        top_p: float,
        system_prompt: str,
        user_prompt: str
    ) -> List[Dict[str, Any]]:
        """Helper to generate a single submission from a direct prompt."""
        try:
            logger.info(f"🔄 {provider_name}/{model} - 반복 {iteration+1} (temp={temperature}, top_p={top_p})")

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
                    "iteration": iteration + 1,
                    "strategy": "refinement"  # Mark as a refinement task
                })
            
            logger.info(f"✅ {provider_name}/{model} - 반복 {iteration+1} 성공: {len(valid_submissions)}개 작명 생성")
            return valid_submissions

        except Exception as e:
            logger.error(f"❌ {provider_name}/{model} - 반복 {iteration+1} 실패: {e}")
            return []


def create_async_creative_llm_orchestrator() -> AsyncCreativeLLMOrchestrator:
    """Create and return an async creative LLM orchestrator instance."""
    return AsyncCreativeLLMOrchestrator()
