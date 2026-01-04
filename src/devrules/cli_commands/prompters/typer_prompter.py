"""Typer-based prompter implementation as fallback."""

from typing import Optional

import typer
from typing_extensions import NoReturn

from devrules.cli_commands.prompters import Prompter


class TyperPrompter(Prompter):
    """Typer-based prompting strategy as fallback.

    This implementation uses Typer's built-in prompting functions to provide
    a basic but functional CLI experience when gum is not available.
    """

    def is_available(self) -> bool:
        """Typer is always available as it's a core dependency."""
        return True

    def confirm(self, message: str, default: bool = False) -> bool:
        """Show a yes/no confirmation dialog using typer.

        Args:
            message: The confirmation question to display
            default: Default value if user just presses enter

        Returns:
            True if user confirmed, False otherwise
        """
        return typer.confirm(message, default=default)

    def choose(
        self,
        options: list[str],
        header: str = "",
        limit: int = 1,
    ) -> Optional[str | list[str]]:
        """Interactive selection from a list of options using typer.

        Args:
            options: List of options to choose from
            header: Header text to display above choices
            limit: Number of selections allowed (1 for single, 0 for unlimited)

        Returns:
            Selected option(s) as string (if limit=1) or list of strings (if limit>1),
            or None if cancelled
        """
        if not options:
            return None

        if header:
            typer.echo(f"\n{header}")

        for idx, option in enumerate(options, 1):
            typer.echo(f"  {idx}. {option}")

        if limit == 1:
            # Single selection
            try:
                choice = typer.prompt("Enter number", type=int, default=1)
                if 1 <= choice <= len(options):
                    return options[choice - 1]
                else:
                    typer.secho("Invalid selection", fg=typer.colors.RED)
                    return None
            except (ValueError, typer.Abort):
                return None
        else:
            # Multi-selection
            typer.echo("\nEnter numbers separated by spaces (or 'all' for all options):")
            try:
                selection = typer.prompt("Your selection", type=str, default="")

                if selection.lower() == "all":
                    return options if limit == 0 else options[:limit]

                if not selection.strip():
                    return []

                indices = [int(x.strip()) for x in selection.split()]
                selected = []
                for idx in indices:
                    if 1 <= idx <= len(options):
                        selected.append(options[idx - 1])
                    else:
                        typer.secho(f"Invalid selection: {idx}", fg=typer.colors.YELLOW)

                return selected if selected else None
            except (ValueError, typer.Abort):
                return None

    def input_text(
        self,
        placeholder: str = "",
        header: str = "",
        default: str = "",
        char_limit: int = 0,
    ) -> Optional[str]:
        """Get single-line text input from user using typer.

        Args:
            placeholder: Placeholder text to show (displayed as prompt message)
            header: Header text to display
            default: Default value to pre-fill
            char_limit: Maximum characters allowed (0 for unlimited) - not enforced by typer

        Returns:
            User input string or None if cancelled
        """
        if header:
            typer.echo(f"\n{header}")

        prompt_text = placeholder if placeholder else "Enter text"

        try:
            result = typer.prompt(prompt_text, default=default if default else "")

            # Enforce char_limit if specified
            if char_limit > 0 and len(result) > char_limit:
                typer.secho(
                    f"Input exceeds character limit ({char_limit}). Truncating...",
                    fg=typer.colors.YELLOW,
                )
                return result[:char_limit]

            return result if result else None
        except typer.Abort:
            return None

    def write(
        self,
        placeholder: str = "",
        header: str = "",
        char_limit: int = 0,
        default: str = "",
    ) -> Optional[str]:
        """Get multi-line text input from user using typer.

        Note: Typer doesn't natively support multi-line input, so this falls back
        to single-line input with a note to the user.

        Args:
            placeholder: Placeholder text to show
            header: Header text to display
            char_limit: Maximum characters allowed (0 for unlimited)
            default: Default value to pre-fill

        Returns:
            User input string or None if cancelled
        """
        if header:
            typer.echo(f"\n{header}")
        else:
            typer.echo("\nEnter text (multi-line not supported in fallback mode):")

        prompt_text = placeholder if placeholder else "Enter text"

        try:
            result = typer.prompt(prompt_text, default=default if default else "")

            # Enforce char_limit if specified
            if char_limit > 0 and len(result) > char_limit:
                typer.secho(
                    f"Input exceeds character limit ({char_limit}). Truncating...",
                    fg=typer.colors.YELLOW,
                )
                return result[:char_limit]

            return result if result else None
        except typer.Abort:
            return None

    def filter_list(
        self,
        options: list[str],
        placeholder: str = "Search...",
        header: str = "",
    ) -> Optional[str | list[str]]:
        """Interactive fuzzy filter through a list using typer.

        Note: Typer doesn't support fuzzy filtering, so this falls back to
        the choose() method for selection.

        Args:
            options: List of options to filter through
            placeholder: Search placeholder text (not used in typer fallback)
            header: Header text to display

        Returns:
            Selected option or None if cancelled
        """
        # Fallback to choose() since typer doesn't support fuzzy filtering
        return self.choose(options, header or "Select an option:", limit=1)

    def style(
        self,
        text: str,
        foreground: Optional[int] = None,
        background: Optional[int] = None,
        bold: bool = False,
        italic: bool = False,
    ) -> str:
        """Style text with colors and formatting.

        Note: Typer has limited styling support, so this returns the original text.
        Use print_styled() for colored output.

        Args:
            text: Text to style
            foreground: Foreground color (not used in typer)
            background: Background color (not used in typer)
            bold: Whether to make text bold (not used in typer)
            italic: Whether to make text italic (not used in typer)

        Returns:
            Original text (styling not supported in fallback mode)
        """
        # Typer doesn't support returning styled text, only printing it
        return text

    def print_styled(
        self,
        text: str,
        foreground: Optional[int] = None,
        bold: bool = False,
    ) -> None:
        """Print styled text to terminal using typer.

        Args:
            text: Text to print
            foreground: Foreground color (mapped to typer colors)
            bold: Whether to make text bold
        """
        # Map common color codes to typer colors
        color_map = {
            82: typer.colors.GREEN,
            196: typer.colors.RED,
            214: typer.colors.YELLOW,
            81: typer.colors.CYAN,
            212: typer.colors.MAGENTA,
            222: typer.colors.BRIGHT_YELLOW,
        }

        fg_color = color_map.get(foreground) if foreground else None
        typer.secho(text, fg=fg_color, bold=bold)

    def success(self, message: str) -> None:
        """Print a success message (green with checkmark).

        Args:
            message: Success message to display
        """
        typer.secho(f"✔ {message}", fg=typer.colors.GREEN, bold=True)

    def error(self, message: str) -> None:
        """Print an error message (red with X mark).

        Args:
            message: Error message to display
        """
        typer.secho(f"✘ {message}", fg=typer.colors.RED, bold=True)

    def warning(self, message: str) -> None:
        """Print a warning message (yellow with warning symbol).

        Args:
            message: Warning message to display
        """
        typer.secho(f"⚠ {message}", fg=typer.colors.YELLOW)

    def info(self, message: str) -> None:
        """Print an info message (cyan with info symbol).

        Args:
            message: Info message to display
        """
        typer.secho(f"ℹ {message}", fg=typer.colors.CYAN)

    def exit(self, code: int) -> NoReturn:
        """Exit the program with a given exit code.

        Args:
            code: Exit code
        """
        raise typer.Exit(code)
