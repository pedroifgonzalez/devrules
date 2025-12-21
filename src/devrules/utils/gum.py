"""Gum utilities for enhanced terminal UI.

Provides glamorous terminal interactions using Charmbracelet's gum tool.
Falls back to standard input methods if gum is not installed.
"""

import shutil
import subprocess
from typing import Optional

from devrules.utils.history import get_history_manager

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
        # Don't capture stderr so user sees the interactive UI
        result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
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
        # Don't capture stderr so user sees the interactive UI
        result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
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
        # Don't capture stderr so user sees the interactive UI
        result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception:
        return None


def input_text_with_history(
    prompt_type: str,
    placeholder: str = "",
    header: str = "",
    default: str = "",
    char_limit: int = 0,
    save_to_history: bool = True,
) -> Optional[str]:
    """Get text input from user with history suggestions.

    Shows recent history entries as suggestions using gum filter if history exists,
    otherwise falls back to regular input.

    Args:
        prompt_type: Type of prompt for history tracking (e.g., 'branch_description')
        placeholder: Placeholder text
        header: Header text
        default: Default value
        char_limit: Maximum characters (0 for unlimited)
        save_to_history: Whether to save the result to history

    Returns:
        User input or None if cancelled
    """
    if not GUM_AVAILABLE:
        return None

    history_manager = get_history_manager()
    recent = history_manager.get_recent(prompt_type, limit=10)

    # If we have history, use filter for suggestions
    if recent:
        # Add a special option to enter new value
        options = ["[Enter new value]"] + recent

        # Show filter with history
        cmd = ["gum", "filter", "--placeholder", placeholder or "Search or type new value..."]
        if header:
            cmd.extend(["--header", header])

        try:
            result = subprocess.run(
                cmd,
                input="\n".join(options),
                stdout=subprocess.PIPE,
                text=True,
            )

            if result.returncode != 0:
                return None

            selected = result.stdout.strip()

            # Determine default value for input
            input_default = default
            if selected != "[Enter new value]":
                input_default = selected

            # Always show input prompt, pre-filled with selected history item (or default)
            new_value = input_text(
                placeholder=placeholder,
                header=header or "Edit value:",
                default=input_default,
                char_limit=char_limit,
            )

            if new_value and save_to_history:
                history_manager.add_entry(prompt_type, new_value)

            return new_value

        except Exception:
            # Fall back to regular input
            pass

    # No history or filter failed - use regular input
    regular_input_result = input_text(
        placeholder=placeholder,
        header=header,
        default=default,
        char_limit=char_limit,
    )

    if regular_input_result and save_to_history:
        history_manager.add_entry(prompt_type, regular_input_result)

    if regular_input_result:
        return str(regular_input_result)
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
        # Don't capture stderr so user sees the interactive UI
        result = subprocess.run(
            cmd,
            input="\n".join(options),
            stdout=subprocess.PIPE,
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


def table(
    rows: list[list[str]],
    headers: list[str] | None = None,
    border: str = "rounded",
    border_foreground: int = 99,
) -> str:
    """Render a table using gum format.

    Args:
        rows: List of rows, each row is a list of cell values
        headers: Optional header row
        border: Border style (rounded, double, thick, normal, hidden)
        border_foreground: Border color

    Returns:
        Formatted table string
    """
    if not GUM_AVAILABLE or not rows:
        # Fallback to simple ASCII table
        return _simple_table(rows, headers)

    # Build CSV-like input for gum table (data rows only, headers via --columns)
    all_rows = []
    for row in rows:
        all_rows.append(",".join(f'"{cell}"' for cell in row))

    csv_input = "\n".join(all_rows)

    cmd = ["gum", "table", "--print"]  # -p for static print
    if headers:
        cmd.extend(["--columns", ",".join(headers)])
    if border:
        cmd.extend(["--border", border])
    if border_foreground:
        cmd.extend(["--border.foreground", str(border_foreground)])

    try:
        result = subprocess.run(
            cmd,
            input=csv_input,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.rstrip("\n")
    except Exception:
        pass

    return _simple_table(rows, headers)


def _simple_table(rows: list[list[str]], headers: list[str] | None = None) -> str:
    """Simple ASCII table fallback."""
    if not rows:
        return ""

    # Calculate column widths
    all_rows = [headers] + rows if headers else rows
    col_widths = []
    for col_idx in range(len(all_rows[0])):
        max_width = max(len(str(row[col_idx])) for row in all_rows if col_idx < len(row))
        col_widths.append(max_width)

    lines = []

    # Header
    if headers:
        header_line = " │ ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
        lines.append(f"│ {header_line} │")
        separator = "─┼─".join("─" * w for w in col_widths)
        lines.append(f"├─{separator}─┤")

    # Rows
    for row in rows:
        row_line = " │ ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
        lines.append(f"│ {row_line} │")

    return "\n".join(lines)


def print_table(
    rows: list[list[str]],
    headers: list[str] | None = None,
    border: str = "rounded",
    border_foreground: int = 99,
) -> None:
    """Print a formatted table.

    Args:
        rows: List of rows
        headers: Optional headers
        border: Border style
        border_foreground: Border color
    """
    print(table(rows, headers, border, border_foreground))


def print_stick_header(header: str):
    print(style(header, foreground=81, bold=True))
    print(style("=" * 50, foreground=81))


def print_list(header: str, items: list[str]):
    print_styled(header)
    for item in items:
        print_styled(item)
