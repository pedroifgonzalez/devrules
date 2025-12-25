import os
import shutil
import subprocess

import requests
import typer

from devrules.config import GitHubConfig
from devrules.dtos.github import PRInfo
from devrules.messages import pr as msg


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


def gh_create_pr(base: str, current_branch: str, pr_title: str):
    cmd = [
        "gh",
        "pr",
        "create",
        "--base",
        base,
        "--head",
        current_branch,
        "--title",
        pr_title,
        "--fill",
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        typer.secho(msg.FAILED_TO_CREATE_PR.format(e), fg=typer.colors.RED)
        raise typer.Exit(code=1)
