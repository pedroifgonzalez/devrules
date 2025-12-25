import functools
from typing import Callable, TypeVar, cast

from typing_extensions import ParamSpec

from devrules.core.git_service import ensure_git_repo as ensure_git_repo_

P = ParamSpec("P")
T = TypeVar("T")


def ensure_git_repo() -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator that ensures the function is being called from within a Git repository.

    Raises:
        typer.Exit: If not in a Git repository
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            ensure_git_repo_()
            return func(*args, **kwargs)

        return cast(Callable[P, T], wrapper)

    return decorator
