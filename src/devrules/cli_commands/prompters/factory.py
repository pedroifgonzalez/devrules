"""Factory for creating the appropriate prompter instance."""

from devrules.cli_commands.prompters import Prompter
from devrules.cli_commands.prompters.gum_prompter import GumPrompter
from devrules.cli_commands.prompters.typer_prompter import TyperPrompter


def get_prompter() -> Prompter:
    """Get the best available prompter strategy.

    Returns GumPrompter if gum is installed and available,
    otherwise falls back to TyperPrompter.

    Returns:
        Prompter instance (GumPrompter or TyperPrompter)
    """
    gum_prompter = GumPrompter()
    if gum_prompter.is_available():
        return gum_prompter
    return TyperPrompter()


# Singleton instance for convenience
_prompter_instance: Prompter | None = None


def get_default_prompter() -> Prompter:
    """Get the default prompter instance (singleton).

    This creates a single prompter instance that is reused across
    the application to avoid repeated availability checks.

    Returns:
        Prompter instance (singleton)
    """
    global _prompter_instance
    if _prompter_instance is None:
        _prompter_instance = get_prompter()
    return _prompter_instance
