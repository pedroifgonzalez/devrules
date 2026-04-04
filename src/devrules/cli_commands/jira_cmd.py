"""CLI commands for Jira integration."""

import os
from typing import Any, Callable, Dict, Optional

import typer

from devrules.adapters.prompters.factory import get_default_prompter
from devrules.config import JiraConfig, load_config
from devrules.core.jira_service import JiraService

prompter = get_default_prompter()


def _get_jira_service() -> JiraService:
    """Load config and create a Jira service instance."""
    config = load_config(None)
    jira_config: JiraConfig = config.jira

    email = jira_config.email or os.getenv("JIRA_EMAIL")
    api_token = jira_config.api_token or os.getenv("JIRA_API_TOKEN")
    missing_fields = []
    if not jira_config.url:
        missing_fields.append("jira.url")
    if not email:
        missing_fields.append("jira.email or JIRA_EMAIL")
    if not api_token:
        missing_fields.append("jira.api_token or JIRA_API_TOKEN")
    if missing_fields:
        prompter.error("Jira is not fully configured. Missing: " + ", ".join(missing_fields))
        raise prompter.exit(1)

    return JiraService(jira_config)


def _quote_jql_value(value: str) -> str:
    """Escape a value for JQL."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _build_jql(
    raw_jql: Optional[str],
    project: Optional[str],
    status: Optional[str],
    assignee: Optional[str],
    default_project: Optional[str],
) -> str:
    """Build a JQL query from filters."""
    if raw_jql:
        return raw_jql

    final_project = project or default_project
    parts: list[str] = []

    if final_project:
        parts.append(f"project = {_quote_jql_value(final_project)}")
    if status:
        parts.append(f"status = {_quote_jql_value(status)}")
    if assignee:
        parts.append(f"assignee = {_quote_jql_value(assignee)}")

    return " AND ".join(parts) if parts else "ORDER BY updated DESC"


def _parse_labels(labels: Optional[str]) -> list[str]:
    """Parse comma-separated labels."""
    if not labels:
        return []
    return [label.strip() for label in labels.split(",") if label.strip()]


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    """Register Jira commands."""

    @app.command("list-jira-issues")
    def list_jira_issues(
        jql: Optional[str] = typer.Option(None, "--jql", help="Raw JQL query string"),
        project: Optional[str] = typer.Option(None, "--project", "-p", help="Jira project key"),
        status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
        assignee: Optional[str] = typer.Option(None, "--assignee", "-a", help="Filter by assignee"),
        max_results: int = typer.Option(
            50, "--max-results", help="Maximum number of issues to return"
        ),
    ) -> None:
        """List Jira issues using JQL or convenience filters."""
        prompter.header("List Jira issues")

        service = _get_jira_service()
        query = _build_jql(jql, project, status, assignee, service.config.default_project)

        try:
            issues = service.search_issues(query, max_results=max_results)
        except ValueError as exc:
            prompter.error(str(exc))
            raise prompter.exit(1)

        if not issues:
            prompter.info("No Jira issues matched the query.")
            return

        prompter.info("KEY\tSTATUS\tTYPE\tASSIGNEE\tSUMMARY")
        for issue in issues:
            assignee_name = issue.assignee or "-"
            summary = issue.summary.replace("\n", " ").strip()
            prompter.indented_message(
                f"{issue.key}\t{issue.status or '-'}\t{issue.issue_type or '-'}\t"
                f"{assignee_name}\t{summary}"
            )

    @app.command("create-jira-issue")
    def create_jira_issue(
        project: Optional[str] = typer.Option(None, "--project", "-p", help="Jira project key"),
        summary: str = typer.Option(..., "--summary", help="Issue summary"),
        issue_type: str = typer.Option("Task", "--type", help="Jira issue type"),
        description: Optional[str] = typer.Option(None, "--description", help="Issue description"),
        priority: Optional[str] = typer.Option(None, "--priority", help="Issue priority"),
        labels: Optional[str] = typer.Option(None, "--labels", help="Comma-separated labels"),
    ) -> None:
        """Create a Jira issue."""
        prompter.header("Create Jira issue")

        service = _get_jira_service()
        final_project = project or service.config.default_project

        if not final_project:
            typed_project = prompter.input_text("Project key", default="")
            if not typed_project:
                prompter.error("Project is required when no default Jira project is configured.")
                raise prompter.exit(1)
            final_project = typed_project.strip()

        try:
            issue = service.create_issue(
                project=final_project,
                summary=summary,
                issue_type=issue_type,
                description=description,
                priority=priority,
                labels=_parse_labels(labels),
            )
        except ValueError as exc:
            prompter.error(str(exc))
            raise prompter.exit(1)

        prompter.success(f"Created Jira issue {issue.key}")
        prompter.info(issue.url)

    @app.command("transition-jira-issue")
    def transition_jira_issue(
        issue: str = typer.Argument(..., help="Jira issue key"),
        status: Optional[str] = typer.Option(None, "--status", "-s", help="Target status name"),
        list_transitions: bool = typer.Option(
            False, "--list-transitions", help="List available transitions for the issue"
        ),
    ) -> None:
        """List or execute Jira issue transitions."""
        prompter.header("Transition Jira issue")

        service = _get_jira_service()

        try:
            transitions = service.get_transitions(issue)
        except ValueError as exc:
            prompter.error(str(exc))
            raise prompter.exit(1)

        if list_transitions:
            if not transitions:
                prompter.info(f"No transitions available for {issue}.")
                return

            prompter.info("ID\tNAME")
            for transition in transitions:
                prompter.indented_message(f"{transition.id}\t{transition.name}")
            return

        if not status:
            prompter.error("Provide --status to execute a transition, or use --list-transitions.")
            raise prompter.exit(1)

        selected_transition = next(
            (transition for transition in transitions if transition.name.lower() == status.lower()),
            None,
        )
        if not selected_transition:
            available = ", ".join(transition.name for transition in transitions) or "none"
            prompter.error(
                f"Transition '{status}' is not available for {issue}. Available transitions: {available}"
            )
            raise prompter.exit(1)

        try:
            changed = service.transition_issue(issue, selected_transition.id)
        except ValueError as exc:
            prompter.error(str(exc))
            raise prompter.exit(1)

        if changed:
            prompter.success(f"Transitioned {issue} to {selected_transition.name}")

    return {
        "list_jira_issues": list_jira_issues,
        "create_jira_issue": create_jira_issue,
        "transition_jira_issue": transition_jira_issue,
    }
