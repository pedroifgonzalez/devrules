"""Custom validation rules CLI commands."""

import typer
from rich.console import Console
from rich.table import Table

from devrules.config import load_config
from devrules.core.rules_engine import RuleRegistry, discover_rules, execute_rule

console = Console()
rules_app = typer.Typer(help="Manage and run custom validation rules.")


def register(app: typer.Typer):
    """Register the rules command group with the main application."""
    app.add_typer(rules_app, name="rules")
    return {"rules": rules_app}


@rules_app.callback()
def load_rules():
    """Load configured rules before any command runs."""
    config = load_config()
    discover_rules(config.custom_rules)


@rules_app.command("list")
def list_rules():
    """List all available custom validation rules."""
    rules = RuleRegistry.list_rules()

    if not rules:
        console.print("[yellow]No custom rules found.[/yellow]")
        console.print(
            "Configure [bold]custom_rules.paths[/bold] or [bold]custom_rules.packages[/bold] in your config file."
        )
        return

    table = Table(title="Available Custom Rules")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")

    for rule in rules:
        table.add_row(rule.name, rule.description or "-")

    console.print(table)


@rules_app.command("run")
def run_rule(
    name: str = typer.Argument(..., help="Name of the rule to run"),
):
    """Run a specific custom rule."""
    # Note: For now, we don't pass any context arguments from CLI.
    # In the future, we could add flags or automatic context injection (like git repo state).

    console.print(f"Running rule: [bold]{name}[/bold]...")

    success, message = execute_rule(name)

    if success:
        console.print(f"[green]✔ PASSED:[/green] {message}")
    else:
        console.print(f"[red]✘ FAILED:[/red] {message}")
        raise typer.Exit(code=1)
