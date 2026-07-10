import os


def get_project_root() -> str:
    """
    Get the root directory of the project.

    Returns:
        str: The absolute path to the project root directory.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return project_root

def get_abs_path(relative_path: str) -> str:
    """
    Get the absolute path of a file or directory given its relative path from the project root.

    Args:
        relative_path (str): The relative path from the project root.

    Returns:
        str: The absolute path to the specified file or directory.
    """
    project_root = get_project_root()
    abs_path = os.path.join(project_root, relative_path)
    return abs_path