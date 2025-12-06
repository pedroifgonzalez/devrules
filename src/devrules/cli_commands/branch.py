from typing import Any, Callable, Dict, Optional

import typer

from devrules.config import load_config
from devrules.core.git_service import (
    create_and_checkout_branch,
    create_staging_branch_name,
    delete_branch_local_and_remote,
    detect_scope,
    ensure_git_repo,
    get_branch_name_interactive,
    get_current_branch,
    get_existing_branches,
    get_merged_branches,
    handle_existing_branch,
    resolve_issue_branch,
)
from devrules.core.project_service import find_project_item_for_issue, resolve_project_number
from devrules.validators.branch import validate_branch, validate_single_branch_per_issue_env
from devrules.validators.ownership import list_user_owned_branches
from devrules.validators.repo_state import display_repo_state_issues, validate_repo_state


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command()
    def check_branch(
        branch: str,
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
    ):
        """Validate branch naming convention."""
        config = load_config(config_file)
        is_valid, message = validate_branch(branch, config.branch)

        if is_valid:
            typer.secho(f"✔ {message}", fg=typer.colors.GREEN)
            raise typer.Exit(code=0)
        else:
            typer.secho(f"✘ {message}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    @app.command()
    def create_branch(
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
        branch_name: Optional[str] = typer.Argument(
            None, help="Branch name (if not provided, interactive mode)"
        ),
        project: Optional[str] = typer.Option(
            None, "--project", "-p", help="Project to extract the information from"
        ),
        issue: Optional[int] = typer.Option(
            None, "--issue", "-i", help="Issue to extract the information from"
        ),
        for_staging: bool = typer.Option(
            False, "--for-staging", "-fs", help="Create staging branch based on current branch"
        ),
        skip_checks: bool = typer.Option(
            False, "--skip-checks", help="Skip repository state validation"
        ),
    ):
        """Create a new Git branch with validation (interactive mode)."""
        config = load_config(config_file)
        ensure_git_repo()

        # Validate repository state before creating branch
        if not skip_checks and (
            config.validation.check_uncommitted or config.validation.check_behind_remote
        ):
            typer.echo("\n🔍 Checking repository state...")
            is_valid, messages = validate_repo_state(
                check_uncommitted=config.validation.check_uncommitted,
                check_behind=config.validation.check_behind_remote,
                warn_only=config.validation.warn_only,
            )

            if not is_valid:
                display_repo_state_issues(messages, warn_only=False)
                typer.echo()
                raise typer.Exit(code=1)
            elif messages and not all("✅" in msg for msg in messages):
                # Show warnings but continue
                display_repo_state_issues(messages, warn_only=True)
                if not typer.confirm("\n  Continue anyway?", default=False):
                    typer.echo("Cancelled.")
                    raise typer.Exit(code=0)

        # Determine branch name from different sources
        if for_staging:
            current_branch = get_current_branch()
            final_branch_name = create_staging_branch_name(current_branch)
            typer.echo(f"\n🔄 Creating staging branch from: {current_branch}")
        elif branch_name:
            final_branch_name = branch_name
        elif issue and project:
            owner, project_number = resolve_project_number(project=project)
            gh_project_item = find_project_item_for_issue(
                owner=owner, project_number=project_number, issue=issue
            )
            scope = detect_scope(config=config, project_item=gh_project_item)
            final_branch_name = resolve_issue_branch(
                scope=scope, project_item=gh_project_item, issue=issue
            )
        else:
            final_branch_name = get_branch_name_interactive(config)

        # Validate branch name
        typer.echo(f"\n🔍 Validating branch name: {final_branch_name}")
        is_valid, message = validate_branch(final_branch_name, config.branch)

        if not is_valid:
            typer.secho(f"\n✘ {message}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        typer.secho("✔ Branch name is valid!", fg=typer.colors.GREEN)

        # Enforce one-branch-per-issue-per-environment rule when enabled
        if config.branch.enforce_single_branch_per_issue_env:
            existing_branches = get_existing_branches()
            is_unique, uniqueness_message = validate_single_branch_per_issue_env(
                final_branch_name, existing_branches
            )

            if not is_unique:
                typer.secho(f"\n✘ {uniqueness_message}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        # Check if branch already exists and handle it
        handle_existing_branch(final_branch_name)

        # Confirm creation
        typer.echo(f"\n📌 Ready to create branch: {final_branch_name}")
        if not typer.confirm("\n  Create and checkout?", default=True):
            typer.echo("Cancelled.")
            raise typer.Exit(code=0)

        # Create and checkout branch
        create_and_checkout_branch(final_branch_name)

    @app.command()
    def list_owned_branches():
        """Show all local Git branches owned by the current user."""

        try:
            branches = list_user_owned_branches()
        except RuntimeError as e:
            typer.secho(f"✘ {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        if not branches:
            typer.secho("No branches owned by you were found.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

        typer.secho("Branches owned by you:\n", fg=typer.colors.GREEN, bold=True)
        for b in branches:
            typer.echo(f"- {b}")

        raise typer.Exit(code=0)

    @app.command()
    def delete_branch(
        branch: Optional[str] = typer.Argument(
            None, help="Name of the branch to delete (omit for interactive mode)"
        ),
        remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
        force: bool = typer.Option(False, "--force", "-f", help="Force delete even if not merged"),
    ):
        """Delete a branch locally and on the remote, enforcing ownership rules."""

        import subprocess

        ensure_git_repo()

        # Load owned branches first (used for interactive and validation)
        try:
            owned_branches = list_user_owned_branches()
        except RuntimeError as e:
            typer.secho(f"✘ {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        if not owned_branches:
            typer.secho("No owned branches available to delete.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

        # Interactive selection if branch not provided
        if branch is None:
            typer.secho("\n🗑 Delete Branch", fg=typer.colors.CYAN, bold=True)
            typer.echo("=" * 50)
            typer.echo("\n📋 Select a branch to delete:")

            for idx, b in enumerate(owned_branches, 1):
                typer.echo(f"  {idx}. {b}")

            choice = typer.prompt("\nEnter number", type=int)

            if choice < 1 or choice > len(owned_branches):
                typer.secho("✘ Invalid choice", fg=typer.colors.RED)
                raise typer.Exit(code=1)

            branch = owned_branches[choice - 1]

        # Basic safety: don't delete main shared branches through this command
        if branch in ("main", "master", "develop") or branch.startswith("release/"):
            typer.secho(
                f"✘ Refusing to delete shared branch '{branch}' via CLI.", fg=typer.colors.RED
            )
            raise typer.Exit(code=1)

        # Prevent deleting the currently checked-out branch
        try:
            current_branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
            current_branch = current_branch_result.stdout.strip()
        except subprocess.CalledProcessError:
            typer.secho("✘ Unable to determine current branch", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        if current_branch == branch:
            typer.secho("✘ Cannot delete the branch you are currently on.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        # Enforce ownership rules before allowing delete using the same logic
        if branch not in owned_branches:
            typer.secho(
                f"✘ You are not allowed to delete branch '{branch}' because you do not own it.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        # Confirm deletion
        typer.echo(f"You are about to delete branch '{branch}' locally and from remote '{remote}'.")
        if not typer.confirm("  Continue?", default=False):
            typer.echo("Cancelled.")
            raise typer.Exit(code=0)

        # Delete branch using service
        delete_branch_local_and_remote(branch, remote, force)

        raise typer.Exit(code=0)

    @app.command()
    def delete_merged(
        remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
    ):
        """Delete branches that have been merged into develop (interactive)."""

        ensure_git_repo()

        # 1. Get branches merged into develop
        merged_branches = set(get_merged_branches(base_branch="develop"))

        if not merged_branches:
            typer.secho("No branches found that are merged into develop.", fg=typer.colors.YELLOW)
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
            typer.secho(
                "No owned merged branches available to delete (filtered protected/current).",
                fg=typer.colors.YELLOW,
            )
            raise typer.Exit(code=0)

        # 5. Show candidates
        typer.secho("\n🗑 Delete Merged Branches", fg=typer.colors.CYAN, bold=True)
        typer.echo("=" * 50)
        typer.echo(
            f"\nThe following branches are merged into 'develop' and owned by you.\nThey will be deleted locally and from remote '{remote}':\n"
        )

        for b in final_candidates:
            typer.echo(f"  - {b}")

        # 6. Confirm
        if not typer.confirm("\n  Delete these branches?", default=False):
            typer.echo("Cancelled.")
            raise typer.Exit(code=0)

        # 7. Delete
        typer.echo()
        for b in final_candidates:
            delete_branch_local_and_remote(b, remote, force=False, ignore_remote_error=True)

        raise typer.Exit(code=0)

    return {
        "check_branch": check_branch,
        "create_branch": create_branch,
        "list_owned_branches": list_owned_branches,
        "delete_branch": delete_branch,
        "delete_merged": delete_merged,
    }
