import os
import json
import fnmatch
from typing import List, Dict, Any


def should_exclude(path: str, exclude_patterns: List[str]) -> bool:
    """Check if a file or directory should be excluded based on glob patterns."""
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(
            os.path.basename(path), pattern
        ):
            return True
    return False


def source_to_json(root_dir: str, exclude_patterns: List[str] = None) -> Dict[str, Any]:
    """
    Converts a directory of source code into a JSON object, respecting exclusions.

    :param root_dir: The root directory of the source code.
    :param exclude_patterns: A list of glob patterns to exclude files or directories.
    :return: A dictionary representing the source code.
    """
    if exclude_patterns is None:
        exclude_patterns = []

    project_name = os.path.basename(os.path.abspath(root_dir))
    output = {"project_name": project_name, "files": []}

    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
        # Filter out excluded directories in-place
        dirnames[:] = [
            d
            for d in dirnames
            if not should_exclude(
                os.path.join(os.path.relpath(dirpath, root_dir), d), exclude_patterns
            )
        ]

        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            relative_path = os.path.relpath(filepath, root_dir)

            if should_exclude(relative_path, exclude_patterns):
                continue

            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                output["files"].append({"path": relative_path, "content": content})
            except Exception as e:
                print(f"Error reading file {filepath}: {e}")

    return output


if __name__ == "__main__":
    # --- Configuration ---
    # Define the root directory of your project. Use '.' for the current directory.
    project_root = "."

    # --- Exclusion Patterns ---
    # Add glob patterns for files and directories to exclude.
    # These patterns match against the full relative path (e.g., 'venv/lib/...')
    # or just the basename (e.g., '*.pyc').
    exclusions = [
        # Version control
        ".git/*",
        ".github/*",
        "pgdata/*",
        # Python virtual environment and cache
        "venv",
        ".venv",
        "__pycache__",
        "*.pyc",
        ".ruff_cache",
        "tests",
        # IDE and OS-specific
        ".idea/*",
        ".vscode/*",
        ".DS_Store",
        # Tool-specific files
        ".gitignore",
        ".env.example",
        "source_to_json.py",
        "source_code.json",
        "*.sqlite3",
        "*.db",
        ".coverage",
        # Add any other files or directories to exclude
        # e.g., 'docs/*', '*.log'
    ]
    # ---------------------

    output_filename = "source_code.json"

    print("Starting source code to JSON conversion...")
    json_data = source_to_json(project_root, exclusions)

    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)
        print(f"Successfully converted source code to '{output_filename}'")
        print(f"Total files processed: {len(json_data['files'])}")
    except Exception as e:
        print(f"Error writing JSON file: {e}")
