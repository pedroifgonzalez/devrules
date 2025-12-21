from typing import Any, Callable, Dict, Optional

import typer

from devrules.config import load_config
from devrules.core.git_service import (
    checkout_branch_interactive,
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
from devrules.messages import branch as msg
from devrules.utils import gum
from devrules.utils.gum import GUM_AVAILABLE
from devrules.utils.typer import add_typer_block_message
from devrules.validators.branch import (
    validate_branch,
    validate_cross_repo_card,
    validate_single_branch_per_issue_env,
)
from devrules.validators.ownership import list_user_owned_branches
from devrules.validators.repo_state import display_repo_state_issues, validate_repo_state


def _handle_forbidden_cross_repo_card(gh_project_item: Any, config: Any, repo_message: str) -> None:
    # Prefer a concise, user-friendly message using centralized text.
    try:
        # Derive the expected and actual repo labels for the message.
        expected = f"{getattr(config.github, 'owner', '')}/{getattr(config.github, 'repo', '')}"
        actual = None

        content = getattr(gh_project_item, "content", None) or {}
        if isinstance(content, dict):
            actual = content.get("repository") or None

        if not actual and gh_project_item.repository:
            repo_url = str(gh_project_item.repository)
            if "github.com/" in repo_url:
                parts = repo_url.rstrip("/").split("github.com/")[-1].split("/")
                if len(parts) >= 2:
                    actual = f"{parts[0]}/{parts[1]}"

        if not actual:
            actual = "<unknown>"

        typer.secho(
            msg.CROSS_REPO_CARD_FORBIDDEN.format(actual, expected),
            fg=typer.colors.RED,
        )
    except Exception:
        # Fallback to the raw validator message if anything goes wrong.
        typer.secho(f"\n✘ {repo_message}", fg=typer.colors.RED)

    raise typer.Exit(code=1)


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

        def at_least_one_validation_repo_state_set():
            return any((config.validation.check_uncommitted, config.validation.check_behind_remote))

        # Validate repository state before creating branch
        if not skip_checks and at_least_one_validation_repo_state_set():
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

            # Optional rule: forbid creating branches for cards/issues that belong
            # to a different repository than the one configured for this project.
            if config.branch.forbid_cross_repo_cards:
                is_same_repo, repo_message = validate_cross_repo_card(
                    gh_project_item, config.github
                )

                if not is_same_repo:
                    _handle_forbidden_cross_repo_card(gh_project_item, config, repo_message)

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
            typer.secho(msg.NO_BRANCHES_OWNED_BY_YOU, fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

        add_typer_block_message(
            header="Branches owned by you",
            subheader="",
            messages=[f"- {b}" for b in branches],
            indent_block=False,
        )

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
        ensure_git_repo()

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
                    msg.REFUSING_TO_DELETE_SHARED_BRANCH.format(selected_branch), fg=typer.colors.RED
                )
                raise typer.Exit(code=1)

            # Prevent deleting the currently checked-out branch
            if current_branch == selected_branch:
                typer.secho(msg.CANNOT_DELETE_CURRENT_BRANCH, fg=typer.colors.RED)
                raise typer.Exit(code=1)

            # Enforce ownership rules before allowing delete using the same logic
            if selected_branch not in owned_branches:
                typer.secho(msg.NOT_ALLOWED_TO_DELETE_BRANCH.format(selected_branch), fg=typer.colors.RED)
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
    def delete_merged(
        remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
    ):
        """Delete branches that have been merged into develop (interactive)."""

        ensure_git_repo()

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
    def switch_branch(
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
    ):
        """Interactively switch to another branch (alias: sb)."""
        config = load_config(config_file)
        checkout_branch_interactive(config)

    # Alias for switch-branch
    @app.command(name="sb", hidden=True)
    def sb(
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
    ):
        """Alias for switch-branch."""
        config = load_config(config_file)
        checkout_branch_interactive(config)

    return {
        "check_branch": check_branch,
        "create_branch": create_branch,
        "list_owned_branches": list_owned_branches,
        "delete_branch": delete_branch,
        "delete_merged": delete_merged,
        "switch_branch": switch_branch,
        "sb": sb,
    }
