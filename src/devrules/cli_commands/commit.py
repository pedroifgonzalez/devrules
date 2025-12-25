from typing import Any, Callable, Dict

import typer
from typer_di import Depends

from devrules.cli_commands.context_builders.commit import CommitCtxBuilder
from devrules.core.git_service import commit as git_commit
from devrules.utils.decorators import ensure_git_repo

builder = CommitCtxBuilder()


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command()
    @ensure_git_repo()
    def check_commit(
        ctx: CommitCtxBuilder = Depends(builder.build_check_commit_context),
    ):
        """Validate commit message format."""
        ctx.validate_commit_message()

    @app.command()
    @ensure_git_repo()
    def commit(
        ctx: CommitCtxBuilder = Depends(builder.build_create_commit_context),
    ):
        """Build commit message with guided prompts or passed arguments"""
        ctx.auto_stage_files_if_enabled()
        ctx.enrich_commit_message()
        doc_message = ctx.search_relevant_documentation()
        ctx.confirm_commit()
        options = ctx.get_commit_options()

        git_commit(options, ctx.message, doc_message=doc_message)

    return {
        "check_commit": check_commit,
        "commit": commit,
    }
