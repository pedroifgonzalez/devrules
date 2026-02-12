"""CLI commands for the Work Center."""

import subprocess
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import typer
from typer_di import Depends
from typing_extensions import DefaultDict
from yaspin import yaspin

from devrules.adapters.prompters.factory import get_default_prompter
from devrules.config import Config, load_config
from devrules.core.project_service import (
    add_issue_comment,
    find_project_item_for_issue,
    resolve_project_number,
    update_issue_status,
)
from devrules.tui.services.github_service import GitHubComment, GitHubIssue, GitHubService
from devrules.utils.decorators import ensure_git_repo
from devrules.utils.spinner_ctx import set_spinner


def _get_issues_statuses_legend(config: Config, status_issues: dict) -> str:
    status_emojis = getattr(config.github, "status_emojis", {})
    present_status_emojis = []
    for status, _ in status_issues.items():
        emoji = status_emojis.get(status.strip().lower().replace(" ", "_"))
        if emoji:
            present_status_emojis.append((status, emoji))
    return ", ".join(f"{emoji}: {status}" for status, emoji in present_status_emojis)


def _format_issues_for_list(
    issues: list[GitHubIssue], config: Config, use_emojis: bool = False
) -> list[str]:
    """Format issues for the prompter list with aligned columns."""
    status_emojis = getattr(config.github, "status_emojis", {})

    rows = []
    for issue in issues:
        # Simple normalization for emoji lookup
        emoji_or_status = (
            status_emojis.get(issue.status.strip().lower().replace(" ", "_"), "•")
            if issue.status and use_emojis
            else issue.status
        )
        project_section = (
            f"({config.github.projects.get(issue.project_name)})" if config.github.projects else ""
        )
        priority_section = (
            "!"
            * (
                len(config.github.priorities_hierarchy)
                - config.github.priorities_hierarchy.index(issue.priority)
            )
            if issue.priority and issue.priority in config.github.priorities_hierarchy
            else ""
        )
        title_section = issue.title[:80] + "..." if len(issue.title) > 80 else issue.title
        repo_section = f"«{issue.repo_name.split('-')[-1]}»" if issue.repo_name else ""
        rows.append(
            (
                str(issue.number),
                emoji_or_status or "",
                priority_section,
                title_section,
                repo_section,
                project_section,
            )
        )

    # Compute max widths per column
    col_widths = [0] * 6
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    formatted = []
    for row in rows:
        num, status, priority, title, repo, project = row
        line = (
            f"{num:>{col_widths[0]}} {status:<{col_widths[1]}}   "
            f"{priority:<{col_widths[2]}} {title:<{col_widths[3]}}   "
            f"{repo:<{col_widths[4]}} {project}"
        )
        formatted.append(line)

    return formatted


def _format_comment_for_list(comment: GitHubComment) -> str:
    """Format a comment for the prompter list."""
    # created_at is like "2023-10-27T10:00:00Z"
    try:
        dt = datetime.fromisoformat(comment.created_at.replace("Z", "+00:00"))
        time_str = dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        time_str = comment.created_at

    preview = comment.body[:50].replace("\n", " ")
    if len(comment.body) > 50:
        preview += "..."

    return f"#{comment.issue_number} @{comment.author} ({time_str}): {preview}"


cached_issues: list[GitHubIssue] = []
cached_comments: list[GitHubComment] = []


