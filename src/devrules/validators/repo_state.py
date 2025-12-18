"""Repository state validation."""

import subprocess
from collections import OrderedDict
from typing import Callable, Tuple

import typer


def check_uncommitted_changes() -> Tuple[bool, str]:
    """Check if there are uncommitted changes in the repository.

    Returns:
        Tuple of (has_changes, message)
    """
    try:
        # Check for staged changes
        result_staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            capture_output=True,
        )

        # Check for unstaged changes
        result_unstaged = subprocess.run(
            ["git", "diff", "--quiet"],
            capture_output=True,
        )

        # Check for untracked files
        result_untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
        )

        has_staged = result_staged.returncode != 0
        has_unstaged = result_unstaged.returncode != 0
        has_untracked = bool(result_untracked.stdout.strip())

        if any([has_staged, has_unstaged, has_untracked]):
            changes = []
            if has_staged:
                changes.append("staged changes")
            if has_unstaged:
                changes.append("unstaged changes")
            if has_untracked:
                changes.append("untracked files")

            message = f"Repository has uncommitted {', '.join(changes)}"
            return True, message

        return False, "Working tree is clean"

    except subprocess.CalledProcessError as e:
        return False, f"Error checking repository state: {e}"


def check_behind_remote(branch: str = "HEAD") -> Tuple[bool, str]:
    """Check if local branch is behind remote.

    Args:
        branch: Branch name to check (defaults to current branch)

    Returns:
        Tuple of (is_behind, message)
    """
    try:
        # Get current branch if HEAD specified
        if branch == "HEAD":
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            branch = result.stdout.strip()

        # Fetch latest from remote (quietly)
        subprocess.run(
            ["git", "fetch", "--quiet"],
            capture_output=True,
            check=False,  # Don't fail if no remote
        )

        # Check if remote branch exists
        remote_check = subprocess.run(
            ["git", "rev-parse", "--verify", f"origin/{branch}"],
            capture_output=True,
        )

        if remote_check.returncode != 0:
            # No remote branch, can't be behind
            return False, f"No remote branch 'origin/{branch}' found"

        # Get commits behind
        result = subprocess.run(
            ["git", "rev-list", "--count", f"HEAD..origin/{branch}"],
            capture_output=True,
            text=True,
            check=True,
        )

        commits_behind = int(result.stdout.strip())

        if commits_behind > 0:
            message = f"Local branch is {commits_behind} commit(s) behind origin/{branch}"
            return True, message

        return False, "Local branch is up to date with remote"

    except subprocess.CalledProcessError as e:
        return False, f"Error checking remote status: {e}"
    except ValueError:
        return False, "Error parsing git output"


def validate_repo_state(
    check_uncommitted: bool = True,
    check_behind: bool = True,
    warn_only: bool = False,
) -> Tuple[bool, list]:
    """Validate repository state before operations.

    Args:
        check_uncommitted: Whether to check for uncommitted changes
        check_behind: Whether to check if behind remote
        warn_only: If True, return warnings instead of errors
        branch: Branch to check (defaults to current)

    Returns:
        Tuple of (is_valid, list_of_messages)
    """
    messages = []
    has_issues = False

    MAP_CHECKINGS: dict[str, tuple[bool, Callable]] = OrderedDict(
        {
            "\n🆕 Checking uncommitted changes": (check_uncommitted, check_uncommitted_changes),
            "\n🏎️ Checking behind HEAD": (check_behind, check_behind_remote),
        }
    )

    for label, (check, func) in MAP_CHECKINGS.items():
        if check:
            typer.echo(label)
            issues, msg = func()
            if issues:
                has_issues = True
                messages.append(f"⚠️  {msg}")
                break

    if not has_issues:
        messages.append("✅ Repository state is clean")
        return True, messages

    if warn_only:
        return True, messages

    return False, messages


def display_repo_state_issues(messages: list, warn_only: bool = False) -> None:
    """Display repository state issues to user.

    Args:
        messages: List of issue messages
        warn_only: Whether these are warnings or errors
    """
    if not messages:
        return

    color = typer.colors.YELLOW if warn_only else typer.colors.RED
    prefix = "⚠️  Warning" if warn_only else "❌ Error"

    typer.secho(f"\n{prefix}: Repository state check", fg=color, bold=True)
    for msg in messages:
        typer.echo(f"  {msg}")

    if not warn_only:
        typer.echo("\n💡 Suggestions:")
        typer.echo("  • Commit or stash your changes: git stash")
        typer.echo("  • Pull latest changes: git pull")
        typer.echo("  • Or use --skip-checks to bypass (not recommended)")
