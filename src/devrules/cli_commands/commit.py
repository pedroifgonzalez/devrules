import os
from typing import Any, Callable, Dict, Optional

import typer

from devrules.config import load_config
from devrules.core.git_service import ensure_git_repo, get_current_branch, get_current_issue_number
from devrules.utils import gum
from devrules.validators.commit import validate_commit
from devrules.validators.forbidden_files import (
    get_forbidden_file_suggestions,
    validate_no_forbidden_files,
)
from devrules.validators.ownership import validate_branch_ownership


def build_commit_message_interactive(tags: list[str]) -> Optional[str]:
    """Build commit message interactively using gum or typer fallback.

    Args:
        tags: List of valid commit tags

    Returns:
        Formatted commit message or None if cancelled
    """
    if gum.is_available():
        return _build_commit_with_gum(tags)
    else:
        return _build_commit_with_typer(tags)


def _build_commit_with_gum(tags: list[str]) -> Optional[str]:
    """Build commit message using gum UI."""
    print(gum.style("📝 Create Commit", foreground=81, bold=True))
    print(gum.style("=" * 50, foreground=81))

    # Select tag
    tag = gum.choose(tags, header="Select commit tag:")
    if not tag:
        gum.error("No tag selected")
        return None

    # Write message
    message = gum.input_text(
        placeholder="Describe your changes...",
        header=f"[{tag}] Commit message:",
    )

    if not message:
        gum.error("Message cannot be empty")
        return None

    return f"[{tag}] {message}"


