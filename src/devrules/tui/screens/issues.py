"""Issues screen for browsing GitHub/GitLab issues."""

import os
import re
from typing import List, Optional

from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import DataTable, Label, Select, Static

from devrules.tui.services.github_service import GitHubIssue, GitHubService
from devrules.tui.services.metrics_service import MetricsService


class IssuesScreen(Container):
    """Screen for browsing and tracking issues."""

    def __init__(self, config_file: str | None = None):
        """Initialize issues screen.

        Args:
            config_file: Optional path to config file
        """
        super().__init__()
        self.config_file = config_file
        self.metrics_service = MetricsService(config_file)
        self.github_service: Optional[GitHubService] = None
        self.all_issues: List[GitHubIssue] = []
        self.current_filter = "all"

    def compose(self):
        """Compose the issues screen layout."""
        yield Static("🎫 Issue Tracker", classes="screen-title")

        with Vertical():
            # Filter controls
            with Horizontal(id="filter-controls"):
                yield Label("Filter: ")
                yield Select(
                    [
                        ("All Issues", "all"),
                        ("Open Issues", "open"),
                        ("Closed Issues", "closed"),
                        ("Has Branch", "has_branch"),
                        ("No Branch", "no_branch"),
                    ],
                    value="all",
                    id="issue-filter",
                )

            # Issues table
            with VerticalScroll():
                yield DataTable(id="issues-table", zebra_stripes=True)
                yield Static("", id="issue-status")

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self.load_issues()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle filter selection change."""
        if event.select.id == "issue-filter":
            self.current_filter = str(event.value)
            self.filter_and_display_issues()

    def load_issues(self) -> None:
        """Load issues from GitHub."""
        status = self.query_one("#issue-status", Static)

        # Check if GitHub is configured
        gh_token = os.getenv("GH_TOKEN")
        if not gh_token:
            status.update(
                "⚠️  GitHub token not configured. Set GH_TOKEN environment variable to enable issue tracking.\n\n"
                "Example: export GH_TOKEN=ghp_your_token_here"
            )
            return

        # Try to extract owner/repo from git remote
        owner, repo = self._get_repo_info()
        if not owner or not repo:
            status.update(
                "⚠️  Could not detect GitHub repository. Make sure you're in a git repository with a GitHub remote."
            )
            return

        status.update(f"📡 Fetching issues from {owner}/{repo}...")

        try:
            # Initialize GitHub service
            self.github_service = GitHubService(owner, repo, gh_token)

            # Fetch all issues
            self.all_issues = self.github_service.get_issues(state="all")

            if not self.all_issues:
                status.update(f"No issues found in {owner}/{repo}")
                return

            # Match issues to branches
            self._match_issues_to_branches()

            # Display issues
            self.filter_and_display_issues()

        except Exception as e:
            status.update(f"✗ Error loading issues: {e}")

    def _get_repo_info(self) -> tuple[Optional[str], Optional[str]]:
        """Extract owner and repo from git remote.

        Returns:
            Tuple of (owner, repo) or (None, None) if not found
        """
        import subprocess

        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True,
            )
            remote_url = result.stdout.strip()

            # Parse GitHub URL (supports both HTTPS and SSH)
            # HTTPS: https://github.com/owner/repo.git
            # SSH: git@github.com:owner/repo.git
            match = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)", remote_url)
            if match:
                return match.group(1), match.group(2)

        except subprocess.CalledProcessError:
            pass

        return None, None

    def _match_issues_to_branches(self) -> None:
        """Match issues to existing branches."""
        branches = self.metrics_service.get_all_branches()

        for issue in self.all_issues:
            # Look for branches containing the issue number
            issue_num = str(issue.number)

            for branch in branches:
                # Match patterns like:
                # - feature/123-description
                # - bugfix/123-description
                # - 123-description
                # - feature-123
                # Or just containing the issue number
                if (
                    f"/{issue_num}-" in branch  # feature/123-desc
                    or f"-{issue_num}-" in branch  # feature-123-desc
                    or f"/{issue_num}" in branch  # feature/123
                    or branch.startswith(f"{issue_num}-")  # 123-desc
                    or f"-{issue_num}" in branch  # feature-123
                ):
                    issue.has_branch = True
                    issue.branch_name = branch
                    break

    def filter_and_display_issues(self) -> None:
        """Filter and display issues based on current filter."""
        # Filter issues
        filtered_issues = self.all_issues

        if self.current_filter == "open":
            filtered_issues = [i for i in self.all_issues if i.state == "open"]
        elif self.current_filter == "closed":
            filtered_issues = [i for i in self.all_issues if i.state == "closed"]
        elif self.current_filter == "has_branch":
            filtered_issues = [i for i in self.all_issues if i.has_branch]
        elif self.current_filter == "no_branch":
            filtered_issues = [i for i in self.all_issues if not i.has_branch]

        # Display in table
        table = self.query_one("#issues-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Status", "#", "Title", "Branch", "Labels")

        for issue in filtered_issues:
            # Status icon
            if issue.state == "closed":
                status_icon = "✓"
            elif issue.has_branch:
                status_icon = "🔀"
            else:
                status_icon = "○"

            # Branch info
            branch_info = issue.branch_name if issue.has_branch else "—"

            # Labels
            labels_str = ", ".join(issue.labels[:3]) if issue.labels else "—"
            if len(issue.labels) > 3:
                labels_str += "..."

            table.add_row(
                status_icon,
                f"#{issue.number}",
                issue.title[:50] + ("..." if len(issue.title) > 50 else ""),
                branch_info[:30] + ("..." if branch_info != "—" and len(branch_info) > 30 else ""),
                labels_str,
            )

        # Update status
        status = self.query_one("#issue-status", Static)
        has_branch_count = sum(1 for i in self.all_issues if i.has_branch)
        no_branch_count = len(self.all_issues) - has_branch_count

        status.update(
            f"Showing {len(filtered_issues)} of {len(self.all_issues)} issues • "
            f"{has_branch_count} with branches • "
            f"{no_branch_count} without branches"
        )
