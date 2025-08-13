"""
Modular Groq client for LLM interactions.
This module provides a clean interface for chatting with Groq's LLM models.
"""

import os
from typing import List, Dict, Any, Optional, Union, AsyncGenerator
from groq import Groq, AsyncGroq
from groq.types.chat import ChatCompletionChunk
import asyncio


class GroqConfig:
    """Configuration class for Groq client settings."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "openai/gpt-oss-120b",
        temperature: float = 1.0,
        max_completion_tokens: int = 8192,
        top_p: float = 1.0,
        reasoning_effort: str = "medium",
        stream: bool = True,
        stop: Optional[Union[str, List[str]]] = None
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable must be set or provided")
        
        self.model = model
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens
        self.top_p = top_p
        self.reasoning_effort = reasoning_effort
        self.stream = stream
        self.stop = stop


class GroqClient:
    """Main Groq client class for LLM interactions."""
    
    def __init__(self, config: Optional[GroqConfig] = None):
        """Initialize the Groq client with configuration."""
        self.config = config or GroqConfig()
        self.client = Groq(api_key=self.config.api_key)
        self.async_client = AsyncGroq(api_key=self.config.api_key)
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        config: Optional[GroqConfig] = None
    ) -> str:
        """
        Send a chat completion request (non-streaming).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            config: Optional configuration override
            
        Returns:
            The complete response as a string
        """
        config = config or self.config
        
        try:
            completion = self.client.chat.completions.create(
                model=config.model,
                messages=messages,
                temperature=config.temperature,
                max_completion_tokens=config.max_completion_tokens,
                top_p=config.top_p,
                reasoning_effort=config.reasoning_effort,
                stream=False,
                stop=config.stop
            )
            return completion.choices[0].message.content
        except Exception as e:
            raise Exception(f"Groq chat completion failed: {str(e)}")
    
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        config: Optional[GroqConfig] = None
    ) -> str:
        """
        Send a streaming chat completion request.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            config: Optional configuration override
            
        Returns:
            The complete response as a string
        """
        config = config or self.config
        
        try:
            completion = self.client.chat.completions.create(
                model=config.model,
                messages=messages,
                temperature=config.temperature,
                max_completion_tokens=config.max_completion_tokens,
                top_p=config.top_p,
                reasoning_effort=config.reasoning_effort,
                stream=True,
                stop=config.stop
            )
            
            full_response = ""
            for chunk in completion:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    print(content, end="", flush=True)
            
            print()  # New line after streaming
            return full_response
        except Exception as e:
            raise Exception(f"Groq streaming chat completion failed: {str(e)}")
    
    async def chat_async(
        self,
        messages: List[Dict[str, str]],
        config: Optional[GroqConfig] = None
    ) -> str:
        """
        Send an async chat completion request (non-streaming).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            config: Optional configuration override
            
        Returns:
            The complete response as a string
        """
        config = config or self.config
        
        try:
            completion = await self.async_client.chat.completions.create(
                model=config.model,
                messages=messages,
                temperature=config.temperature,
                max_completion_tokens=config.max_completion_tokens,
                top_p=config.top_p,
                reasoning_effort=config.reasoning_effort,
                stream=False,
                stop=config.stop
            )
            return completion.choices[0].message.content
        except Exception as e:
            raise Exception(f"Groq async chat completion failed: {str(e)}")
    
    async def chat_stream_async(
        self,
        messages: List[Dict[str, str]],
        config: Optional[GroqConfig] = None
    ) -> AsyncGenerator[str, None]:
        """
        Send an async streaming chat completion request.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            config: Optional configuration override
            
        Yields:
            Response chunks as strings
        """
        config = config or self.config
        
        try:
            completion = await self.async_client.chat.completions.create(
                model=config.model,
                messages=messages,
                temperature=config.temperature,
                max_completion_tokens=config.max_completion_tokens,
                top_p=config.top_p,
                reasoning_effort=config.reasoning_effort,
                stream=True,
                stop=config.stop
            )
            
            async for chunk in completion:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            raise Exception(f"Groq async streaming chat completion failed: {str(e)}")


# Convenience functions for quick usage
def create_groq_client(api_key: Optional[str] = None, **kwargs) -> GroqClient:
    """Create a GroqClient instance with custom configuration."""
    config = GroqConfig(api_key=api_key, **kwargs)
    return GroqClient(config)


def quick_chat(
    message: str,
    api_key: Optional[str] = None,
    model: str = "openai/gpt-oss-120b",
    **kwargs
) -> str:
    """
    Quick chat function for simple single-message interactions.
    
    Args:
        message: The user message to send
        api_key: Optional API key override
        model: Model to use
        **kwargs: Additional configuration options
        
    Returns:
        The LLM response as a string
    """
    client = create_groq_client(api_key=api_key, model=model, **kwargs)
    messages = [{"role": "user", "content": message}]
    return client.chat(messages)


def quick_chat_stream(
    message: str,
    api_key: Optional[str] = None,
    model: str = "openai/gpt-oss-120b",
    **kwargs
) -> str:
    """
    Quick streaming chat function for simple single-message interactions.
    
    Args:
        message: The user message to send
        api_key: Optional API key override
        model: Model to use
        **kwargs: Additional configuration options
        
    Returns:
        The complete LLM response as a string (prints chunks as they arrive)
    """
    client = create_groq_client(api_key=api_key, model=model, **kwargs)
    messages = [{"role": "user", "content": message}]
    return client.chat_stream(messages)
