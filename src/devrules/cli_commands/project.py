import subprocess
from typing import Any, Callable, Dict, Optional

import typer
from yaspin import yaspin

from devrules.config import load_config
from devrules.core.github_service import ensure_gh_installed
from devrules.core.project_service import (
    add_issue_comment,
    find_project_item_for_issue,
    get_project_id,
    get_status_field_id,
    get_status_option_id,
    list_project_items,
    print_project_items,
    resolve_project_number,
)
from devrules.utils import gum
from devrules.utils.gum import GUM_AVAILABLE
from devrules.utils.typer import add_typer_block_message


def _get_valid_statuses() -> list[str]:
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
    subheader = "Available projects:"
    if GUM_AVAILABLE:
        project_key = gum.choose(
            options=projects_keys,
            header=header,
        )
        assert isinstance(project_key, str)
    else:
        add_typer_block_message(
            header=header,
            subheader=subheader,
            messages=[f"{idx}. {b}" for idx, b in enumerate(projects_keys, 1)],
        )
        project_number = typer.prompt("Enter number", type=int)
        if project_number < 1 or project_number > len(projects_keys):
            typer.secho("✘ Invalid choice", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        project_key = projects_keys[project_number - 1]
    return project_key


def _fetch_project_items(
    owner: str, project_number: str, exclude_status: Optional[str] = None
) -> list[dict]:
    items = []
    with yaspin(text="Fetching project items..."):
        items = list_project_items(
            owner=owner,
            project_number=project_number,
            exclude_status=exclude_status,
        )
    if not items:
        typer.secho("✘ No items found in the project", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    return items


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


def _get_status_interactively(valid_statuses: list[str], current_item_status: str) -> Optional[str]:
    """Get the new status interactively."""
    statuses_to_choose = valid_statuses.copy()
    if current_item_status and current_item_status in statuses_to_choose:
        statuses_to_choose.remove(current_item_status)
    if GUM_AVAILABLE:
        output = gum.choose(
            options=statuses_to_choose,
            header="Select the new status",
        )
        status = output if isinstance(output, str) else None
    else:
        typer.echo("\n📋 Select the new status:")
        for i, status_option in enumerate(statuses_to_choose, 1):
            typer.echo(f"{i}. {status_option}")

        while True:
            try:
                selection = typer.prompt("\nEnter the number of the status", type=int)
                if 1 <= selection <= len(statuses_to_choose):
                    status = statuses_to_choose[selection - 1]
                    break
                typer.secho("Invalid selection. Please try again.", fg=typer.colors.YELLOW)
            except ValueError:
                typer.secho("Please enter a valid number.", fg=typer.colors.YELLOW)
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


def _get_issue_and_status_interactively(items: list[Dict]) -> dict:
    """Get issue and status interactively."""
    if GUM_AVAILABLE:
        options = [
            f"#{item.get('content', {}).get('number')} - {item.get('title', 'No title')} [{item.get('status', 'No status')}]"
            for item in items
        ]
        selected = gum.choose(
            options=options,
            header="Select an issue to update",
        )
        if not isinstance(selected, str):
            typer.secho("No issue selected.", fg=typer.colors.YELLOW)
            raise typer.Exit(0)
        issue = int(selected.split(" ")[0][1:])
        selected_item = next(
            (item for item in items if str(item.get("content", {}).get("number")) == str(issue)),
            None,
        )
        if selected_item is None:
            typer.secho("Could not find selected issue.", fg=typer.colors.RED)
            raise typer.Exit(1)
        item_title = selected_item.get("title")
        item_status = selected_item.get("status")
    else:
        typer.echo("\n📋 Select an issue to update:")
        for i, item in enumerate(items, 1):
            issue_num = item.get("content", {}).get("number")
            title = item.get("title", "No title")
            it_status = item.get("status", "No status")
            typer.echo(f"{i}. #{issue_num} - {title} [{it_status}]")

        while True:
            try:
                selection = typer.prompt("\nEnter the number of the issue", type=int)
                if 1 <= selection <= len(items):
                    selected_item = items[selection - 1]
                    if selected_item:
                        issue = selected_item["content"]["number"]
                        item_title = selected_item["title"]
                        item_status = selected_item.get("status", "No status")
                        break
                typer.secho("Invalid selection. Please try again.", fg=typer.colors.YELLOW)
            except ValueError:
                typer.secho("Please enter a valid number.", fg=typer.colors.YELLOW)

    return dict(issue=issue, item_title=item_title, item_status=item_status)


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
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
    ):
        """Update the Status field of a GitHub Project item for a given issue.

        If no issue or status is provided, an interactive prompt will be shown to select them.
        """
        ensure_gh_installed()
        config = load_config(None)

        if GUM_AVAILABLE:
            # Add sticked header for GUM
            print(gum.style("Update issue status", foreground=81, bold=True))
            print(gum.style("=" * 50, foreground=81))

        valid_statuses = _get_valid_statuses()
        projects_keys = list(config.github.projects.keys())
        project_key = project
        if project_key is None:
            project_key = _get_project_interactively(projects_keys=projects_keys)

        if not project_key:
            typer.secho("Not valid project was selected", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        # Resolve project owner and number using existing logic
        owner, project_number = resolve_project_number(project_key)

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
        if status is None and item_status:
            status = _get_status_interactively(valid_statuses, item_status)

        # Validate the status
        if status is None:
            typer.secho("Status is required.", fg=typer.colors.RED)
            raise typer.Exit(1)
        _validate_status(status, valid_statuses)

        # If we got here with an issue number but no item_id, look up the item
        issue_repo, item_title = None, None
        if item_id is None and issue:
            with yaspin(text="Looking up project item..."):
                project_item = find_project_item_for_issue(owner, project_number, issue)
                item_id, item_title = project_item.id, project_item.title
                if project_item.repository:
                    issue_repo = project_item.repository

        integration_comment = None
        if status == config.github.integration_comment_status:
            integration_comment = _ask_for_integration_comment()

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
            typer.secho(
                f"✘ Failed to update project item status: {e}",
                fg=typer.colors.RED,
            )
            if e.stderr:
                typer.echo(e.stderr)
            raise typer.Exit(code=1)

        typer.secho(
            f"✔ Updated status of project item for issue #{issue} to '{status}' (title: {item_title})",
            fg=typer.colors.GREEN,
        )

        if integration_comment and issue_repo and issue:
            repo_owner, repo_name = _get_repo_owner_and_name(
                config=config, owner=owner, issue_repo=issue_repo
            )
            if repo_name and issue:
                with yaspin(text=f"Adding integration comment to issue #{issue}", color="green"):
                    add_issue_comment(repo_owner, repo_name, issue, integration_comment)
                    typer.secho(
                        f"✔ Added integration comment to issue #{issue} (title: {item_title})",
                        fg=typer.colors.GREEN,
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
