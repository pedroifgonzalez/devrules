"""Gum-based prompter implementation for enhanced terminal UI."""

from typing import Optional

from typing_extensions import NoReturn

from devrules.cli_commands.prompters import Prompter
from devrules.utils import gum


class GumPrompter(Prompter):
    """Gum-based prompting strategy for enhanced terminal UI.

    This implementation wraps the existing gum utility functions to provide
    a rich, interactive CLI experience when the gum binary is available.
    """

    def is_available(self) -> bool:
        """Check if gum is installed and available."""
        return gum.is_available()

    def confirm(self, message: str, default: bool = False) -> bool:
        """Show a yes/no confirmation dialog using gum.

        Args:
            message: The confirmation question to display
            default: Default value if user just presses enter

        Returns:
            True if user confirmed, False otherwise
        """
        result = gum.confirm(message, default)
        # gum.confirm returns None if gum is not available
        return result if result is not None else default

    def choose(
        self,
        options: list[str],
        header: str = "",
        limit: int = 1,
    ) -> Optional[str | list[str]]:
        """Interactive selection from a list of options using gum.

        Args:
            options: List of options to choose from
            header: Header text to display above choices
            limit: Number of selections allowed (1 for single, 0 for unlimited)

        Returns:
            Selected option(s) as string (if limit=1) or list of strings (if limit>1),
            or None if cancelled
        """
        return gum.choose(options, header, limit)

    def input_text(
        self,
        placeholder: str = "",
        header: str = "",
        default: str = "",
        char_limit: int = 0,
    ) -> Optional[str]:
        """Get single-line text input from user using gum.

        Args:
            placeholder: Placeholder text to show
            header: Header text to display
            default: Default value to pre-fill
            char_limit: Maximum characters allowed (0 for unlimited)

        Returns:
            User input string or None if cancelled
        """
        return gum.input_text(placeholder, header, default, char_limit)

    def write(
        self,
        placeholder: str = "",
        header: str = "",
        char_limit: int = 0,
        default: str = "",
    ) -> Optional[str]:
        """Get multi-line text input from user using gum.

        Args:
            placeholder: Placeholder text to show
            header: Header text to display
            char_limit: Maximum characters allowed (0 for unlimited)
            default: Default value to pre-fill

        Returns:
            User input string or None if cancelled
        """
        return gum.write(placeholder, header, char_limit, default)

    def filter_list(
        self,
        options: list[str],
        placeholder: str = "Search...",
        header: str = "",
    ) -> Optional[str]:
        """Interactive fuzzy filter through a list using gum.

        Args:
            options: List of options to filter through
            placeholder: Search placeholder text
            header: Header text to display

        Returns:
            Selected option or None if cancelled
        """
        return gum.filter_list(options, placeholder, header)

    def style(
        self,
        text: str,
        foreground: Optional[int] = None,
        background: Optional[int] = None,
        bold: bool = False,
        italic: bool = False,
    ) -> str:
        """Style text with colors and formatting using gum.

        Args:
            text: Text to style
            foreground: Foreground color (256-color palette)
            background: Background color
            bold: Whether to make text bold
            italic: Whether to make text italic

        Returns:
            Styled text string
        """
        return gum.style(
            text,
            foreground=foreground,
            background=background,
            bold=bold,
            italic=italic,
        )

    def print_styled(
        self,
        text: str,
        foreground: Optional[int] = None,
        bold: bool = False,
    ) -> None:
        """Print styled text to terminal using gum.

        Args:
            text: Text to print
            foreground: Foreground color
            bold: Whether to make text bold
        """
        gum.print_styled(text, foreground, bold)

    def success(self, message: str) -> None:
        """Print a success message (green with checkmark).

        Args:
            message: Success message to display
        """
        gum.success(message)

    def error(self, message: str) -> None:
        """Print an error message (red with X mark).

        Args:
            message: Error message to display
        """
        gum.error(message)

    def warning(self, message: str) -> None:
        """Print a warning message (yellow with warning symbol).

        Args:
            message: Warning message to display
        """
        gum.warning(message)

    def info(self, message: str) -> None:
        """Print an info message (cyan with info symbol).

        Args:
            message: Info message to display
        """
        gum.info(message)

    def exit(self, code: int) -> NoReturn:
        """Exit the program with a given exit code.

        Args:
            code: Exit code
        """
        raise SystemExit(code)
