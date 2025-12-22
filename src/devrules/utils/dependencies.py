from pathlib import Path
from typing import Annotated, Optional

import typer
from typer import Option
from typing_extensions import TypedDict
from yaspin import yaspin

from devrules.config import Config, load_config
from devrules.core.git_service import get_current_branch
from devrules.messages import commit as msg
from devrules.utils import gum
from devrules.utils.typer import add_typer_block_message
from devrules.validators.forbidden_files import (
    get_forbidden_file_suggestions,
    validate_no_forbidden_files,
)
from devrules.validators.ownership import validate_branch_ownership


def get_config(
    config_file: Annotated[
        Optional[Path], Option("--config", "-c", help="Path to config file")
    ] = None,
) -> Config:
    return load_config(config_file)


class CommitCtx(TypedDict):
    message: str
    config: Config


def perform_commit_context_builder(
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Commit message"),
    config_file: Annotated[
        Optional[Path], Option("--config", "-c", help="Path to config file")
    ] = None,
) -> CommitCtx:
    config = load_config(config_file)

    if gum.is_available():
        print(gum.style("📝 Create Commit", foreground=81, bold=True))
        print(gum.style("=" * 50, foreground=81))
    else:
        typer.secho("📝 Create Commit", fg=typer.colors.WHITE)
        typer.secho("=" * 50, fg=typer.colors.WHITE)

    if config.commit.forbidden_patterns or config.commit.forbidden_paths:
        with yaspin(
            text="Checking forbidden patterns and paths...", color=typer.colors.GREEN
        ) as spinner:
            is_valid, validation_message = validate_no_forbidden_files(
                forbidden_patterns=config.commit.forbidden_patterns,
                forbidden_paths=config.commit.forbidden_paths,
                check_staged=True,
            )

            if not is_valid:
                spinner.stop()
                add_typer_block_message(
                    header=msg.FORBIDDEN_FILES_DETECTED,
                    subheader=validation_message,
                    messages=["💡 Suggestions:"]
                    + [f"• {suggestion}" for suggestion in get_forbidden_file_suggestions()],
                    indent_block=False,
                    use_separator=False,
                )
                raise typer.Exit(code=1)

            spinner.ok("✔")

    current_branch = get_current_branch()

    # Check if current branch is protected
    if config.commit.protected_branch_prefixes:
        with yaspin(
            text="Checking protected branches prefixes...", color=typer.colors.GREEN
        ) as spinner:
            for prefix in config.commit.protected_branch_prefixes:
                if current_branch.count(prefix):
                    spinner.stop()
                    typer.secho(
                        msg.CANNOT_COMMIT_TO_PROTECTED_BRANCH.format(current_branch, prefix),
                        fg=typer.colors.RED,
                    )
                    raise typer.Exit(code=1)
            spinner.ok("✔")

    if config.commit.restrict_branch_to_owner:
        with yaspin(
            text="Checking if branch belongs to user...", color=typer.colors.GREEN
        ) as spinner:
            is_owner, ownership_message = validate_branch_ownership(current_branch)
            if not is_owner:
                spinner.stop()
                typer.secho(f"✘ {ownership_message}", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            spinner.ok("✔")

    if message:
        pass
    elif gum.is_available():
        message = _build_commit_with_gum(config.commit.tags)
    else:
        message = _build_commit_with_typer(config.commit.tags)

    if not message:
        typer.secho(f"✘ {msg.COMMIT_CANCELLED}", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    return CommitCtx(message=message, config=config)


def _build_commit_with_gum(tags: list[str]) -> Optional[str]:
    """Build commit message using gum UI."""

    # Select tag
    tag = gum.choose(tags, header="Select commit tag:")
    if not tag:
        gum.error(msg.NO_TAG_SELECTED)
        return None

    # Write message with history
    message = gum.input_text_with_history(
        prompt_type=f"commit_message_{tag}",
        placeholder="Describe your changes...",
        header=f"[{tag}] Commit message:",
    )

    if not message:
        gum.error(msg.MESSAGE_CANNOT_BE_EMPTY)
        return None

    return f"[{tag}] {message}"


def _build_commit_with_typer(tags: list[str]) -> Optional[str]:
    """Build commit message using typer prompts (fallback)."""
    add_typer_block_message(
        header="📝 Create Commit",
        subheader="📋 Select commit tag:",
        messages=[f"{idx}. {tag}" for idx, tag in enumerate(tags, 1)],
    )

    tag_choice = typer.prompt("Enter number", type=int, default=1)

    if tag_choice < 1 or tag_choice > len(tags):
        typer.secho(msg.INVALID_CHOICE, fg=typer.colors.RED)
        return None

    tag = tags[tag_choice - 1]

    # Get message
    message = typer.prompt(f"\n[{tag}] Enter commit message")

    if not message:
        typer.secho(f"✘ {msg.MESSAGE_CANNOT_BE_EMPTY}", fg=typer.colors.RED)
        return None

    return f"[{tag}] {message}"
