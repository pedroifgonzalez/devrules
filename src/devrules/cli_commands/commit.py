import os
from typing import Any, Callable, Dict, Optional

import typer

from devrules.config import load_config
from devrules.core.git_service import ensure_git_repo, get_current_branch, get_current_issue_number
from devrules.validators.commit import validate_commit
from devrules.validators.ownership import validate_branch_ownership


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command()
    def check_commit(
        file: str,
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
    ):
        """Validate commit message format."""
        config = load_config(config_file)

        if not os.path.exists(file):
            typer.secho(f"Commit message file not found: {file}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        with open(file, "r") as f:
            message = f.read().strip()

        is_valid, result_message = validate_commit(message, config.commit)

        if is_valid:
            typer.secho(f"✔ {result_message}", fg=typer.colors.GREEN)
            raise typer.Exit(code=0)
        else:
            typer.secho(f"✘ {result_message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    @app.command()
    def commit(
        message: str,
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
    ):
        """Validate and commit changes with a properly formatted message."""
        import subprocess

        config = load_config(config_file)

        # Validate commit
        is_valid, result_message = validate_commit(message, config.commit)

        if not is_valid:
            typer.secho(f"\n✘ {result_message}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        ensure_git_repo()
        current_branch = get_current_branch()

        # Check if current branch is protected (e.g., staging branches for merging)
        if config.commit.protected_branch_prefixes:
            for prefix in config.commit.protected_branch_prefixes:
                if current_branch.count(prefix):
                    typer.secho(
                        f"✘ Cannot commit directly to '{current_branch}'. "
                        f"Branches containing '{prefix}' are protected (merge-only).",
                        fg=typer.colors.RED,
                    )
                    raise typer.Exit(code=1)

        if config.commit.restrict_branch_to_owner:
            # Check branch ownership to prevent committing on another developer's branch
            is_owner, ownership_message = validate_branch_ownership(current_branch)
            if not is_owner:
                typer.secho(f"✘ {ownership_message}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        if config.commit.append_issue_number:
            # Append issue number if configured and not already present
            issue_number = get_current_issue_number()
            if issue_number and f"#{issue_number}" not in message:
                message = f"#{issue_number} {message}"

        options = []
        if config.commit.gpg_sign:
            options.append("-S")
        if config.commit.allow_hook_bypass:
            options.append("-n")
        options.append("-m")
        options.append(message)
        try:
            subprocess.run(
                [
                    "git",
                    "commit",
                    *options,
                ],
                check=True,
            )
            typer.secho("\n✔ Committed changes!", fg=typer.colors.GREEN)
        except subprocess.CalledProcessError as e:
            typer.secho(f"\n✘ Failed to commit changes: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1) from e

    return {
        "check_commit": check_commit,
        "commit": commit,
    }
