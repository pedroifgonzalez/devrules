"""Dashboard command for launching the TUI."""

from typing import Any, Callable, Dict, Optional

import typer

from devrules.cli_commands.prompters.factory import get_default_prompter

prompter = get_default_prompter()


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    """Register dashboard command.

    Args:
        app: Typer application instance

    Returns:
        Dictionary mapping command names to their functions
    """

    @app.command()
    def dashboard(
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to config file"
        ),
    ):
        """Launch interactive TUI dashboard for metrics and issue tracking.

        The dashboard provides:
        - Metrics visualization (branch compliance, commit quality)
        - GitHub/GitLab issue tracking
        - Branch explorer with validation status

        Requires: pip install devrules[tui]
        """
        prompter.header("Show dashboard")
        try:
            from devrules.tui import DevRulesDashboard
        except ImportError:
            prompter.error(
                "Dashboard requires the 'tui' dependency group.",
            )
            prompter.info("Install with:")
            prompter.indented_message("pip install devrules[tui]")
            prompter.info("Or if using uv:")
            prompter.indented_message("uv pip install devrules[tui]")
            raise prompter.exit(code=1)

        if DevRulesDashboard is None:
            prompter.error(
                "Failed to load dashboard. Please reinstall with: pip install devrules[tui]",
            )
            raise prompter.exit(code=1)

        # Launch the TUI
        try:
            dashboard_app = DevRulesDashboard(config_file=config_file)
            dashboard_app.run()
        except Exception as e:
            prompter.error(f"Dashboard error: {e}")
            raise prompter.exit(code=1)

    return {"dashboard": dashboard}
