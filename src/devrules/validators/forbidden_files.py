"""Forbidden files validation."""

import fnmatch
import subprocess
from pathlib import Path
from typing import List, Tuple

import typer


def get_staged_files() -> List[str]:
    """Get list of staged files in the current commit.

    Returns:
        List of file paths
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
        files = result.stdout.strip().split("\n")
        return [f for f in files if f]  # Filter empty strings
    except subprocess.CalledProcessError:
        return []


def get_changed_files(base_branch: str = "HEAD") -> List[str]:
    """Get list of changed files compared to base branch.

    Args:
        base_branch: Base branch to compare against

    Returns:
        List of file paths
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base_branch],
            capture_output=True,
            text=True,
            check=True,
        )
        files = result.stdout.strip().split("\n")
        return [f for f in files if f]
    except subprocess.CalledProcessError:
        return []


def matches_pattern(file_path: str, pattern: str) -> bool:
    """Check if file path matches a glob pattern.

    Args:
        file_path: Path to check
        pattern: Glob pattern (e.g., "*.log", "tmp/*", "**/.env")

    Returns:
        True if matches
    """
    # Support both simple and path patterns
    if fnmatch.fnmatch(file_path, pattern):
        return True

    # Check if any part of the path matches
    parts = Path(file_path).parts
    for i in range(len(parts)):
        subpath = "/".join(parts[i:])
        if fnmatch.fnmatch(subpath, pattern):
            return True

    return False


def check_forbidden_files(
    files: List[str],
    forbidden_patterns: List[str],
    forbidden_paths: List[str],
) -> Tuple[bool, List[str]]:
    """Check if any files match forbidden patterns or paths.

    Args:
        files: List of file paths to check
        forbidden_patterns: List of glob patterns (e.g., "*.dump", "*.env.local")
        forbidden_paths: List of forbidden path prefixes (e.g., "tmp/", "cache/")

    Returns:
        Tuple of (has_forbidden, list_of_forbidden_files)
    """
    forbidden_files = []

    for file in files:
        # Check against patterns
        for pattern in forbidden_patterns:
            if matches_pattern(file, pattern):
                forbidden_files.append(f"{file} (matches pattern: {pattern})")
                break
        else:
            # Check against paths
            for path in forbidden_paths:
                # Normalize path separators
                normalized_path = path.replace("\\", "/")
                normalized_file = file.replace("\\", "/")

                if normalized_file.startswith(normalized_path):
                    forbidden_files.append(f"{file} (in forbidden path: {path})")
                    break

    has_forbidden = len(forbidden_files) > 0
    return has_forbidden, forbidden_files


def validate_no_forbidden_files(
    forbidden_patterns: List[str],
    forbidden_paths: List[str],
    check_staged: bool = True,
) -> Tuple[bool, str]:
    """Validate that no forbidden files are being committed.

    Args:
        forbidden_patterns: List of forbidden glob patterns
        forbidden_paths: List of forbidden path prefixes
        check_staged: Whether to check staged files (if False, checks all changes)

    Returns:
        Tuple of (is_valid, message)
    """
    if not forbidden_patterns and not forbidden_paths:
        return True, "No forbidden file rules configured"

    # Get files to check
    if check_staged:
        files = get_staged_files()
        context = "staged for commit"
    else:
        files = get_changed_files()
        context = "changed"

    if not files:
        return True, f"No files {context}"

    # Check for forbidden files
    has_forbidden, forbidden_files = check_forbidden_files(
        files, forbidden_patterns, forbidden_paths
    )

    if has_forbidden:
        files_list = typer.style("\n  • ".join(forbidden_files), fg=typer.colors.RED, bold=True)
        message = (
            f"Found {len(forbidden_files)} forbidden file(s) {context}:\n"
            f"  • {files_list}\n\n"
            "These files match forbidden patterns or paths and should not be committed."
        )
        return False, message

    return True, f"No forbidden files found in {len(files)} file(s) {context}"


def get_forbidden_file_suggestions() -> List[str]:
    """Get suggestions for handling forbidden files.

    Returns:
        List of suggestion strings
    """
    return [
        "Remove the files from staging: git reset HEAD <file>",
        "Add them to .gitignore if they should never be committed",
        "Move sensitive files to a safe location outside the repository",
        "Use environment variables or config files for sensitive data",
    ]
