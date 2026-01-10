"""CLI commands for commit management."""

import os
from typing import Any, Callable, Dict, Optional

import typer
from typer_di import Depends
from yaspin import yaspin

from devrules.adapters.ai import diny
from devrules.cli_commands.prompters.factory import get_default_prompter
from devrules.config import Config, load_config
from devrules.core.enum import DevRulesEvent
from devrules.core.git_service import get_current_branch, get_current_issue_number
from devrules.messages import commit as msg
from devrules.utils import gum
from devrules.utils.decorators import emit_event, ensure_git_repo
from devrules.utils.typer import add_typer_block_message
from devrules.validators.commit import validate_commit
from devrules.validators.forbidden_files import (
    get_forbidden_file_suggestions,
    validate_no_forbidden_files,
)
from devrules.validators.ownership import validate_branch_ownership

prompter = get_default_prompter()


def build_commit_message_interactive(config: Config, tags: list[str]) -> Optional[str]:
    """Build commit message interactively using gum or typer fallback.

    Args:
        tags: List of valid commit tags

    Returns:
        Formatted commit message or None if cancelled
    """
    default_message = None
    if config.commit.enable_ai_suggestions:
        with yaspin(text="Generating commit message...", color="green"):
            default_message = diny.generate_commit_message()
            if default_message is None:
                # AI generation failed, continue without suggestion
                pass

    if gum.is_available():
        return _build_commit_with_gum(config=config, tags=tags, default_message=default_message)
    else:
        return _build_commit_with_typer(tags, default_message)


def _build_commit_with_gum(
    config: Config, tags: list[str], default_message: Optional[str] = None
) -> Optional[str]:
    """Build commit message using gum UI."""
    print(gum.style("📝 Create Commit", foreground=81, bold=True))
    print(gum.style("=" * 50, foreground=81))

    if config.commit.enable_ai_suggestions and default_message:
        gum.info(f"AI message generated: {default_message}")
    elif config.commit.enable_ai_suggestions and not default_message:
        gum.warning("AI message generation failed or timed out")

    # Select tag
    tag = gum.choose(tags, header="Select commit tag:")
    if not tag:
        gum.error(msg.NO_TAG_SELECTED)
        return None

    # Write message with history
    kwargs = {
        "placeholder": "Describe your changes...",
        "header": f"[{tag}] Commit message:",
    }
    if default_message:
        kwargs["default"] = default_message

    if config.commit.enable_ai_suggestions:
        message = gum.input_text(**kwargs)
    else:
        kwargs.update(
            {
                "prompt_type": f"commit_message_{tag}",
            }
        )
        message = gum.input_text_with_history(**kwargs)

    if not message:
        gum.error(msg.MESSAGE_CANNOT_BE_EMPTY)
        return None

    return f"[{tag}] {message}"


