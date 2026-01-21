"""Additional CLI commands for git hooks integration."""

from typing import Any, Callable, Dict, Optional

import typer
from typer_di import Depends

from devrules.adapters.prompters.factory import get_default_prompter
from devrules.config import Config
from devrules.core.git_service import get_current_branch
from devrules.messages import commit as msg
from devrules.utils.decorators import ensure_git_repo
from devrules.utils.dependencies import get_config
from devrules.utils.typer import add_typer_block_message
from devrules.validators.branch import validate_branch
from devrules.validators.documentation import build_documentation_context, get_changed_files
from devrules.validators.forbidden_files import (
    get_forbidden_file_suggestions,
    validate_no_forbidden_files,
)
from devrules.validators.ownership import validate_branch_ownership

prompter = get_default_prompter()


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    """Register hook commands.

    Args:
        app: Typer application instance.

    Returns:
        Dictionary mapping command names to their functions.
    """

    @app.command()
    @ensure_git_repo()
    def pre_commit_check(
        config: Config = Depends(get_config),
    ):
        """Run pre-commit validations (called by git pre-commit hook)."""
        prompter.header("Run pre-commit validations")
        # Check for forbidden files
        if config.commit.forbidden_patterns or config.commit.forbidden_paths:
            is_valid, validation_message = validate_no_forbidden_files(
                forbidden_patterns=config.commit.forbidden_patterns,
                forbidden_paths=config.commit.forbidden_paths,
                check_staged=True,
            )

            if not is_valid:
                add_typer_block_message(
                    header="🚫 Forbidden Files Detected",
                    subheader=validation_message,
                    messages=["💡 Suggestions:"]
                    + [f"• {suggestion}" for suggestion in get_forbidden_file_suggestions()],
                    indent_block=False,
                )
                raise prompter.exit(code=1)

        current_branch = get_current_branch()

        if config.commit.protected_branch_prefixes:
            for prefix in config.commit.protected_branch_prefixes:
                if current_branch.count(prefix):
                    prompter.error(
                        msg.CANNOT_COMMIT_TO_PROTECTED_BRANCH.format(current_branch, prefix),
                    )
                    raise prompter.exit(code=1)

        if config.commit.restrict_branch_to_owner:
            # Check branch ownership to prevent committing on another developer's branch
            is_owner, ownership_message = validate_branch_ownership(current_branch)
            if not is_owner:
                prompter.error(f"{ownership_message}")
                raise prompter.exit(code=1)

        prompter.success("DevRules Pre-commit checks passed")

    @app.command()
    @ensure_git_repo()
    def pre_push_check(
        branch: Optional[str] = typer.Option(
            None, "--branch", "-b", help="Branch to validate (defaults to current)"
        ),
        config: Config = Depends(get_config),
    ):
        """Run pre-push validations (called by git pre-push hook)."""
        prompter.header("Run pre-push validations")
        # Get current branch if not specified
        if not branch:
            branch = get_current_branch()

        # Validate branch name
        is_valid, message = validate_branch(branch, config.branch)
        if not is_valid:
            prompter.error(message)
            raise prompter.exit(code=1)

        # Check branch ownership if enabled
        if config.commit.restrict_branch_to_owner:
            is_owner, ownership_message = validate_branch_ownership(branch)
            if not is_owner:
                prompter.error(ownership_message)
                raise prompter.exit(code=1)

        # Check if pushing to protected branch
        if config.commit.protected_branch_prefixes:
            for prefix in config.commit.protected_branch_prefixes:
                if branch and branch.startswith(prefix):
                    prompter.error(
                        f"Cannot push to protected branch '{branch}' (prefix: {prefix})",
                    )
                    raise prompter.exit(code=1)

        prompter.success(f"DevRules Pre-push checks passed for branch '{branch}'")

    @app.command()
    @ensure_git_repo()
    def branch_context(
        branch: Optional[str] = typer.Option(
            None, "--branch", "-b", help="Branch to show context for (defaults to current)"
        ),
        config: Config = Depends(get_config),
    ):
        """Show branch context information (called by git post-checkout hook)."""
        # Get current branch if not specified
        prompter.header("Get context from branch and changed files")
        if not branch:
            branch = get_current_branch()

        if branch:
            prompter.info(f"Branch: {branch}")
            prompter.info(
                f"Type: {'Protected' if any(branch.startswith(p) for p in config.commit.protected_branch_prefixes) else 'Standard'}"
            )
            prompter.info(
                f"Owner: {'You' if config.commit.restrict_branch_to_owner else 'Not restricted'}"
            )

        # Show any relevant documentation using snapshot pattern
        if config.documentation.show_on_commit and config.documentation.rules:
            from devrules.cli_commands.commons import show_documentation_context

            # 1️⃣ Capture documentation context (snapshot)
            changed_files = get_changed_files(base_branch=branch or "HEAD")
            if changed_files:
                doc_contexts = build_documentation_context(
                    rules=config.documentation.rules,
                    changed_files=changed_files,
                )

                # 2️⃣ Show documentation context
                if doc_contexts:
                    show_documentation_context(doc_contexts, show_files=False)

    return {
        "pre-commit-check": pre_commit_check,
        "pre-push-check": pre_push_check,
        "branch-context": branch_context,
    }
