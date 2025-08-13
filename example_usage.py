"""
Example usage of the modular Groq client.
This file demonstrates various ways to use the groq_client module.
"""

import asyncio
from groq_client import (
    GroqClient, 
    GroqConfig, 
    create_groq_client, 
    quick_chat, 
    quick_chat_stream
)


def example_basic_usage():
    """Example of basic usage with default configuration."""
    print("=== Basic Usage Example ===")
    
    # Create a client with default settings
    client = GroqClient()
    
    # Send a simple message
    messages = [{"role": "user", "content": "Hello! What's the weather like today?"}]
    response = client.chat(messages)
    print(f"Response: {response}\n")


def example_custom_config():
    """Example with custom configuration."""
    print("=== Custom Configuration Example ===")
    
    # Create custom configuration
    config = GroqConfig(
        model="openai/gpt-oss-120b",
        temperature=0.7,
        max_completion_tokens=1024,
        reasoning_effort="high"
    )
    
    # Create client with custom config
    client = GroqClient(config)
    
    messages = [{"role": "user", "content": "Explain quantum computing in simple terms."}]
    response = client.chat(messages)
    print(f"Response: {response}\n")


def example_streaming():
    """Example of streaming responses."""
    print("=== Streaming Example ===")
    
    client = GroqClient()
    messages = [{"role": "user", "content": "Write a short story about a robot learning to paint."}]
    
    print("Streaming response:")
    response = client.chat_stream(messages)
    print(f"\nFull response length: {len(response)} characters\n")


def example_conversation():
    """Example of a multi-turn conversation."""
    print("=== Conversation Example ===")
    
    client = GroqClient()
    conversation = [
        {"role": "user", "content": "Hi! I'm learning Python. Can you help me?"},
    ]
    
    # First response
    response = client.chat(conversation)
    print(f"Assistant: {response}")
    
    # Add assistant's response to conversation
    conversation.append({"role": "assistant", "content": response})
    conversation.append({"role": "user", "content": "What's the best way to start with Python?"})
    
    # Second response
    response = client.chat(conversation)
    print(f"Assistant: {response}\n")


def example_quick_functions():
    """Example using the quick convenience functions."""
    print("=== Quick Functions Example ===")
    
    # Quick chat (non-streaming)
    response = quick_chat("What are the benefits of modular code?")
    print(f"Quick response: {response}\n")
    
    # Quick streaming chat
    print("Quick streaming response:")
    response = quick_chat_stream("Write a haiku about programming.")
    print(f"\nQuick streaming response length: {len(response)} characters\n")


async def example_async_usage():
    """Example of async usage."""
    print("=== Async Usage Example ===")
    
    client = GroqClient()
    messages = [{"role": "user", "content": "What's the capital of France?"}]
    
    # Async non-streaming
    response = await client.chat_async(messages)
    print(f"Async response: {response}")
    
    # Async streaming
    print("Async streaming response:")
    async for chunk in client.chat_stream_async(messages):
        print(chunk, end="", flush=True)
    print("\n")


def example_error_handling():
    """Example of error handling."""
    print("=== Error Handling Example ===")
    
    try:
        # This will fail if GROQ_API_KEY is not set
        client = GroqClient()
        messages = [{"role": "user", "content": "Test message"}]
        response = client.chat(messages)
        print(f"Success: {response}")
    except Exception as e:
        print(f"Error caught: {e}\n")


if __name__ == "__main__":
    # Run synchronous examples
    example_basic_usage()
    example_custom_config()
    example_streaming()
    example_conversation()
    example_quick_functions()
    example_error_handling()
    
    # Run async example
    print("Running async example...")
    asyncio.run(example_async_usage())
