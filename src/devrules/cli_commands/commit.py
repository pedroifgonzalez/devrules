import os
from typing import Any, Callable, Dict

import typer
from typer_di import Depends
from yaspin import yaspin

from devrules.config import Config, load_config
from devrules.core.git_service import commit as git_commit
from devrules.core.git_service import get_current_issue_number, stage_all_files
from devrules.messages import commit as msg
from devrules.utils import gum
from devrules.utils.decorators import ensure_git_repo
from devrules.utils.dependencies import CommitCtx, perform_commit_context_builder
from devrules.validators.commit import validate_commit
from devrules.validators.documentation import get_relevant_documentation


def confirm_commit(message: str):
    if gum.is_available():
        print(f"\n📝 Commit message: {gum.style(message, foreground=82)}")
        confirmed = gum.confirm("Proceed with commit?")
        if confirmed is False:
            typer.secho(msg.COMMIT_CANCELLED, fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)
    else:
        typer.echo(f"\n📝 Commit message: {message}")
        if not typer.confirm("Proceed with commit?", default=True):
            typer.secho(msg.COMMIT_CANCELLED, fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)


def search_relevant_documentation(config: Config):
    doc_message = None
    if config.documentation.show_on_commit and config.documentation.rules:
        has_docs, doc_message = get_relevant_documentation(
            rules=config.documentation.rules,
            base_branch="HEAD",
            show_files=True,
        )
        if not has_docs:
            doc_message = None
    return doc_message


def get_commit_options(config: Config) -> list:
    options = []
    for option, config_option in zip(
        ("-S", "-n"),
        (config.commit.gpg_sign, config.commit.allow_hook_bypass),
    ):
        if config_option:
            options.append(option)
    return options


def enrich_commit_message(message: str, config: Config):
    if config.commit.append_issue_number:
        with yaspin(text="Appending issue number...", color=typer.colors.GREEN) as spinner:
            issue_number = get_current_issue_number()
            if issue_number and f"#{issue_number}" not in message:
                message = f"#{issue_number} {message}"
            spinner.ok("✔")
    return message


def auto_stage_files_if_enabled(config: Config):
    if config.commit.auto_stage:
        with yaspin(text="Auto staging files...", color=typer.colors.GREEN) as spinner:
            stage_all_files()
            spinner.ok("✔")


def validate_commit_message(message: str, config: Config):
    is_valid, result_message = validate_commit(message, config.commit)
    if is_valid:
        typer.secho(f"✔ {result_message}", fg=typer.colors.GREEN)
        raise typer.Exit(code=0)
    else:
        typer.secho(f"✘ {result_message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def check_commit_message_file(file: str):
    if not os.path.exists(file):
        typer.secho(msg.COMMIT_MESSAGE_FILE_NOT_FOUND.format(file), fg=typer.colors.RED)
        raise typer.Exit(code=1)


def read_file_content(file: str):
    with open(file, "r") as f:
        return f.read().strip()


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command()
    @ensure_git_repo()
    def check_commit(
        file: str,
        config: Config = Depends(load_config),
    ):
        """Validate commit message format."""

        check_commit_message_file(file)
        message = read_file_content(file)
        validate_commit_message(message, config)

    @app.command()
    @ensure_git_repo()
    def commit(
        ctx: CommitCtx = Depends(perform_commit_context_builder),
    ):
        """Build commit message with guided prompts or passed arguments"""
        message = ctx["message"]
        config = ctx["config"]

        auto_stage_files_if_enabled(config)
        message = enrich_commit_message(message, config)
        doc_message = search_relevant_documentation(config)
        confirm_commit(message)
        options = get_commit_options(config)
        git_commit(options, message, doc_message=doc_message)

    return {
        "check_commit": check_commit,
        "commit": commit,
    }
