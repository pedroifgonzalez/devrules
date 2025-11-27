import os
from typing import Optional, Dict, Callable, Any
from devrules.config import load_config
from devrules.validators.commit import validate_commit
from devrules.core.git_service import ensure_git_repo
from devrules.core.git_service import get_current_branch
from devrules.validators.ownership import validate_branch_ownership
from devrules.core.git_service import get_current_issue_number
import typer


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

        if config.commit.restrict_branch_to_owner:
            # Check branch ownership to prevent committing on another developer's branch
            current_branch = get_current_branch()

            is_owner, ownership_message = validate_branch_ownership(current_branch)
            if not is_owner:
                typer.secho(f"✘ {ownership_message}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        if config.commit.append_issue_number:
            # Append issue number if configured and not already present
            issue_number = get_current_issue_number()
            if issue_number and f"#{issue_number}" not in message:
                message = f"#{issue_number} {message}"

        try:
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-n" if config.commit.allow_hook_bypass else "",
                    "-m",
                    message,
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
