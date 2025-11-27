"""Dashboard command for launching the TUI."""

from typing import Any, Callable, Dict, Optional

import typer


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
        try:
            from devrules.tui import DevRulesDashboard
        except ImportError:
            typer.secho(
                "✘ Dashboard requires the 'tui' dependency group.",
                fg=typer.colors.RED,
                bold=True,
            )
            typer.echo("\nInstall with:")
            typer.secho("  pip install devrules[tui]", fg=typer.colors.CYAN)
            typer.echo("\nOr if using uv:")
            typer.secho("  uv pip install devrules[tui]", fg=typer.colors.CYAN)
            raise typer.Exit(code=1)

        if DevRulesDashboard is None:
            typer.secho(
                "✘ Failed to load dashboard. Please reinstall with: pip install devrules[tui]",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        # Launch the TUI
        try:
            dashboard_app = DevRulesDashboard(config_file=config_file)
            dashboard_app.run()
        except Exception as e:
            typer.secho(f"✘ Dashboard error: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    return {"dashboard": dashboard}
