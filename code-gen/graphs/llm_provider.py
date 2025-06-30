from graphs.config_provider import get_config
from utilities.llm_manager import LLMManager

config = get_config()
llmManager = LLMManager(config)

def get_llm_manager():
    return llmManager