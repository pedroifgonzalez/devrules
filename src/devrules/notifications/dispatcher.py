from typing import Iterable

from devrules.notifications.channels.base import NotificationChannel
from devrules.notifications.events import NotificationEvent


class NotificationDispatcher:
    def __init__(self, channels: Iterable[NotificationChannel]):
        self.channels = list(channels)

    def dispatch(self, event: NotificationEvent) -> None:
        for channel in self.channels:
            if channel.supports(event):
                channel.send(event)
