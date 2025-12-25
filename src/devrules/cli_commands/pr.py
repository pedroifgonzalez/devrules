from typing import Any, Callable, Dict, Optional

import typer
from typer_di import Depends

from devrules.cli_commands.context_builders.pr import PrCtxBuilder
from devrules.config import Config, load_config
from devrules.core.git_service import get_current_branch
from devrules.core.github_service import fetch_pr_info
from devrules.utils.decorators import ensure_git_repo
from devrules.validators.pr import validate_pr

builder = PrCtxBuilder()


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command()
    def check_pr(
        pr_number: int,
        owner: Optional[str] = typer.Option(None, "--owner", "-o", help="GitHub repository owner"),
        repo: Optional[str] = typer.Option(None, "--repo", "-r", help="GitHub repository name"),
        config: Config = Depends(load_config),
    ):
        """Validate PR size and title format."""
        # Use CLI arguments if provided, otherwise fall back to config
        github_owner = owner or config.github.owner
        github_repo = repo or config.github.repo

        if not github_owner or not github_repo:
            typer.secho(
                "✘ GitHub owner and repo must be provided via CLI arguments (--owner, --repo) "
                "or configured in the config file under [github] section.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        try:
            pr_info = fetch_pr_info(github_owner, github_repo, pr_number, config.github)
        except ValueError as e:
            typer.secho(f"✘ {str(e)}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        except Exception as e:
            typer.secho(f"✘ Error fetching PR: {str(e)}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        typer.echo(f"PR Title: {pr_info.title}")
        typer.echo(f"Total LOC: {pr_info.additions + pr_info.deletions}")
        typer.echo(f"Files changed: {pr_info.changed_files}")
        typer.echo("")

        # Get current branch for status validation
        current_branch = None
        if config.pr.require_issue_status_check:
            try:
                current_branch = get_current_branch()
            except Exception:
                # If we can't get current branch, validation will skip status check
                pass

        is_valid, messages = validate_pr(
            pr_info, config.pr, current_branch=current_branch, github_config=config.github
        )

        for message in messages:
            if "✔" in message or "ℹ" in message:
                typer.secho(message, fg=typer.colors.GREEN)
            elif "⚠" in message:
                typer.secho(message, fg=typer.colors.YELLOW)
            else:
                typer.secho(message, fg=typer.colors.RED)

        raise typer.Exit(code=0 if is_valid else 1)

    @app.command()
    @ensure_git_repo()
    def ipr(ctx: PrCtxBuilder = Depends(builder.build_create_pr_context)):
        """Interactive PR creation - select target branch with guided prompts."""
        # Validate that current branch is not protected
        ctx.validate_current_branch_is_not_protected()
        ctx.show_documentation()
        ctx.validate_current_branch_is_not_base()
        ctx.derive_pr_title()
        ctx.allow_edit_pr_title()
        ctx.validate_pr_status()
        ctx.confirm_pr()
        ctx.auto_push_if_enabled()
        ctx.create_pr()

    return {
        "check_pr": check_pr,
        "ipr": ipr,
    }
