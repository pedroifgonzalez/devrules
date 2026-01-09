import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

from devrules.config import GitHubConfig, PRConfig
from devrules.dtos.github import PRInfo, ProjectItem
from devrules.validators.pr import validate_pr, validate_pr_issue_status


def load_github_configs(filepath: Path):
    """Loads GitHubConfig objects from a JSON file."""
    with filepath.open("r") as f:
        data = json.load(f)
    return [GitHubConfig(**cfg) for cfg in data]


CONFIG_PATH = Path(__file__).resolve().parent / "github_configs.json"
github_configs = load_github_configs(CONFIG_PATH)
current_github_config_scenario = github_configs[0]
github_config_with_project = github_configs[1]
github_config_with_valid_statuses = github_configs[2]


def pr_config():
    return PRConfig(
        max_files=10,
        max_loc=50,
        require_title_tag=True,
        allowed_pr_statuses=["In Progress"],
    )


def pr_config_not_allowed_pr_statuses():
    return PRConfig(
        max_files=10,
        max_loc=50,
        require_title_tag=True,
    )


def pr_config_with_title_pattern():
    return PRConfig(
        max_files=10,
        max_loc=50,
        require_title_tag=True,
        title_pattern=r"^\[ADD\].+",
        allowed_pr_statuses=["In Progress"],
    )


def pr_config_with_issue_check():
    return PRConfig(
        max_files=10,
        max_loc=50,
        require_title_tag=True,
        require_issue_status_check=True,
        allowed_pr_statuses=["In Progress"],
    )


@pytest.mark.parametrize(
    "branch_name,expected,messages,pr_config,github_config,patches",  # Added github_config to parameters
    [
        (
            "feature/no-issue-branch-does-not-matter",
            True,
            ["ℹ No issue number found in branch name - status check skipped"],
            pr_config(),
            current_github_config_scenario,
            [],
        ),
        (
            "",
            False,
            ["✘ No branch name provided"],
            pr_config(),
            current_github_config_scenario,
            [],
        ),
        (
            "feature/12-no-projects-configured",
            False,
            ["✘ No projects configured for status check"],
            pr_config(),
            current_github_config_scenario,
            [],
        ),
        (
            "feature/404-exception-is-raised",
            False,
            ["✘ Issue #404 not found in projects: devrules"],
            pr_config(),
            github_config_with_project,
            [
                patch(
                    "devrules.validators.pr.resolve_project_number",
                    return_value=("test-owner", "8"),
                ),
                patch("devrules.validators.pr.find_project_item_for_issue", side_effect=Exception),
            ],
        ),
        (
            "feature/999-issue-not-found-in-projects",
            False,
            ["✘ Issue #999 not found in projects: devrules"],
            pr_config(),
            github_config_with_project,
            [
                patch(
                    "devrules.validators.pr.resolve_project_number",
                    return_value=("test-owner", "8"),
                ),
                patch("devrules.validators.pr.find_project_item_for_issue", return_value=None),
            ],
        ),
        (
            "feature/15-not-statuses-allowed-configured",
            True,
            ["⚠ No allowed statuses configured - all statuses permitted"],
            pr_config_not_allowed_pr_statuses(),
            github_config_with_project,
            [
                patch(
                    "devrules.validators.pr.resolve_project_number",
                    return_value=("test-owner", "8"),
                ),
                patch(
                    "devrules.validators.pr.find_project_item_for_issue",
                    return_value=ProjectItem(status="In Review"),
                ),
            ],
        ),
        (
            "feature/19-issue-status-not-in-statuses-allowed-configured",
            False,
            [
                "✘ Issue #19 has status 'In Review' which is not allowed for PR creation",
                "⚠ Allowed statuses: In Progress",
            ],
            pr_config(),
            github_config_with_valid_statuses,
            [
                patch(
                    "devrules.validators.pr.resolve_project_number",
                    return_value=("test-owner", "8"),
                ),
                patch(
                    "devrules.validators.pr.find_project_item_for_issue",
                    return_value=ProjectItem(status="In Review"),
                ),
            ],
        ),
        (
            "feature/21-issue-status-in-statuses-allowed-configured",
            True,
            ["✔ Issue #21 status 'In Progress' is allowed for PR creation"],
            pr_config(),
            github_config_with_valid_statuses,
            [
                patch(
                    "devrules.validators.pr.resolve_project_number",
                    return_value=("test-owner", "8"),
                ),
                patch(
                    "devrules.validators.pr.find_project_item_for_issue",
                    return_value=ProjectItem(status="In Progress"),
                ),
            ],
        ),
    ],
)
def test_validate_pr_issue_status(
    branch_name, expected, pr_config, github_config, messages, patches
):
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        result, response = validate_pr_issue_status(
            current_branch=branch_name,
            pr_config=pr_config,
            github_config=github_config,
        )

    assert result == expected
    assert response == messages


