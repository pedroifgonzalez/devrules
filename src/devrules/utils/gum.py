"""Gum utilities for enhanced terminal UI.

Provides glamorous terminal interactions using Charmbracelet's gum tool.
Falls back to standard input methods if gum is not installed.
"""

import shutil
import subprocess
from typing import Optional

# Check if gum is available
GUM_AVAILABLE = shutil.which("gum") is not None


def is_available() -> bool:
    """Check if gum is installed and available."""
    return GUM_AVAILABLE


def choose(
    options: list[str],
    header: str = "",
    limit: int = 1,
) -> Optional[str | list[str]]:
    """Interactive selection from a list of options.

    Args:
        options: List of options to choose from
        header: Header text to display above choices
        limit: Number of selections allowed (0 for unlimited)

    Returns:
        Selected option(s) or None if cancelled
    """
    if not GUM_AVAILABLE or not options:
        return None

    cmd = ["gum", "choose"]
    if header:
        cmd.extend(["--header", header])
    if limit == 0:
        cmd.append("--no-limit")
    elif limit > 1:
        cmd.extend(["--limit", str(limit)])
    cmd.extend(options)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        output = result.stdout.strip()
        if limit == 1:
            return output
        return output.split("\n") if output else []
    except Exception:
        return None


def input_text(
    placeholder: str = "",
    header: str = "",
    default: str = "",
    char_limit: int = 0,
) -> Optional[str]:
    """Get text input from user.

    Args:
        placeholder: Placeholder text
        header: Header text
        default: Default value
        char_limit: Maximum characters (0 for unlimited)

    Returns:
        User input or None if cancelled
    """
    if not GUM_AVAILABLE:
        return None

    cmd = ["gum", "input"]
    if placeholder:
        cmd.extend(["--placeholder", placeholder])
    if header:
        cmd.extend(["--header", header])
    if default:
        cmd.extend(["--value", default])
    if char_limit > 0:
        cmd.extend(["--char-limit", str(char_limit)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception:
        return None


def write(
    placeholder: str = "",
    header: str = "",
    char_limit: int = 0,
) -> Optional[str]:
    """Multi-line text input.

    Args:
        placeholder: Placeholder text
        header: Header text
        char_limit: Maximum characters (0 for unlimited)

    Returns:
        User input or None if cancelled
    """
    if not GUM_AVAILABLE:
        return None

    cmd = ["gum", "write"]
    if placeholder:
        cmd.extend(["--placeholder", placeholder])
    if header:
        cmd.extend(["--header", header])
    if char_limit > 0:
        cmd.extend(["--char-limit", str(char_limit)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception:
        return None


def confirm(message: str, default: bool = False) -> Optional[bool]:
    """Show confirmation dialog.

    Args:
        message: Confirmation message
        default: Default value if user presses enter

    Returns:
        True/False or None if gum not available
    """
    if not GUM_AVAILABLE:
        return None

    cmd = ["gum", "confirm", message]
    if default:
        cmd.append("--default=yes")

    try:
        result = subprocess.run(cmd)
        return result.returncode == 0
    except Exception:
        return None


def spin(title: str, command: list[str]) -> int:
    """Run command with a spinner.

    Args:
        title: Spinner title
        command: Command to run

    Returns:
        Exit code of the command
    """
    if not GUM_AVAILABLE:
        # Fall back to running command directly
        result = subprocess.run(command)
        return result.returncode

    cmd = ["gum", "spin", "--spinner", "dot", "--title", title, "--"] + command

    try:
        result = subprocess.run(cmd)
        return result.returncode
    except Exception:
        # Fall back to running command directly
        result = subprocess.run(command)
        return result.returncode


def filter_list(
    options: list[str],
    placeholder: str = "Search...",
    header: str = "",
) -> Optional[str]:
    """Interactive fuzzy filter through a list.

    Args:
        options: List of options to filter
        placeholder: Search placeholder
        header: Header text

    Returns:
        Selected option or None if cancelled
    """
    if not GUM_AVAILABLE or not options:
        return None

    cmd = ["gum", "filter"]
    if placeholder:
        cmd.extend(["--placeholder", placeholder])
    if header:
        cmd.extend(["--header", header])

    try:
        result = subprocess.run(
            cmd,
            input="\n".join(options),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception:
        return None


def style(
    text: str,
    foreground: Optional[int] = None,
    background: Optional[int] = None,
    bold: bool = False,
    italic: bool = False,
    border: Optional[str] = None,
    border_foreground: Optional[int] = None,
    padding: Optional[str] = None,
    margin: Optional[str] = None,
) -> str:
    """Style text with colors and formatting.

    Args:
        text: Text to style
        foreground: Foreground color (256-color palette)
        background: Background color
        bold: Bold text
        italic: Italic text
        border: Border style (rounded, double, thick, normal, hidden)
        border_foreground: Border color
        padding: Padding (e.g., "1 2" for vertical horizontal)
        margin: Margin (e.g., "1" for all sides)

    Returns:
        Styled text or original text if gum not available
    """
    if not GUM_AVAILABLE:
        return text

    cmd = ["gum", "style"]
    if foreground is not None:
        cmd.extend(["--foreground", str(foreground)])
    if background is not None:
        cmd.extend(["--background", str(background)])
    if bold:
        cmd.append("--bold")
    if italic:
        cmd.append("--italic")
    if border:
        cmd.extend(["--border", border])
    if border_foreground is not None:
        cmd.extend(["--border-foreground", str(border_foreground)])
    if padding:
        cmd.extend(["--padding", padding])
    if margin:
        cmd.extend(["--margin", margin])
    cmd.append(text)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.rstrip("\n")
    except Exception:
        return text


def print_styled(
    text: str,
    foreground: Optional[int] = None,
    bold: bool = False,
) -> None:
    """Print styled text to terminal.

    Args:
        text: Text to print
        foreground: Foreground color
        bold: Bold text
    """
    if GUM_AVAILABLE:
        styled = style(text, foreground=foreground, bold=bold)
        print(styled)
    else:
        print(text)


# Convenience functions for common styles
def success(message: str) -> None:
    """Print success message (green)."""
    print_styled(f"✔ {message}", foreground=82, bold=True)


def error(message: str) -> None:
    """Print error message (red)."""
    print_styled(f"✘ {message}", foreground=196, bold=True)


def warning(message: str) -> None:
    """Print warning message (yellow)."""
    print_styled(f"⚠ {message}", foreground=214)


def info(message: str) -> None:
    """Print info message (cyan)."""
    print_styled(f"ℹ {message}", foreground=81)
