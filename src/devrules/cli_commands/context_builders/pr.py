import re
from pathlib import Path

import typer
from typing_extensions import Annotated, Optional, Self
from yaspin import yaspin

from devrules.cli_commands.context_builders.base import BaseCtxBuilder
from devrules.config import load_config
from devrules.core.git_service import push_branch, remote_branch_exists
from devrules.core.github_service import ensure_gh_installed, gh_create_pr
from devrules.messages import pr as msg
from devrules.utils import gum
from devrules.utils.typer import add_typer_block_message
from devrules.validators.documentation import display_documentation_guidance
from devrules.validators.pr import validate_pr_issue_status
from devrules.validators.pr_target import (
    get_current_branch,
    suggest_pr_target,
    validate_pr_base_not_protected,
    validate_pr_target,
)


class PrCtxBuilder(BaseCtxBuilder):
    def auto_push_if_enabled(self):
        if self.config.pr.auto_push:
            if not remote_branch_exists(self.current_branch):
                with yaspin(
                    text=f"🚀 Pushing branch '{self.current_branch}' to origin...", color="cyan"
                ):
                    push_branch(self.current_branch)
            else:
                typer.secho(
                    f"\nℹ Branch '{self.current_branch}' already exists on remote, skipping push.",
                    fg=typer.colors.BLUE,
                )

    def validate_current_branch_is_not_protected(self):
        is_valid_base, base_message = validate_pr_base_not_protected(
            self.current_branch,
            self.config.commit.protected_branch_prefixes,
        )
        if not is_valid_base:
            typer.secho(f"\n✘ {base_message}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    def set_header(self):
        if gum.is_available():
            print(gum.style("🔀 Create Pull Request", foreground=81, bold=True))
            print(gum.style("=" * 50, foreground=81))
            typer.echo(f"\n📌 Current branch: {self.current_branch}")
        else:
            add_typer_block_message(
                header="🔀 Create Pull Request",
                subheader=f"📌 Current branch: {self.current_branch}",
                messages=[],
                indent_block=False,
            )

    def select_base_branch_interactive(
        self, allowed_targets: list[str], suggested: str = "develop"
    ) -> str:
        """Select base branch interactively using gum or typer fallback.

        Args:
            allowed_targets: List of allowed target branches
            suggested: Suggested default branch

        Returns:
            Selected base branch
        """
        if not allowed_targets:
            allowed_targets = ["develop", "main", "master"]

        if gum.is_available():
            print(gum.style("🎯 Select Target Branch", foreground=81, bold=True))
            selected = gum.choose(allowed_targets, header="Select base branch for PR:")
            if selected:
                return selected if isinstance(selected, str) else selected[0]
            return suggested
        else:
            typer.echo("\n🎯 Select base branch:")
            for idx, branch in enumerate(allowed_targets, 1):
                marker = " (suggested)" if branch == suggested else ""
                typer.echo(f"  {idx}. {branch}{marker}")

            choice = typer.prompt("Enter number", type=int, default=1)
            if 1 <= choice <= len(allowed_targets):
                return allowed_targets[choice - 1]
            return suggested

    def get_target_branch(self):
        allowed_targets = self.config.pr.allowed_targets or ["develop", "main", "master"]
        suggested = suggest_pr_target(self.current_branch, self.config.pr) or "develop"

        base = self.select_base_branch_interactive(allowed_targets, suggested)

        is_valid_target, target_message = validate_pr_target(
            source_branch=self.current_branch,
            target_branch=base,
            config=self.config.pr,
        )

        if not is_valid_target:
            add_typer_block_message(
                header=msg.INVALID_PR_TARGET,
                subheader="",
                messages=[target_message],
                indent_block=False,
            )
            raise typer.Exit(code=1)
        self.target_branch = base
        return base

    def build_create_pr_context(
        self,
        target: str = typer.Option(
            "develop", "--target", "-b", help="Target branch for the pull request"
        ),
        project: Optional[str] = typer.Option(
            None,
            "--project",
            "-p",
            help="Project to check issue status against",
        ),
        config_file: Annotated[
            Optional[Path], typer.Option("--config", "-c", help="Path to config file")
        ] = None,
    ) -> Self:
        ensure_gh_installed()
        current_branch = get_current_branch()

        if not current_branch:
            raise typer.Exit(code=1)

        self.set_current_branch(current_branch)

        config = load_config(config_file)
        self.set_config(config)

        # Header
        self.set_header()
        self.project = project
        self.target_branch = target
        return self

    def show_documentation(self):
        if self.config.documentation.show_on_pr and self.config.documentation.rules:
            display_documentation_guidance(
                rules=self.config.documentation.rules,
                base_branch=self.target_branch,
                show_files=True,
            )

    def validate_current_branch_is_not_base(self):
        if self.current_branch == self.target_branch:
            typer.secho(
                "✘ Current branch is the same as the base branch; nothing to create a PR for.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

    def derive_pr_title(self):
        prefix = None
        name_part = self.current_branch
        if "/" in self.current_branch:
            prefix, name_part = self.current_branch.split("/", 1)

        prefix_to_tag = {
            "feature": "FTR",
            "bugfix": "FIX",
            "hotfix": "FIX",
            "docs": "DOCS",
            "release": "REF",
        }

        tag = prefix_to_tag.get(prefix or "", "FTR")

        name_core = name_part
        issue_match = re.match(r"^(\d+)-(.*)$", name_core)
        if issue_match:
            name_core = issue_match.group(2)

        words = name_core.replace("_", "-").split("-")
        words = [w for w in words if w]
        humanized = " ".join(words).lower()
        if humanized:
            humanized = humanized[0].upper() + humanized[1:]

        pr_title = f"[{tag}] {humanized}" if humanized else f"[{tag}] {self.current_branch}"

        self.pr_title = pr_title

    def allow_edit_pr_title(self):
        pr_title = self.pr_title
        if gum.is_available():
            edited_title = gum.input_text_with_history(
                prompt_type="pr_title",
                placeholder=self.pr_title,
                header="📝 PR Title (edit or press Enter to accept):",
                default=self.pr_title,
            )
            if edited_title:
                pr_title = edited_title
        else:
            typer.echo(f"\n📝 Suggested PR title: {self.pr_title}")
            if typer.confirm("Edit title?", default=False):
                pr_title = typer.prompt("Enter new title", default=self.pr_title)
        self.pr_title = pr_title

    def validate_pr_status(self):
        if self.config.pr.require_issue_status_check:
            with yaspin(text="🔍 Checking issue status...") as spinner:
                project_override = self.project
                is_valid, messages = validate_pr_issue_status(
                    self.current_branch,
                    self.config.pr,
                    self.config.github,
                    project_override=project_override,
                )
                spinner.stop()
                for message in messages:
                    if "✔" in message or "ℹ" in message:
                        typer.secho(message, fg=typer.colors.GREEN)
                    elif "⚠" in message:
                        typer.secho(message, fg=typer.colors.YELLOW)
                    else:
                        typer.secho(message, fg=typer.colors.RED)

                if not is_valid:
                    typer.echo()
                    typer.secho(
                        "✘ Cannot create PR: Issue status check failed",
                        fg=typer.colors.RED,
                    )
                    raise typer.Exit(code=1)

            typer.echo()

    def confirm_pr(self):
        if gum.is_available():
            print("\n📋 Summary:")
            print(
                f"   Branch: {gum.style(self.current_branch, foreground=212)} → {gum.style(self.target_branch, foreground=82)}"
            )
            print(f"   Title:  {gum.style(self.pr_title, foreground=222)}")
            confirmed = gum.confirm("Create this PR?")
            if confirmed is False:
                typer.secho(msg.PR_CANCELLED, fg=typer.colors.YELLOW)
                raise typer.Exit(code=0)
        else:
            typer.echo(f"\n📝 Title: {self.pr_title}")
            if not typer.confirm("\nCreate this PR?", default=True):
                typer.secho(msg.PR_CANCELLED, fg=typer.colors.YELLOW)
                raise typer.Exit(code=0)

    def create_pr(self):
        with yaspin(text="Creating PR...", color="green") as spinner:
            gh_create_pr(self.target_branch, self.current_branch, self.pr_title)
            spinner.ok("✔")
            typer.secho(f"\n✔ Created pull request: {self.pr_title}", fg=typer.colors.GREEN)
