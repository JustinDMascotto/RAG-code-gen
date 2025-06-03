"""LLM management and retry logic for the RAG system."""

import time
from typing import Any, Dict
from langchain_anthropic import ChatAnthropic


def estimate_tokens(text: str) -> int:
    """Rough estimate of tokens (1 token ≈ 4 characters for English)."""
    return len(text) // 4


def invoke_llm_with_retry(chain, input_data: Dict[str, Any], max_retries: int = 3, base_delay: int = 2):
    """Invoke LLM with exponential backoff retry logic and token monitoring."""
    
    # Estimate total input size
    input_str = str(input_data)
    estimated_tokens = estimate_tokens(input_str)
    
    if estimated_tokens > 8000:  # Conservative limit
        print(f"⚠️  Large input detected (~{estimated_tokens} tokens). This might cause issues.")
    
    for attempt in range(max_retries):
        try:
            return chain.invoke(input_data)
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check if it's a retryable error
            if any(keyword in error_msg for keyword in ['overloaded', '529', 'rate limit', 'timeout', 'connection', 'token']):
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    print(f"⏳ Claude API issue (attempt {attempt + 1}/{max_retries})")
                    print(f"   Error: {str(e)[:100]}...")
                    print(f"   Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"❌ Claude API still unavailable after {max_retries} attempts")
                    print(f"   Error: {e}")
                    print(f"   Try reducing context size or check your API key")
                    raise
            else:
                # Non-retryable error, raise immediately
                raise
    
    return None


class LLMManager:
    """Manages LLM instances and provides retry functionality."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize LLM manager with configuration."""
        self.config = config
        self.llm = ChatAnthropic(
            model=config["llm"]["model"],
            temperature=config["llm"]["temperature"],
            api_key=config["llm"]["api_key"],
            max_tokens=config["llm"]["max_tokens"],
        )
    
    def invoke_with_retry(self, chain, input_data: Dict[str, Any], max_retries: int = 3) -> Any:
        """Invoke a chain with retry logic."""
        return invoke_llm_with_retry(chain, input_data, max_retries)
    
    def get_llm(self) -> ChatAnthropic:
        """Get the LLM instance."""
        return self.llm