def _build_commit_with_typer(
    tags: list[str], default_message: Optional[str] = None
) -> Optional[str]:
    """Build commit message using typer prompts (fallback)."""
    add_typer_block_message(
        header="📝 Create Commit",
        subheader="📋 Select commit tag:",
        messages=[f"{idx}. {tag}" for idx, tag in enumerate(tags, 1)],
    )

    tag_choice = typer.prompt("Enter number", type=int, default=1)

    if tag_choice < 1 or tag_choice > len(tags):
        typer.secho(msg.INVALID_CHOICE, fg=typer.colors.RED)
        return None

    tag = tags[tag_choice - 1]

    # Get message
    message = typer.prompt(f"\n[{tag}] Enter commit message", default=default_message)

    if not message:
        typer.secho(f"✘ {msg.MESSAGE_CANNOT_BE_EMPTY}", fg=typer.colors.RED)
        return None

    return f"[{tag}] {message}"


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    """Register commit commands.

    Args:
        app: Typer application instance.

    Returns:
        Dictionary mapping command names to their functions.
    """

    @app.command()
    @ensure_git_repo()
    def check_commit(
        file: str,
        config: Config = Depends(load_config),
    ):
        """Validate commit message format."""

        if not os.path.exists(file):
            typer.secho(msg.COMMIT_MESSAGE_FILE_NOT_FOUND.format(file), fg=typer.colors.RED)
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
    @ensure_git_repo()
    def commit(
        message: str,
        skip_checks: bool = typer.Option(
            False, "--skip-checks", help="Skip file validation and documentation checks"
        ),
        config: Config = Depends(load_config),
    ):
        """Validate and commit changes with a properly formatted message."""
        import subprocess

        typer.secho("Checking commit requirements...", fg=typer.colors.BLUE)

        # Check for forbidden files (unless skipped)
        if not skip_checks and (config.commit.forbidden_patterns or config.commit.forbidden_paths):
            is_valid, validation_message = validate_no_forbidden_files(
                forbidden_patterns=config.commit.forbidden_patterns,
                forbidden_paths=config.commit.forbidden_paths,
                check_staged=True,
            )

            if not is_valid:
                add_typer_block_message(
                    header=msg.FORBIDDEN_FILES_DETECTED,
                    subheader=validation_message,
                    messages=["💡 Suggestions:"]
                    + [f"• {suggestion}" for suggestion in get_forbidden_file_suggestions()],
                    indent_block=False,
                    use_separator=False,
                )
                raise typer.Exit(code=1)

        # Validate commit
        is_valid, result_message = validate_commit(message, config.commit)

        if not is_valid:
            typer.secho(f"\n✘ {result_message}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        current_branch = get_current_branch()

        # Check if current branch is protected (e.g., staging branches for merging)
        if config.commit.protected_branch_prefixes:
            for prefix in config.commit.protected_branch_prefixes:
                if current_branch.count(prefix):
                    typer.secho(
                        msg.CANNOT_COMMIT_TO_PROTECTED_BRANCH.format(current_branch, prefix),
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

        if config.commit.auto_stage:
            typer.secho("Auto staging files...", fg=typer.colors.GREEN)
            subprocess.run(
                [
                    "git",
                    "add",
                    "--all",
                ],
                check=True,
            )

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
            typer.secho(f"\n{msg.COMMITTED_CHANGES}", fg=typer.colors.GREEN)

            # Show context-aware documentation AFTER commit
            if doc_message:
                typer.secho(f"{doc_message}", fg=typer.colors.YELLOW)
        except subprocess.CalledProcessError as e:
            typer.secho(f"\n{msg.FAILED_TO_COMMIT_CHANGES.format(e)}", fg=typer.colors.RED)
            raise typer.Exit(code=1) from e

    @app.command()
    @ensure_git_repo()
    @emit_event(DevRulesEvent.PRE_COMMIT)
    def icommit(
        skip_checks: bool = typer.Option(
            False, "--skip-checks", help="Skip file validation and documentation checks"
        ),
        config: Config = Depends(load_config),
    ):
        """Interactive commit - build commit message with guided prompts."""
        import subprocess

        current_branch = get_current_branch()

        # Check for forbidden files (unless skipped)
        if not skip_checks and (config.commit.forbidden_patterns or config.commit.forbidden_paths):
            with yaspin(text="Checking forbidden files...") as spinner:
                is_valid, validation_message = validate_no_forbidden_files(
                    forbidden_patterns=config.commit.forbidden_patterns,
                    forbidden_paths=config.commit.forbidden_paths,
                    check_staged=True,
                )

                if not is_valid:
                    add_typer_block_message(
                        header=msg.FORBIDDEN_FILES_DETECTED,
                        subheader=validation_message,
                        messages=["💡 Suggestions:"]
                        + [f"• {suggestion}" for suggestion in get_forbidden_file_suggestions()],
                        indent_block=False,
                        use_separator=False,
                    )
                    raise typer.Exit(code=1)
                spinner.ok("✔")

        # Check if current branch is protected
        if config.commit.protected_branch_prefixes:
            with yaspin(text="Validating protected branches...") as spinner:
                for prefix in config.commit.protected_branch_prefixes:
                    if current_branch.count(prefix):
                        typer.secho(
                            msg.CANNOT_COMMIT_TO_PROTECTED_BRANCH.format(current_branch, prefix),
                            fg=typer.colors.RED,
                        )
                        raise typer.Exit(code=1)
                spinner.ok("✔")

        if config.commit.restrict_branch_to_owner:
            with yaspin(text="Checking branch ownership...") as spinner:
                is_owner, ownership_message = validate_branch_ownership(current_branch)
                if not is_owner:
                    typer.secho(f"✘ {ownership_message}", fg=typer.colors.RED)
                    raise typer.Exit(code=1)
                spinner.ok("✔")

        # Build commit message interactively
        message = build_commit_message_interactive(config=config, tags=config.commit.tags)

        if not message:
            typer.secho(f"✘ {msg.COMMIT_CANCELLED}", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

        # Validate commit message
        with yaspin(text="Validating commit message...") as spinner:
            is_valid, result_message = validate_commit(message, config.commit)
            if not is_valid:
                typer.secho(f"\n✘ {result_message}", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            spinner.ok("✔")

        if config.commit.append_issue_number:
            with yaspin(text="Checking issue number...") as spinner:
                issue_number = get_current_issue_number()
                if issue_number and f"#{issue_number}" not in message:
                    message = f"#{issue_number} {message}"
                spinner.ok("✔")

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
        prompter.info(f"\n📝 Commit message: {message}")
        if not prompter.confirm("Proceed with commit?", default=True):
            prompter.warning(msg.COMMIT_CANCELLED)
            raise typer.Exit(code=0)

        if config.commit.auto_stage:
            prompter.info("Auto staging files...")
            subprocess.run(
                [
                    "git",
                    "add",
                    "--all",
                ],
                check=True,
            )

        options = []
        if config.commit.gpg_sign:
            options.append("-S")
        if config.commit.allow_hook_bypass:
            options.append("-n")
        options.append("-m")
        options.append(message)

        try:
            subprocess.run(["git", "commit", *options], check=True)
            prompter.success(msg.COMMITTED_CHANGES)

            if doc_message:
                prompter.info(doc_message)
        except subprocess.CalledProcessError as e:
            typer.secho(f"\n{msg.FAILED_TO_COMMIT_CHANGES.format(e)}", fg=typer.colors.RED)
            raise typer.Exit(code=1) from e

    return {
        "check_commit": check_commit,
        "commit": commit,
        "icommit": icommit,
    }
