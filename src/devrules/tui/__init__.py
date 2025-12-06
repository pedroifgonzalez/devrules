"""TUI (Terminal User Interface) module for DevRules.

This module provides an interactive dashboard for visualizing metrics,
tracking issues, and exploring branches. It requires the 'tui' dependency
group to be installed:

    pip install devrules[tui]
"""

__all__ = ["DevRulesDashboard"]

try:
    from devrules.tui.app import DevRulesDashboard
except ImportError:
    # Textual not installed - this is fine, just means TUI features unavailable
    DevRulesDashboard = None  # type: ignore
