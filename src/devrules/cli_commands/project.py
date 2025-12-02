import subprocess
from typing import Any, Callable, Dict, Optional

import typer

from devrules.config import load_config
from devrules.core.github_service import ensure_gh_installed
from devrules.core.project_service import (
    add_issue_comment,
    find_project_item_for_issue,
    get_project_id,
    get_project_item_title_by_id,
    get_status_field_id,
    get_status_option_id,
    print_project_items,
    resolve_project_number,
)


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


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command()
    def update_issue_status(
        issue: int = typer.Argument(..., help="Issue number (e.g. 123)"),
        status: str = typer.Option(..., "--status", "-s", help="New project status value"),
        project: str = typer.Option(
            ...,
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
        """Update the Status field of a GitHub Project item for a given issue."""

        ensure_gh_installed()

        # Load config to validate allowed statuses
        config = load_config(None)
        valid_statuses = _get_valid_statuses()

        if status not in valid_statuses:
            allowed = ", ".join(valid_statuses)
            typer.secho(
                f"✘ Invalid status '{status}'. Allowed values: {allowed}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        # Resolve project owner and number using existing logic
        owner, project_number = resolve_project_number(project)

        # Determine which project item to update: direct item id or lookup by issue
        issue_repo = None
        if item_id is not None:
            item_title = get_project_item_title_by_id(owner, project_number, item_id)
        else:
            project_item = find_project_item_for_issue(owner, project_number, issue)
            item_id, item_title = project_item.id, project_item.title
            if project_item.repository:
                issue_repo = project_item.repository

        integration_comment = None
        if status == "Waiting Integration":
            typer.echo("\n📝 Please provide integration details for frontend colleagues:")
            typer.echo("   Options:")
            typer.echo("   1. Type a simple comment directly")
            typer.echo("   2. Press Enter to open your editor for multi-line markdown")
            typer.echo("")

            simple_comment = typer.prompt(
                "Comment (or press Enter for editor)", default="", show_default=False
            ).strip()

            if simple_comment:
                integration_comment = simple_comment
            else:
                integration_comment = typer.edit(
                    "\n# Add integration details below (markdown supported)\n# Lines starting with # will be ignored\n\n"
                )
                if integration_comment:
                    lines = [
                        line
                        for line in integration_comment.split("\n")
                        if not line.strip().startswith("#")
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

        project_id = get_project_id(owner, project_number)
        status_field_id = get_status_field_id(owner, project_number)
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

        if integration_comment:
            repo_to_use = issue_repo if issue_repo else config.github.repo

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

            add_issue_comment(repo_owner, repo_name, issue, integration_comment)
            typer.secho(
                f"✔ Added integration comment to issue #{issue}",
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

    return {
        "update_issue_status": update_issue_status,
        "list_issues": list_issues,
    }
