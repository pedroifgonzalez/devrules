"""Project service for interacting with GitHub Projects logic."""

import functools
import json
import re
import subprocess
from typing import Optional, Tuple

import typer

from devrules.adapters.prompters.factory import get_default_prompter
from devrules.config import load_config
from devrules.dtos.github import ProjectItem
from devrules.utils.project_cache import get_project_cache_manager
from devrules.utils.spinner_ctx import stop_spinner, update_spinner_text

VIDEO_EXTENSIONS = (".mp4", ".webm", ".gif")

prompter = get_default_prompter()


def extract_media_urls(text: str) -> list[str]:
    """Extract media URLs from a given text."""
    if not text:
        return []

    url_regex = r"https?://[^\s\)]+"
    urls = re.findall(url_regex, text)

    return [
        url
        for url in urls
        if url.lower().endswith(VIDEO_EXTENSIONS)
        or "https://github.com/user-attachments/assets/" in url
    ]


def resolve_project_number(project: str) -> Tuple[str, str]:
    """Resolve project key/number to (owner, project_number) using config.

    Logic is copied from cli._resolve_project_number to keep behavior
    identical, only centralized here.
    """
    update_spinner_text("Resolving project number...")

    config = load_config(None)
    owner = getattr(config.github, "owner", None)

    if not owner:
        typer.secho(
            "✘ GitHub owner must be configured in the config file under the [github] section to use --project.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    project_str = str(project)
    project_number: Optional[str] = None

    if project_str.isdigit():
        project_number = project_str
    else:
        projects_map = getattr(config.github, "projects", {}) or {}
        raw_value = projects_map.get(project_str)

        if raw_value is None:
            prompter.warning(
                f"Unknown project key '{project_str}'",
            )
            available_projects = list(projects_map.keys())
            selected_project = prompter.choose(available_projects)
            raw_value = projects_map.get(selected_project)

        match = __import__("re").search(r"(\d+)", str(raw_value))
        if match:
            project_number = match.group(1)
        else:
            raw_str = str(raw_value).strip()
            if raw_str.isdigit():
                project_number = raw_str

    if project_number is None:
        typer.secho(
            f"✘ Unable to determine numeric project ID from '{project}'. Configure it as a number or include '#<id>' in the value.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Validate project exists using cache if available
    if getattr(config.github, "project_cache_enabled", False):
        cache_mgr = get_project_cache_manager(getattr(config.github, "project_cache_path", None))
        cached_id = cache_mgr.get_project_id(owner, project_number)
        if cached_id:
            # Project exists in cache, validation successful
            return owner, project_number

    return owner, project_number


def parse_project_items(stdout: str):
    """Parse gh project item-list JSON output into an items list.

    Behavior mirrors cli._parse_project_items.
    """

    try:
        data = json.loads(stdout or "[]")
    except json.JSONDecodeError:
        typer.echo(stdout)
        raise typer.Exit(code=1)

    if isinstance(data, dict) and "items" in data:
        items = data.get("items", [])
    else:
        items = data

    if not items:
        typer.secho("✘ No project items found in the project.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    return items


def select_single_item_for_issue(items, issue: int):
    """Select a single project item matching an issue number.

    Behavior mirrors cli._select_single_item_for_issue.
    """

    issue_str = str(issue)
    needle_hash = f"#{issue_str}"

    matches = []
    for item in items:
        raw_type = item.get("type") or ""
        content = item.get("content", {}) or {}
        content_url = content.get("url", "") or ""

        norm_type = str(raw_type).strip().lower()
        is_issue = "issues" in content_url or norm_type == "issue"

        title = item.get("title") or content.get("title", "")
        if not title:
            continue

        if (needle_hash in title or (issue_str in title and needle_hash not in title)) and is_issue:
            matches.append(item)
            continue

        number = content.get("number")
        if number is not None and str(number) == issue_str and is_issue:
            matches.append(item)

    if not matches:
        typer.secho(
            f"✘ Could not find a project item with issue number #{issue} in the title.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    if len(matches) > 1:
        # TODO: use generic prompter
        typer.secho(
            f"⚠ Multiple project items match issue number #{issue}. Please select one:",
            fg=typer.colors.YELLOW,
        )
        for idx, item in enumerate(matches, 1):
            title = item.get("title") or item.get("content", {}).get("title", "")
            typer.echo(f"{idx}. {title}")

        while True:
            try:
                choice = typer.prompt("Enter your choice", type=int)
                if 1 <= choice <= len(matches):
                    return matches[choice - 1]
                else:
                    typer.secho(
                        f"✘ Invalid choice. Please enter a number between 1 and {len(matches)}.",
                        fg=typer.colors.RED,
                    )
            except (ValueError, typer.Abort):
                typer.secho("✘ Selection cancelled.", fg=typer.colors.RED)
                raise typer.Exit(code=1)

    return matches[0]


def find_project_item_for_issue(owner: str, project_number: str, issue: int) -> ProjectItem:
    """Wrapper around gh project item-list to find item by issue number."""
    update_spinner_text("Finding project item for issue...")
    cmd = [
        "gh",
        "project",
        "item-list",
        project_number,
        "--owner",
        owner,
        "--format",
        "json",
        "--limit",
        "200",
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
            f"✘ Failed to list project items: {e}",
            fg=typer.colors.RED,
        )
        if e.stderr:
            typer.echo(e.stderr)
        raise typer.Exit(code=1)

    stop_spinner()
    items = parse_project_items(result.stdout)
    item = select_single_item_for_issue(items, issue)

    project_item = ProjectItem(
        assignees=item.get("assignees", []),
        id=item.get("id"),
        labels=item.get("labels"),
        repository=item.get("repository"),
        status=item.get("status"),
        title=item.get("title"),
    )

    if not project_item.id:
        typer.secho("✘ Matching project item does not have an 'id' field.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    return project_item


@functools.lru_cache(maxsize=64)
def _get_project_fields(owner: str, project_number: str) -> list[dict]:
    config = load_config(None)
    if getattr(config.github, "project_cache_enabled", False):
        cache_mgr = get_project_cache_manager(getattr(config.github, "project_cache_path", None))
        cached_fields = cache_mgr.get_fields(owner, project_number)
        if cached_fields is not None:
            return cached_fields

    cmd = [
        "gh",
        "project",
        "field-list",
        project_number,
        "--owner",
        owner,
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
            f"✘ Failed to list project fields: {e}",
            fg=typer.colors.RED,
        )
        if e.stderr:
            typer.echo(e.stderr)
        raise typer.Exit(code=1)

    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        typer.echo(result.stdout)
        raise typer.Exit(code=1)

    if isinstance(data, dict) and "fields" in data:
        fields = data.get("fields", [])
    elif isinstance(data, list):
        fields = data
    else:
        fields = []

    if getattr(config.github, "project_cache_enabled", False) and fields:
        cache_mgr = get_project_cache_manager(getattr(config.github, "project_cache_path", None))
        cache_mgr.set_fields(owner, project_number, fields)

    return fields


@functools.lru_cache(maxsize=64)
def get_project_id(owner: str, project_number: str) -> str:
    """Return project node id using gh project view.

    Mirrors cli._get_project_id.
    """

    config = load_config(None)
    if getattr(config.github, "project_cache_enabled", False):
        cache_mgr = get_project_cache_manager(getattr(config.github, "project_cache_path", None))
        cached_id = cache_mgr.get_project_id(owner, project_number)
        if cached_id:
            return cached_id

    cmd = [
        "gh",
        "project",
        "view",
        project_number,
        "--owner",
        owner,
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
            f"✘ Failed to get project info: {e}",
            fg=typer.colors.RED,
        )
        if e.stderr:
            typer.echo(e.stderr)
        raise typer.Exit(code=1)

    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        typer.echo(result.stdout)
        raise typer.Exit(code=1)

    project_id = data.get("id")
    if not project_id:
        typer.secho(
            "✘ Unable to determine project id from gh project view output.", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    if getattr(config.github, "project_cache_enabled", False):
        cache_mgr = get_project_cache_manager(getattr(config.github, "project_cache_path", None))
        cache_mgr.set_project_id(owner, project_number, str(project_id))

    return project_id


def get_status_field_id(owner: str, project_number: str) -> str:
    """Return the field id for the project's "Status" field."""

    fields = _get_project_fields(owner, project_number)

    for field in fields:
        if field.get("name") == "Status":
            field_id = field.get("id")
            if field_id:
                return field_id

    typer.secho("✘ Could not find a 'Status' field in the project.", fg=typer.colors.RED)
    raise typer.Exit(code=1)


def get_status_option_id(owner: str, project_number: str, status: str) -> str:
    """Return the option id for a given Status value in the project."""

    fields = _get_project_fields(owner, project_number)

    for field in fields:
        if field.get("name") != "Status":
            continue

        options = field.get("options") or []
        for opt in options:
            if opt.get("name") == status:
                option_id = opt.get("id")
                if option_id:
                    return option_id

    typer.secho(
        f"✘ Could not find a Status option named '{status}' in the project.",
        fg=typer.colors.RED,
    )
    raise typer.Exit(code=1)


def get_project_item_title_by_id(owner: str, project_number: str, item_id: str) -> str:
    """Return the title of a project item given its id."""

    cmd = [
        "gh",
        "project",
        "item-list",
        project_number,
        "--owner",
        owner,
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
            f"✘ Failed to list project items: {e}",
            fg=typer.colors.RED,
        )
        if e.stderr:
            typer.echo(e.stderr)
        raise typer.Exit(code=1)

    items = parse_project_items(result.stdout)
    for item in items:
        if str(item.get("id")) == str(item_id):
            return item.get("title") or item.get("content", {}).get("title", "")

    typer.secho(
        f"✘ Could not find a project item with id '{item_id}' in the project.",
        fg=typer.colors.RED,
    )
    raise typer.Exit(code=1)


def add_issue_comment(
    owner: str, repo: str, issue: int, comment: str, title: str = "Integration Details"
) -> None:
    """Add a comment to a GitHub issue using gh CLI."""

    if comment.strip().startswith("#"):
        body = comment
    else:
        body = f"## {title}\n\n{comment}"

    repo_full = f"{owner}/{repo}"

    cmd = [
        "gh",
        "issue",
        "comment",
        str(issue),
        "--repo",
        repo_full,
        "--body",
        body,
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
            f"✘ Failed to add comment to issue #{issue} in {repo_full}",
            fg=typer.colors.RED,
        )
        if e.stderr:
            typer.echo(e.stderr)

        if "Could not resolve to an issue" in str(e.stderr):
            typer.secho(
                f"⚠ Issue #{issue} does not exist in repository {repo_full}",
                fg=typer.colors.YELLOW,
            )
            typer.secho(
                "  Make sure the issue number matches the repository in your config",
                fg=typer.colors.YELLOW,
            )

        typer.secho(
            "⚠ Status was updated but comment failed to post",
            fg=typer.colors.YELLOW,
        )


def list_project_items(
    owner: str, project_number: str, exclude_status: Optional[str] = None
) -> list[dict]:
    """List all items in a GitHub project, optionally excluding items with a specific status.

    Args:
        owner: The repository owner
        project_number: The project number
        exclude_status: Optional status to exclude (e.g., "Done")

    Returns:
        List of project items with their details
    """

    cmd = [
        "gh",
        "project",
        "item-list",
        project_number,
        "--owner",
        owner,
        "--format",
        "json",
        "--limit",
        "100",
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            typer.echo(result.stdout)
            raise typer.Exit(code=1)

        items = output.get("items", [])

        # Filter out items with the excluded status if specified
        if exclude_status is not None:
            items = [item for item in items if item.get("status") != exclude_status]

        return items

    except subprocess.CalledProcessError as e:
        typer.secho(
            f"✘ Failed to list project items: {e}",
            fg=typer.colors.RED,
        )
        if e.stderr:
            typer.echo(e.stderr)
        raise typer.Exit(code=1) from e


def print_project_items(
    stdout: str,
    assignee: Optional[str],
    project_str: str,
    status: Optional[str] = None,
) -> None:
    """Pretty-print project items with optional assignee and status filters.

    Mirrors cli._print_project_items behavior.
    """

    try:
        data = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        typer.echo(stdout)
        raise typer.Exit(code=1)

    if isinstance(data, dict) and "items" in data:
        items = data.get("items", [])
    elif isinstance(data, list):
        items = data
    else:
        items = []

    if status:
        status_lower = status.lower()
        filtered_by_status = []
        for item in items:
            item_status = (item.get("status") or "").lower()
            if item_status == status_lower:
                filtered_by_status.append(item)

        items = filtered_by_status

    if assignee:
        assignee_lower = assignee.lower()
        filtered_items = []
        for item in items:
            content = item.get("content", {}) or {}

            raw_assignees = []
            top_level = item.get("assignees") or []
            content_level = content.get("assignees") or []

            if isinstance(top_level, list):
                raw_assignees.extend(top_level)
            if isinstance(content_level, list):
                raw_assignees.extend(content_level)

            usernames = []
            for a in raw_assignees:
                if isinstance(a, str):
                    usernames.append(a)
                elif isinstance(a, dict):
                    login = a.get("login") or a.get("name")
                    if login:
                        usernames.append(login)

            if any(u.lower() == assignee_lower for u in usernames):
                filtered_items.append(item)

        items = filtered_items

    if not items:
        typer.echo("No project items found.")
        return

    config = load_config(None)
    configured_emojis = getattr(config.github, "status_emojis", None)

    def _norm_status_key(value: Optional[str] = None) -> str:
        return (value or "").strip().lower().replace(" ", "_")

    if configured_emojis:
        raw_emojis = dict(configured_emojis)
    else:
        raw_emojis = {
            "Backlog": "📋",
            "Blocked": "⛔",
            "To Do": "📝",
            "In Progress": "🚧",
            "Waiting Integration": "🔄",
            "QA Testing": "🧪",
            "QA In Progress": "🔬",
            "QA Approved": "✅",
            "Pending To Deploy": "⏳",
            "Done": "🏁",
        }

    status_emojis = {_norm_status_key(name): emoji for name, emoji in raw_emojis.items()}

    configured_statuses = getattr(config.github, "valid_statuses", None)
    if configured_statuses:
        missing_emoji_statuses = [
            s for s in configured_statuses if _norm_status_key(s) not in status_emojis
        ]
        if missing_emoji_statuses:
            missing_str = ", ".join(missing_emoji_statuses)
            typer.secho(
                f"⚠ Some statuses do not have emojis configured: {missing_str}",
                fg=typer.colors.YELLOW,
            )

    typer.echo(f"Project {project_str}:")
    for item in items:
        content = item.get("content", {}) or {}
        title = item.get("title") or content.get("title", "")
        status = item.get("status", "")
        priority = item.get("priority", "")
        number = content.get("number")

        emoji = status_emojis.get(_norm_status_key(status), "•")

        if number is not None:
            typer.echo(f"{emoji} #{number} [{status or '-'}] ({priority or '-'}) {title}")
        else:
            typer.echo(f"{emoji} [{status or '-'}] ({priority or '-'}) {title}")


def show_issue_on_web(issue: str) -> bool:
    """Open an issue on the web using GitHub CLI."""
    cmd = ["gh", "issue", "view", issue, "--web"]
    try:
        subprocess.run(cmd, capture_output=True, check=True, text=True)
    except subprocess.CalledProcessError as e:
        typer.secho(f"Error opening issue on web: {e}", fg=typer.colors.RED)
        return False
    else:
        return True


def get_issue_evidence(issue: str) -> list[str]:
    """Get issue list of assets added as evidence"""
    evidence: list[str] = []

    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "view",
                issue,
                "--json",
                "comments",
            ],
            capture_output=True,
            check=True,
            text=True,
        )

        data = json.loads(result.stdout)

        # Comments
        for comment in data.get("comments", []):
            evidence.extend(extract_media_urls(comment.get("body", "")))

    except subprocess.CalledProcessError as e:
        typer.secho(
            f"gh command failed: {e.stderr or e}",
            fg=typer.colors.RED,
        )
    except (json.JSONDecodeError, KeyError) as e:
        typer.secho(
            f"Error getting issue evidence: {e}",
            fg=typer.colors.RED,
        )

    # Remove duplicates while preserving order
    return list(dict.fromkeys(evidence))


def update_issue_status(owner: str, project_number: str, item_id: str, status: str) -> None:
    """Update the Status field of a GitHub Project item.

    Args:
        owner: The repository owner
        project_number: The project number
        item_id: The project item ID
        status: The new status name
    """
    project_id = get_project_id(owner, project_number)
    status_field_id = get_status_field_id(owner, project_number)
    status_option_id = get_status_option_id(owner, project_number, status)
    update_spinner_text("Updating issue status")
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
