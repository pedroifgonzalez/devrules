from pathlib import Path
from typing import Annotated, Any, Optional

import typer
from typing_extensions import Self
from yaspin import yaspin

from devrules.cli_commands.context_builders.base import BaseCtxBuilder
from devrules.config import load_config
from devrules.core.git_service import (
    create_staging_branch_name,
    delete_branch_local_and_remote,
    detect_scope,
    get_branch_name_interactive,
    get_current_branch,
    get_existing_branches,
    resolve_issue_branch,
)
from devrules.core.project_service import find_project_item_for_issue, resolve_project_number
from devrules.messages import branch as msg
from devrules.utils import gum
from devrules.utils.typer import add_typer_block_message
from devrules.validators.branch import (
    validate_branch,
    validate_cross_repo_card,
    validate_single_branch_per_issue_env,
)
from devrules.validators.ownership import list_user_owned_branches
from devrules.validators.repo_state import display_repo_state_issues, validate_repo_state


class BranchCtxBuilder(BaseCtxBuilder):
    def set_final_branch_name(self, final_branch_name: str) -> Self:
        self.final_branch_name = final_branch_name
        return self

    def confirm_branch_creation(self):
        typer.echo(f"\n📌 Ready to create branch: {self.final_branch_name}")
        if not typer.confirm("\n  Create and checkout?", default=True):
            typer.echo("Cancelled.")
            raise typer.Exit(code=0)

    def enforce_one_branch_per_issue_if_enabled(self):
        if self.config.branch.enforce_single_branch_per_issue_env:
            existing_branches = get_existing_branches()
            is_unique, uniqueness_message = validate_single_branch_per_issue_env(
                self.final_branch_name, existing_branches
            )
            if not is_unique:
                typer.secho(f"✘ {uniqueness_message}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

    def _validate_branch(self):
        with yaspin(text="Validating branch name...", color="yellow"):
            is_valid, message = validate_branch(self.final_branch_name, self.config.branch)
            if is_valid:
                typer.secho(f"✔ {message}", fg=typer.colors.GREEN)
            else:
                typer.secho(f"✘ {message}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

    def _handle_forbidden_cross_repo_card(
        self, gh_project_item: Any, config: Any, repo_message: str
    ) -> None:
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

    def validate_repo_state(self):
        perform_validation = any(
            (self.config.validation.check_uncommitted, self.config.validation.check_behind_remote)
        )
        if perform_validation:
            with yaspin(text="🔍 Checking repository state...", color="green"):
                is_valid, messages = validate_repo_state(
                    check_uncommitted=self.config.validation.check_uncommitted,
                    check_behind=self.config.validation.check_behind_remote,
                    warn_only=self.config.validation.warn_only,
                )
                if not is_valid:
                    display_repo_state_issues(messages, warn_only=False)
                    typer.echo()
                    raise typer.Exit(code=1)
                elif messages and not all("✅" in msg for msg in messages):
                    display_repo_state_issues(messages, warn_only=True)
                    if not typer.confirm("\n  Continue anyway?", default=False):
                        typer.echo("Cancelled.")
                        raise typer.Exit(code=0)

    def build_check_branch_context(
        self,
        branch: str,
        config_file: Annotated[
            Optional[Path], typer.Option("--config", "-c", help="Path to config file")
        ] = None,
    ) -> Self:
        config = load_config(config_file)
        self.set_config(config)
        self.set_final_branch_name(branch)
        return self

    def build_create_branch_context(
        self,
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
        config_file: Annotated[
            Optional[Path], typer.Option("--config", "-c", help="Path to config file")
        ] = None,
    ) -> Self:
        config = load_config(config_file)
        self.set_config(config)

        # Determine branch name from different sources
        if branch_name:
            final_branch_name = branch_name
        elif for_staging:
            current_branch = get_current_branch()
            with yaspin(text=f"🔄 Creating staging branch from: {current_branch}", color="green"):
                final_branch_name = create_staging_branch_name(current_branch)
        elif issue and project:
            with yaspin(text=f"🔄 Resolving project number for {project}", color="green"):
                owner, project_number, _ = resolve_project_number(project=project)
            with yaspin(text=f"🔄 Finding project item for issue {issue}", color="green"):
                gh_project_item = find_project_item_for_issue(
                    owner=owner, project_number=project_number, issue=issue
                )
            if config.branch.forbid_cross_repo_cards:
                with yaspin(text="🔄 Validating cross-repo card", color="green"):
                    is_same_repo, repo_message = validate_cross_repo_card(
                        gh_project_item, config.github
                    )
                if not is_same_repo:
                    self._handle_forbidden_cross_repo_card(gh_project_item, config, repo_message)
            with yaspin(text="🔄 Detecting scope", color="green"):
                scope = detect_scope(config=config, project_item=gh_project_item)
            with yaspin(text="🔄 Resolving issue branch", color="green"):
                final_branch_name = resolve_issue_branch(
                    scope=scope, project_item=gh_project_item, issue=issue
                )
        else:
            final_branch_name = get_branch_name_interactive(config)

        self.set_final_branch_name(final_branch_name)

        return self

    def set_owned_branches(self, owned_branches: list[str]):
        self.owned_branches = owned_branches

    def _validate_user_has_deletable_branches(self):
        owned_branches = list_user_owned_branches()
        if not owned_branches:
            typer.secho(msg.NO_OWNED_BRANCHES_TO_DELETE, fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)
        self.set_owned_branches(owned_branches)

    def set_branches_to_delete(self, branches: list[str]):
        self.branches_to_delete = branches

    def confirm_delete_branches(self):
        if not self.branches_to_delete:
            typer.secho(msg.NO_SELECTED_BRANCHES_TO_DELETE, fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

        typer.secho(msg.DELETE_BRANCHES_STATEMENT)
        messages = [f"✘ {b}" for _, b in enumerate(self.branches_to_delete, 1)]
        for message in messages:
            typer.secho(f"    {message}")
        typer.echo()
        if gum.is_available():
            confirmation = gum.confirm(message="Continue?")
        else:
            confirmation = typer.confirm("Continue?", default=False)

        if not confirmation:
            typer.echo(msg.CANCELLED)
            raise typer.Exit(code=0)

    def validate_selected_branches_to_delete(self):
        # Basic safety: don't delete main shared branches through this command
        current_branch = get_current_branch()
        for selected_branch in self.branches_to_delete:
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
            if selected_branch not in self.owned_branches:
                typer.secho(
                    msg.NOT_ALLOWED_TO_DELETE_BRANCH.format(selected_branch), fg=typer.colors.RED
                )
                raise typer.Exit(code=1)

    def select_branches_to_delete(self, branch: Optional[str] = None):
        # Interactive selection if branch not provided
        branches = [branch] if branch else []
        if not branches:
            if gum.is_available():
                print(gum.style("🗑 Delete branches", foreground=81, bold=True))
                print(gum.style("=" * 50, foreground=81))
                branches = gum.choose(
                    options=self.owned_branches, header="Select branches to be deleted:", limit=0
                )
            else:
                add_typer_block_message(
                    header="🗑 Delete Branches",
                    subheader="📋 Select branches to be deleted:",
                    messages=[f"{idx}. {b}" for idx, b in enumerate(self.owned_branches, 1)],
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
                    if choice < 1 or choice > len(self.owned_branches):
                        typer.secho(msg.INVALID_CHOICE, fg=typer.colors.RED)
                        raise typer.Exit(code=1)
                    to_delete = self.owned_branches[choice - 1]
                    branches.append(to_delete)

        if isinstance(branches, list):
            self.set_branches_to_delete(branches)
        elif isinstance(branches, str):
            self.set_branches_to_delete([branches])

    def set_remote(self, remote: str):
        self.remote = remote

    def set_force(self, force: bool):
        self.force = force

    def build_delete_branch_context(
        self,
        branch: Optional[str] = typer.Argument(
            None, help="Name of the branch to delete (omit for interactive mode)"
        ),
        remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
        force: bool = typer.Option(False, "--force", "-f", help="Force delete even if not merged"),
    ):
        self.set_remote(remote)
        self.set_force(force)
        self._validate_user_has_deletable_branches()
        self.select_branches_to_delete(branch)
        return self

    def delete_branches(self):
        remote = self.remote
        force = self.force
        for selected_branch in self.branches_to_delete:
            delete_branch_local_and_remote(selected_branch, remote, force)
