"""Notification dispatcher for sending events to multiple channels."""

from typing import Iterable

from loguru import logger

from devrules.notifications.channels.base import NotificationChannel
from devrules.notifications.events import NotificationEvent


class NotificationDispatcher:
    """Dispatches notification events to registered channels."""

    def __init__(self, channels: Iterable[NotificationChannel]):
        """Initialize the notification dispatcher."""
        self.channels = list(channels)

    def dispatch(self, event: NotificationEvent) -> None:
        """Dispatch a notification event."""
        logger.debug(f"Dispatching event: {event}")
        for channel in self.channels:
            if channel.supports(event):
                try:
                    channel.send(event)
                except Exception:
                    logger.exception("Failed to send notification via %s", type(channel).__name__)
