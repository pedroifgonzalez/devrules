from .dispatcher import NotificationDispatcher
from .events import NotificationEvent

_dispatcher: NotificationDispatcher | None = None


def configure(dispatcher: NotificationDispatcher) -> None:
    global _dispatcher
    _dispatcher = dispatcher


def emit(event: NotificationEvent) -> None:
    if _dispatcher is None:
        return  # notifications disabled or not configured
    _dispatcher.dispatch(event)
