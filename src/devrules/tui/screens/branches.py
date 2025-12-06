"""Branches screen for exploring local branches."""

from textual.containers import Container, VerticalScroll
from textual.widgets import DataTable, Static

from devrules.tui.services.metrics_service import MetricsService


class BranchesScreen(Container):
    """Screen for exploring branches and their validation status."""

    def __init__(self, config_file: str | None = None):
        """Initialize branches screen.

        Args:
            config_file: Optional path to config file
        """
        super().__init__()
        self.config_file = config_file
        self.metrics_service = MetricsService(config_file)

    def compose(self):
        """Compose the branches screen layout."""
        yield Static("🌿 Branch Explorer", classes="screen-title")

        with VerticalScroll():
            yield DataTable(id="branches-table")
            yield Static("Loading branches...", id="branch-status")

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self.load_branches()

    def load_branches(self) -> None:
        """Load and display branch data."""
        try:
            table = self.query_one("#branches-table", DataTable)
            table.add_columns("Status", "Branch Name")

            metrics = self.metrics_service.analyze_branches()
            all_branches = self.metrics_service.get_all_branches()

            for branch in all_branches:
                is_valid = branch not in metrics.invalid_branch_names
                status = "✓" if is_valid else "✗"
                table.add_row(status, branch)

            # Update status
            status_widget = self.query_one("#branch-status", Static)
            status_widget.update(
                f"Showing {len(all_branches)} branches • "
                f"{metrics.valid_branches} valid • "
                f"{metrics.invalid_branches} invalid"
            )

        except Exception as e:
            status_widget = self.query_one("#branch-status", Static)
            status_widget.update(f"✗ Error loading branches: {e}")
