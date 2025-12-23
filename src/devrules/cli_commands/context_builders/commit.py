import os
from pathlib import Path
from typing import Annotated, Optional, Self

import typer
from yaspin import yaspin

from devrules.cli_commands.context_builders.base import BaseCtxBuilder
from devrules.config import load_config
from devrules.core.git_service import get_current_branch, get_current_issue_number, stage_all_files
from devrules.messages import commit as msg
from devrules.utils import gum
from devrules.utils.typer import add_typer_block_message
from devrules.validators.commit import validate_commit
from devrules.validators.documentation import get_relevant_documentation
from devrules.validators.forbidden_files import (
    get_forbidden_file_suggestions,
    validate_no_forbidden_files,
)
from devrules.validators.ownership import validate_branch_ownership


class CommitCtxBuilder(BaseCtxBuilder):
    def set_commit_message_file(self, file: str):
        self.commit_message_file = file

    def set_message(self, message: str):
        self.message = message

    def build_check_commit_context(
        self,
        file: str,
        config_file: Annotated[
            Optional[Path], typer.Option("--config", "-c", help="Path to config file")
        ] = None,
    ) -> Self:
        self.set_config(load_config(config_file))
        self.set_commit_message_file(file)
        return self

    def _validate_pre_requisites(self):
        self.validate_forbidden_patterns()
        self.check_branch_ownership()
        self.check_branch_protection()

    def print_header(self):
        if gum.is_available():
            print(gum.style("📝 Create Commit", foreground=81, bold=True))
            print(gum.style("=" * 50, foreground=81))
        else:
            typer.secho("📝 Create Commit", fg=typer.colors.WHITE)
            typer.secho("=" * 50, fg=typer.colors.WHITE)

    def build_create_commit_context(
        self,
        message: Optional[str] = typer.Option(None, "--message", "-m", help="Commit message"),
        config_file: Annotated[
            Optional[Path], typer.Option("--config", "-c", help="Path to config file")
        ] = None,
    ) -> Self:
        config = load_config(config_file)
        self.set_config(config)

        current_branch = get_current_branch()
        self.set_current_branch(current_branch)

        self.print_header()
        self._validate_pre_requisites()

        if message:
            pass
        elif gum.is_available():
            message = self._build_commit_with_gum(self.config.commit.tags)
        else:
            message = self._build_commit_with_typer(self.config.commit.tags)

        if not message:
            typer.secho(f"✘ {msg.COMMIT_CANCELLED}", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

        self.set_message(message)

        return self

    def validate_forbidden_patterns(self) -> Self:
        if self.config.commit.forbidden_patterns or self.config.commit.forbidden_paths:
            with yaspin(
                text="Checking forbidden patterns and paths...", color=typer.colors.GREEN
            ) as spinner:
                is_valid, validation_message = validate_no_forbidden_files(
                    forbidden_patterns=self.config.commit.forbidden_patterns,
                    forbidden_paths=self.config.commit.forbidden_paths,
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

        return self

    def check_branch_ownership(self) -> Self:
        if self.config.commit.restrict_branch_to_owner:
            with yaspin(
                text="Checking if branch belongs to user...", color=typer.colors.GREEN
            ) as spinner:
                is_owner, ownership_message = validate_branch_ownership(self.current_branch)
                if not is_owner:
                    spinner.stop()
                    typer.secho(f"✘ {ownership_message}", fg=typer.colors.RED)
                    raise typer.Exit(code=1)
                spinner.ok("✔")
        return self

    def check_branch_protection(self) -> Self:
        # Check if current branch is protected
        if self.config.commit.protected_branch_prefixes:
            with yaspin(
                text="Checking protected branches prefixes...", color=typer.colors.GREEN
            ) as spinner:
                for prefix in self.config.commit.protected_branch_prefixes:
                    if self.current_branch.count(prefix):
                        spinner.stop()
                        typer.secho(
                            msg.CANNOT_COMMIT_TO_PROTECTED_BRANCH.format(
                                self.current_branch, prefix
                            ),
                            fg=typer.colors.RED,
                        )
                        raise typer.Exit(code=1)
                spinner.ok("✔")
        return self

    def _build_commit_with_gum(self, tags: list[str]) -> Optional[str]:
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

    def _build_commit_with_typer(self, tags: list[str]) -> Optional[str]:
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

    def confirm_commit(self):
        if gum.is_available():
            print(f"\n📝 Commit message: {gum.style(self.message, foreground=82)}")
            confirmed = gum.confirm("Proceed with commit?")
            if confirmed is False:
                typer.secho(msg.COMMIT_CANCELLED, fg=typer.colors.YELLOW)
                raise typer.Exit(code=0)
        else:
            typer.echo(f"\n📝 Commit message: {self.message}")
            if not typer.confirm("Proceed with commit?", default=True):
                typer.secho(msg.COMMIT_CANCELLED, fg=typer.colors.YELLOW)
                raise typer.Exit(code=0)

    def search_relevant_documentation(self):
        doc_message = None
        if self.config.documentation.show_on_commit and self.config.documentation.rules:
            has_docs, doc_message = get_relevant_documentation(
                rules=self.config.documentation.rules,
                base_branch="HEAD",
                show_files=True,
            )
            if not has_docs:
                doc_message = None
        return doc_message

    def get_commit_options(self) -> list:
        options = []
        for option, config_option in zip(
            ("-S", "-n"),
            (self.config.commit.gpg_sign, self.config.commit.allow_hook_bypass),
        ):
            if config_option:
                options.append(option)
        return options

    def enrich_commit_message(self) -> Self:
        if self.config.commit.append_issue_number:
            issue_number = get_current_issue_number()
            if issue_number and f"#{issue_number}" not in self.message:
                with yaspin(text="Appending issue number...", color=typer.colors.GREEN) as spinner:
                    self.message = f"#{issue_number} {self.message}"
                spinner.ok("✔")
        return self

    def auto_stage_files_if_enabled(self):
        if self.config.commit.auto_stage:
            with yaspin(text="Auto staging files...", color=typer.colors.GREEN) as spinner:
                stage_all_files()
                spinner.ok("✔")

    def validate_commit_message(self):
        is_valid, result_message = validate_commit(self.message, self.config.commit)
        if is_valid:
            typer.secho(f"✔ {result_message}", fg=typer.colors.GREEN)
            raise typer.Exit(code=0)
        else:
            typer.secho(f"✘ {result_message}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    def check_commit_message_file(self):
        if not os.path.exists(self.commit_message_file):
            typer.secho(
                msg.COMMIT_MESSAGE_FILE_NOT_FOUND.format(self.commit_message_file),
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

    def read_file_content(self):
        with open(self.commit_message_file, "r") as f:
            return f.read().strip()
