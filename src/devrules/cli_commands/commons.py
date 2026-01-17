"""Module containing common functions."""

from typing import Dict, Optional

from yaspin import yaspin

from devrules.cli_commands.prompters.factory import get_default_prompter
from devrules.config import DocumentationRule
from devrules.core.project_service import list_project_items
from devrules.validators.documentation import find_matching_rules, get_changed_files

prompter = get_default_prompter()


def _fetch_project_items(
    owner: str, project_number: str, exclude_status: Optional[str] = None
) -> list[dict]:
    """Fetch items from a GitHub project.

    Args:
        owner: The GitHub owner.
        project_number: The project number.
        exclude_status: Optional status to exclude.

    Returns:
        List of project items.

    Raises:
        typer.Exit: If no items are found.
    """
    items = []
    with yaspin(text="Fetching project items..."):
        items = list_project_items(
            owner=owner,
            project_number=project_number,
            exclude_status=exclude_status,
        )
    if not items:
        prompter.error("No items found in the project")
        raise prompter.exit(1)
    return items


def _get_issue_and_status_interactively(items: list[Dict]) -> dict:
    """Get issue and status interactively."""
    selected = prompter.filter_list(
        options=[f"{item.get('content', {}).get('number')}.{item.get('title')}" for item in items],
        header="Select an issue to update",
    )
    if selected is None:
        prompter.error("No selected issue")
        raise prompter.exit(1)

    issue, title = selected.split(".")
    item_status = None
    for item in items:
        number = item.get("content", {}).get("number")
        if not number:
            continue
        if str(number) == issue:
            item_status = item.get("status")
    if not item_status:
        prompter.error("No issue number was found")
        prompter.exit(1)
    return dict(issue=issue, item_title=title, item_status=item_status)


def _show_relevant_documentation(
    rules: list[DocumentationRule], base_branch: str = "HEAD", show_files: bool = True
) -> None:
    """Get relevant documentation for changed files.

    Args:
        rules: List of documentation rules to check
        base_branch: Base branch to compare against
        show_files: Whether to show which files triggered rules
    """
    if not rules:
        return None

    # Get changed files
    files = get_changed_files(base_branch)
    if not files:
        return None

    # Find matching rules
    matches = find_matching_rules(files, rules)

    if not matches:
        return

    # Group by rule
    rule_groups = {}
    for file_path, rule in matches:
        rule_key = f"{rule.file_pattern}:{rule.docs_url}"
        if rule_key not in rule_groups:
            rule_groups[rule_key] = {"rule": rule, "files": []}
        rule_groups[rule_key]["files"].append(file_path)

    # Format message
    prompter.header("Context Aware Documentation")

    for group_data in rule_groups.values():
        rule = group_data["rule"]
        files = group_data["files"]

        prompter.info(f"Pattern: {rule.file_pattern}")

        if show_files and len(files) <= 5:
            prompter.info(f"Files: {', '.join(files)}")
        elif show_files:
            prompter.info(f"Files: {len(files)} file(s) matched")

        if rule.message:
            prompter.info(f"{rule.message}")

        if rule.docs_url:
            prompter.info(f"Docs: {rule.docs_url}")

        if rule.checklist:
            prompter.info("Checklist:")
            for item in rule.checklist:
                prompter.indented_message(f"• {item}")
