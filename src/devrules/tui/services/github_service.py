"""GitHub service for fetching issues and PR data."""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    status: Optional[str] = None
    project_name: Optional[str] = None


@dataclass
class GitHubComment:
    """GitHub comment data."""

    id: int
    body: str
    author: str
    created_at: str
    issue_number: int
    issue_title: str
    html_url: str


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
        self._auth_user_cache: Optional[str] = None

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

    def get_authenticated_user(self) -> Optional[str]:
        """Get the login of the authenticated user.

        Returns:
            User login or None if authentication fails
        """
        if self._auth_user_cache:
            return self._auth_user_cache

        if not self.token:
            return None

        url = f"{self.base_url}/user"
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            data = response.json()
            self._auth_user_cache = data.get("login")
            return self._auth_user_cache
        except requests.RequestException:
            return None

    def get_my_actionable_issues(
        self, excluded_statuses: List[str], project_filter: Optional[str] = None
    ) -> List[GitHubIssue]:
        """Fetch actionable issues assigned to the current user.

        Args:
            excluded_statuses: List of status names to exclude
            project_filter: Optional project name to filter by

        Returns:
            List of filtered GitHub issues
        """
        user = self.get_authenticated_user()
        if not user:
            return []

        # 1. Fetch all open issues assigned to me
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/issues"
        params = {"state": "open", "assignee": user, "per_page": "100"}

        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=10)
            response.raise_for_status()
            raw_issues = response.json()
        except requests.RequestException:
            return []

        # 2. Integrate with project service to get status for each issue
        from devrules.core.project_service import (
            find_project_item_for_issue,
            resolve_project_number,
        )

        issues = []
        for item in raw_issues:
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

            # We need to find which project this issue belongs to if we want status
            # For now, let's assume we check the project_filter or all projects in config
            from devrules.config import load_config

            config = load_config()
            projects_to_check = []
            if project_filter:
                projects_to_check = [project_filter]
            else:
                projects_to_check = list(config.github.projects.keys())

            found_in_any_project = False
            for p_key in projects_to_check:
                try:
                    owner, p_num = resolve_project_number(p_key)
                    project_item = find_project_item_for_issue(owner, p_num, issue.number)
                    if project_item:
                        issue.status = project_item.status
                        issue.project_name = p_key
                        found_in_any_project = True
                        break
                except Exception:
                    # Issue might not be in this project
                    continue

            # Filter by excluded statuses
            if issue.status in excluded_statuses:
                continue

            # If project_filter was provided, only include if found in that project
            if project_filter and not found_in_any_project:
                continue

            issues.append(issue)

        return issues

    def get_recent_comments(self, hours: int = 24) -> List[GitHubComment]:
        """Fetch recent comments on issues assigned to the current user.

        Args:
            hours: Number of hours to look back

        Returns:
            List of recent GitHub comments
        """
        user = self.get_authenticated_user()
        if not user:
            return []

        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/issues/comments"
        params = {"since": since, "per_page": "100"}

        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=15)
            response.raise_for_status()
            raw_comments = response.json()
        except requests.RequestException:
            return []

        # Get my issues to cross-reference
        # Note: we might want to optimize this by just checking 'assignee' on the issue linked to comment
        # but the issues/comments endpoint doesn't return full issue data, only issue_url.

        recent_comments = []
        for item in raw_comments:
            comment_user = item.get("user", {}).get("login")
            if comment_user == user:
                continue

            # To know if the issue is assigned to me, we'd need to fetch the issue details
            # OR we can assume that if we are in the "Work Center", we care about comments
            # where the user is involved.
            # The prompt says: "Use GitHub REST API to fetch comments on issues assigned to the current user"

            issue_url = item.get("issue_url")
            if not issue_url:
                continue

            try:
                issue_resp = requests.get(issue_url, headers=self._get_headers(), timeout=10)
                issue_resp.raise_for_status()
                issue_data = issue_resp.json()

                assignee = (
                    issue_data.get("assignee", {}).get("login")
                    if issue_data.get("assignee")
                    else None
                )
                if assignee != user:
                    continue

                comment = GitHubComment(
                    id=item["id"],
                    body=item["body"],
                    author=comment_user,
                    created_at=item["created_at"],
                    issue_number=issue_data["number"],
                    issue_title=issue_data["title"],
                    html_url=item["html_url"],
                )
                recent_comments.append(comment)
            except Exception:
                continue

        return recent_comments
