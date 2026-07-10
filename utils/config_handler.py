from utils.path_tool import get_abs_path
import yaml


def load_config(config_path) -> dict:
    """
    Load the RAG configuration from a YAML file.

    Args:
        config_path (str): The path to the configuration YAML file.

    Returns:
        dict: The loaded configuration as a dictionary.
    """
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    
    return config


rag_config = load_config(get_abs_path("config/rag.yml"))
chroma_config = load_config(get_abs_path("config/chroma.yml"))
prompts_config = load_config(get_abs_path("config/prompts.yml"))

if __name__ == "__main__":
    # Example usage
    # print(rag_config)
    # print(chroma_config)
    print(prompts_config)