"""CLI commands for commit management."""

import os
from typing import Any, Callable, Dict, Optional

import typer
from typer_di import Depends
from yaspin import inject_spinner, yaspin
from yaspin.core import Yaspin
from yaspin.spinners import Spinners

from devrules.adapters.ai import diny
from devrules.cli_commands.prompters import Prompter
from devrules.cli_commands.prompters.factory import get_default_prompter
from devrules.config import Config, load_config
from devrules.core.enum import DevRulesEvent
from devrules.core.git_service import commit as _commit
from devrules.core.git_service import get_current_branch, get_current_issue_number, stage_files
from devrules.messages import commit as msg
from devrules.utils.decorators import emit_events, ensure_git_repo
from devrules.utils.typer import add_typer_block_message
from devrules.validators.commit import validate_commit
from devrules.validators.forbidden_files import (
    get_forbidden_file_suggestions,
    validate_no_forbidden_files,
)
from devrules.validators.ownership import validate_branch_ownership

prompter: Prompter = get_default_prompter()


def build_commit_message_interactive(config: Config, tags: list[str]) -> str:
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

    if config.commit.enable_ai_suggestions and default_message:
        prompter.info(f"AI message generated: {default_message}")
    elif config.commit.enable_ai_suggestions and not default_message:
        prompter.warning("AI message generation failed or timed out")

    # Select tag
    tag = prompter.choose(tags, header="Select commit tag:")
    if not tag:
        prompter.error(msg.NO_TAG_SELECTED)
        raise prompter.exit(code=0)

    kwargs = {
        "placeholder": "Describe your changes...",
        "header": f"[{tag}] Commit message:",
    }
    if default_message:
        kwargs["default"] = default_message

    message = prompter.input_text(**kwargs)

    if not message:
        prompter.warning(f"{msg.COMMIT_CANCELLED}")
        raise prompter.exit(code=0)

    message = f"[{tag}] {message}"

    return message


@inject_spinner(Spinners.dots, text="Validating commit message...", color="yellow")
def _validate_commit(spinner: Yaspin, message: str, config: Config):
    is_valid, result_message = validate_commit(message, config.commit)
    spinner.ok("✔")
    if not is_valid:
        spinner.fail("✘")
        prompter.error(result_message)
        raise prompter.exit(code=1)


@inject_spinner(Spinners.dots, text="Checking issue number...", color="magenta")
def _auto_append_issue_number(spinner: Yaspin, message: str, config: Config):
    if config.commit.append_issue_number:
        issue_number = get_current_issue_number()
        if issue_number and f"#{issue_number}" not in message:
            spinner.text = "Issue number appended to commit message."
            message = f"#{issue_number} {message}"
        spinner.ok("✔")


@inject_spinner(Spinners.dots, text="Checking forbidden files...", color="yellow")
def _validate_forbidden_files(spinner: Yaspin, skip_checks: bool, config: Config):
    if not skip_checks and (config.commit.forbidden_patterns or config.commit.forbidden_paths):
        is_valid, validation_message = validate_no_forbidden_files(
            forbidden_patterns=config.commit.forbidden_patterns,
            forbidden_paths=config.commit.forbidden_paths,
            check_staged=True,
        )
        spinner.ok("✔")
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


@inject_spinner(Spinners.dots, text="Validating protected branches...", color="yellow")
def _validate_branch_protection(spinner: Yaspin, current_branch: str, config: Config):
    if config.commit.protected_branch_prefixes:
        for prefix in config.commit.protected_branch_prefixes:
            if current_branch.count(prefix):
                typer.secho(
                    msg.CANNOT_COMMIT_TO_PROTECTED_BRANCH.format(current_branch, prefix),
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)
        spinner.ok("✔")


@inject_spinner(Spinners.dots, text="Checking branch ownership...", color="yellow")
def _validate_ownership(spinner: Yaspin, current_branch: str, config: Config):
    if config.commit.restrict_branch_to_owner:
        is_owner, ownership_message = validate_branch_ownership(current_branch)
        if not is_owner:
            typer.secho(f"✘ {ownership_message}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        spinner.ok("✔")


@inject_spinner(Spinners.dots, text="Getting context aware documentation...", color="blue")
def _get_documentation_guidance(
    spinner: Yaspin, skip_checks: bool, config: Config
) -> Optional[str]:
    if not skip_checks and config.documentation.show_on_commit and config.documentation.rules:
        from devrules.validators.documentation import get_relevant_documentation

        has_docs, doc_message = get_relevant_documentation(
            rules=config.documentation.rules,
            base_branch="HEAD",
            show_files=True,
        )
        if has_docs:
            return doc_message
    return None


def _confirm_commit(message: str):
    prompter.info(f"📝 Commit message: {message}")
    if not prompter.confirm("Proceed with commit?", default=True):
        prompter.warning(msg.COMMIT_CANCELLED)
        raise typer.Exit(code=0)


def _stage_files(config: Config):
    if config.commit.auto_stage:
        prompter.info("Auto staging files...")
        stage_files()


def _perform_commit(message: str, config: Config, doc_message: Optional[str] = None):
    success, message = _commit(message, config)
    if not success:
        typer.secho(f"\n{msg.FAILED_TO_COMMIT_CHANGES.format(message)}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    prompter.success(msg.COMMITTED_CHANGES)
    if doc_message:
        prompter.info(doc_message.strip("\n"))


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
    @emit_events(DevRulesEvent.PRE_COMMIT, DevRulesEvent.POST_COMMIT)
    def icommit(
        skip_checks: bool = typer.Option(
            False, "--skip-checks", help="Skip file validation and documentation checks"
        ),
        config: Config = Depends(load_config),
    ):
        """Interactive commit - build commit message with guided prompts."""
        prompter.header("📝 Create Commit")
        current_branch = get_current_branch()
        # Perform validations
        _validate_forbidden_files(skip_checks, config)
        _validate_branch_protection(current_branch, config)
        _validate_ownership(current_branch, config)
        # Build commit message
        message = build_commit_message_interactive(config=config, tags=config.commit.tags)
        # Validate commit message
        _validate_commit(message, config)
        # Perform post-commit validation operations
        _auto_append_issue_number(message, config)
        doc_message = _get_documentation_guidance(skip_checks, config)
        _stage_files(config=config)
        # Confirm before committing
        _confirm_commit(message=message)
        _perform_commit(message=message, config=config, doc_message=doc_message)

    return {
        "check_commit": check_commit,
        "commit": commit,
        "icommit": icommit,
    }
