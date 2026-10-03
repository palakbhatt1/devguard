from typing import List

IGNORED_PATHS = [
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".env.example",
    "labels.csv",
]

COMMON_PLACEHOLDERS = [
    "your_api_key",
    "your_token",
    "your_secret",
    "example_key",
    "dummy_key",
    "test_token",
    "xxxx",
    "00000000",
    "12345678",
    "change_me",
    "insert_here",
    "todo_key",
]


def is_path_ignored(file_path: str) -> bool:
    """Check if file path should be excluded from secret scanning."""
    normalized = file_path.replace("\\", "/").lower()
    return any(ignored in normalized.split("/") for ignored in IGNORED_PATHS)


def is_known_placeholder(secret: str) -> bool:
    """Check if candidate secret is an obvious static decoy placeholder."""
    secret_lower = secret.lower()
    return any(placeholder in secret_lower for placeholder in COMMON_PLACEHOLDERS)
