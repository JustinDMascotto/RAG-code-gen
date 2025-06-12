from pathlib import Path
from typing import Union, List, Optional


def read_files(paths: Union[str, List[str]], project_root: Optional[str] = None) -> str:
    """
    Given a list of file paths (or a single file path), returns a string that
    concatenates the contents of each file. Each file is prefixed with its path for clarity.

    Args:
        paths: A single file path or a list of file paths to read.
        project_root: Optional project root path. If provided, relative paths starting with './'
                     are resolved relative to this root. If not provided, uses current working directory.

    File paths starting with './' are resolved relative to the project root.
    Absolute paths and other relative paths are used as-is.

    Skips files that do not exist or cannot be read.
    """
    if isinstance(paths, str):
        file_paths = [paths]
    else:
        file_paths = paths

    output = []
    root_path = Path(project_root) if project_root else Path.cwd()

    for path_str in file_paths:
        # Resolve relative paths starting with './' to project root
        if path_str.startswith('./'):
            path = root_path / path_str[1:]  # Remove '.' prefix from './<file>'
        else:
            path = root_path /  Path(path_str)

        if not path.exists() or not path.is_file():
            output.append(f"# Skipping invalid file: {path_str}\n")
            continue
        try:
            content = path.read_text(encoding="utf-8")
            output.append(f"# File: {path_str}\n{content}\n")
        except Exception as e:
            output.append(f"# Error reading file {path_str}: {str(e)}\n")

    return "\n".join(output)


def write_file_to_path(filename: str, path: str, contents: str) -> bool:
    """
    Write contents to a file at the specified path.

    Args:
        filename: The name of the file to write.
        path: The directory path where the file should be written.
        contents: The content to write to the file.

    Returns:
        bool: True if the file was written successfully, False otherwise.
    """
    try:
        # Create Path objects
        dir_path = Path(path)
        file_path = dir_path / filename
        
        # Create parent directories if they don't exist
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # Write the content to the file
        file_path.write_text(contents, encoding="utf-8")
        
        return True
        
    except Exception as e:
        print(f"Error writing file {filename} to {path}: {str(e)}")
        return False