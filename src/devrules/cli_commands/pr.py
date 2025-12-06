import re
from typing import Any, Callable, Dict, Optional

import typer

from devrules.config import load_config
from devrules.core.git_service import ensure_git_repo, get_current_branch
from devrules.core.github_service import ensure_gh_installed, fetch_pr_info
from devrules.validators.documentation import display_documentation_guidance
from devrules.validators.pr import validate_pr
from devrules.validators.pr_target import (
    suggest_pr_target,
    validate_pr_base_not_protected,
    validate_pr_target,
)


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command()
    def create_pr(
        base: str = typer.Option(
            "develop", "--base", "-b", help="Base branch for the pull request"
        ),
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
        project: Optional[str] = typer.Option(
            None,
            "--project",
            "-p",
            help="Project to check issue status against (faster than checking all)",
        ),
        skip_checks: bool = typer.Option(
            False, "--skip-checks", help="Skip target validation and documentation checks"
        ),
    ):
        """Create a GitHub pull request for the current branch against the base branch."""
        import subprocess

        ensure_gh_installed()
        ensure_git_repo()

        # Load config first
        config = load_config(config_file)

        # Determine current branch
        current_branch = get_current_branch()

        # Validate that current branch is not protected (staging branches)
        if not skip_checks:
            is_valid_base, base_message = validate_pr_base_not_protected(
                current_branch,
                config.commit.protected_branch_prefixes,
            )
            if not is_valid_base:
                typer.secho(f"\n✘ {base_message}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        # Validate PR target branch
        if not skip_checks:
            is_valid_target, target_message = validate_pr_target(
                source_branch=current_branch,
                target_branch=base,
                config=config.pr,
            )

            if not is_valid_target:
                typer.secho("\n✘ Invalid PR Target", fg=typer.colors.RED, bold=True)
                typer.echo(f"  {target_message}")

                # Try to suggest a better target
                suggested = suggest_pr_target(current_branch, config.pr)
                if suggested:
                    typer.echo(f"\n💡 Suggested target: {suggested}")
                    typer.echo(f"   Try: devrules create-pr --base {suggested}")

                typer.echo()
                raise typer.Exit(code=1)

        # Show context-aware documentation
        if not skip_checks and config.documentation.show_on_pr and config.documentation.rules:
            display_documentation_guidance(
                rules=config.documentation.rules,
                base_branch=base,
                show_files=True,
            )

        if current_branch == base:
            typer.secho(
                "✘ Current branch is the same as the base branch; nothing to create a PR for.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        # Derive PR title from branch name
        # Example: feature/add-create-pr-command -> [FTR] Add create pr command
        prefix = None
        name_part = current_branch
        if "/" in current_branch:
            prefix, name_part = current_branch.split("/", 1)

        # Map common prefixes to tags, falling back to FTR
        prefix_to_tag = {
            "feature": "FTR",
            "bugfix": "FIX",
            "hotfix": "FIX",
            "docs": "DOCS",
            "release": "REF",
        }

        tag = prefix_to_tag.get(prefix or "", "FTR")

        # Strip a leading numeric issue and hyphen if present (e.g. 123-add-thing)
        name_core = name_part
        issue_match = re.match(r"^(\d+)-(.*)$", name_core)
        if issue_match:
            name_core = issue_match.group(2)

        words = name_core.replace("_", "-").split("-")
        words = [w for w in words if w]
        humanized = " ".join(words).lower()
        if humanized:
            humanized = humanized[0].upper() + humanized[1:]

        pr_title = f"[{tag}] {humanized}" if humanized else f"[{tag}] {current_branch}"

        # Validate issue status if enabled
        if config.pr.require_issue_status_check:
            from devrules.validators.pr import validate_pr_issue_status

            typer.echo("\n🔍 Checking issue status...")

            # Use CLI project option if provided, otherwise use config
            project_override = [project] if project else None
            is_valid, messages = validate_pr_issue_status(
                current_branch, config.pr, config.github, project_override=project_override
            )

            for msg in messages:
                if "✔" in msg or "ℹ" in msg:
                    typer.secho(msg, fg=typer.colors.GREEN)
                elif "⚠" in msg:
                    typer.secho(msg, fg=typer.colors.YELLOW)
                else:
                    typer.secho(msg, fg=typer.colors.RED)

            if not is_valid:
                typer.echo()
                typer.secho(
                    "✘ Cannot create PR: Issue status check failed",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)

            typer.echo()

        cmd = [
            "gh",
            "pr",
            "create",
            "--base",
            base,
            "--head",
            current_branch,
            "--title",
            pr_title,
            "--fill",
        ]

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            typer.secho(f"✘ Failed to create pull request: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        typer.secho(f"✔ Created pull request: {pr_title}", fg=typer.colors.GREEN)

    @app.command()
    def check_pr(
        pr_number: int,
        owner: Optional[str] = typer.Option(None, "--owner", "-o", help="GitHub repository owner"),
        repo: Optional[str] = typer.Option(None, "--repo", "-r", help="GitHub repository name"),
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
    ):
        """Validate PR size and title format."""
        config = load_config(config_file)

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

        for msg in messages:
            if "✔" in msg or "ℹ" in msg:
                typer.secho(msg, fg=typer.colors.GREEN)
            elif "⚠" in msg:
                typer.secho(msg, fg=typer.colors.YELLOW)
            else:
                typer.secho(msg, fg=typer.colors.RED)

        raise typer.Exit(code=0 if is_valid else 1)

    return {
        "create_pr": create_pr,
        "check_pr": check_pr,
    }
