"""Custom validation rules CLI commands."""

from typing import Any, Callable, Dict, Optional

import typer

from devrules.cli_commands.prompters import Prompter
from devrules.cli_commands.prompters.factory import get_default_prompter
from devrules.config import load_config
from devrules.core.rules_engine import RuleDefinition, RuleRegistry, discover_rules, execute_rule
from devrules.utils.typer import add_typer_block_message

prompter: Prompter = get_default_prompter()


def _get_custom_rules() -> list[RuleDefinition]:
    custom_rules = RuleRegistry.list_rules()
    if not custom_rules:
        prompter.error("No custom rules found.")
        return prompter.exit(1)
    return custom_rules


def _run_rule(rule: Optional[str] = None):
    if not rule:
        rule = _select_rule()
    prompter.info(f"Executing rule '{rule}'...")
    success, message = execute_rule(rule)
    if success:
        prompter.success(f"Rule executed successfully: {message}")
    else:
        prompter.error(f"Rule execution failed: {message}")


def _select_rule() -> str:
    custom_rules = _get_custom_rules()
    rule = prompter.choose(
        options=[rule.name for rule in custom_rules],
        header="Select a rule to execute",
    )
    if rule is None:
        prompter.error("No selected rule")
        return prompter.exit(1)
    elif isinstance(rule, str):
        return rule
    prompter.error("Multiple rules selected")
    return prompter.exit(1)


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.callback()
    def load_rules():
        """Load configured rules before any command runs."""
        config = load_config()
        discover_rules(config.custom_rules)

    @app.command()
    def list_rules():
        """List all available custom validation rules."""
        custom_rules = _get_custom_rules()
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
        _run_rule(name)

    return {
        "list_rules": list_rules,
        "run_rule": run_rule,
    }
