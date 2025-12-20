"""CLI commands for managing Functional Groups."""

from typing import Any, Callable, Dict

import toml
import typer
from rich.console import Console
from rich.table import Table

from devrules.config import find_config_file, load_config

console = Console()


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command("group-status")
    def status():
        """Show the status of all defined functional groups."""
        config = load_config()

        if not config.functional_groups:
            typer.secho("No functional groups defined in configuration.", fg=typer.colors.YELLOW)
            return

        table = Table(title="Functional Groups Status")
        table.add_column("Group", style="cyan")
        table.add_column("Base Branch", style="green")
        table.add_column("Integration Cursor", style="magenta")
        table.add_column("Environment", style="yellow")
        table.add_column("Next Merge Target", style="blue")

        for name, group in config.functional_groups.items():
            cursor_branch = "-"
            cursor_env = "-"
            target = group.base_branch

            if group.integration_cursor:
                cursor_branch = group.integration_cursor.branch
                cursor_env = group.integration_cursor.environment or "-"
                target = group.integration_cursor.branch

            table.add_row(name, group.base_branch, cursor_branch, cursor_env, target)

        console.print(table)

    @app.command("add-group")
    def add_group(
        name: str,
        base_branch: str = "develop",
        branch_pattern: str = "",
        description: str = "",
    ):
        """Add a new functional group to the configuration file."""
        config_path = find_config_file()
        if not config_path:
            typer.secho("Configuration file not found", fg="red")
            raise typer.Exit(1)

        # Load raw toml to preserve comments and structure as much as possible
        try:
            data = toml.load(config_path)
        except Exception as e:
            typer.secho(f"Error loading config file: {e}", fg="red")
            raise typer.Exit(1)

        # Ensure functional_groups section exists
        if "functional_groups" not in data:
            data["functional_groups"] = {}

        # Check if group already exists
        if name in data["functional_groups"]:
            typer.secho(f"Functional group '{name}' already exists in configuration.", fg="red")
            raise typer.Exit(1)

        # Add the new group
        data["functional_groups"][name] = {
            "description": description,
            "base_branch": base_branch,
            "branch_pattern": branch_pattern,
        }

        try:
            with open(config_path, "w") as f:
                toml.dump(data, f)
            typer.secho(
                f"[green]Added functional group '{name}' with base branch '{base_branch}'.[/green]"
            )
        except Exception as e:
            typer.secho(f"[red]Error writing to config file: {e}[/red]")
            raise typer.Exit(1)

    @app.command("set-cursor")
    def set_cursor(group_name: str, branch: str, environment: str = "dev"):
        """Update the integration cursor for a functional group."""
        config_path = find_config_file()
        if not config_path:
            typer.secho("Configuration file not found", fg="red")
            raise typer.Exit(1)

        # Load raw toml to preserve comments and structure as much as possible
        try:
            data = toml.load(config_path)
        except Exception as e:
            typer.secho(f"Error loading config file: {e}", fg="red")
            raise typer.Exit(1)

        if "functional_groups" not in data or group_name not in data["functional_groups"]:
            typer.secho(f"Functional group '{group_name}' not found in configuration.", fg="red")
            raise typer.Exit(1)

        # Update the cursor
        data["functional_groups"][group_name]["integration_cursor"] = {
            "branch": branch,
            "environment": environment,
        }

        try:
            with open(config_path, "w") as f:
                toml.dump(data, f)
            typer.secho(
                f"[green]Updated cursor for group '{group_name}' to '{branch}' ({environment}).[/green]"
            )
        except Exception as e:
            typer.secho(f"[red]Error writing to config file: {e}[/red]")
            raise typer.Exit(1)

    return {
        "groups-status": status,
        "add-group": add_group,
        "set-cursor": set_cursor,
    }
