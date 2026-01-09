import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

from devrules.config import GitHubConfig, PRConfig
from devrules.dtos.github import ProjectItem
from devrules.validators.pr import validate_pr_issue_status


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
