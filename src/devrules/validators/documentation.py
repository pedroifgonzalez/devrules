"""Context-aware documentation linking."""

import fnmatch
import subprocess
from pathlib import Path
from typing import List, Tuple

from devrules.config import DocumentationRule
from devrules.utils import gum


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


def format_documentation_message(
    matches: List[Tuple[str, DocumentationRule]], show_files: bool = True
) -> str:
    """Format documentation guidance message.

    Args:
        matches: List of (file, rule) tuples
        show_files: Whether to show which files triggered each rule

    Returns:
        Formatted message string
    """
    if not matches:
        return ""

    # Group by rule
    rule_groups = {}
    for file_path, rule in matches:
        rule_key = f"{rule.file_pattern}:{rule.docs_url}"
        if rule_key not in rule_groups:
            rule_groups[rule_key] = {"rule": rule, "files": []}
        rule_groups[rule_key]["files"].append(file_path)

    # Always use list format for documentation display
    return _format_docs_list(rule_groups, show_files)


def _format_docs_table(rule_groups: dict, show_files: bool) -> str:
    """Format documentation as a table using gum."""
    lines = []

    # Header
    lines.append(gum.style("\n📚 Context-Aware Documentation", foreground=81, bold=True))
    lines.append(gum.style("=" * 60, foreground=81))
    lines.append("")

    # Build table rows
    table_rows = []
    for group_data in rule_groups.values():
        rule = group_data["rule"]
        files = group_data["files"]

        # Pattern column
        pattern = rule.file_pattern

        # Files column
        if show_files and len(files) <= 3:
            files_str = ", ".join(files)
        elif show_files:
            files_str = f"{len(files)} file(s)"
        else:
            files_str = "-"

        # Info column (message or docs URL)
        info = rule.message or rule.docs_url or "-"
        if len(info) > 40:
            info = info[:37] + "..."

        table_rows.append([pattern, files_str, info])

    # Print table
    lines.append(
        gum.table(
            table_rows,
            headers=["Pattern", "Files", "Info"],
            border="rounded",
            border_foreground=99,
        )
    )

    # Show checklists separately (they don't fit well in tables)
    for group_data in rule_groups.values():
        rule = group_data["rule"]
        if rule.checklist:
            lines.append("")
            lines.append(gum.style(f"✅ Checklist for {rule.file_pattern}:", foreground=82))
            for item in rule.checklist:
                lines.append(f"   • {item}")

        # Show full docs URL if truncated
        if rule.docs_url and len(rule.docs_url) > 40:
            lines.append(gum.style(f"🔗 {rule.docs_url}", foreground=81))

    lines.append("")
    return "\n".join(lines)


def _format_docs_list(rule_groups: dict, show_files: bool) -> str:
    """Format documentation as a list (fallback)."""
    lines = [
        "\n📚 Context-Aware Documentation",
        "=" * 50,
        "",
    ]

    for group_data in rule_groups.values():
        rule = group_data["rule"]
        files = group_data["files"]

        lines.append(f"📌 Pattern: {rule.file_pattern}")

        if show_files and len(files) <= 5:
            lines.append(f"   Files: {', '.join(files)}")
        elif show_files:
            lines.append(f"   Files: {len(files)} file(s) matched")

        if rule.message:
            lines.append(f"   ℹ️  {rule.message}")

        if rule.docs_url:
            lines.append(f"   🔗 Docs: {rule.docs_url}")

        if rule.checklist:
            lines.append("   ✅ Checklist:")
            for item in rule.checklist:
                lines.append(f"      • {item}")

        lines.append("")

    return "\n".join(lines)


def get_relevant_documentation(
    rules: List[DocumentationRule], base_branch: str = "HEAD", show_files: bool = True
) -> Tuple[bool, str]:
    """Get relevant documentation for changed files.

    Args:
        rules: List of documentation rules to check
        base_branch: Base branch to compare against
        show_files: Whether to show which files triggered rules

    Returns:
        Tuple of (has_matches, formatted_message)
    """
    if not rules:
        return False, ""

    # Get changed files
    files = get_changed_files(base_branch)
    if not files:
        return False, ""

    # Find matching rules
    matches = find_matching_rules(files, rules)

    if not matches:
        return False, ""

    # Format message
    message = format_documentation_message(matches, show_files)
    return True, message


def display_documentation_guidance(
    rules: List[DocumentationRule],
    base_branch: str = "HEAD",
    show_files: bool = True,
) -> bool:
    """Display documentation guidance for changed files.

    Args:
        rules: List of documentation rules
        base_branch: Base branch to compare against
        show_files: Whether to show which files triggered rules

    Returns:
        True if any documentation was shown
    """
    has_docs, message = get_relevant_documentation(rules, base_branch, show_files)

    if has_docs and message:
        print(message)
        return True

    return False


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
