"""Spinner context utilities. Allow to set, get and update spinner text"""

from contextvars import ContextVar

from yaspin.core import Spinner

spinner_var: ContextVar[Spinner | None] = ContextVar("spinner_var", default=None)


def set_spinner(spinner: Spinner) -> None:
    """Set the spinner"""
    spinner_var.set(spinner)


def get_spinner() -> Spinner | None:
    """Get the spinner"""
    spinner = spinner_var.get()
    return spinner


def update_spinner_text(text: str) -> None:
    """Update the spinner text"""
    spinner = get_spinner()
    if spinner:
        spinner.text = text
    return


def stop_spinner():
    """Stop the spinner"""
    spinner = get_spinner()
    if spinner:
        spinner.stop()
    return
