"""GitHub service for fetching issues and PR data."""

import os
from dataclasses import dataclass
from typing import List, Optional

import requests


@dataclass
class GitHubIssue:
    """GitHub issue data."""

    number: int
    title: str
    state: str
    labels: List[str]
    assignee: Optional[str]
    url: str
    has_branch: bool = False
    branch_name: Optional[str] = None


class GitHubService:
    """Service for interacting with GitHub API."""

    def __init__(self, owner: str, repo: str, token: Optional[str] = None):
        """Initialize GitHub service.

        Args:
            owner: Repository owner
            repo: Repository name
            token: GitHub token (defaults to GH_TOKEN env var)
        """
        self.owner = owner
        self.repo = repo
        self.token = token or os.getenv("GH_TOKEN")
        self.base_url = "https://api.github.com"

    def _get_headers(self) -> dict:
        """Get request headers with authentication.

        Returns:
            Headers dictionary
        """
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def get_issues(
        self, state: str = "open", labels: Optional[List[str]] = None
    ) -> List[GitHubIssue]:
        """Fetch issues from GitHub.

        Args:
            state: Issue state ('open', 'closed', 'all')
            labels: Optional list of label filters

        Returns:
            List of GitHub issues
        """
        if not self.token:
            # Return empty list if no token configured
            return []

        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/issues"
        params = {"state": state, "per_page": "100"}

        if labels:
            params["labels"] = ",".join(labels)

        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=10)
            response.raise_for_status()

            issues = []
            for item in response.json():
                # Skip pull requests (they appear in issues endpoint)
                if "pull_request" in item:
                    continue

                issue = GitHubIssue(
                    number=item["number"],
                    title=item["title"],
                    state=item["state"],
                    labels=[label["name"] for label in item.get("labels", [])],
                    assignee=item["assignee"]["login"] if item.get("assignee") else None,
                    url=item["html_url"],
                )
                issues.append(issue)

            return issues

        except requests.RequestException:
            # Return empty list on error
            return []

    def is_configured(self) -> bool:
        """Check if GitHub service is properly configured.

        Returns:
            True if token is available
        """
        return self.token is not None
