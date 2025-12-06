"""Dashboard screen showing metrics and statistics."""

from textual.containers import Container, Vertical
from textual.widgets import Static

from devrules.tui.services.metrics_service import MetricsService
from devrules.tui.widgets.metrics_card import MetricsCard


class DashboardScreen(Container):
    """Main dashboard screen with metrics overview."""

    def __init__(self, config_file: str | None = None):
        """Initialize dashboard screen.

        Args:
            config_file: Optional path to config file
        """
        super().__init__()
        self.config_file = config_file
        self.metrics_service = MetricsService(config_file)

    def compose(self):
        """Compose the dashboard layout."""
        yield Static("📊 DevRules Metrics Dashboard", classes="screen-title")

        with Vertical():
            yield MetricsCard(
                title="Branch Compliance",
                value="Loading...",
                description="Percentage of branches following naming conventions",
                metric_id="branch_compliance",
                show_progress=True,
            )
            yield MetricsCard(
                title="Commit Quality",
                value="Loading...",
                description="Percentage of commits with valid messages (last 100)",
                metric_id="commit_quality",
                show_progress=True,
            )
            yield MetricsCard(
                title="Active Branches",
                value="Loading...",
                description="Total number of local branches",
                metric_id="active_branches",
            )
            yield Static("📈 Loading metrics...", id="status-message")

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self.load_metrics()

    def load_metrics(self) -> None:
        """Load metrics data in background."""
        self.run_worker(self._fetch_metrics(), exclusive=True)

    async def _fetch_metrics(self) -> None:
        """Fetch metrics from git repository."""
        try:
            # Get metrics (this runs in a worker thread)
            metrics = self.metrics_service.get_repository_metrics()

            # Update branch compliance
            branch_card = self.query_one("#branch_compliance", MetricsCard)
            branch_pct = metrics.branch_metrics.compliance_percentage
            branch_card.update_value(
                f"{branch_pct:.1f}% ({metrics.branch_metrics.valid_branches}/{metrics.branch_metrics.total_branches})",
                progress=branch_pct / 100.0,
            )

            # Update commit quality
            commit_card = self.query_one("#commit_quality", MetricsCard)
            commit_pct = metrics.commit_metrics.compliance_percentage
            commit_card.update_value(
                f"{commit_pct:.1f}% ({metrics.commit_metrics.valid_commits}/{metrics.commit_metrics.total_commits})",
                progress=commit_pct / 100.0,
            )

            # Update active branches
            branches_card = self.query_one("#active_branches", MetricsCard)
            branches_card.update_value(str(metrics.branch_metrics.total_branches))

            # Update status
            status = self.query_one("#status-message", Static)
            status.update("✓ Metrics loaded successfully")

        except Exception as e:
            status = self.query_one("#status-message", Static)
            status.update(f"✗ Error loading metrics: {e}")
