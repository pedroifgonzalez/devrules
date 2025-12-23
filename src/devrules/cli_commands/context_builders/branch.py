from pathlib import Path
from typing import Annotated, Any, Optional

import typer
from typing_extensions import Self
from yaspin import yaspin

from devrules.cli_commands.context_builders.base import BaseCtxBuilder
from devrules.config import load_config
from devrules.core.git_service import (
    create_staging_branch_name,
    detect_scope,
    get_branch_name_interactive,
    get_current_branch,
    get_existing_branches,
    resolve_issue_branch,
)
from devrules.core.project_service import find_project_item_for_issue, resolve_project_number
from devrules.messages import branch as msg
from devrules.validators.branch import (
    validate_branch,
    validate_cross_repo_card,
    validate_single_branch_per_issue_env,
)
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
        self.set_config(config_file)
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
                owner, project_number = resolve_project_number(project=project)
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
