"""CLI commands for pull requests."""

import re
import subprocess
from typing import Any, Callable, Dict, Optional

import typer
from typer_di import Depends
from yaspin import yaspin

from devrules.cli_commands.prompters import Prompter
from devrules.cli_commands.prompters.factory import get_default_prompter
from devrules.config import Config, load_config
from devrules.core.enum import DevRulesEvent
from devrules.core.git_service import get_current_branch, remote_branch_exists
from devrules.core.github_service import ensure_gh_installed, fetch_pr_info
from devrules.messages import pr as msg
from devrules.utils.decorators import emit_events, ensure_git_repo
from devrules.utils.typer import add_typer_block_message
from devrules.validators.documentation import display_documentation_guidance
from devrules.validators.pr import validate_pr
from devrules.validators.pr_target import (
    suggest_pr_target,
    validate_pr_base_not_protected,
    validate_pr_target,
)

prompter: Prompter = get_default_prompter()


def derive_pr_title(branch: str) -> str:
    """Derive a human-friendly PR title from a branch name."""
    prefix = None
    name_part = branch

    if "/" in branch:
        prefix, name_part = branch.split("/", 1)

    prefix_to_tag = {
        "feature": "FTR",
        "bugfix": "FIX",
        "hotfix": "FIX",
        "docs": "DOCS",
        "release": "REF",
    }

    tag = prefix_to_tag.get(prefix or "", "FTR")

    issue_match = re.match(r"^(\d+)-(.*)$", name_part)
    if issue_match:
        name_part = issue_match.group(2)

    words = [w for w in name_part.replace("_", "-").split("-") if w]
    humanized = " ".join(words).lower()

    if humanized:
        humanized = humanized.capitalize()

    return f"[{tag}] {humanized}" if humanized else f"[{tag}] {branch}"


def select_base_branch_interactive(
    allowed_targets: list[str],
    suggested: str,
) -> str:
    """Select base branch using the unified prompter."""
    prompter.header("🎯 Select Target Branch")

    if not allowed_targets:
        allowed_targets = ["develop", "main", "master"]

    if suggested in allowed_targets:
        allowed_targets = [suggested] + [b for b in allowed_targets if b != suggested]

    selected = prompter.choose(
        allowed_targets,
        header="Select base branch for PR:",
    )

    if not selected:
        prompter.warning("No branch selected, using suggested.")
        return suggested

    return selected


def run_pr_validations(
    *,
    current_branch: str,
    base: str,
    skip_checks: bool,
    config: Config,
):
    """Run all PR validations."""
    if skip_checks:
        return

    is_valid_base, base_message = validate_pr_base_not_protected(
        current_branch,
        config.commit.protected_branch_prefixes,
    )
    if not is_valid_base:
        prompter.error(base_message)
        raise prompter.exit(code=1)

    is_valid_target, target_message = validate_pr_target(
        source_branch=current_branch,
        target_branch=base,
        config=config.pr,
    )

    if not is_valid_target:
        suggested = suggest_pr_target(current_branch, config.pr)
        messages = [target_message]

        if suggested:
            messages.append(f"💡 Suggested target: {suggested}")

        add_typer_block_message(
            header=msg.INVALID_PR_TARGET,
            subheader="",
            messages=messages,
            indent_block=False,
        )
        raise prompter.exit(code=1)


