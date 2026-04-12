"""CLI commands for commit management."""

from typing import Any, Callable, Dict

import typer
from typer_di import Depends
from yaspin import inject_spinner, yaspin
from yaspin.core import Yaspin
from yaspin.spinners import Spinners

from devrules.adapters.ai import diny
from devrules.adapters.prompters import Prompter
from devrules.adapters.prompters.factory import get_default_prompter
from devrules.config import Config, load_config
from devrules.core.enum import DevRulesEvent
from devrules.core.git_service import commit as _commit
from devrules.core.git_service import (
    get_current_branch,
    get_current_issue_number,
    push_branch,
    stage_files,
)
from devrules.messages import commit as msg
from devrules.utils.commit_template import (
    DEFAULT_COMMIT_TEMPLATE,
    DEFAULT_CONTEXT_TEMPLATE,
    format_commit_message,
    requires_context,
    uses_context,
)
from devrules.utils.decorators import emit_events, ensure_git_repo
from devrules.utils.typer import add_typer_block_message
from devrules.validators.commit import validate_commit
from devrules.validators.documentation import (
    DocumentationContext,
    build_documentation_context,
    get_changed_files,
)
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

    template = config.commit.template or DEFAULT_COMMIT_TEMPLATE
    context_template = config.commit.context_template or DEFAULT_CONTEXT_TEMPLATE
    context = ""
    if uses_context(template):
        context = (
            prompter.input_text(
                placeholder="Enter context/scope or leave empty to skip",
                header="Commit context:",
                default="",
            )
            or ""
        )
        if requires_context(template) and not context.strip():
            prompter.error("Commit context is required by the configured template.")
            raise prompter.exit(code=1)

    kwargs = {
        "placeholder": "Describe your changes...",
        "header": "Commit message:",
    }
    if default_message:
        kwargs["default"] = default_message

    commit_body = prompter.write(**kwargs)

    if not commit_body:
        prompter.warning(f"{msg.COMMIT_CANCELLED}")
        raise prompter.exit(code=0)

    return format_commit_message(
        template=template,
        tag=tag,
        message=commit_body,
        context=context,
        context_template=context_template,
    )


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
    if not is_valid:
        spinner.fail("✘")
        prompter.error(result_message)
        raise prompter.exit(code=1)
    spinner.ok("✔")


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
        if not is_valid:
            spinner.fail("✘")
            add_typer_block_message(
                header=msg.FORBIDDEN_FILES_DETECTED,
                subheader=validation_message,
                messages=["💡 Suggestions:"]
                + [f"• {suggestion}" for suggestion in get_forbidden_file_suggestions()],
                indent_block=False,
                use_separator=False,
            )
            raise prompter.exit(code=1)
        spinner.ok("✔")


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
            if current_branch.startswith(prefix):
                spinner.fail("✘")
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
            spinner.fail("✘")
            prompter.error(ownership_message)
            raise prompter.exit(code=1)
        spinner.ok("✔")


@inject_spinner(Spinners.dots, text="Building documentation context...")
def build_doc_context(spinner: Yaspin, config: Config) -> list[DocumentationContext]:
    """Build documentation context snapshot before commit.

    Args:
        spinner (Yaspin): injected spinner
        config (Config): config

    Returns:
        List of DocumentationContext objects
    """
    if not config.documentation.show_on_commit or not config.documentation.rules:
        spinner.ok("✔")
        return []

    # Get changed files (staged files before commit)
    changed_files = get_changed_files(base_branch="HEAD")

    if not changed_files:
        spinner.ok("✔")
        return []

    # Build context snapshot
    contexts = build_documentation_context(
        rules=config.documentation.rules,
        changed_files=changed_files,
    )

    spinner.ok("✔")
    return contexts


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


def _perform_commit(message: str, config: Config, doc_contexts: list[DocumentationContext]):
    """Perform commit and show documentation context.

    Args:
        message (str): commit message
        config (Config): config
        doc_contexts: Documentation context snapshot captured before commit

    Raises:
        prompter.exit: if any error occurs
    """
    success, commit_message = _commit(message, config)
    if not success:
        prompter.error(msg.FAILED_TO_COMMIT_CHANGES.format(commit_message))
        raise prompter.exit(code=1)
    prompter.success(msg.COMMITTED_CHANGES)

    if config.commit.auto_push:
        prompter.info("Auto pushing commit is enabled, pushing...")
        success, message = push_branch(get_current_branch())
        if not success:
            prompter.error(message)
            raise prompter.exit(code=1)

    # Show documentation context after commit
    if doc_contexts:
        from devrules.cli_commands.commons import show_documentation_context

        show_documentation_context(doc_contexts, show_files=True)


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
    @emit_events([DevRulesEvent.PRE_COMMIT, DevRulesEvent.POST_COMMIT])
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

        # 1️⃣ Capture documentation context BEFORE commit (snapshot)
        doc_contexts = build_doc_context(config)

        _confirm_commit(message)

        # 2️⃣ Perform commit and show documentation context
        _perform_commit(message, config, doc_contexts)

    return {
        "commit": commit,
    }
