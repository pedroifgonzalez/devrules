"""Jira related DTOs."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class JiraIssue:
    """Jira issue data structure."""

    key: str
    summary: str
    status: str
    assignee: Optional[str] = None
    issue_type: str = ""
    priority: Optional[str] = None
    labels: list[str] = field(default_factory=list)
    url: str = ""
    created: Optional[str] = None
    updated: Optional[str] = None


@dataclass
class JiraTransition:
    """Jira transition data structure."""

    id: str
    name: str
