from devrules.core.git_service import ensure_git_repo, get_current_branch
from devrules.core.github_service import ensure_gh_installed
from typing import Dict, Callable, Any, Optional
import typer
import re
from devrules.config import load_config
from devrules.core.github_service import fetch_pr_info
from devrules.validators.pr import validate_pr


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command()
    def create_pr(
        base: str = typer.Option(
            "develop", "--base", "-b", help="Base branch for the pull request"
        ),
    ):
        """Create a GitHub pull request for the current branch against the base branch."""
        import subprocess

        ensure_gh_installed()
        ensure_git_repo()

        # Determine current branch
        current_branch = get_current_branch()

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

        is_valid, messages = validate_pr(pr_info, config.pr)

        for msg in messages:
            if "✔" in msg:
                typer.secho(msg, fg=typer.colors.GREEN)
            else:
                typer.secho(msg, fg=typer.colors.RED)

        raise typer.Exit(code=0 if is_valid else 1)

    return {
        "create_pr": create_pr,
        "check_pr": check_pr,
    }
