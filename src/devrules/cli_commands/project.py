"""CLI commands for project management."""

import subprocess
from typing import Any, Callable, Dict, Optional

import typer
from yaspin import yaspin

from devrules.cli_commands.commons import _fetch_project_items, _get_issue_and_status_interactively
from devrules.cli_commands.prompters.factory import get_default_prompter
from devrules.config import load_config
from devrules.core.git_service import get_current_branch, get_current_issue_number
from devrules.core.github_service import ensure_gh_installed
from devrules.core.permission_service import can_transition_status
from devrules.core.project_service import (
    add_issue_comment,
    find_project_item_for_issue,
    get_issue_evidence,
    get_project_id,
    get_status_field_id,
    get_status_option_id,
    print_project_items,
    resolve_project_number,
    show_issue_on_web,
)
from devrules.utils.issue_mapping import get_issue_mapping_manager
from devrules.utils.typer import add_typer_block_message

prompter = get_default_prompter()


def _get_valid_statuses() -> list[str]:
    """Get list of valid statuses from config or default.

    Returns:
        List of valid status strings.
    """
    config = load_config(None)
    configured_statuses = getattr(config.github, "valid_statuses", None)
    if configured_statuses:
        return list(configured_statuses)

    return [
        "Backlog",
        "Blocked",
        "To Do",
        "In Progress",
        "Waiting Integration",
        "QA Testing",
        "QA In Progress",
        "QA Approved",
        "Pending To Deploy",
        "Done",
    ]


def _get_project_interactively(projects_keys: list[str]) -> Optional[str]:
    """Get project interactively

    Args:
        projects_keys (list[str]): List of project keys

    Returns:
        Optional[str]: Selected project key or None if cancelled
    """
    header = "Select a project"
    project_key = prompter.choose(options=projects_keys, header=header)
    return project_key


def _ask_for_integration_comment() -> Optional[str]:
    """Ask for integration details for frontend colleagues.

    Returns:
        Optional[str]: The integration comment or None if cancelled.
    """
    add_typer_block_message(
        header="📝 Please provide integration details for frontend colleagues:",
        subheader="Options:",
        messages=[
            "1. Type a simple comment directly",
            "2. Press Enter to open your editor for multi-line markdown",
        ],
    )
    simple_comment = typer.prompt(
        "Comment (or press Enter for editor)", default="", show_default=False
    ).strip()

    if simple_comment:
        integration_comment = simple_comment
    else:
        integration_comment = typer.edit(
            "\n#! Add integration details below (markdown supported)\n#! Lines starting with #! will be ignored\n\n"
        )
        if integration_comment:
            lines = [
                line
                for line in integration_comment.split("\n")
                if not line.strip().startswith("#!")
            ]
            integration_comment = "\n".join(lines).strip()

    if not integration_comment:
        typer.secho(
            "⚠ Warning: No comment provided for Waiting Integration status",
            fg=typer.colors.YELLOW,
        )
        confirm = typer.confirm("Continue without a comment?", default=False)
        if not confirm:
            typer.echo("Cancelled.")
            raise typer.Exit(code=0)
    return integration_comment


def _ask_for_evidence(issue: str) -> None:
    """Show to user the issue on web and aks him to complete adding some evidence"""
    with yaspin(text="Checking if there are evidence assets..."):
        evidence = get_issue_evidence(issue)

    if evidence:
        prompter.info("Evidence assets found, continuing...")
        return None

    with yaspin(text="Loading issue on web...", color="yellow"):
        show_issue_on_web(issue)

    prompter.info("The issue was opened on your browser. Please add evidence")
    response = prompter.confirm("Are you done adding evidence?")

    if response is False:
        prompter.error("Cancelled.")
        raise prompter.exit(0)

    # check evidence was added
    with yaspin(text="Checking evidence...", color="yellow"):
        evidence = get_issue_evidence(issue)

    # if evidence was added continue, if warn user and ask to continue anyway
    if not evidence:
        prompter.warning("No evidence found")
        confirm = prompter.confirm("Continue without evidence?", default=False)
        if not confirm:
            prompter.error("Cancelled.")
            raise prompter.exit(0)

    prompter.info("Evidence assets found, continuing...")
    return None


