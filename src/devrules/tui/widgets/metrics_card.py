"""Metrics card widget for displaying statistics."""

from textual.containers import Container
from textual.widgets import Label, ProgressBar, Static


class MetricsCard(Container):
    """A card widget displaying a metric with optional progress bar."""

    DEFAULT_CSS = """
    MetricsCard {
        height: auto;
        border: solid $primary;
        padding: 1 2;
        margin: 1 0;
        background: $surface;
    }

    MetricsCard .metric-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    MetricsCard .metric-value {
        text-style: bold;
        color: $success;
        content-align: center middle;
        height: 3;
    }

    MetricsCard .metric-description {
        color: $text-muted;
        text-style: italic;
        margin-top: 1;
    }

    MetricsCard ProgressBar {
        margin: 1 0;
    }
    """

    def __init__(
        self,
        title: str,
        value: str,
        description: str = "",
        metric_id: str = "",
        show_progress: bool = False,
        progress_value: float = 0.0,
    ):
        """Initialize the metrics card.

        Args:
            title: Card title
            value: Metric value to display
            description: Optional description
            metric_id: Optional ID for updating the metric
            show_progress: Whether to show a progress bar
            progress_value: Progress value (0.0 to 1.0)
        """
        super().__init__(id=metric_id or None)
        self.metric_title = title
        self.metric_value = value
        self.metric_description = description
        self.show_progress = show_progress
        self.progress_value = progress_value

    def compose(self):
        """Compose the card layout."""
        yield Label(self.metric_title, classes="metric-title")
        yield Static(self.metric_value, classes="metric-value")

        if self.show_progress:
            yield ProgressBar(total=100, show_eta=False)

        if self.metric_description:
            yield Label(self.metric_description, classes="metric-description")

    def update_value(self, value: str, progress: float | None = None) -> None:
        """Update the metric value.

        Args:
            value: New value to display
            progress: Optional progress value (0.0 to 1.0)
        """
        value_widget = self.query_one(".metric-value", Static)
        value_widget.update(value)

        if progress is not None and self.show_progress:
            progress_bar = self.query_one(ProgressBar)
            progress_bar.update(progress=progress * 100)
