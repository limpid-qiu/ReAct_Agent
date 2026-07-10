import hashlib
import os
from utils.logger_handler import logger
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader,TextLoader,Docx2txtLoader


def get_file_md5_hex(filepath: str) -> str:
    """
    Calculate the MD5 hash of a file and return it as a hexadecimal string.

    Args:
        filepath (str): The path to the file.
    return: md5 hash of the file in hexadecimal format
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    if not os.path.isfile(filepath):
        raise ValueError(f"Path is not a file: {filepath}")
    
    md5 = hashlib.md5()
    chunk_size = 4096  # Read in chunks of 4KB
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                md5.update(chunk)
        return md5.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating MD5 for file {filepath}: {e}")
        return None

def listdir_with_allowed_types(directory: str, allowed_types: list[str]) -> list:
    """
    List files in a directory that match the allowed file types.

    Args:
        directory (str): The path to the directory.
        allowed_types (list): A list of allowed file extensions (e.g., ["txt", "pdf"]).

    Returns:
        list: A list of file paths that match the allowed types.
    """
    if not os.path.exists(directory):
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not os.path.isdir(directory):
        raise ValueError(f"Path is not a directory: {directory}")
    
    normalized_allowed_types = [
        ext.lower() if ext.startswith('.') else f".{ext.lower()}" for ext in allowed_types
    ]

    matched_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext.lower()) for ext in normalized_allowed_types):
                matched_files.append(os.path.join(root, file))
    
    return matched_files

def pdf_loader(file_path: str) -> list[Document]:
    """
    Load a PDF file and return its content as text.

    Args:
        file_path (str): The path to the PDF file.
    Returns:
        list[Document]: A list of Document objects containing the text content of the PDF.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    if not os.path.isfile(file_path):
        raise ValueError(f"Path is not a file: {file_path}")
    
    try:
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        return documents
    except Exception as e:
        logger.error(f"Error loading PDF file {file_path}: {e}")
        return []
    
def text_loader(file_path: str) -> list[Document]:
    """
    Load a text file and return its content as text.

    Args:
        file_path (str): The path to the text file.
    Returns:
        list[Document]: A list of Document objects containing the text content of the file.
    """
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    if not os.path.isfile(file_path):
        raise ValueError(f"Path is not a file: {file_path}")
    
    try:
        loader = TextLoader(file_path, encoding='utf-8')
        documents = loader.load()
        return documents
    except Exception as e:
        logger.error(f"Error loading text file {file_path}: {e}")
        return []
    
def docx_loader(file_path: str) -> list[Document]:
    """
    Load a DOCX file and return its content as text.

    Args:
        file_path (str): The path to the DOCX file.
    Returns:
        list[Document]: A list of Document objects containing the text content of the DOCX file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    if not os.path.isfile(file_path):
        raise ValueError(f"Path is not a file: {file_path}")
    
    try:
        loader = Docx2txtLoader(file_path)
        documents = loader.load()
        return documents
    except Exception as e:
        logger.error(f"Error loading DOCX file {file_path}: {e}")
        return []
    
if __name__ == "__main__":
    from utils.config_handler import chroma_config
    dir = chroma_config.get("data_path", "data")
    allowed_types = chroma_config.get("allow_knowledge_file_type", [])
    listed_files = listdir_with_allowed_types(dir, allowed_types)
    # print(listed_files)

    file = listed_files[0] if listed_files else None
    md5 = get_file_md5_hex(file)
    print(f"File: {file}, MD5: {md5}")
    if file.lower().endswith('.pdf'):
        docs = pdf_loader(file)
    elif file.lower().endswith('.txt'):
        docs = text_loader(file)
    elif file.lower().endswith('.docx'):
        docs = docx_loader(file)
    print(docs[0].page_content)