def _get_repo_owner_and_name(config, owner, issue_repo) -> tuple[str, str]:
    """Get the repository owner and name."""
    repo_to_use = issue_repo if issue_repo else config.github.repo
    repo_to_use = str(repo_to_use)
    if "github.com/" in repo_to_use:
        parts = repo_to_use.split("github.com/")[-1].strip("/")
        owner_repo = parts.split("/")[:2]
        if len(owner_repo) == 2:
            repo_owner, repo_name = owner_repo
        else:
            repo_owner, repo_name = owner, config.github.repo
    elif "/" in repo_to_use:
        repo_owner, repo_name = repo_to_use.split("/", 1)
    else:
        repo_owner, repo_name = owner, repo_to_use

    return repo_owner, repo_name


def _get_status_interactively(
    valid_statuses: list[str], current_item_status: Optional[str] = None
) -> Optional[str]:
    """Get the new status interactively."""
    statuses_to_choose = valid_statuses.copy()
    if current_item_status and current_item_status in statuses_to_choose:
        statuses_to_choose.remove(current_item_status)

    # Handle empty list case
    if not statuses_to_choose:
        prompter.warning("No other statuses available to choose from.")
        return None

    status = prompter.choose(options=statuses_to_choose, header="Select the new status")
    return status


def _validate_status(status: str, valid_statuses: list[str]) -> None:
    """Validate the status."""
    if status not in valid_statuses:
        allowed = ", ".join(valid_statuses)
        typer.secho(
            f"✘ Invalid status '{status}'. Allowed values: {allowed}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    """Register project commands.

    Args:
        app: Typer application instance.

    Returns:
        Dictionary mapping command names to their functions.
    """

    @app.command()
    def update_issue_status(
        issue: Optional[int] = typer.Argument(None, help="Issue number (e.g. 123)"),
        status: Optional[str] = typer.Option(
            None, "--status", "-s", help="New project status value"
        ),
        project: Optional[str] = typer.Option(
            None,
            "--project",
            "-p",
            help="GitHub project number or key (uses 'gh project item-list')",
        ),
        item_id: Optional[str] = typer.Option(
            None,
            "--item-id",
            help="Direct GitHub Project item id (skips searching by issue number)",
        ),
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Bypass permission check (only for privileged roles or disabled permissions)",
        ),
    ):
        """Update the Status field of a GitHub Project item for a given issue.

        If no issue or status is provided, an interactive prompt will be shown to select them.
        """

        prompter.header("Update issue status")

        ensure_gh_installed()
        config = load_config(None)

        valid_statuses = _get_valid_statuses()
        projects_keys = list(config.github.projects.keys())

        # Try to get mapping from current branch first
        mapping_manager = get_issue_mapping_manager()
        current_branch = get_current_branch()
        branch_mapping = mapping_manager.get_mapping_by_branch(current_branch)

        if branch_mapping:
            project_key = branch_mapping["project_key"]
            issue = branch_mapping["issue_number"]
            if item_id is None and getattr(config.github, "project_cache_enabled", False):
                item_id = branch_mapping.get("item_id")
            prompter.info("Found mapping for branch, continuing...")
        else:
            project_key = project
            if project_key is None:
                project_key = _get_project_interactively(projects_keys=projects_keys)

        if not project_key:
            prompter.error("Not valid project was selected")
            raise prompter.exit(1)

        # Resolve project owner and number using existing logic
        owner, project_number = resolve_project_number(project_key)

        # Extract issue from branch if possible (skip if already found from mapping)
        if issue is None:
            with yaspin(text="Extracting issue from branch") as spinner:
                extracted_issue_number = get_current_issue_number()
                if extracted_issue_number is not None:
                    issue = int(extracted_issue_number)
                    spinner.write(f"✔ Issue {extracted_issue_number} found")
                else:
                    spinner.write("✘ No issue found")

        # If no issue is provided, show interactive selection
        item_status = None
        if issue is None and item_id is None:
            final_status = valid_statuses[-1]
            items = _fetch_project_items(owner, project_number, exclude_status=final_status)
            issue_data = _get_issue_and_status_interactively(items)
            issue = issue_data.get("issue")
            item_title = issue_data.get("item_title")
            item_status = issue_data.get("item_status")

        # If no status is provided, show interactive status selection
        if status is None:
            status = _get_status_interactively(valid_statuses, item_status)

        # Validate the status
        if status is None:
            prompter.error("Status is required.")
            raise prompter.exit(1)

        _validate_status(status, valid_statuses)

        # Permission check for status transition
        if not force:
            is_permitted, permission_msg = can_transition_status(status, config)
            if permission_msg and is_permitted:
                # Warning case - allowed but with warning
                prompter.warning(permission_msg)
            elif not is_permitted:
                prompter.error(permission_msg)
                raise prompter.exit(1)

        # If we got here with an issue number but no item_id, look up the item
        issue_repo, item_title = None, None
        if item_id is None and issue:
            if getattr(config.github, "project_cache_enabled", False):
                issue_mapping = mapping_manager.get_mapping_by_issue(int(issue))
                if (
                    issue_mapping
                    and issue_mapping.get("project_key") == project_key
                    and issue_mapping.get("item_id")
                ):
                    item_id = issue_mapping.get("item_id")

            with yaspin(text="Looking up project item..."):
                project_item = find_project_item_for_issue(owner, project_number, issue)
                item_id, item_title = project_item.id, project_item.title
                if project_item.repository:
                    issue_repo = project_item.repository

        integration_comment = None
        if status == config.github.integration_comment_status:
            integration_comment = _ask_for_integration_comment()

        if status == config.github.require_evidence_status:
            _ask_for_evidence(issue=str(issue))

        with yaspin(text="Get project id..."):
            project_id = get_project_id(owner, project_number)
        with yaspin(text="Get status field id..."):
            status_field_id = get_status_field_id(owner, project_number)
        with yaspin(text="Get status option id..."):
            status_option_id = get_status_option_id(owner, project_number, status)

        cmd = [
            "gh",
            "project",
            "item-edit",
            "--id",
            item_id,
            "--field-id",
            status_field_id,
            "--project-id",
            project_id,
            "--single-select-option-id",
            status_option_id,
        ]

        try:
            with yaspin(text="Updating status...", color="green"):
                subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                )
        except subprocess.CalledProcessError as e:
            prompter.error(
                f"Failed to update project item status: {e}",
            )
            raise prompter.exit(1)

        prompter.success(
            f"Updated status of project item for issue #{issue} to '{status}' (title: {item_title})",
        )

        # Store the mapping for future use
        mapping_manager.add_mapping(issue, current_branch, project_key, item_id=item_id)

        if integration_comment and issue_repo and issue:
            repo_owner, repo_name = _get_repo_owner_and_name(
                config=config, owner=owner, issue_repo=issue_repo
            )
            if repo_name and issue:
                with yaspin(text=f"Adding integration comment to issue #{issue}", color="green"):
                    add_issue_comment(repo_owner, repo_name, issue, integration_comment)
                    prompter.success(
                        f"Added integration comment to issue #{issue} (title: {item_title})",
                    )

    @app.command()
    def list_issues(
        state: str = typer.Option(
            "open",
            "--state",
            "-s",
            help="Issue state: open, closed, or all",
        ),
        limit: int = typer.Option(
            30,
            "--limit",
            "-L",
            help="Maximum number of issues to list",
        ),
        assignee: Optional[str] = typer.Option(
            None,
            "--assignee",
            "-a",
            help="Filter by assignee (GitHub username)",
        ),
        status: Optional[str] = typer.Option(
            None,
            "--status",
            help="Filter project items by Status field (requires --project)",
        ),
        project: Optional[str] = typer.Option(
            None,
            "--project",
            "-p",
            help="GitHub project number or key (uses 'gh project item-list')",
        ),
    ):
        """List GitHub issues using the gh CLI."""
        prompter.header("List issues")
        ensure_gh_installed()

        if project is not None:
            # Validate status against configured valid_statuses when filtering project items
            if status is not None:
                valid_statuses = _get_valid_statuses()

                if status not in valid_statuses:
                    allowed = ", ".join(valid_statuses)
                    typer.secho(
                        f"✘ Invalid status '{status}'. Allowed values: {allowed}",
                        fg=typer.colors.RED,
                    )
                    raise typer.Exit(code=1)

            project_str = str(project)

            if project_str.lower() == "all":
                config = load_config(None)
                owner = getattr(config.github, "owner", None)
                projects_map = getattr(config.github, "projects", {}) or {}

                if not owner:
                    typer.secho(
                        "✘ GitHub owner must be configured in the config file under the [github] section to use --project all.",
                        fg=typer.colors.RED,
                    )
                    raise typer.Exit(code=1)

                if not projects_map:
                    typer.secho(
                        "✘ No projects configured under [github.projects] to use with --project all.",
                        fg=typer.colors.RED,
                    )
                    raise typer.Exit(code=1)

                for key, label in sorted(projects_map.items()):
                    owner_for_key, project_number_for_key = resolve_project_number(key)

                    cmd = [
                        "gh",
                        "project",
                        "item-list",
                        project_number_for_key,
                        "--owner",
                        owner_for_key,
                        "--limit",
                        str(limit),
                        "--format",
                        "json",
                    ]

                    try:
                        result = subprocess.run(
                            cmd,
                            check=True,
                            capture_output=True,
                            text=True,
                        )
                    except subprocess.CalledProcessError as e:
                        typer.secho(
                            f"✘ Failed to run gh command for project '{key}': {e}",
                            fg=typer.colors.RED,
                        )
                        if e.stderr:
                            typer.echo(e.stderr)
                        raise typer.Exit(code=1)

                    print_project_items(result.stdout, assignee, label, status)

                return

            owner, project_number = resolve_project_number(project)

            cmd = [
                "gh",
                "project",
                "item-list",
                project_number,
                "--owner",
                owner,
                "--limit",
                str(limit),
                "--format",
                "json",
            ]
        else:
            if status is not None:
                typer.secho(
                    "✘ --status can only be used together with --project.",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)

            cmd = ["gh", "issue", "list", "--state", state, "--limit", str(limit)]

            if assignee:
                cmd.extend(["--assignee", assignee])

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            typer.secho(
                f"✘ Failed to run gh command: {e}",
                fg=typer.colors.RED,
            )
            if e.stderr:
                typer.echo(e.stderr)
            raise typer.Exit(code=1)

        if project is not None:
            print_project_items(result.stdout, assignee, project, status)
        else:
            typer.echo(result.stdout)

    @app.command()
    def describe_issue(
        issue: int = typer.Argument(..., help="Issue number (e.g. 123)"),
        repo: Optional[str] = typer.Option(
            None,
            "--repo",
            "-r",
            help="Repository in format owner/repo (defaults to config)",
        ),
    ):
        """Show the description (body) of a GitHub issue."""
        prompter.header("Describe issue")
        ensure_gh_installed()

        config = load_config(None)

        # Determine repository
        if repo:
            repo_arg = repo
        else:
            github_owner = getattr(config.github, "owner", None)
            github_repo = getattr(config.github, "repo", None)
            if github_owner and github_repo:
                repo_arg = f"{github_owner}/{github_repo}"
            else:
                typer.secho(
                    "✘ Repository must be provided via --repo or configured in the config file under [github] section.",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)

        cmd = [
            "gh",
            "issue",
            "view",
            str(issue),
            "--repo",
            repo_arg,
        ]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            typer.secho(
                f"✘ Failed to fetch issue #{issue}: {e}",
                fg=typer.colors.RED,
            )
            if e.stderr:
                typer.echo(e.stderr)
            raise typer.Exit(code=1)

        typer.echo(result.stdout)

    return {
        "update_issue_status": update_issue_status,
        "list_issues": list_issues,
        "describe_issue": describe_issue,
    }
