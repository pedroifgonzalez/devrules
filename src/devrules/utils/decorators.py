"""Decorators for CLI commands and services."""

import functools
from typing import Callable, TypeVar, cast

from typing_extensions import ParamSpec

from devrules.core.events_engine import attach_event
from devrules.core.git_service import ensure_git_repo as ensure_git_repo_
from devrules.core.rules_engine import RuleDefinition, execute_rule, prompt_for_rule_arguments

P = ParamSpec("P")
T = TypeVar("T")


def ensure_git_repo() -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator that ensures the function is being called from within a Git repository.

    Raises:
        typer.Exit: If not in a Git repository
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        """Decorator that ensures the function is being called from within a Git repository."""

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            """Decorator that ensures the function is being called from within a Git repository."""
            ensure_git_repo_()
            return func(*args, **kwargs)

        return cast(Callable[P, T], wrapper)

    return decorator


def emit_event(event: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator that emits an event for running custom rules hooked to that event
    """
    from devrules.cli_commands.prompters.factory import get_default_prompter

    prompter = get_default_prompter()

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        """Decorator that ensures the function is being called from within a Git repository."""

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            """Decorator that ensures the function is being called from within a Git repository."""
            custom_rules: list[RuleDefinition] = attach_event(event)
            for custom_rule in custom_rules:
                prompter.info(f"Running custom rule: {custom_rule.name}")
                prompted_kwargs = prompt_for_rule_arguments(custom_rule.name)
                valid, message = execute_rule(custom_rule.name, **prompted_kwargs)
                if not valid:
                    prompter.error(message)
                    prompter.exit(1)
                prompter.success(message)
            return func(*args, **kwargs)

        return cast(Callable[P, T], wrapper)

    return decorator
