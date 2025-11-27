"""Tests for TUI components."""

from devrules.tui.widgets.metrics_card import MetricsCard


def test_metrics_card_initialization():
    """Test that MetricsCard can be initialized."""
    card = MetricsCard(
        title="Test Metric", value="100%", description="Test description", metric_id="test_metric"
    )

    assert card.metric_title == "Test Metric"
    assert card.metric_value == "100%"
    assert card.metric_description == "Test description"
    assert card.id == "test_metric"


def test_metrics_card_with_progress():
    """Test MetricsCard with progress bar."""
    card = MetricsCard(
        title="Progress Metric",
        value="75%",
        description="Test",
        show_progress=True,
        progress_value=0.75,
    )

    assert card.show_progress is True
    assert card.progress_value == 0.75


def test_metrics_card_without_description():
    """Test MetricsCard without description."""
    card = MetricsCard(title="Simple Metric", value="42")

    assert card.metric_description == ""
