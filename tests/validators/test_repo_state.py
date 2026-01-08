"""Tests for repository state validation."""

import subprocess
from unittest.mock import MagicMock, patch

from devrules.validators.repo_state import (
    check_behind_remote,
    check_uncommitted_changes,
    display_repo_state_issues,
    validate_repo_state,
)


@patch("devrules.validators.repo_state.subprocess.run")
def test_check_uncommitted_changes_clean(mock_run):
    """Test checking uncommitted changes when repo is clean."""
    # Mock all git commands to return clean state
    mock_run.side_effect = [
        MagicMock(returncode=0),  # git diff --cached (no staged changes)
        MagicMock(returncode=0),  # git diff (no unstaged changes)
        MagicMock(stdout="", returncode=0),  # git ls-files (no untracked)
    ]

    has_changes, message = check_uncommitted_changes()

    assert has_changes is False
    assert "clean" in message.lower()


@patch("devrules.validators.repo_state.subprocess.run")
def test_check_uncommitted_changes_staged(mock_run):
    """Test checking uncommitted changes with staged files."""
    mock_run.side_effect = [
        MagicMock(returncode=1),  # git diff --cached (has staged changes)
        MagicMock(returncode=0),  # git diff (no unstaged changes)
        MagicMock(stdout="", returncode=0),  # git ls-files (no untracked)
    ]

    has_changes, message = check_uncommitted_changes()

    assert has_changes is True
    assert "staged changes" in message.lower()


@patch("devrules.validators.repo_state.subprocess.run")
def test_check_uncommitted_changes_unstaged(mock_run):
    """Test checking uncommitted changes with unstaged files."""
    mock_run.side_effect = [
        MagicMock(returncode=0),  # git diff --cached (no staged changes)
        MagicMock(returncode=1),  # git diff (has unstaged changes)
        MagicMock(stdout="", returncode=0),  # git ls-files (no untracked)
    ]

    has_changes, message = check_uncommitted_changes()

    assert has_changes is True
    assert "unstaged changes" in message.lower()


@patch("devrules.validators.repo_state.subprocess.run")
def test_check_uncommitted_changes_untracked(mock_run):
    """Test checking uncommitted changes with untracked files."""
    mock_run.side_effect = [
        MagicMock(returncode=0),  # git diff --cached (no staged changes)
        MagicMock(returncode=0),  # git diff (no unstaged changes)
        MagicMock(stdout="newfile.txt\n", returncode=0),  # git ls-files (has untracked)
    ]

    has_changes, message = check_uncommitted_changes()

    assert has_changes is True
    assert "untracked files" in message.lower()


@patch("devrules.validators.repo_state.subprocess.run")
def test_check_uncommitted_changes_error(mock_run):
    """Git errors should surface as error messages without crashing."""
    mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd="git diff")

    has_changes, message = check_uncommitted_changes()

    assert has_changes is False
    assert "error checking repository state" in message.lower()


@patch("devrules.validators.repo_state.subprocess.run")
def test_check_uncommitted_changes_multiple(mock_run):
    """Test checking uncommitted changes with multiple types."""
    mock_run.side_effect = [
        MagicMock(returncode=1),  # git diff --cached (has staged changes)
        MagicMock(returncode=1),  # git diff (has unstaged changes)
        MagicMock(stdout="newfile.txt\n", returncode=0),  # git ls-files (has untracked)
    ]

    has_changes, message = check_uncommitted_changes()

    assert has_changes is True
    assert "staged changes" in message.lower()
    assert "unstaged changes" in message.lower()
    assert "untracked files" in message.lower()


@patch("devrules.validators.repo_state.subprocess.run")
def test_check_behind_remote_up_to_date(mock_run):
    """Test checking if behind remote when up to date."""
    mock_run.side_effect = [
        MagicMock(stdout="main\n", returncode=0),  # git rev-parse --abbrev-ref HEAD
        MagicMock(returncode=0),  # git fetch
        MagicMock(returncode=0),  # git rev-parse --verify origin/main
        MagicMock(stdout="0\n", returncode=0),  # git rev-list --count
    ]

    is_behind, message = check_behind_remote()

    assert is_behind is False
    assert "up to date" in message.lower()


@patch("devrules.validators.repo_state.subprocess.run")
def test_check_behind_remote_is_behind(mock_run):
    """Test checking if behind remote when commits are missing."""
    mock_run.side_effect = [
        MagicMock(stdout="main\n", returncode=0),  # git rev-parse --abbrev-ref HEAD
        MagicMock(returncode=0),  # git fetch
        MagicMock(returncode=0),  # git rev-parse --verify origin/main
        MagicMock(stdout="5\n", returncode=0),  # git rev-list --count (5 commits behind)
    ]

    is_behind, message = check_behind_remote()

    assert is_behind is True
    assert "5 commit" in message.lower()
    assert "behind" in message.lower()


@patch("devrules.validators.repo_state.subprocess.run")
def test_check_behind_remote_no_remote_branch(mock_run):
    """Test checking if behind remote when no remote branch exists."""
    mock_run.side_effect = [
        MagicMock(stdout="feature-branch\n", returncode=0),  # git rev-parse --abbrev-ref HEAD
        MagicMock(returncode=0),  # git fetch
        MagicMock(returncode=1),  # git rev-parse --verify (remote branch doesn't exist)
    ]

    is_behind, message = check_behind_remote()

    assert is_behind is False
    assert "no remote branch" in message.lower()


