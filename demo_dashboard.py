#!/usr/bin/env python
"""Demo script to launch the DevRules TUI dashboard."""

import sys

sys.path.insert(0, "src")

from devrules.tui.app import DevRulesDashboard

if __name__ == "__main__":
    app = DevRulesDashboard()
    app.run()
