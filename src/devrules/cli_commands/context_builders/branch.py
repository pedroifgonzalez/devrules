from pathlib import Path
from typing import Annotated, Any, Optional

import typer
from typing_extensions import TypedDict

from devrules.config import Config, load_config
from devrules.core.git_service import (
    create_staging_branch_name,
    detect_scope,
    get_branch_name_interactive,
    get_current_branch,
    resolve_issue_branch,
)
from devrules.core.project_service import find_project_item_for_issue, resolve_project_number
from devrules.messages import branch as msg
from devrules.validators.branch import validate_cross_repo_card
from devrules.validators.repo_state import display_repo_state_issues, validate_repo_state


class CreateBranchCtx(TypedDict):
    config: Config
    final_branch_name: str


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


def create_branch_context(
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
) -> CreateBranchCtx:
    config = load_config(config_file)

    if any((config.validation.check_uncommitted, config.validation.check_behind_remote)):
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
        if config.branch.forbid_cross_repo_cards:
            is_same_repo, repo_message = validate_cross_repo_card(gh_project_item, config.github)
            if not is_same_repo:
                _handle_forbidden_cross_repo_card(gh_project_item, config, repo_message)
        scope = detect_scope(config=config, project_item=gh_project_item)
        final_branch_name = resolve_issue_branch(
            scope=scope, project_item=gh_project_item, issue=issue
        )
    else:
        final_branch_name = get_branch_name_interactive(config)

    return CreateBranchCtx(
        config=config,
        final_branch_name=final_branch_name,
    )
