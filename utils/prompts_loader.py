from utils.logger_handler import logger
from utils.config_handler import prompts_config

def load_prompt(prompt_path: str) -> str:
    """
    Load a prompt from a text file.

    Args:
        prompt_path (str): The path to the prompt text file.
    Returns:
        str: The content of the prompt as a string.
    """
    try:
        with open(prompt_path, 'r', encoding='utf-8') as file:
            prompt = file.read()
        return prompt
    except Exception as e:
        logger.error(f"Error loading prompt file {prompt_path}: {e}")
        return ""
    
system_prompt =load_prompt(prompts_config.get("main_prompt_path", "prompts/main_prompt.txt"))
rag_prompt = load_prompt(prompts_config.get("rag_summarize_prompt_path", "prompts/rag_summarize.txt"))
report_prompt = load_prompt(prompts_config.get("report_prompt_path", "prompts/report_prompt.txt"))
