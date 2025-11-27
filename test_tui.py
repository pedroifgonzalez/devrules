#!/usr/bin/env python
"""Quick test script to verify TUI dashboard works."""

import sys

sys.path.insert(0, "src")

try:
    from devrules.tui.app import DevRulesDashboard

    print("✓ Successfully imported DevRulesDashboard")

    # Create app instance
    app = DevRulesDashboard()
    print("✓ Successfully created dashboard instance")
    print(
        "\nDashboard is ready! Run with: PYTHONPATH=src ./.venv/bin/python -m devrules.cli dashboard"
    )

except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)