def create_pr_internal(
    *,
    base: str,
    title: str,
    project: Optional[str],
    skip_checks: bool,
    auto_push: bool,
    config: Config,
):
    """Shared PR creation engine."""
    ensure_gh_installed()

    current_branch = get_current_branch()

    if current_branch == base:
        prompter.error(msg.CURRENT_BRANCH_SAME_AS_BASE)
        raise prompter.exit(code=1)

    run_pr_validations(
        current_branch=current_branch,
        base=base,
        skip_checks=skip_checks,
        config=config,
    )

    if not skip_checks and config.documentation.show_on_pr and config.documentation.rules:
        display_documentation_guidance(
            rules=config.documentation.rules,
            base_branch=base,
            show_files=True,
        )

    # Issue status validation
    if config.pr.require_issue_status_check:
        from devrules.validators.pr import validate_pr_issue_status

        with yaspin(text="🔍 Checking issue status...") as spinner:
            project_override = [project] if project else None
            is_valid, messages = validate_pr_issue_status(
                current_branch,
                config.pr,
                config.github,
                project_override=project_override,
            )
            spinner.stop()

            for m in messages:
                if "✔" in m or "ℹ" in m:
                    prompter.success(m)
                elif "⚠" in m:
                    prompter.warning(m)
                else:
                    prompter.error(m)

            if not is_valid:
                prompter.error("Cannot create PR: Issue status check failed")
                raise prompter.exit(code=1)

    # Confirmation
    prompter.info(f"🔀 {current_branch} → {base}")
    prompter.info(f"📝 Title: {title}")

    if not prompter.confirm("Create this PR?", default=True):
        prompter.warning(msg.PR_CANCELLED)
        raise prompter.exit(code=0)

    # Auto-push
    if auto_push:
        if not remote_branch_exists(current_branch):
            with yaspin(text=f"🚀 Pushing '{current_branch}'..."):
                subprocess.run(
                    ["git", "push", "-u", "origin", current_branch],
                    check=True,
                )
        else:
            prompter.info(f"Branch '{current_branch}' already exists on remote, skipping push.")

    # Create PR
    cmd = [
        "gh",
        "pr",
        "create",
        "--base",
        base,
        "--head",
        current_branch,
        "--title",
        title,
        "--fill",
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        prompter.error(msg.FAILED_TO_CREATE_PR.format(e))
        raise prompter.exit(code=1)

    prompter.success(f"Created pull request: {title}")


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    """Register PR commands."""

    @app.command()
    @emit_events(DevRulesEvent.PRE_PR)
    @ensure_git_repo()
    def create_pr(
        base: str = typer.Option("develop", "--base", "-b"),
        project: Optional[str] = typer.Option(None, "--project", "-p"),
        skip_checks: bool = typer.Option(False, "--skip-checks"),
        auto_push: Optional[bool] = typer.Option(None, "--auto-push/--no-auto-push"),
        config: Config = Depends(load_config),
    ):
        """Interactive PR creation."""
        prompter.header("🔀 Create Pull Request")

        current_branch = get_current_branch()
        prompter.info(f"📌 Current branch: {current_branch}")

        allowed_targets = config.pr.allowed_targets or ["develop", "main", "master"]
        suggested = suggest_pr_target(current_branch, config.pr) or "develop"

        base = select_base_branch_interactive(allowed_targets, suggested)

        title = derive_pr_title(current_branch)

        edited = prompter.input_text(
            header="📝 PR Title:",
            default=title,
            placeholder=title,
        )
        if edited:
            title = edited

        create_pr_internal(
            base=base,
            title=title,
            project=project,
            skip_checks=skip_checks,
            auto_push=auto_push or config.pr.auto_push,
            config=config,
        )

    @app.command()
    def check_pr(
        pr_number: Optional[int] = typer.Option(None, "--pr-number", "-p"),
        owner: Optional[str] = typer.Option(None, "--owner", "-o"),
        repo: Optional[str] = typer.Option(None, "--repo", "-r"),
        config: Config = Depends(load_config),
    ):
        """Validate PR size and title format."""
        prompter.header("🔍 Validate Pull Request")
        github_owner = owner or config.github.owner
        github_repo = repo or config.github.repo
        pr_number_selected = pr_number or prompter.input_text(
            header="PR Number:", placeholder="PR Number"
        )

        if not github_owner or not github_repo:
            prompter.error("GitHub owner and repo must be provided via CLI or config.")
            raise prompter.exit(code=1)

        try:
            pr_number_selected = int(pr_number_selected)
        except ValueError:
            pr_number_selected = None

        if not pr_number_selected:
            prompter.error("PR number invalid")
            raise prompter.exit(code=1)

        with yaspin(text="Searching PR information...") as spinner:
            try:
                pr_info = fetch_pr_info(
                    github_owner,
                    github_repo,
                    pr_number_selected,
                    config.github,
                )
            except Exception as e:
                spinner.stop()
                prompter.error(str(e))
                raise prompter.exit(code=1)

        prompter.info(f"PR Title: {pr_info.title}")
        prompter.info(f"Total LOC: {pr_info.additions + pr_info.deletions}")
        prompter.info(f"Files changed: {pr_info.changed_files}")

        current_branch = None
        if config.pr.require_issue_status_check:
            try:
                current_branch = get_current_branch()
            except Exception:
                pass

        is_valid, messages = validate_pr(
            pr_info,
            config.pr,
            current_branch=current_branch,
            github_config=config.github,
        )

        for m in messages:
            lower_m = m.lower()
            if "valid" in lower_m or "acceptable" in lower_m or "skipped" in lower_m:
                prompter.success(m)
            elif "too" in lower_m or "does not" in lower_m:
                prompter.error(m)
            else:
                prompter.info(m)

        raise prompter.exit(code=0 if is_valid else 1)

    return {
        "create_pr": create_pr,
        "check_pr": check_pr,
    }
