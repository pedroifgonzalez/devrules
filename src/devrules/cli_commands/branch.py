from typing import Any, Callable, Dict, Optional

import typer
from typer_di import Depends

from devrules.cli_commands.context_builders.branch import BranchCtxBuilder
from devrules.core.git_service import (
    checkout_branch_interactive,
    create_and_checkout_branch,
    delete_branch_local_and_remote,
    get_current_branch,
    get_merged_branches,
    handle_existing_branch,
)
from devrules.messages import branch as msg
from devrules.utils import gum
from devrules.utils.decorators import ensure_git_repo
from devrules.utils.gum import GUM_AVAILABLE
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
        branch: Optional[str] = typer.Argument(
            None, help="Name of the branch to delete (omit for interactive mode)"
        ),
        remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
        force: bool = typer.Option(False, "--force", "-f", help="Force delete even if not merged"),
    ):
        """Delete a branch locally and on the remote, enforcing ownership rules."""

        # Load owned branches first (used for interactive and validation)
        try:
            owned_branches = list_user_owned_branches()
        except RuntimeError as e:
            typer.secho(f"✘ {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        if not owned_branches:
            typer.secho(msg.NO_OWNED_BRANCHES_TO_DELETE, fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

        # Interactive selection if branch not provided
        branches = [branch] if branch else []
        if not branches:
            if GUM_AVAILABLE:
                print(gum.style("🗑 Delete branches", foreground=81, bold=True))
                print(gum.style("=" * 50, foreground=81))
                branches = gum.choose(
                    options=owned_branches, header="Select branches to be deleted:", limit=0
                )
            else:
                add_typer_block_message(
                    header="🗑 Delete Branches",
                    subheader="📋 Select branches to be deleted:",
                    messages=[f"{idx}. {b}" for idx, b in enumerate(owned_branches, 1)],
                )
                typer.echo()
                choices = typer.prompt("Enter number, multiple separated by a space", type=str)
                choices = choices.split(" ")
                try:
                    choices = [int(choice) for choice in choices]
                except ValueError:
                    typer.secho(msg.INVALID_CHOICE, fg=typer.colors.RED)
                    raise typer.Exit(code=1)
                for choice in choices:
                    if choice < 1 or choice > len(owned_branches):
                        typer.secho(msg.INVALID_CHOICE, fg=typer.colors.RED)
                        raise typer.Exit(code=1)
                    to_delete = owned_branches[choice - 1]
                    branches.append(to_delete)

        # Basic safety: don't delete main shared branches through this command
        current_branch = get_current_branch()
        for selected_branch in branches:
            protected_branches = ("main", "master", "develop")
            is_release_branch = selected_branch.startswith("release/")
            if selected_branch in protected_branches or is_release_branch:
                typer.secho(
                    msg.REFUSING_TO_DELETE_SHARED_BRANCH.format(selected_branch),
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)

            # Prevent deleting the currently checked-out branch
            if current_branch == selected_branch:
                typer.secho(msg.CANNOT_DELETE_CURRENT_BRANCH, fg=typer.colors.RED)
                raise typer.Exit(code=1)

            # Enforce ownership rules before allowing delete using the same logic
            if selected_branch not in owned_branches:
                typer.secho(
                    msg.NOT_ALLOWED_TO_DELETE_BRANCH.format(selected_branch), fg=typer.colors.RED
                )
                raise typer.Exit(code=1)

        if branches:
            typer.echo()
            typer.secho(msg.DELETE_BRANCHES_STATEMENT)
            messages = [f"✘ {b}" for _, b in enumerate(branches, 1)]
            for message in messages:
                typer.secho(f"    {message}")
            typer.echo()

            if GUM_AVAILABLE:
                confirmation = gum.confirm(message="Continue?")
            else:
                confirmation = typer.confirm("Continue?", default=False)

            if not confirmation:
                typer.echo(msg.CANCELLED)
                raise typer.Exit(code=0)

            for selected_branch in branches:
                delete_branch_local_and_remote(selected_branch, remote, force)
        else:
            typer.secho(msg.NO_SELECTED_BRANCHES_TO_DELETE, fg=typer.colors.YELLOW)

        raise typer.Exit(code=0)

    @app.command()
    @ensure_git_repo()
    def delete_merged(
        remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
    ):
        """Delete branches that have been merged into develop (interactive)."""

        if GUM_AVAILABLE:
            gum.print_stick_header(header="Delete merged branches")

        # 1. Get branches merged into develop
        merged_branches = set(get_merged_branches(base_branch="develop"))

        if not merged_branches:
            typer.secho(msg.NO_MERGED_BRANCHES, fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

        # 2. Get owned branches
        try:
            owned_branches = set(list_user_owned_branches())
        except RuntimeError as e:
            typer.secho(f"✘ {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        # 3. Intersect: Only delete merged branches that are owned by the user
        candidates = sorted(list(merged_branches.intersection(owned_branches)))

        # 4. Filter out protected branches and current branch
        current_branch = get_current_branch()
        final_candidates = []

        for b in candidates:
            if b in ("main", "master", "develop") or b.startswith("release/"):
                continue
            if b == current_branch:
                continue
            final_candidates.append(b)

        if not final_candidates:
            typer.secho(msg.NO_OWNED_MERGED_BRANCHES, fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

        if GUM_AVAILABLE:
            delete_branches_selection = gum.choose(
                header="Select branches to delete",
                options=final_candidates,
                limit=0,
            )
            assert isinstance(delete_branches_selection, list)
            if not delete_branches_selection:
                typer.secho("No branches selected for deletion.", fg=typer.colors.YELLOW)
                raise typer.Exit(code=1)
            delete_branches = [f"✘ {b}" for b in delete_branches_selection]
            gum.print_list(
                header="⚠ You are about to delete the following branches:",
                items=delete_branches,
            )
            response = gum.confirm("Delete these branches?")
            final_candidates = delete_branches_selection
        else:
            add_typer_block_message(
                header="🗑 Delete Merged Branches",
                subheader="Branches already merged and owned by you:",
                messages=[f"{idx}. {b}" for idx, b in enumerate(final_candidates, 1)],
            )
            typer.echo()
            choices = typer.prompt("Enter number, multiple separated by a space", type=str)
            choices = choices.split(" ")
            delete_branches = []
            try:
                choices = [int(choice) for choice in choices]
            except ValueError:
                typer.secho(msg.INVALID_CHOICE, fg=typer.colors.RED)
                raise typer.Exit(code=1)
            for choice in choices:
                if choice < 1 or choice > len(final_candidates):
                    typer.secho(msg.INVALID_CHOICE, fg=typer.colors.RED)
                    raise typer.Exit(code=1)
                to_delete = final_candidates[choice - 1]
                delete_branches.append(to_delete)
            final_candidates = delete_branches
            typer.echo()
            typer.secho("⚠ You are about to delete the following branches:")
            for branch in delete_branches:
                typer.secho(f"✘ {branch}")
            typer.echo()
            response = typer.confirm("Delete these branches?")

        if not response:
            typer.echo(msg.CANCELLED)
            raise typer.Exit(code=0)

        typer.echo()
        for b in final_candidates:
            delete_branch_local_and_remote(b, remote, force=False, ignore_remote_error=True)

        raise typer.Exit(code=0)

    @app.command(name="switch-branch")
    @ensure_git_repo()
    def switch_branch():
        """Interactively switch to another branch (alias: sb)."""
        checkout_branch_interactive()

    # Alias for switch-branch
    @app.command(name="sb", hidden=True)
    @ensure_git_repo()
    def sb():
        """Alias for switch-branch."""
        checkout_branch_interactive()

    return {
        "check_branch": check_branch,
        "create_branch": create_branch,
        "list_owned_branches": list_owned_branches,
        "delete_branch": delete_branch,
        "delete_merged": delete_merged,
        "switch_branch": switch_branch,
        "sb": sb,
    }
