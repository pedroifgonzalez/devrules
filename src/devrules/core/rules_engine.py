"""Core logic for discovering and executing custom validation rules."""

import importlib.util
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from devrules.config import CustomRulesConfig
from devrules.core.enum import DevRulesEvent

# Type alias for a rule function
# A rule function takes arbitrary kwargs and returns (bool, str)
RuleFunction = Callable[..., Tuple[bool, str]]


@dataclass
class RuleDefinition:
    """Definition of a registered rule."""

    name: str
    func: RuleFunction
    description: str = ""
    hooks: Optional[list[DevRulesEvent]] = None
    ignore_defaults: bool = False


class RuleRegistry:
    """Registry for custom validation rules."""

    _rules: Dict[str, RuleDefinition] = {}

    @classmethod
    def register(
        cls,
        name: str,
        description: str = "",
        hooks: Optional[list[DevRulesEvent]] = None,
        ignore_defaults: bool = False,
    ) -> Callable[[RuleFunction], RuleFunction]:
        """Decorator to register a function as a rule."""

        def decorator(func: RuleFunction) -> RuleFunction:
            if name in cls._rules:
                # We warn but don't stop, latest definition wins
                pass
            cls._rules[name] = RuleDefinition(
                name=name,
                func=func,
                description=description,
                hooks=hooks,
                ignore_defaults=ignore_defaults,
            )
            return func

        return decorator

    @classmethod
    def get_rule(cls, name: str) -> Optional[RuleDefinition]:
        """Get a rule by name."""
        return cls._rules.get(name)

    @classmethod
    def list_rules(cls) -> List[RuleDefinition]:
        """List all registered rules."""
        return sorted(cls._rules.values(), key=lambda r: r.name)

    @classmethod
    def clear(cls):
        """Clear registry (mostly for tests)."""
        cls._rules.clear()


# Public decorator alias
rule = RuleRegistry.register


def discover_rules(config: CustomRulesConfig):
    """Discover rules from configured paths and packages."""

    # 1. Load from paths
    for path_str in config.paths:
        path = Path(path_str).resolve()
        if not path.exists():
            print(f"Warning: Rule path does not exist: {path}")
            continue

        if path.is_file() and path.suffix == ".py":
            _load_file(path)
        elif path.is_dir():
            for py_file in path.glob("**/*.py"):
                if py_file.name.startswith("_"):
                    continue
                _load_file(py_file)

    # 2. Load from packages
    for package in config.packages:
        try:
            importlib.import_module(package)
        except ImportError as e:
            print(f"Warning: Could not import rule package '{package}': {e}")


def _load_file(path: Path):
    """Load a python file as a module to trigger decorators."""
    module_name = f"devrules_custom_{path.stem}"

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            print(f"Warning: Failed to load rule file '{path}': {e}")


def execute_rule(name: str, *args, **kwargs) -> Tuple[bool, str]:
    """Execute a specific rule by name."""
    definition = RuleRegistry.get_rule(name)
    if not definition:
        return False, f"Rule '{name}' not found."

    try:
        # Check if function expects specific arguments from kwargs
        sig = inspect.signature(definition.func)

        # Build arguments based on signature
        # We pass only what the function asks for from the available context
        call_args = {}
        positional_args = []

        # Process parameters in order
        list(sig.parameters.keys())
        arg_index = 0

        for param_name, param in sig.parameters.items():
            # Handle positional arguments first
            if arg_index < len(args) and param.kind in [
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ]:
                positional_args.append(args[arg_index])
                arg_index += 1
            # Handle keyword arguments
            elif param_name in kwargs:
                call_args[param_name] = kwargs[param_name]
            # Use default values if available
            elif param.default is not inspect.Parameter.empty:
                continue
            # Handle **kwargs parameter
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                call_args.update(kwargs)  # Pass remaining kwargs to **kwargs
                break
            # Handle *args parameter
            elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                # Pass remaining positional args to *args
                positional_args.extend(args[arg_index:])
                arg_index = len(args)  # Mark all args as consumed
            # Required parameter missing
            else:
                return False, f"Missing required argument: {param_name}"

        return definition.func(*positional_args, **call_args)
    except Exception as e:
        return False, f"Error executing rule '{name}': {e}"


def prompt_for_rule_arguments(rule_name: str) -> Dict[str, Any]:
    """Interactively prompt for rule arguments based on the rule's signature."""
    from devrules.cli_commands.prompters import Prompter
    from devrules.cli_commands.prompters.factory import get_default_prompter

    prompter: Prompter = get_default_prompter()

    rule = RuleRegistry.get_rule(rule_name)
    if not rule:
        return {}

    sig = inspect.signature(rule.func)
    kwargs = {}

    for param_name, param in sig.parameters.items():
        # Get type information for better prompting
        param_type = "string"
        if param.annotation != inspect.Parameter.empty:
            annotation = param.annotation
            type_name = getattr(annotation, "__name__", str(annotation))
            param_type = type_name.lower()

        # Prompt for the value
        param_default = None
        if param.default != inspect.Parameter.empty:
            param_default = param.default

        if rule.ignore_defaults and param.default != inspect.Parameter.empty:
            kwargs[param_name] = param.default
            continue

        prompt_text = f"Enter value for '{param_name}' ({param_type}):"
        value = prompter.input_text(
            prompt_text, default=str(param_default) if param_default is not None else None
        )

        if not value:
            prompter.error(f"No value provided for required argument '{param_name}'")
            return prompter.exit(1)

        kwargs[param_name] = value

    return kwargs