@pytest.mark.parametrize(
    "pr_info,expected_is_valid,expected_messages,pr_config,current_branch,github_config,patches",
    [
        # Valid PR: all checks pass
        (
            PRInfo(additions=10, deletions=10, changed_files=5, title="Valid title"),
            True,
            ["✔ PR title valid", "✔ PR size acceptable: 20 LOC", "✔ File count acceptable: 5"],
            pr_config(),
            None,
            None,
            [],
        ),
        # Invalid title with pattern
        (
            PRInfo(additions=10, deletions=10, changed_files=5, title="Invalid title"),
            False,
            [
                "✘ PR title does not follow required format",
                "✔ PR size acceptable: 20 LOC",
                "✔ File count acceptable: 5",
            ],
            pr_config_with_title_pattern(),
            None,
            None,
            [],
        ),
        # Valid title with pattern
        (
            PRInfo(additions=10, deletions=10, changed_files=5, title="[ADD] Valid title"),
            True,
            ["✔ PR title valid", "✔ PR size acceptable: 20 LOC", "✔ File count acceptable: 5"],
            pr_config_with_title_pattern(),
            None,
            None,
            [],
        ),
        # Too many LOC
        (
            PRInfo(additions=30, deletions=30, changed_files=5, title="Valid title"),
            False,
            ["✔ PR title valid", "✘ PR too large: 60 LOC (max: 50)", "✔ File count acceptable: 5"],
            pr_config(),
            None,
            None,
            [],
        ),
        # Too many files
        (
            PRInfo(additions=10, deletions=10, changed_files=15, title="Valid title"),
            False,
            ["✔ PR title valid", "✔ PR size acceptable: 20 LOC", "✘ Too many files: 15 (max: 10)"],
            pr_config(),
            None,
            None,
            [],
        ),
        # Issue check enabled but no branch/config provided
        (
            PRInfo(additions=10, deletions=10, changed_files=5, title="Valid title"),
            True,
            [
                "⚠ Issue status check enabled but branch/config not provided - skipping",
                "✔ PR title valid",
                "✔ PR size acceptable: 20 LOC",
                "✔ File count acceptable: 5",
            ],
            pr_config_with_issue_check(),
            None,
            None,
            [],
        ),
        # Issue check enabled, branch provided but no github_config
        (
            PRInfo(additions=10, deletions=10, changed_files=5, title="Valid title"),
            True,
            [
                "⚠ Issue status check enabled but branch/config not provided - skipping",
                "✔ PR title valid",
                "✔ PR size acceptable: 20 LOC",
                "✔ File count acceptable: 5",
            ],
            pr_config_with_issue_check(),
            "feature/123-branch",
            None,
            [],
        ),
        # Issue check enabled, issue status invalid
        (
            PRInfo(additions=10, deletions=10, changed_files=5, title="Valid title"),
            False,
            [
                "✘ Issue #123 has status 'In Review' which is not allowed for PR creation",
                "⚠ Allowed statuses: In Progress",
                "✔ PR title valid",
                "✔ PR size acceptable: 20 LOC",
                "✔ File count acceptable: 5",
            ],
            pr_config_with_issue_check(),
            "feature/123-branch",
            github_config_with_valid_statuses,
            [
                patch(
                    "devrules.validators.pr.validate_pr_issue_status",
                    return_value=(
                        False,
                        [
                            "✘ Issue #123 has status 'In Review' which is not allowed for PR creation",
                            "⚠ Allowed statuses: In Progress",
                        ],
                    ),
                ),
            ],
        ),
        # Issue check enabled, issue status valid
        (
            PRInfo(additions=10, deletions=10, changed_files=5, title="Valid title"),
            True,
            [
                "✔ Issue #123 status 'In Progress' is allowed for PR creation",
                "✔ PR title valid",
                "✔ PR size acceptable: 20 LOC",
                "✔ File count acceptable: 5",
            ],
            pr_config_with_issue_check(),
            "feature/123-branch",
            github_config_with_valid_statuses,
            [
                patch(
                    "devrules.validators.pr.validate_pr_issue_status",
                    return_value=(
                        True,
                        ["✔ Issue #123 status 'In Progress' is allowed for PR creation"],
                    ),
                ),
            ],
        ),
        # No issue check, branch with no issue number
        (
            PRInfo(additions=10, deletions=10, changed_files=5, title="Valid title"),
            True,
            ["✔ PR title valid", "✔ PR size acceptable: 20 LOC", "✔ File count acceptable: 5"],
            pr_config(),
            "feature/no-issue-branch",
            github_config_with_valid_statuses,
            [],
        ),
    ],
)
def test_validate_pr(
    pr_info, expected_is_valid, expected_messages, pr_config, current_branch, github_config, patches
):
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        result, messages = validate_pr(
            pr_info=pr_info,
            pr_config=pr_config,
            current_branch=current_branch,
            github_config=github_config,
        )

    assert result == expected_is_valid
    assert messages == expected_messages