def _handle_pending_issues(config: Config, project_filter: Optional[str] = None):
    """Handle the Pending Issues flow."""
    prompter = get_default_prompter()
    gh = GitHubService(
        owner=config.github.owner, repo=config.github.repo, token=config.github.token
    )

    global cached_issues

    issues = []
    if not cached_issues:
        with yaspin(text="Fetching actionable issues...") as spinner:
            set_spinner(spinner)
            issues = gh.get_my_actionable_issues(
                excluded_statuses=config.github.excluded_work_statuses,
                project_filter=project_filter,
            )
            cached_issues.extend(issues)
    else:
        issues = cached_issues

    if not issues:
        prompter.info("No actionable issues found.")
        return

    sorted_issues, status_issues = [], DefaultDict(list)
    for issue in issues:
        status_issues[issue.status].append(issue)
    for _, iss in status_issues.items():
        sorted_issues.extend(iss)

    # sort by priority (already normalized to priorities_hierarchy values at fetch time)
    if config.github.priorities_hierarchy:
        hierarchy = config.github.priorities_hierarchy
        fallback = len(hierarchy)
        sorted_issues.sort(
            key=lambda x: (
                hierarchy.index(x.priority) if x.priority and x.priority in hierarchy else fallback
            )
        )

    use_emojis = False
    formatted_labels = _format_issues_for_list(sorted_issues, config, use_emojis)
    issue_options = dict(zip(formatted_labels, sorted_issues))
    selected_label = prompter.filter_list(
        list(issue_options.keys()),
        placeholder="Search issues...",
        header=f"Select an issue:\n{_get_issues_statuses_legend(config=config, status_issues=status_issues) if use_emojis else ''}\n",
    )

    if not selected_label:
        return

    issue_options = {k.strip(): v for k, v in issue_options.items()}
    issue = issue_options[selected_label]

    action = prompter.choose(
        ["Start working", "Ask doubt", "View details", "Open in browser"],
        header=f"Actions for #{issue.number}:",
    )

    if action == "Start working":
        _start_working(issue, config)
    elif action == "Ask doubt":
        _ask_doubt(issue, config)
    elif action == "View details":
        _view_details(issue)
    elif action == "Open in browser":
        _open_in_browser(issue)


def _start_working(issue: GitHubIssue, config: Config):
    """Action: Start working on an issue."""
    prompter = get_default_prompter()

    try:
        # 1. Update status
        if not issue.project_name:
            prompter.error("Issue is not associated with a project.")
            return

        owner, p_num = resolve_project_number(issue.project_name)

        # We need the item_id. GitHubIssue doesn't have it yet,
        # but gh.get_my_actionable_issues could have populated it.
        # For now, let's look it up again to be sure if needed,
        # but better to have it in GitHubIssue.

        # Redoing lookup to get item_id if we didn't store it
        # Actually, let's assume we need to find it.
        with yaspin(
            text=f"Updating issue status (Using {config.github.start_work_status})..."
        ) as spinner:
            set_spinner(spinner)
            project_item = find_project_item_for_issue(owner, p_num, issue.number)
            update_issue_status(owner, p_num, project_item.id, config.github.start_work_status)

        prompter.success(f"Status updated to '{config.github.start_work_status}'.")

        # 2. Create branch
        # We invoke the branch creation logic.
        # Since 'create_branch' is a Typer command, we call it if possible or use subprocess for simplicity
        # but the prompt says "Invoke the branch creation logic...".
        # I'll import create_branch and call it.

        prompter.info("Creating branch...")
        # create_branch is decorated with @ensure_git_repo and Depends.
        # Calling it directly might be tricky.
        # Better to use subprocess to call 'devrules create-branch'

        cmd = [
            "devrules",
            "create-branch",
            "--issue",
            str(issue.number),
            "--project",
            issue.project_name,
        ]
        subprocess.run(cmd)

    except Exception as e:
        prompter.error(f"Failed to start work: {e}")


def _ask_doubt(issue: GitHubIssue, config: Config):
    """Action: Ask a doubt (post a comment)."""
    prompter = get_default_prompter()

    question = prompter.write(
        placeholder="Type your question or doubt...",
        header=f"Ask doubt on #{issue.number}:",
    )

    if not question:
        return

    try:
        with yaspin(text="Posting comment..."):
            add_issue_comment(config.github.owner, config.github.repo, issue.number, question)
        prompter.success("Comment posted successfully!")
    except Exception as e:
        prompter.error(f"Failed to post comment: {e}")


def _view_details(issue: GitHubIssue):
    """Action: View issue details in terminal."""
    prompter = get_default_prompter()
    cmd = ["gh", "issue", "view", str(issue.number)]
    if issue.owner and issue.repo_name:
        cmd.extend(["-R", f"{issue.owner}/{issue.repo_name}"])
    try:
        subprocess.run(cmd)
    except Exception as e:
        prompter.error(f"Failed to view details: {e}")


def _open_in_browser(issue: GitHubIssue):
    """Action: Open issue in browser."""
    prompter = get_default_prompter()
    cmd = ["gh", "issue", "view", str(issue.number), "--web"]
    try:
        subprocess.run(cmd)
        prompter.info(f"Opened #{issue.number} in browser.")
    except Exception as e:
        prompter.error(f"Failed to open browser: {e}")


