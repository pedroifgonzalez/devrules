from abc import ABC, abstractmethod

from devrules.notifications.events import NotificationEvent


class NotificationChannel(ABC):
    @abstractmethod
    def supports(self, event: NotificationEvent) -> bool:
        """Return True if this channel handles this event type."""

    @abstractmethod
    def send(self, event: NotificationEvent) -> None:
        """Deliver the event."""
