"""Custom validation rules CLI commands."""

import inspect
from typing import Any, Callable, Dict, Optional

import typer

from devrules.cli_commands.prompters import Prompter
from devrules.cli_commands.prompters.factory import get_default_prompter
from devrules.config import load_config
from devrules.core.rules_engine import RuleDefinition, RuleRegistry, discover_rules, execute_rule
from devrules.utils.typer import add_typer_block_message

prompter: Prompter = get_default_prompter()


def _get_custom_rules() -> list[RuleDefinition]:
    """Get the list of custom rules.

    Returns:
        List of RuleDefinition objects.

    Raises:
        typer.Exit: If no rules are found.
    """
    custom_rules = RuleRegistry.list_rules()
    if not custom_rules:
        prompter.error("No custom rules found.")
        return prompter.exit(1)
    return custom_rules


def _format_rule_arguments(rule: RuleDefinition) -> Optional[str]:
    """Format the arguments information for a rule."""
    sig = inspect.signature(rule.func)
    params = []

    for param_name, param in sig.parameters.items():
        if param_name == "kwargs":
            continue

        param_str = param_name

        # Add type annotation if available
        if param.annotation != inspect.Parameter.empty:
            param_str += f": {param.annotation.__name__}"

        # Add default value if available
        if param.default != inspect.Parameter.empty:
            param_str += f" = {param.default}"

        params.append(param_str)

    if params:
        return "\n".join(f"  - {param}" for param in params)

    return None


def _prompt_for_rule_arguments(rule_name: str) -> Dict[str, Any]:
    """Interactively prompt for rule arguments based on the rule's signature."""
    rule = RuleRegistry.get_rule(rule_name)
    if not rule:
        return {}

    sig = inspect.signature(rule.func)
    kwargs = {}

    for param_name, param in sig.parameters.items():
        # Get type information for better prompting
        param_type = "string"
        if param.annotation != inspect.Parameter.empty:
            param_type = param.annotation.__name__.lower()

        # Prompt for the value
        param_default = None
        if param.default != inspect.Parameter.empty:
            param_default = param.default

        prompt_text = f"Enter value for '{param_name}' ({param_type}):"
        value = prompter.input_text(
            prompt_text, default=str(param_default) if param_default else None
        )

        if not value:
            prompter.error(f"No value provided for required argument '{param_name}'")
            return prompter.exit(1)

        kwargs[param_name] = value

    return kwargs


def _run_rule(rule: Optional[str] = None, *args, **kwargs):
    """Execute a custom rule.

    Args:
        rule: The name of the rule to execute.
        *args: Positional arguments for the rule.
        **kwargs: Keyword arguments for the rule.
    """
    if not rule:
        rule = _select_rule()

    # If no arguments provided (both positional and keyword), prompt for required ones interactively
    if not args and not kwargs:
        prompted_args = _prompt_for_rule_arguments(rule)
        kwargs.update(prompted_args)

    prompter.info(f"Executing rule '{rule}'...")
    success, message = execute_rule(rule, *args, **kwargs)
    if success:
        prompter.success(f"Rule executed successfully: {message}")
    else:
        prompter.error(f"Rule execution failed: {message}")


def _select_rule() -> str:
    """Interactively select a custom rule.

    Returns:
        The name of the selected rule.

    Raises:
        typer.Exit: If no rule is selected or multiple are selected.
    """
    custom_rules = _get_custom_rules()
    rule = prompter.choose(
        options=[rule.name for rule in custom_rules],
        header="Select a rule:",
    )
    if rule is None:
        prompter.error("No selected rule")
        return prompter.exit(1)
    elif isinstance(rule, str):
        return rule
    prompter.error("Multiple rules selected")
    return prompter.exit(1)


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    """Register custom rules commands.

    Args:
        app: Typer application instance.

    Returns:
        Dictionary mapping command names to their functions.
    """

    @app.callback()
    def load_rules():
        """Load configured rules before any command runs."""
        config = load_config()
        discover_rules(config.custom_rules)

    @app.command()
    def list_rules():
        """List all available custom validation rules."""
        custom_rules = _get_custom_rules()

        messages = []
        rules_and_descriptions = [f"{rule.name}: {rule.description}" for rule in custom_rules]
        rules_arguments = [_format_rule_arguments(rule) for rule in custom_rules]

        for rule_description, args in zip(rules_and_descriptions, rules_arguments):
            messages.append(rule_description)
            if args:
                messages.append("Arguments:")
                messages.append(args)
            else:
                messages.append("No arguments required")
            messages.append("")

        add_typer_block_message(
            header="Available Custom Rules:",
            subheader="",
            messages=messages,
            indent_block=True,
            use_separator=False,
        )

    @app.command()
    def run_rule(
        name: Optional[str] = typer.Option(None, help="Name of the rule to run"),
        args: Optional[str] = typer.Option(
            None, help="Positional arguments to pass to the rule (comma-separated)"
        ),
        kwargs: Optional[str] = typer.Option(
            None, help="Arguments to pass to the rule (format: key=value,key2=value2)"
        ),
    ):
        """Run a specific custom rule."""
        if not name:
            name = _select_rule()

        positional_args_list = []
        if args:
            for arg in args.split(","):
                arg = arg.strip()
                positional_args_list.append(arg)

        last_kwargs = {}
        if kwargs:
            for arg_pair in kwargs.split(","):
                if "=" not in arg_pair:
                    prompter.error(f"Invalid argument format: {arg_pair}. Use key=value format.")
                    return prompter.exit(1)
                key, value = arg_pair.split("=", 1)
                last_kwargs[key.strip()] = value.strip()

        _run_rule(name, *positional_args_list, **last_kwargs)

    return {
        "list_rules": list_rules,
        "run_rule": run_rule,
    }
