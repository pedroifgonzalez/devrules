"""Context-aware documentation linking."""

import fnmatch
import subprocess
from dataclasses import dataclass
from typing import List

from devrules.config import DocumentationRule


@dataclass
class DocumentationContext:
    """Snapshot of documentation context for changed files."""

    rule: DocumentationRule
    files: List[str]


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
    if "**" in pattern:
        prefix = pattern.split("**")[0]
        if file_path.count(prefix):
            return True

    return False


def build_documentation_context(
    rules: List[DocumentationRule],
    changed_files: List[str],
) -> List[DocumentationContext]:
    """Build documentation context snapshot before commit.

    This function captures the context of changed files and matching rules
    as a snapshot that doesn't depend on Git state afterwards.

    Args:
        rules: List of documentation rules to check
        changed_files: List of changed file paths

    Returns:
        List of DocumentationContext objects with matched rules and files
    """
    if not rules or not changed_files:
        return []

    # Group files by rule
    rule_groups = {}

    for file_path in changed_files:
        for rule in rules:
            # Avoid duplicate rules
            rule_key = f"{rule.file_pattern}:{rule.docs_url}:{rule.message}"

            if matches_file_pattern(file_path, rule.file_pattern):
                if rule_key not in rule_groups:
                    rule_groups[rule_key] = {"rule": rule, "files": []}
                rule_groups[rule_key]["files"].append(file_path)

    # Convert to DocumentationContext objects
    contexts = [
        DocumentationContext(rule=group["rule"], files=group["files"])
        for group in rule_groups.values()
    ]

    return contexts


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