def _build_commit_with_typer(tags: list[str]) -> Optional[str]:
    """Build commit message using typer prompts (fallback)."""
    typer.secho("\n📝 Create Commit", fg=typer.colors.CYAN, bold=True)
    typer.echo("=" * 50)

    # Select tag
    typer.echo("\n📋 Select commit tag:")
    for idx, tag in enumerate(tags, 1):
        typer.echo(f"  {idx}. {tag}")

    tag_choice = typer.prompt("\nEnter number", type=int, default=1)

    if tag_choice < 1 or tag_choice > len(tags):
        typer.secho("✘ Invalid choice", fg=typer.colors.RED)
        return None

    tag = tags[tag_choice - 1]

    # Get message
    message = typer.prompt(f"\n[{tag}] Enter commit message")

    if not message:
        typer.secho("✘ Message cannot be empty", fg=typer.colors.RED)
        return None

    return f"[{tag}] {message}"


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command()
    def check_commit(
        file: str,
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
    ):
        """Validate commit message format."""
        config = load_config(config_file)

        if not os.path.exists(file):
            typer.secho(f"Commit message file not found: {file}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        with open(file, "r") as f:
            message = f.read().strip()

        is_valid, result_message = validate_commit(message, config.commit)

        if is_valid:
            typer.secho(f"✔ {result_message}", fg=typer.colors.GREEN)
            raise typer.Exit(code=0)
        else:
            typer.secho(f"✘ {result_message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    @app.command()
    def commit(
        message: str,
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
        skip_checks: bool = typer.Option(
            False, "--skip-checks", help="Skip file validation and documentation checks"
        ),
    ):
        """Validate and commit changes with a properly formatted message."""
        import subprocess

        config = load_config(config_file)

        # Check for forbidden files (unless skipped)
        if not skip_checks and (config.commit.forbidden_patterns or config.commit.forbidden_paths):
            is_valid, validation_message = validate_no_forbidden_files(
                forbidden_patterns=config.commit.forbidden_patterns,
                forbidden_paths=config.commit.forbidden_paths,
                check_staged=True,
            )

            if not is_valid:
                typer.secho("\n✘ Forbidden Files Detected", fg=typer.colors.RED, bold=True)
                typer.echo(validation_message)
                typer.echo("\n💡 Suggestions:")
                for suggestion in get_forbidden_file_suggestions():
                    typer.echo(f"  • {suggestion}")
                typer.echo()
                raise typer.Exit(code=1)

        # Validate commit
        is_valid, result_message = validate_commit(message, config.commit)

        if not is_valid:
            typer.secho(f"\n✘ {result_message}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        ensure_git_repo()
        current_branch = get_current_branch()

        # Check if current branch is protected (e.g., staging branches for merging)
        if config.commit.protected_branch_prefixes:
            for prefix in config.commit.protected_branch_prefixes:
                if current_branch.count(prefix):
                    typer.secho(
                        f"✘ Cannot commit directly to '{current_branch}'. "
                        f"Branches containing '{prefix}' are protected (merge-only).",
                        fg=typer.colors.RED,
                    )
                    raise typer.Exit(code=1)

        if config.commit.restrict_branch_to_owner:
            # Check branch ownership to prevent committing on another developer's branch
            is_owner, ownership_message = validate_branch_ownership(current_branch)
            if not is_owner:
                typer.secho(f"✘ {ownership_message}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        if config.commit.append_issue_number:
            # Append issue number if configured and not already present
            issue_number = get_current_issue_number()
            if issue_number and f"#{issue_number}" not in message:
                message = f"#{issue_number} {message}"

        # Get documentation guidance BEFORE commit (while files are still staged)
        doc_message = None
        if not skip_checks and config.documentation.show_on_commit and config.documentation.rules:
            from devrules.validators.documentation import get_relevant_documentation

            has_docs, doc_message = get_relevant_documentation(
                rules=config.documentation.rules,
                base_branch="HEAD",
                show_files=True,
            )
            if not has_docs:
                doc_message = None

        options = []
        if config.commit.gpg_sign:
            options.append("-S")
        if config.commit.allow_hook_bypass:
            options.append("-n")
        options.append("-m")
        options.append(message)
        try:
            subprocess.run(
                [
                    "git",
                    "commit",
                    *options,
                ],
                check=True,
            )
            typer.secho("\n✔ Committed changes!", fg=typer.colors.GREEN)

            # Show context-aware documentation AFTER commit
            if doc_message:
                typer.secho(f"{doc_message}", fg=typer.colors.YELLOW)
        except subprocess.CalledProcessError as e:
            typer.secho(f"\n✘ Failed to commit changes: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1) from e

    @app.command()
    def icommit(
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
        skip_checks: bool = typer.Option(
            False, "--skip-checks", help="Skip file validation and documentation checks"
        ),
    ):
        """Interactive commit - build commit message with guided prompts."""
        import subprocess

        config = load_config(config_file)
        ensure_git_repo()

        # Check for forbidden files (unless skipped)
        if not skip_checks and (config.commit.forbidden_patterns or config.commit.forbidden_paths):
            is_valid, validation_message = validate_no_forbidden_files(
                forbidden_patterns=config.commit.forbidden_patterns,
                forbidden_paths=config.commit.forbidden_paths,
                check_staged=True,
            )

            if not is_valid:
                typer.secho("\n✘ Forbidden Files Detected", fg=typer.colors.RED, bold=True)
                typer.echo(validation_message)
                typer.echo("\n💡 Suggestions:")
                for suggestion in get_forbidden_file_suggestions():
                    typer.echo(f"  • {suggestion}")
                typer.echo()
                raise typer.Exit(code=1)

        # Build commit message interactively
        message = build_commit_message_interactive(config.commit.tags)

        if not message:
            typer.secho("✘ Commit cancelled", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

        # Validate commit message
        is_valid, result_message = validate_commit(message, config.commit)

        if not is_valid:
            typer.secho(f"\n✘ {result_message}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        current_branch = get_current_branch()

        # Check if current branch is protected
        if config.commit.protected_branch_prefixes:
            for prefix in config.commit.protected_branch_prefixes:
                if current_branch.count(prefix):
                    typer.secho(
                        f"✘ Cannot commit directly to '{current_branch}'. "
                        f"Branches containing '{prefix}' are protected (merge-only).",
                        fg=typer.colors.RED,
                    )
                    raise typer.Exit(code=1)

        if config.commit.restrict_branch_to_owner:
            is_owner, ownership_message = validate_branch_ownership(current_branch)
            if not is_owner:
                typer.secho(f"✘ {ownership_message}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        if config.commit.append_issue_number:
            issue_number = get_current_issue_number()
            if issue_number and f"#{issue_number}" not in message:
                message = f"#{issue_number} {message}"

        # Get documentation guidance
        doc_message = None
        if not skip_checks and config.documentation.show_on_commit and config.documentation.rules:
            from devrules.validators.documentation import get_relevant_documentation

            has_docs, doc_message = get_relevant_documentation(
                rules=config.documentation.rules,
                base_branch="HEAD",
                show_files=True,
            )
            if not has_docs:
                doc_message = None

        # Confirm before committing
        if gum.is_available():
            print(f"\n📝 Commit message: {gum.style(message, foreground=82)}")
            confirmed = gum.confirm("Proceed with commit?")
            if confirmed is False:
                typer.secho("Commit cancelled", fg=typer.colors.YELLOW)
                raise typer.Exit(code=0)
        else:
            typer.echo(f"\n📝 Commit message: {message}")
            if not typer.confirm("Proceed with commit?", default=True):
                typer.secho("Commit cancelled", fg=typer.colors.YELLOW)
                raise typer.Exit(code=0)

        options = []
        if config.commit.gpg_sign:
            options.append("-S")
        if config.commit.allow_hook_bypass:
            options.append("-n")
        options.append("-m")
        options.append(message)

        try:
            subprocess.run(["git", "commit", *options], check=True)
            typer.secho("\n✔ Committed changes!", fg=typer.colors.GREEN)

            if doc_message:
                typer.secho(f"{doc_message}", fg=typer.colors.YELLOW)
        except subprocess.CalledProcessError as e:
            typer.secho(f"\n✘ Failed to commit changes: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1) from e

    return {
        "check_commit": check_commit,
        "commit": commit,
        "icommit": icommit,
    }
