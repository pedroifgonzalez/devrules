"""CLI commands for commit management."""

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


def build_commit_message_interactive(config: Config, tags: list[str], prompter: Prompter) -> str:
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

    message = prompter.write(**kwargs)

    if not message:
        prompter.warning(f"{msg.COMMIT_CANCELLED}")
        raise prompter.exit(code=0)

    message = f"[{tag}] {message}"

    return message


@inject_spinner(Spinners.dots, text="Validating commit message...")
def _validate_commit(spinner: Yaspin, message: str, config: Config):
    """Validates commit message

    Args:
        spinner (Yaspin): injected spinner
        message (str): commit message
        config (Config): config

    Raises:
        prompter.exit: if commit message is invalid
    """
    is_valid, result_message = validate_commit(message, config.commit)
    spinner.ok("✔")
    if not is_valid:
        spinner.fail("✘")
        prompter.error(result_message)
        raise prompter.exit(code=1)


@inject_spinner(Spinners.dots, text="Checking issue number...")
def _auto_append_issue_number(spinner: Yaspin, message: str, config: Config):
    """Auto append issue number to commit message if necessary

    Args:
        spinner (Yaspin): injected spinner
        message (str): commit message
        config (Config): config
    """
    if config.commit.append_issue_number:
        issue_number = get_current_issue_number()
        if issue_number and f"#{issue_number}" not in message:
            spinner.text = "Issue number appended to commit message."
            message = f"#{issue_number} {message}"
        spinner.ok("✔")
    return message


@inject_spinner(Spinners.dots, text="Checking forbidden files...")
def _validate_forbidden_files(spinner: Yaspin, skip_checks: bool, config: Config):
    """Validates forbidden files

    Args:
        spinner (Yaspin): injected spinner
        skip_checks (bool): skip checks
        config (Config): config

    Raises:
        prompter.exit: if forbidden files are detected
    """
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
            raise prompter.exit(code=1)


@inject_spinner(Spinners.dots, text="Validating protected branches...")
def _validate_branch_protection(spinner: Yaspin, current_branch: str, config: Config):
    """Validates protected branches

    Args:
        spinner (Yaspin): injected spinner
        current_branch (str): current branch
        config (Config): config

    Raises:
        prompter.exit: if current branch is protected
    """
    if config.commit.protected_branch_prefixes:
        for prefix in config.commit.protected_branch_prefixes:
            spinner.stop()
            if current_branch.count(prefix):
                prompter.error(
                    msg.CANNOT_COMMIT_TO_PROTECTED_BRANCH.format(current_branch, prefix),
                )
                raise prompter.exit(code=1)
        spinner.ok("✔")


@inject_spinner(Spinners.dots, text="Checking branch ownership...")
def _validate_ownership(spinner: Yaspin, current_branch: str, config: Config):
    """Validate current branch ownserhip if necessary

    Args:
        spinner (Yaspin): injected spinner
        current_branch (str): current branch
        config (Config): config

    Raises:
        prompter.exit: if current branch is not owned by the user
    """
    if config.commit.restrict_branch_to_owner:
        is_owner, ownership_message = validate_branch_ownership(current_branch)
        if not is_owner:
            prompter.error(ownership_message)
            raise prompter.exit(code=1)
        spinner.ok("✔")


@inject_spinner(Spinners.dots, text="Getting context aware documentation...")
def show_documentation_guidance(
    spinner: Yaspin, skip_checks: bool, config: Config
) -> Optional[str]:
    """Get documentation guidance

    Args:
        spinner (Yaspin): injected spinner
        skip_checks (bool): skip checks
        config (Config): config

    Returns:
        Optional[str]: documentation guidance
    """
    if not skip_checks and config.documentation.show_on_commit and config.documentation.rules:
        from devrules.cli_commands.commons import _show_relevant_documentation

        _show_relevant_documentation(
            rules=config.documentation.rules,
            base_branch="HEAD",
            show_files=True,
        )
    return None


def _confirm_commit(message: str):
    """Confirm commit

    Args:
        message (str): commit message

    Raises:
        prompter.exit: if confirmation is false
    """
    prompter.info(f"Commit message: {message}")
    if not prompter.confirm("Proceed with commit?", default=True):
        prompter.warning(msg.COMMIT_CANCELLED)
        raise prompter.exit(code=0)


def _stage_files(config: Config):
    """Auto stage files if necessary

    Args:
        config (Config): config
    """
    if config.commit.auto_stage:
        prompter.info("Auto staging files...")
        stage_files()


def _perform_commit(message: str, config: Config, doc_message: Optional[str] = None):
    """Perform commit

    Args:
        message (str): commit message
        config (Config): config
        doc_message (Optional[str], optional): documentation message. Defaults to None.

    Raises:
        prompter.exit: if any error occurs
    """
    success, message = _commit(message, config)
    if not success:
        prompter.error(msg.FAILED_TO_COMMIT_CHANGES.format(message))
        raise prompter.exit(code=1)
    prompter.success(msg.COMMITTED_CHANGES)
    show_documentation_guidance(skip_checks=False, config=config)


def run_validations(
    *,
    skip_checks: bool,
    current_branch: str,
    config: Config,
):
    _validate_forbidden_files(skip_checks, config)
    _validate_branch_protection(current_branch, config)
    _validate_ownership(current_branch, config)


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    """Register commit commands.

    Args:
        app: Typer application instance.

    Returns:
        Dictionary mapping command names to their functions.
    """

    @app.command()
    @ensure_git_repo()
    @emit_events(DevRulesEvent.PRE_COMMIT, DevRulesEvent.POST_COMMIT)
    def commit(
        skip_checks: bool = typer.Option(
            False, "--skip-checks", help="Skip file validation and documentation checks"
        ),
        message: str = typer.Option(
            None,
            "--message",
            "-m",
            help="Commit message",
        ),
        config: Config = Depends(load_config),
    ):
        """Interactive commit - build commit message with guided prompts."""
        prompter.header("Commit changes")
        current_branch = get_current_branch()
        run_validations(
            skip_checks=skip_checks,
            current_branch=current_branch,
            config=config,
        )
        message = message or build_commit_message_interactive(
            config=config,
            tags=config.commit.tags,
            prompter=prompter,
        )
        _validate_commit(message, config)
        message = _auto_append_issue_number(message, config)
        _stage_files(config)
        _confirm_commit(message)
        _perform_commit(message, config)

    return {
        "commit": commit,
    }
