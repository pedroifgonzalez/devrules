"""Main Textual application for DevRules dashboard."""

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, TabbedContent, TabPane

from devrules.tui.screens.branches import BranchesScreen
from devrules.tui.screens.dashboard import DashboardScreen
from devrules.tui.screens.issues import IssuesScreen


class DevRulesDashboard(App):
    """DevRules TUI Dashboard Application."""

    CSS = """
    Screen {
        background: $surface;
    }

    Header {
        background: $primary;
    }

    Footer {
        background: $panel;
    }

    TabbedContent {
        height: 1fr;
    }

    TabPane {
        padding: 1 2;
    }

    .screen-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
        text-align: center;
    }

    #filter-controls {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        background: $panel;
    }

    #issue-status, #branch-status, #status-message {
        margin-top: 1;
        padding: 1;
        background: $panel;
        color: $text-muted;
    }

    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
        ("r", "refresh", "Refresh Data"),
        ("?", "help", "Help"),
        ("h", "help", "Help"),
    ]

    def __init__(self, config_file: str | None = None):
        """Initialize the dashboard.

        Args:
            config_file: Optional path to config file
        """
        super().__init__()
        self.config_file = config_file
        self.title = "DevRules Dashboard"
        self.sub_title = "Development Guidelines Monitor"

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield Header()
        with TabbedContent(initial="dashboard", id="tabs"):
            with TabPane("Dashboard", id="dashboard"):
                yield DashboardScreen(config_file=self.config_file)
            with TabPane("Issues", id="issues"):
                yield IssuesScreen(config_file=self.config_file)
            with TabPane("Branches", id="branches"):
                yield BranchesScreen(config_file=self.config_file)
        yield Footer()

    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.dark = not self.dark  # type: ignore
        self.notify("Dark mode " + ("enabled" if self.dark else "disabled"), timeout=1)

    def action_refresh(self) -> None:
        """Refresh all data."""
        self.notify("Refreshing data...", title="Refresh")

        # Get the active tab and refresh its content
        tabs = self.query_one("#tabs", TabbedContent)
        active_pane = tabs.active

        if active_pane == "dashboard":
            screen = self.query_one(DashboardScreen)
            screen.load_metrics()
        elif active_pane == "issues":
            screen = self.query_one(IssuesScreen)
            screen.load_issues()
        elif active_pane == "branches":
            screen = self.query_one(BranchesScreen)
            screen.load_branches()

        self.notify("Data refreshed!", title="Refresh", timeout=2)

    def action_help(self) -> None:
        """Show help screen."""
        help_text = """
# DevRules Dashboard - Keyboard Shortcuts

## Navigation
- `Tab` / `Shift+Tab` - Switch between tabs
- `↑` `↓` `←` `→` - Navigate tables and lists
- `Enter` - Select item (where applicable)

## Actions
- `r` - Refresh current tab data
- `d` - Toggle dark/light mode
- `?` or `h` - Show this help screen
- `q` - Quit dashboard

## Tabs
1. **Dashboard** - View metrics and compliance statistics
2. **Issues** - Browse GitHub issues and branch status
3. **Branches** - Explore local branches and validation

## Tips
- Set `GH_TOKEN` environment variable for issue tracking
- Use filters in Issues tab to find specific issues
- Press `r` to refresh data after making changes

Press any key to close this help screen.
"""
        self.notify(help_text, title="Help", timeout=30)
