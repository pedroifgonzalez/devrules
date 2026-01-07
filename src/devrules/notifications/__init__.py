"""Notifications package for DevRules."""

from .dispatcher import NotificationDispatcher
from .events import NotificationEvent

_dispatcher: NotificationDispatcher | None = None


def configure(dispatcher: NotificationDispatcher) -> None:
    """Configure the notification dispatcher."""
    global _dispatcher
    _dispatcher = dispatcher


def emit(event: NotificationEvent) -> None:
    """Emit a notification event."""
    if _dispatcher is None:
        return  # notifications disabled or not configured
    _dispatcher.dispatch(event)
