"""Notification dispatcher for sending events to multiple channels."""

import logging
from typing import Iterable

from devrules.notifications.channels.base import NotificationChannel
from devrules.notifications.events import NotificationEvent

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Dispatches notification events to registered channels."""

    def __init__(self, channels: Iterable[NotificationChannel]):
        """Initialize the notification dispatcher."""
        self.channels = list(channels)

    def dispatch(self, event: NotificationEvent) -> None:
        """Dispatch a notification event."""
        for channel in self.channels:
            if channel.supports(event):
                try:
                    channel.send(event)
                except Exception:
                    logger.exception("Failed to send notification via %s", type(channel).__name__)
