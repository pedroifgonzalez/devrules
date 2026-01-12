"""Abstract prompter interface for CLI interactions.

This module defines the abstract base class for different prompting strategies
(e.g., Gum, Typer) used throughout the devrules CLI.
"""

from abc import ABC, abstractmethod
from typing import Optional

from typing_extensions import NoReturn


class Prompter(ABC):
    """Abstract base class for CLI prompting strategies.

    Implementations should provide concrete methods for interactive CLI prompts
    using either Gum (enhanced terminal UI) or Typer (fallback) strategies.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the prompting strategy is available.

        Returns:
            True if the strategy can be used, False otherwise.
        """
        pass

    @abstractmethod
    def confirm(self, message: str, default: bool = False) -> bool:
        """Show a yes/no confirmation dialog.

        Args:
            message: The confirmation question to display
            default: Default value if user just presses enter

        Returns:
            True if user confirmed, False otherwise
        """
        pass

    @abstractmethod
    def choose(
        self,
        options: list[str],
        header: str = "",
        limit: int = 1,
    ) -> Optional[str | list[str]]:
        """Interactive selection from a list of options.

        Args:
            options: List of options to choose from
            header: Header text to display above choices
            limit: Number of selections allowed (1 for single, 0 for unlimited)

        Returns:
            Selected option(s) as string (if limit=1) or list of strings (if limit>1),
            or None if cancelled
        """
        pass

    @abstractmethod
    def input_text(
        self,
        placeholder: str = "",
        header: str = "",
        default: str = "",
        char_limit: int = 0,
    ) -> Optional[str]:
        """Get single-line text input from user.

        Args:
            placeholder: Placeholder text to show
            header: Header text to display
            default: Default value to pre-fill
            char_limit: Maximum characters allowed (0 for unlimited)

        Returns:
            User input string or None if cancelled
        """
        pass

    @abstractmethod
    def write(
        self,
        placeholder: str = "",
        header: str = "",
        char_limit: int = 0,
        default: str = "",
    ) -> Optional[str]:
        """Get multi-line text input from user.

        Args:
            placeholder: Placeholder text to show
            header: Header text to display
            char_limit: Maximum characters allowed (0 for unlimited)
            default: Default value to pre-fill

        Returns:
            User input string or None if cancelled
        """
        pass

    @abstractmethod
    def filter_list(
        self,
        options: list[str],
        placeholder: str = "Search...",
        header: str = "",
    ) -> Optional[str]:
        """Interactive fuzzy filter through a list.

        Args:
            options: List of options to filter through
            placeholder: Search placeholder text
            header: Header text to display

        Returns:
            Selected option or None if cancelled
        """
        pass

    @abstractmethod
    def style(
        self,
        text: str,
        foreground: Optional[int] = None,
        background: Optional[int] = None,
        bold: bool = False,
        italic: bool = False,
    ) -> str:
        """Style text with colors and formatting.

        Args:
            text: Text to style
            foreground: Foreground color (256-color palette)
            background: Background color
            bold: Whether to make text bold
            italic: Whether to make text italic

        Returns:
            Styled text string (or original text if styling not available)
        """
        pass

    @abstractmethod
    def print_styled(
        self,
        text: str,
        foreground: Optional[int] = None,
        bold: bool = False,
    ) -> None:
        """Print styled text to terminal.

        Args:
            text: Text to print
            foreground: Foreground color
            bold: Whether to make text bold
        """
        pass

    @abstractmethod
    def success(self, message: str) -> None:
        """Print a success message (typically green with checkmark).

        Args:
            message: Success message to display
        """
        pass

    @abstractmethod
    def error(self, message: str) -> None:
        """Print an error message (typically red with X mark).

        Args:
            message: Error message to display
        """
        pass

    @abstractmethod
    def warning(self, message: str) -> None:
        """Print a warning message (typically yellow with warning symbol).

        Args:
            message: Warning message to display
        """
        pass

    @abstractmethod
    def info(self, message: str) -> None:
        """Print an info message (typically cyan with info symbol).

        Args:
            message: Info message to display
        """
        pass

    @abstractmethod
    def exit(self, code: int) -> NoReturn:
        """Exit the program with the given exit code.

        Args:
            code: Exit code
        """
        raise SystemExit(code)

    @abstractmethod
    def header(self, header: str) -> None:
        """Display a header

        Args:
            header (str): Header content message
        """
        pass


__all__ = ["Prompter"]
