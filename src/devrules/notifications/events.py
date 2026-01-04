"""Notification events definitions."""

from dataclasses import dataclass
from typing import Protocol


class NotificationEvent(Protocol):
    """Protocol for all notification events."""

    type: str


@dataclass(frozen=True)
class DeployEvent(NotificationEvent):
    """Event triggered during deployment."""

    repo: str
    branch: str
    environment: str
    author: str
    type: str = "deploy"
