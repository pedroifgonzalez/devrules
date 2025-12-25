from typing import Any, Callable, Dict

import typer
from typer_di import Depends

from devrules.cli_commands.context_builders.branch import BranchCtxBuilder
from devrules.core.git_service import (
    checkout_branch_interactive,
    create_and_checkout_branch,
    handle_existing_branch,
)
from devrules.messages import branch as msg
from devrules.utils.decorators import ensure_git_repo
from devrules.utils.typer import add_typer_block_message
from devrules.validators.ownership import list_user_owned_branches

builder = BranchCtxBuilder()


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command()
    @ensure_git_repo()
    def check_branch(
        ctx: BranchCtxBuilder = Depends(builder.build_create_branch_context),
    ):
        """Validate branch naming convention."""
        ctx._validate_branch()

    @app.command()
    @ensure_git_repo()
    def create_branch(
        ctx: BranchCtxBuilder = Depends(builder.build_create_branch_context),
    ):
        """Create a new Git branch with validation (interactive mode)."""
        ctx._validate_branch()
        ctx.enforce_one_branch_per_issue_if_enabled()
        handle_existing_branch(ctx.final_branch_name)
        ctx.confirm_branch_creation()
        create_and_checkout_branch(ctx.final_branch_name)

    @app.command()
    @ensure_git_repo()
    def list_owned_branches():
        """Show all local Git branches owned by the current user."""

        branches = list_user_owned_branches()
        if not branches:
            typer.secho(msg.NO_BRANCHES_OWNED_BY_YOU, fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

        add_typer_block_message(
            header="Branches owned by you",
            subheader="",
            messages=[f"- {b}" for b in branches],
        )

    @app.command()
    @ensure_git_repo()
    def delete_branch(
        ctx: BranchCtxBuilder = Depends(builder.build_delete_branch_context),
    ):
        """Delete a branch locally and on the remote, enforcing ownership rules."""
        ctx.validate_selected_branches_to_delete()
        ctx.confirm_delete_branches()
        ctx.delete_branches()

    @app.command(name="switch-branch")
    @ensure_git_repo()
    def switch_branch():
        """Interactively switch to another branch (alias: sb)."""
        checkout_branch_interactive()

    return {
        "check_branch": check_branch,
        "create_branch": create_branch,
        "list_owned_branches": list_owned_branches,
        "delete_branch": delete_branch,
        "switch_branch": switch_branch,
    }
