"""GitHub service for interacting with GitHub API."""

import os
import shutil
import subprocess

import requests
import typer
from yaspin import yaspin

from devrules.adapters.prompters.factory import get_default_prompter
from devrules.config import GitHubConfig
from devrules.dtos.github import PRInfo

prompter = get_default_prompter()


def ensure_gh_installed() -> None:
    """Ensure the GitHub CLI `gh` is installed."""
    if shutil.which("gh") is None:
        typer.secho(
            "✘ GitHub CLI 'gh' is not installed or not in PATH. "
            "Install it from https://cli.github.com/.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


def fetch_pr_info(owner: str, repo: str, pr_number: int, github_config: GitHubConfig) -> PRInfo:
    """Fetch PR information from GitHub API."""
    token = os.getenv("GH_TOKEN")
    if not token:
        raise ValueError("GH_TOKEN environment variable not set")

    url = f"{github_config.api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers, timeout=github_config.timeout)

    if response.status_code != 200:
        raise Exception(f"GitHub API error: {response.status_code} - {response.text}")

    data = response.json()
    return PRInfo(
        additions=data.get("additions", 0),
        deletions=data.get("deletions", 0),
        changed_files=data.get("changed_files", 0),
        title=data.get("title", ""),
    )


def update_issue_status(item_id: str, status_field_id: str, project_id: str, status_option_id: str):
    """Update the status of a project item on GitHub."""
    cmd = [
        "gh",
        "project",
        "item-edit",
        "--id",
        item_id,
        "--field-id",
        status_field_id,
        "--project-id",
        project_id,
        "--single-select-option-id",
        status_option_id,
    ]

    try:
        with yaspin(text="Updating status...", color="green"):
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
    except subprocess.CalledProcessError as e:
        prompter.error(
            f"Failed to update project item status: {e}",
        )
        raise prompter.exit(1)


def link_branch_to_issue(issue: int, branch_name: str) -> tuple[bool, str]:
    """Link a branch to an issue on GitHub."""
    cmd = [
        "gh",
        "issue",
        "develop",
        str(issue),
        "--name",
        branch_name,
    ]
    try:
        with yaspin(text="Linking branch to issue...", color="green"):
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
    except subprocess.CalledProcessError as e:
        prompter.error(
            f"Failed to link branch to issue: {e}",
        )
        raise prompter.exit(1)

    return True, "Branch linked to issue successfully."
