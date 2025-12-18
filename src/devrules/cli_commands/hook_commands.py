"""Additional CLI commands for git hooks integration."""

from typing import Any, Callable, Dict, Optional

import typer

from devrules.config import load_config
from devrules.core.git_service import ensure_git_repo, get_current_branch
from devrules.messages import commit as msg
from devrules.utils.typer import add_typer_block_message
from devrules.validators.branch import validate_branch
from devrules.validators.forbidden_files import (
    get_forbidden_file_suggestions,
    validate_no_forbidden_files,
)
from devrules.validators.ownership import validate_branch_ownership


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command()
    def pre_commit_check(
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
    ):
        """Run pre-commit validations (called by git pre-commit hook)."""
        config = load_config(config_file)

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
                raise typer.Exit(code=1)

        current_branch = get_current_branch()

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

        typer.secho("✔ DevRules Pre-commit checks passed", fg=typer.colors.GREEN)

    @app.command()
    def pre_push_check(
        branch: Optional[str] = typer.Option(
            None, "--branch", "-b", help="Branch to validate (defaults to current)"
        ),
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
    ):
        """Run pre-push validations (called by git pre-push hook)."""
        config = load_config(config_file)
        ensure_git_repo()

        # Get current branch if not specified
        if not branch:
            branch = get_current_branch()

        # Validate branch name
        is_valid, message = validate_branch(branch, config.branch)
        if not is_valid:
            typer.secho(f"✘ {message}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        # Check branch ownership if enabled
        if config.commit.restrict_branch_to_owner:
            is_owner, ownership_message = validate_branch_ownership(branch)
            if not is_owner:
                typer.secho(f"✘ {ownership_message}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        # Check if pushing to protected branch
        if config.commit.protected_branch_prefixes:
            for prefix in config.commit.protected_branch_prefixes:
                if branch and branch.startswith(prefix):
                    typer.secho(
                        f"✘ Cannot push to protected branch '{branch}' (prefix: {prefix})",
                        fg=typer.colors.RED,
                    )
                    raise typer.Exit(code=1)

        typer.secho(
            f"✔ DevRules Pre-push checks passed for branch '{branch}'", fg=typer.colors.GREEN
        )

    @app.command()
    def branch_context(
        branch: Optional[str] = typer.Option(
            None, "--branch", "-b", help="Branch to show context for (defaults to current)"
        ),
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
    ):
        """Show branch context information (called by git post-checkout hook)."""
        config = load_config(config_file)
        ensure_git_repo()

        # Get current branch if not specified
        if not branch:
            branch = get_current_branch()

        if branch:
            # Show branch information
            add_typer_block_message(
                header=f"📌 Branch: {branch}",
                subheader="",
                messages=[
                    f"• Type: {'Protected' if any(branch.startswith(p) for p in config.commit.protected_branch_prefixes) else 'Standard'}",
                    (
                        "• Owner: You"
                        if config.commit.restrict_branch_to_owner
                        else "• Owner: Not restricted"
                    ),
                ],
                indent_block=False,
            )

        # Show any relevant documentation
        if config.documentation.show_on_commit and config.documentation.rules:
            from devrules.validators.documentation import get_relevant_documentation

            has_docs, doc_message = get_relevant_documentation(
                rules=config.documentation.rules,
                base_branch=branch,
                show_files=False,
            )
            if has_docs:
                typer.echo()
                typer.secho(doc_message, fg=typer.colors.YELLOW)

    return {
        "pre-commit-check": pre_commit_check,
        "pre-push-check": pre_push_check,
        "branch-context": branch_context,
    }
