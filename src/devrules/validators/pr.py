"""Pull request validation."""

import os
import re
import requests
from dataclasses import dataclass
from devrules.config import PRConfig, GitHubConfig


@dataclass
class PRInfo:
    """Pull request information."""

    additions: int
    deletions: int
    changed_files: int
    title: str


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


def validate_pr(pr_info: PRInfo, config: PRConfig) -> tuple:
    """Validate pull request against configuration rules."""
    messages = []
    is_valid = True

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
