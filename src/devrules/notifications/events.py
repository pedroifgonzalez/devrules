from dataclasses import dataclass


class NotificationEvent:
    """Base class for all notification events."""

    type: str


@dataclass(frozen=True)
class DeployEvent(NotificationEvent):
    branch: str
    environment: str
    author: str
    type: str = "deploy"
