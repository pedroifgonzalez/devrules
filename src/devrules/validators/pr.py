"""Pull request validation."""

import re
from typing import Optional

from devrules.config import GitHubConfig, PRConfig
from devrules.dtos.github import PRInfo


def validate_pr_issue_status(
    current_branch: str,
    config: PRConfig,
    github_config: GitHubConfig,
) -> tuple[bool, list[str]]:
    """Validate that the branch's associated issue has an allowed status.

    Args:
        current_branch: Name of the current branch
        config: PR configuration
        github_config: GitHub configuration

    Returns:
        Tuple of (is_valid, messages)
    """
    from devrules.core.project_service import find_project_item_for_issue, resolve_project_number
    from devrules.validators.branch import _extract_issue_number

    messages = []

    # Extract issue number from branch
    issue_number = _extract_issue_number(current_branch)
    if issue_number is None:
        # No issue number in branch, skip check
        messages.append("ℹ No issue number found in branch name - status check skipped")
        return True, messages

    # Determine which project to check
    project_key = config.project_for_status_check
    if not project_key:
        # Use first configured project if available
        if github_config.projects:
            project_key = next(iter(github_config.projects.keys()))
        else:
            messages.append("✘ No project configured for status check")
            return False, messages

    # Resolve project number
    try:
        owner, project_number = resolve_project_number(project_key)
    except Exception as e:
        messages.append(f"✘ Failed to resolve project '{project_key}': {e}")
        return False, messages

    # Fetch project item for issue
    try:
        project_item = find_project_item_for_issue(owner, project_number, int(issue_number))
    except Exception as e:
        messages.append(f"✘ Failed to fetch project item for issue #{issue_number}: {e}")
        return False, messages

    # Check if status is allowed
    current_status = project_item.status
    allowed_statuses = config.allowed_pr_statuses

    if not allowed_statuses:
        messages.append("⚠ No allowed statuses configured - all statuses permitted")
        return True, messages

    if current_status in allowed_statuses:
        messages.append(
            f"✔ Issue #{issue_number} status '{current_status}' is allowed for PR creation"
        )
        return True, messages
    else:
        messages.append(
            f"✘ Issue #{issue_number} has status '{current_status}' which is not allowed for PR creation"
        )
        messages.append(f"  Allowed statuses: {', '.join(allowed_statuses)}")
        return False, messages


def validate_pr(
    pr_info: PRInfo,
    config: PRConfig,
    current_branch: Optional[str] = None,
    github_config: Optional[GitHubConfig] = None,
) -> tuple:
    """Validate pull request against configuration rules.

    Args:
        pr_info: Pull request information
        config: PR configuration
        current_branch: Optional current branch name for status validation
        github_config: Optional GitHub configuration for status validation

    Returns:
        Tuple of (is_valid, messages)
    """
    messages = []
    is_valid = True

    # Check issue status if enabled
    if config.require_issue_status_check:
        if current_branch and github_config:
            status_valid, status_messages = validate_pr_issue_status(
                current_branch, config, github_config
            )
            messages.extend(status_messages)
            if not status_valid:
                is_valid = False
        else:
            messages.append(
                "⚠ Issue status check enabled but branch/config not provided - skipping"
            )

    total_loc = pr_info.additions + pr_info.deletions

    # Check title format
    if config.require_title_tag:
        pattern = re.compile(config.title_pattern)
        if pattern.match(pr_info.title):
            messages.append("✔ PR title valid")
        else:
            messages.append("✘ PR title does not follow required format")
            is_valid = False

    # Check LOC
    if total_loc > config.max_loc:
        messages.append(f"✘ PR too large: {total_loc} LOC (max: {config.max_loc})")
        is_valid = False
    else:
        messages.append(f"✔ PR size acceptable: {total_loc} LOC")

    # Check files
    if pr_info.changed_files > config.max_files:
        messages.append(f"✘ Too many files: {pr_info.changed_files} (max: {config.max_files})")
        is_valid = False
    else:
        messages.append(f"✔ File count acceptable: {pr_info.changed_files}")

    return is_valid, messages
