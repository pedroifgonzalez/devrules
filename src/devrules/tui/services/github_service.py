"""GitHub service for fetching issues and PR data."""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests
from loguru import logger

from devrules.utils.spinner_ctx import update_spinner_text


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
    repo_name: Optional[str] = None
    owner: Optional[str] = None


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
        update_spinner_text("Fetching user information...")
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
        except requests.RequestException as e:
            logger.error(e)
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

        from devrules.config import load_config
        from devrules.core.project_service import list_project_items, resolve_project_number

        config = load_config(None)
        projects_map = config.github.projects

        projects_to_check = []
        if project_filter:
            if project_filter in projects_map:
                projects_to_check.append(project_filter)
            else:
                # If key not found, maybe it's a number, but resolve_project_number expects keys for mapping.
                # branch.py logic mostly relies on keys.
                # But let's try to search if it matches.
                projects_to_check.append(project_filter)
        else:
            projects_to_check = list(projects_map.keys())

        issues = []
        seen_numbers = set()

        for p_key in projects_to_check:
            try:
                owner, p_num = resolve_project_number(p_key)
                items = list_project_items(owner, p_num)
            except Exception:
                continue

            for item in items:
                content = item.get("content", {})
                if not content or content.get("type") != "Issue":
                    continue

                # Check assignee
                # Assignees can be on top-level item or inside content
                assignees = item.get("assignees", [])
                if not assignees:
                    assignees = content.get("assignees", [])

                is_assigned = False
                for a in assignees:
                    # API can return dict or string depending on version/parsing
                    login = a.get("login") if isinstance(a, dict) else str(a)
                    if login == user:
                        is_assigned = True
                        break

                if not is_assigned:
                    continue

                status = item.get("status")
                if status in excluded_statuses:
                    continue

                # Check state to filter out closed issues
                # 'state' is usually "OPEN" or "CLOSED" in content
                state = content.get("state", "OPEN").lower()
                if state == "closed":
                    continue

                number = content.get("number")
                if not number:
                    continue

                if number in seen_numbers:
                    continue
                seen_numbers.add(number)

                # Extract labels
                labels = item.get("labels", [])
                # Sometimes labels are strings, sometimes dicts
                label_names = []
                for label in labels:
                    if isinstance(label, dict):
                        label_names.append(label.get("name", ""))
                    else:
                        label_names.append(str(label))

                repo = item["content"].get("repository", "").split("/", maxsplit=1)
                owner, repo_name = "", ""
                if len(repo) == 2:
                    owner, repo_name = repo[0], repo[1]
                issue = GitHubIssue(
                    number=number,
                    title=content.get("title", ""),
                    state=state,
                    labels=label_names,
                    assignee=user,
                    url=content.get("url", ""),
                    status=status,
                    project_name=p_key,
                    repo_name=repo_name,
                    owner=owner,
                )
                issues.append(issue)

        return sorted(issues, key=lambda x: x.number, reverse=True)

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