@patch("devrules.validators.repo_state.subprocess.run")
def test_check_behind_remote_git_error(mock_run):
    """Errors while checking remote status should be handled gracefully."""
    mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd="git rev-parse")

    is_behind, message = check_behind_remote()

    assert is_behind is False
    assert "error checking remote status" in message.lower()


@patch("devrules.validators.repo_state.subprocess.run")
def test_check_behind_remote_invalid_output(mock_run):
    """Invalid git output should return a parsing error message."""
    mock_run.side_effect = [
        MagicMock(stdout="main\n", returncode=0),  # rev-parse branch
        MagicMock(returncode=0),  # fetch
        MagicMock(returncode=0),  # rev-parse origin/main
        MagicMock(stdout="not-a-number\n", returncode=0),  # rev-list output invalid
    ]

    is_behind, message = check_behind_remote()

    assert is_behind is False
    assert "error parsing git output" in message.lower()


@patch("devrules.validators.repo_state.subprocess.run")
def test_validate_repo_state_all_clean(mock_run):
    """Test validating repo state when everything is clean."""
    # Mock clean state
    mock_run.side_effect = [
        MagicMock(returncode=0),  # git diff --cached
        MagicMock(returncode=0),  # git diff
        MagicMock(stdout="", returncode=0),  # git ls-files
        MagicMock(stdout="main\n", returncode=0),  # git rev-parse --abbrev-ref HEAD
        MagicMock(returncode=0),  # git fetch
        MagicMock(returncode=0),  # git rev-parse --verify origin/main
        MagicMock(stdout="0\n", returncode=0),  # git rev-list --count
    ]

    is_valid, messages = validate_repo_state(
        check_uncommitted=True,
        check_behind=True,
        warn_only=False,
    )

    assert is_valid is True
    assert any("clean" in msg.lower() for msg in messages)


@patch("devrules.validators.repo_state.subprocess.run")
def test_validate_repo_state_has_issues(mock_run):
    """Test validating repo state when there are issues."""
    # Mock uncommitted changes
    mock_run.side_effect = [
        MagicMock(returncode=1),  # git diff --cached (has changes)
        MagicMock(returncode=0),  # git diff
        MagicMock(stdout="", returncode=0),  # git ls-files
        MagicMock(stdout="main\n", returncode=0),  # git rev-parse --abbrev-ref HEAD
        MagicMock(returncode=0),  # git fetch
        MagicMock(returncode=0),  # git rev-parse --verify origin/main
        MagicMock(stdout="3\n", returncode=0),  # git rev-list --count (3 behind)
    ]

    is_valid, messages = validate_repo_state(
        check_uncommitted=True,
        check_behind=True,
        warn_only=False,
    )

    assert is_valid is False
    assert len(messages) == 1  # One uncommitted change


@patch("devrules.validators.repo_state.subprocess.run")
def test_validate_repo_state_warn_only(mock_run):
    """Test validating repo state with warn_only mode."""
    # Mock uncommitted changes
    mock_run.side_effect = [
        MagicMock(returncode=1),  # git diff --cached (has changes)
        MagicMock(returncode=0),  # git diff
        MagicMock(stdout="", returncode=0),  # git ls-files
        MagicMock(stdout="main\n", returncode=0),  # git rev-parse --abbrev-ref HEAD
        MagicMock(returncode=0),  # git fetch
        MagicMock(returncode=0),  # git rev-parse --verify origin/main
        MagicMock(stdout="0\n", returncode=0),  # git rev-list --count
    ]

    is_valid, messages = validate_repo_state(
        check_uncommitted=True,
        check_behind=True,
        warn_only=True,
    )

    # Should still return valid in warn_only mode
    assert is_valid is True
    assert len(messages) > 0


@patch("devrules.validators.repo_state.subprocess.run")
def test_validate_repo_state_skip_checks(mock_run):
    """Test validating repo state with checks disabled."""
    is_valid, messages = validate_repo_state(
        check_uncommitted=False,
        check_behind=False,
        warn_only=False,
    )

    # Should return valid when no checks are performed
    assert is_valid is True
    assert any("clean" in msg.lower() for msg in messages)

    # Should not call any git commands
    mock_run.assert_not_called()


@patch("devrules.validators.repo_state.typer")
def test_display_repo_state_issues_warn_only(mock_typer):
    """Display helper should format warnings correctly."""
    messages = ["⚠️  Repo has issues"]

    display_repo_state_issues(messages, warn_only=True)

    mock_typer.secho.assert_called_once()
    assert "warning" in mock_typer.secho.call_args[0][0].lower()
    mock_typer.echo.assert_any_call(f"  {messages[0]}")


@patch("devrules.validators.repo_state.typer")
def test_display_repo_state_issues_errors(mock_typer):
    """Display helper should include suggestions when not warn_only."""
    messages = ["⚠️  Repo has issues"]

    display_repo_state_issues(messages, warn_only=False)

    mock_typer.secho.assert_called_once()
    assert "error" in mock_typer.secho.call_args[0][0].lower()
    mock_typer.echo.assert_any_call("  • Commit or stash your changes: git stash")
    mock_typer.echo.assert_any_call("  • Pull latest changes: git pull")


@patch("devrules.validators.repo_state.typer")
def test_display_repo_state_issues_no_messages(mock_typer):
    """Display helper should exit early when there are no messages."""

    display_repo_state_issues([], warn_only=False)

    mock_typer.secho.assert_not_called()
    mock_typer.echo.assert_not_called()
