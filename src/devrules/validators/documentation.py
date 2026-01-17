"""Context-aware documentation linking."""

import fnmatch
import subprocess
from pathlib import Path
from typing import List, Tuple

from devrules.config import DocumentationRule


def get_changed_files(base_branch: str = "HEAD") -> List[str]:
    """Get list of changed files.

    Args:
        base_branch: Base branch to compare against (default: HEAD for staged files)

    Returns:
        List of file paths
    """
    try:
        if base_branch == "HEAD":
            # Get staged files
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
                check=True,
            )
        else:
            # Get all changes compared to base branch
            result = subprocess.run(
                ["git", "diff", "--name-only", base_branch],
                capture_output=True,
                text=True,
                check=True,
            )

        files = result.stdout.strip().split("\n")
        return [f for f in files if f]  # Filter empty strings
    except subprocess.CalledProcessError:
        return []


def matches_file_pattern(file_path: str, pattern: str) -> bool:
    """Check if file path matches a glob pattern.

    Args:
        file_path: Path to check
        pattern: Glob pattern (e.g., "migrations/**", "api/*.py")

    Returns:
        True if matches
    """
    # Direct match
    if fnmatch.fnmatch(file_path, pattern):
        return True

    # Check with full path matching for ** patterns
    path_obj = Path(file_path)

    # Convert pattern to parts for recursive matching
    if "**" in pattern:
        file_parts = list(path_obj.parts)

        # Try to match pattern at any depth
        for i in range(len(file_parts)):
            test_path = "/".join(file_parts[i:])
            test_pattern = pattern.replace("**/", "")
            if fnmatch.fnmatch(test_path, test_pattern):
                return True

    return False


def find_matching_rules(
    files: List[str], rules: List[DocumentationRule]
) -> List[Tuple[str, DocumentationRule]]:
    """Find documentation rules that match the changed files.

    Args:
        files: List of changed file paths
        rules: List of documentation rules

    Returns:
        List of tuples (matched_file, rule)
    """
    matches = []
    seen_rules = set()

    for file_path in files:
        for rule in rules:
            # Avoid duplicate rules
            rule_key = f"{rule.file_pattern}:{rule.docs_url}"
            if rule_key in seen_rules:
                continue

            if matches_file_pattern(file_path, rule.file_pattern):
                matches.append((file_path, rule))
                seen_rules.add(rule_key)

    return matches


def validate_documentation_patterns(rules: List[DocumentationRule]) -> List[str]:
    """Validate that documentation rules have valid patterns.

    Args:
        rules: List of documentation rules to validate

    Returns:
        List of validation error messages (empty if all valid)
    """
    errors = []

    for i, rule in enumerate(rules):
        if not rule.file_pattern:
            errors.append(f"Rule #{i+1}: file_pattern is required")

        if not rule.docs_url and not rule.message and not rule.checklist:
            errors.append(
                f"Rule #{i+1} ({rule.file_pattern}): Must provide at least one of: "
                "docs_url, message, or checklist"
            )

    return errors
