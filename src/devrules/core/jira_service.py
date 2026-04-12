"""Jira service for interacting with the Jira Cloud REST API."""

import os
from typing import Optional

import requests

from devrules.config import JiraConfig
from devrules.dtos.jira import JiraIssue, JiraTransition


class JiraService:
    """Service wrapper around the Jira Cloud REST API."""

    def __init__(self, config: JiraConfig):
        """Store Jira connection parameters."""
        self.config = config
        self.base_url = config.url.rstrip("/")
        self.timeout = config.timeout

    def _get_auth(self) -> tuple[str, str]:
        """Get Jira basic auth credentials from config or environment."""
        email = self.config.email or os.getenv("JIRA_EMAIL")
        api_token = self.config.api_token or os.getenv("JIRA_API_TOKEN")

        if not self.base_url:
            raise ValueError("Jira URL is not configured")
        if not email or not api_token:
            raise ValueError(
                "Jira authentication is not configured. Set jira.email and jira.api_token or "
                "JIRA_EMAIL and JIRA_API_TOKEN."
            )

        return email, api_token

    def _get_headers(self) -> dict[str, str]:
        """Return default Jira request headers."""
        return {"Accept": "application/json", "Content-Type": "application/json"}

    def _build_url(self, endpoint: str) -> str:
        """Build a full Jira API URL."""
        if not self.base_url:
            raise ValueError("Jira URL is not configured")
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def _parse_issue(self, issue_data: dict) -> JiraIssue:
        """Map Jira API issue payloads into DTOs."""
        fields = issue_data.get("fields", {})
        assignee = fields.get("assignee") or {}
        issue_type = fields.get("issuetype") or {}
        priority = fields.get("priority") or {}
        status = fields.get("status") or {}

        return JiraIssue(
            key=issue_data.get("key", ""),
            summary=fields.get("summary", ""),
            status=status.get("name", ""),
            assignee=assignee.get("displayName"),
            issue_type=issue_type.get("name", ""),
            priority=priority.get("name"),
            labels=fields.get("labels", []) or [],
            url=f"{self.base_url}/browse/{issue_data.get('key', '')}" if self.base_url else "",
            created=fields.get("created"),
            updated=fields.get("updated"),
        )

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Execute a Jira API request."""
        response = requests.request(
            method=method,
            url=self._build_url(endpoint),
            auth=self._get_auth(),
            headers=self._get_headers(),
            timeout=self.timeout,
            **kwargs,
        )
        return response

    def _get_issue(self, issue_key: str) -> JiraIssue:
        """Fetch a single issue by key."""
        response = self._request(
            "GET",
            f"/rest/api/3/issue/{issue_key}",
            params={
                "fields": ",".join(
                    [
                        "summary",
                        "status",
                        "assignee",
                        "issuetype",
                        "priority",
                        "labels",
                        "created",
                        "updated",
                    ]
                )
            },
        )

        if response.status_code == 401:
            raise ValueError("Jira authentication failed. Check your Jira credentials.")
        if response.status_code == 404:
            raise ValueError(f"Jira issue '{issue_key}' was not found.")
        if response.status_code >= 400:
            raise ValueError(f"Failed to fetch Jira issue '{issue_key}': {response.text}")

        return self._parse_issue(response.json())

    def search_issues(
        self, jql: str, max_results: int = 50, fields: Optional[list[str]] = None
    ) -> list[JiraIssue]:
        """Search Jira issues using JQL."""
        selected_fields = fields or [
            "summary",
            "status",
            "assignee",
            "issuetype",
            "priority",
            "labels",
            "created",
            "updated",
        ]

        issues: list[JiraIssue] = []
        next_page_token: Optional[str] = None
        page_size = min(max_results, 100)

        while len(issues) < max_results:
            payload: dict[str, object] = {
                "jql": jql,
                "maxResults": page_size,
                "fields": selected_fields,
            }
            if next_page_token:
                payload["nextPageToken"] = next_page_token

            response = self._request(
                "POST",
                "/rest/api/3/search/jql",
                json=payload,
            )

            if response.status_code == 401:
                raise ValueError("Jira authentication failed. Check your Jira credentials.")
            if response.status_code == 400:
                raise ValueError(f"Invalid Jira JQL query: {response.text}")
            if response.status_code >= 400:
                raise ValueError(f"Failed to search Jira issues: {response.text}")

            payload_response = response.json()
            batch = [self._parse_issue(item) for item in payload_response.get("issues", [])]
            issues.extend(batch)

            fetched = len(batch)
            next_page_token = payload_response.get("nextPageToken")
            is_last = payload.get("isLast")

            if fetched == 0 or is_last is True or not next_page_token:
                break

        return issues[:max_results]

    def create_issue(
        self,
        project: str,
        summary: str,
        issue_type: str,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        labels: Optional[list[str]] = None,
    ) -> JiraIssue:
        """Create a Jira issue and return its hydrated DTO."""
        fields_payload: dict[str, object] = {
            "project": {"key": project},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }

        if description:
            fields_payload["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            }
        if priority:
            fields_payload["priority"] = {"name": priority}
        if labels:
            fields_payload["labels"] = labels

        response = self._request("POST", "/rest/api/3/issue", json={"fields": fields_payload})

        if response.status_code == 401:
            raise ValueError("Jira authentication failed. Check your Jira credentials.")
        if response.status_code == 404:
            raise ValueError(f"Jira project '{project}' was not found.")
        if response.status_code == 400:
            raise ValueError(f"Invalid Jira issue fields: {response.text}")
        if response.status_code >= 400:
            raise ValueError(f"Failed to create Jira issue: {response.text}")

        issue_key = response.json().get("key")
        if not issue_key:
            raise ValueError("Jira issue was created but no issue key was returned.")

        return self._get_issue(issue_key)

    def get_transitions(self, issue_key: str) -> list[JiraTransition]:
        """Fetch available transitions for a Jira issue."""
        response = self._request("GET", f"/rest/api/3/issue/{issue_key}/transitions")

        if response.status_code == 401:
            raise ValueError("Jira authentication failed. Check your Jira credentials.")
        if response.status_code == 404:
            raise ValueError(f"Jira issue '{issue_key}' was not found.")
        if response.status_code >= 400:
            raise ValueError(f"Failed to fetch Jira transitions for '{issue_key}': {response.text}")

        return [
            JiraTransition(id=item.get("id", ""), name=item.get("name", ""))
            for item in response.json().get("transitions", [])
        ]

    def transition_issue(self, issue_key: str, transition_id: str) -> bool:
        """Transition a Jira issue to a new state."""
        response = self._request(
            "POST",
            f"/rest/api/3/issue/{issue_key}/transitions",
            json={"transition": {"id": transition_id}},
        )

        if response.status_code == 401:
            raise ValueError("Jira authentication failed. Check your Jira credentials.")
        if response.status_code == 404:
            raise ValueError(f"Jira issue '{issue_key}' was not found.")
        if response.status_code == 400:
            raise ValueError(
                f"Transition '{transition_id}' is not available for Jira issue '{issue_key}'."
            )
        if response.status_code >= 400:
            raise ValueError(f"Failed to transition Jira issue '{issue_key}': {response.text}")

        return response.status_code in (200, 204)
