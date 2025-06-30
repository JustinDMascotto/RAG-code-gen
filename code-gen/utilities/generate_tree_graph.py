import os
import fnmatch

def read_gitignore_patterns(root_path: str) -> list:
    """Read patterns from .gitignore files found in the directory tree."""
    patterns = []
    gitignore_path = os.path.join(root_path, '.gitignore')
    
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        # Remove leading slash for fnmatch compatibility
                        if line.startswith('/'):
                            line = line[1:]
                        patterns.append(line)
        except (IOError, UnicodeDecodeError):
            pass  # Silently ignore errors reading .gitignore
    
    return patterns

def generate_tree_human_readable(path: str, prefix: str = "", exclude_patterns: list = None) -> str:
    if exclude_patterns is None:
        exclude_patterns = [
            ".git",
            ".idea", 
            "__pycache__",
            "*.pyc",
            ".DS_Store",
            "node_modules",
            ".vscode",
            "*.egg-info",
            ".pytest_cache",
            ".mypy_cache",
            "build",
            "dist",
            ".gradle",
            ".ipynb_checkpoints"
        ]
        
        # Add patterns from .gitignore if present
        gitignore_patterns = read_gitignore_patterns(path)
        exclude_patterns.extend(gitignore_patterns)
    
    def should_exclude(entry_name):
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(entry_name, pattern):
                return True
        return False
    
    tree_str = ""
    entries = sorted(os.listdir(path))
    for i, entry in enumerate(entries):
        full_path = os.path.join(path, entry)
        if should_exclude(entry):
            continue  # Skip this file/directory
        connector = "└── " if i == len(entries) - 1 else "├── "
        tree_str += f"{prefix}{connector}{entry}\n"
        if os.path.isdir(full_path):
            extension = "    " if i == len(entries) - 1 else "│   "
            tree_str += generate_tree_human_readable(full_path, prefix + extension, exclude_patterns)
    return tree_str

def generate_package_list(path: str) -> str:
    exclude_patterns = [
        ".git", ".idea", "__pycache__", "*.pyc", ".DS_Store", "node_modules",
        ".vscode", "*.egg-info", ".pytest_cache", ".mypy_cache", "build", "dist",
        ".gradle", ".ipynb_checkpoints"
    ]
    exclude_patterns.extend(read_gitignore_patterns(path))

    def should_exclude(entry_name: str) -> bool:
        return any(fnmatch.fnmatch(entry_name, pattern) for pattern in exclude_patterns)

    grouped = {}

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not should_exclude(d)]
        files = [f for f in files if not should_exclude(f)]

        if not files:
            continue

        rel_root = os.path.relpath(root, path)
        if rel_root == ".":
            continue

        qualified = rel_root.replace(os.sep, ".")
        grouped.setdefault(qualified, []).extend(
            os.path.splitext(f)[0] for f in files
        )

    lines = []
    for pkg, files in sorted(grouped.items()):
        lines.append(f"{pkg}:")
        for f in sorted(files):
            lines.append(f"  - {f}")
        lines.append("")

    return "\n".join(lines)