def _handle_new_comments(config: Config):
    """Handle the New Comments flow."""
    prompter = get_default_prompter()
    gh = GitHubService(
        owner=config.github.owner, repo=config.github.repo, token=config.github.token
    )

    global cached_comments

    if not cached_comments:
        with yaspin(text="Fetching recent comments..."):
            comments = gh.get_recent_comments(hours=config.github.recent_comments_hours)
            cached_comments.extend(comments)
    else:
        comments = cached_comments

    if not comments:
        prompter.info("No new comments found.")
        return

    comment_options = {_format_comment_for_list(c): c for c in comments}
    selected_label = prompter.filter_list(
        list(comment_options.keys()),
        placeholder="Search comments...",
        header="Recent comments on your issues:",
    )

    if not selected_label:
        return

    comment = comment_options[selected_label]

    action = prompter.choose(
        ["Respond 💬", "Update issue status 📝"],
        header=f"Actions for comment on #{comment.issue_number}:",
    )

    if action == "Respond 💬":
        _respond_to_comment(comment, config)
    elif action == "Update issue status 📝":
        _update_issue_status_flow(comment, config)


def _respond_to_comment(comment: GitHubComment, config: Config):
    """Action: Respond to a comment."""
    prompter = get_default_prompter()

    prompter.info(f"--- Comment from @{comment.author} ---")
    prompter.info(comment.body)
    prompter.info("-" * 30)

    response = prompter.write(
        placeholder="Type your response...",
        header=f"Respond to @{comment.author} on #{comment.issue_number}:",
    )

    if not response:
        return

    try:
        with yaspin(text="Posting response..."):
            add_issue_comment(
                config.github.owner,
                config.github.repo,
                comment.issue_number,
                response,
                title="Doubt:",
            )
        prompter.success("Response posted successfully!")
    except Exception as e:
        prompter.error(f"Failed to post response: {e}")


def _update_issue_status_flow(comment: GitHubComment, config: Config):
    """Action: Update issue status from comment flow."""
    prompter = get_default_prompter()

    valid_statuses = config.github.valid_statuses or [
        "Backlog",
        "Blocked",
        "To Do",
        "In Progress",
        "Waiting Integration",
        "Done",
    ]

    new_status = prompter.choose(
        valid_statuses,
        header=f"Select new status for #{comment.issue_number}:",
    )

    if not new_status:
        return

    try:
        # Find which project this issue belongs to.
        # This is the tricky part because comments don't have project info.
        # We might need to iterate projects to find it.
        with yaspin(text="Finding issue project..."):
            found_p_key = None
            found_p_item = None
            for p_key in config.github.projects:
                try:
                    owner, p_num = resolve_project_number(p_key)
                    item = find_project_item_for_issue(owner, p_num, comment.issue_number)
                    if item:
                        found_p_key = p_key
                        found_p_item = item
                        break
                except Exception:
                    continue

        if not found_p_key or not found_p_item:
            prompter.error(f"Could not find project for issue #{comment.issue_number}.")
            return

        integration_comment = None
        if new_status == config.github.integration_comment_status:
            # Reusing integration comment logic
            integration_comment = prompter.write(
                placeholder="Add integration details (markdown supported)...",
                header="📝 Integration Details:",
            )
            if not integration_comment:
                if not prompter.confirm("Continue without integration comment?", default=False):
                    return

        with yaspin(text="Updating status..."):
            owner, p_num = resolve_project_number(found_p_key)
            update_issue_status(owner, p_num, found_p_item.id, new_status)

        prompter.success(f"Issue #{comment.issue_number} status updated to '{new_status}'.")

        if integration_comment:
            with yaspin(text="Adding integration comment..."):
                add_issue_comment(
                    config.github.owner,
                    config.github.repo,
                    comment.issue_number,
                    integration_comment,
                )
            prompter.success("Integration comment added.")

    except Exception as e:
        prompter.error(f"Failed to update status: {e}")


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    """Register Work Center commands."""

    @app.command(name="center")
    @ensure_git_repo()
    def center(
        project: Optional[str] = typer.Option(None, "--project", "-p", help="Filter by project"),
        config: Config = Depends(load_config),
    ):
        """Interactive Work Center (alias: wc)."""
        prompter = get_default_prompter()

        done = False
        while not done:
            choice = prompter.choose(
                ["Pending Issues", "New Comments"],
                header="Work Center - Main Menu",
            )
            if not choice:
                done = True
                break
            if choice == "Pending Issues":
                _handle_pending_issues(config, project)
            elif choice == "New Comments":
                _handle_new_comments(config)

            done = prompter.confirm("Are you done?", default=True)

    return {"center": center}
