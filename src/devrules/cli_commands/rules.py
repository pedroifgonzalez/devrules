"""Custom validation rules CLI commands."""

from typing import Any, Callable, Dict, Optional

import typer

from devrules.config import load_config
from devrules.core.rules_engine import RuleRegistry, discover_rules, execute_rule
from devrules.utils import gum
from devrules.utils.typer import add_typer_block_message


def _run_rule(name: str):
    typer.secho(f"Executing rule '{name}'...", fg=typer.colors.YELLOW)
    success, message = execute_rule(name)
    if success:
        typer.secho(f"Rule executed successfully: {message}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"Rule execution failed: {message}", fg=typer.colors.RED)


def _select_rule():
    custom_rules = RuleRegistry.list_rules()
    rule = custom_rules[0].name
    if gum.is_available():
        rule = gum.choose(
            options=[rule.name for rule in custom_rules],
            header="Select a rule to execute",
        )
    else:
        pass
    return rule


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.callback()
    def load_rules():
        """Load configured rules before any command runs."""
        config = load_config()
        discover_rules(config.custom_rules)

    @app.command()
    def list_rules():
        """List all available custom validation rules."""
        custom_rules = RuleRegistry.list_rules()
        if not custom_rules:
            typer.secho("No custom rules found.", fg=typer.colors.RED)
            return

        add_typer_block_message(
            header="Available Custom Rules:",
            subheader="",
            messages=[
                f"{pos}. {rule.name}: {rule.description}"
                for pos, rule in enumerate(custom_rules, 1)
            ],
            indent_block=True,
            use_separator=False,
        )

    @app.command()
    def run_rule(
        name: Optional[str] = typer.Option(None, help="Name of the rule to run"),
    ):
        """Run a specific custom rule."""
        if not name:
            name = _select_rule()
        if name:
            _run_rule(name)

    return {
        "list_rules": list_rules,
        "run_rule": run_rule,
    }
