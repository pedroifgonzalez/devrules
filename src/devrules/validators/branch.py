"""Branch name validation."""

import re
from typing import List, Optional, Tuple

from devrules.config import BranchConfig, GitHubConfig
from devrules.dtos.github import ProjectItem


def validate_branch(branch_name: str, config: BranchConfig) -> tuple:
    """Validate branch name against configuration rules."""
    pattern = re.compile(config.pattern)

    if config.require_issue_number:
        issue_number = _extract_issue_number(branch_name)
        if not issue_number:
            return False, f"Branch name must contain an issue number: {branch_name}"

    if pattern.match(branch_name):
        return True, f"Branch name valid: {branch_name}"

    error_msg = f"Invalid branch name: {branch_name}\n"
    error_msg += f"Expected pattern: {config.pattern}\n"
    error_msg += f"Valid prefixes: {', '.join(config.prefixes)}"

    return False, error_msg


def _extract_issue_number(branch_name: str) -> Optional[str]:
    """Extract the issue number from a branch name, if present.

    Assumes branches follow the configured pattern, e.g.:
    ``feature/123-fix-login`` or ``bugfix/456-something``.
    """

    match = re.match(r"^[^/]+\/(?P<issue>\d+)-.+", branch_name)
    if not match:
        return None

    return match.group("issue")


def _get_environment(branch_name: str) -> str:
    """Return the environment name for a branch based on its name.

    - If the branch name contains "staging" anywhere, it is considered staging.
    - Otherwise it is considered dev.
    """

    return "staging" if "staging" in branch_name else "dev"


def validate_single_branch_per_issue_env(
    branch_name: str, existing_branches: List[str]
) -> Tuple[bool, str]:
    """Enforce that only one branch per issue per environment exists locally.

    The environment is inferred from the branch name:
    - "staging" in the name -> staging environment
    - otherwise -> dev environment
    """

    issue = _extract_issue_number(branch_name)
    if issue is None:
        return True, "No issue number detected in branch name — rule not applied"

    env = _get_environment(branch_name)

    for existing in existing_branches:
        if existing == branch_name:
            continue

        existing_issue = _extract_issue_number(existing)
        if existing_issue is None:
            continue

        if existing_issue != issue:
            continue

        existing_env = _get_environment(existing)
        if existing_env != env:
            continue

        return (
            False,
            f"Only one branch is allowed per issue per environment. "
            f"Issue {issue!r} already has a {env} branch: {existing!r}",
        )

    return True, "Branch respects the one-branch-per-issue-per-environment rule"


def validate_cross_repo_card(
    project_item: ProjectItem, github_config: GitHubConfig
) -> Tuple[bool, str]:
    """Validate that the project item belongs to the configured GitHub repository.

    Returns (is_valid, message).
    """

    owner = getattr(github_config, "owner", None)
    repo = getattr(github_config, "repo", None)

    if not owner or not repo:
        # If GitHub repo is not configured, we skip this rule.
        return True, "GitHub owner/repo not configured — cross-repo check skipped"

    expected = f"{owner}/{repo}"

    actual_repo = None

    # Prefer the structured repository field when available (owner/repo)
    content = getattr(project_item, "content", None) or {}
    if isinstance(content, dict):
        actual_repo = content.get("repository") or None

    # Fallback to URL-style repository field (https://github.com/owner/repo)
    if not actual_repo and project_item.repository:
        repo_url = str(project_item.repository)
        if "github.com/" in repo_url:
            parts = repo_url.rstrip("/").split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                actual_repo = f"{parts[0]}/{parts[1]}"

    if not actual_repo:
        # If we cannot determine the project item's repository, allow it but log context.
        return True, "Project item repository could not be determined — cross-repo check skipped"

    if actual_repo != expected:
        return (
            False,
            f"Issue/card belongs to '{actual_repo}', which does not match the configured repo '{expected}'.",
        )

    return True, "Project item belongs to the configured repository"
