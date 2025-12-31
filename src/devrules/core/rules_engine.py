"""Core logic for discovering and executing custom validation rules."""

import importlib.util
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from devrules.config import CustomRulesConfig

# Type alias for a rule function
# A rule function takes arbitrary kwargs and returns (bool, str)
RuleFunction = Callable[..., Tuple[bool, str]]


@dataclass
class RuleDefinition:
    """Definition of a registered rule."""

    name: str
    func: RuleFunction
    description: str = ""


class RuleRegistry:
    """Registry for custom validation rules."""

    _rules: Dict[str, RuleDefinition] = {}

    @classmethod
    def register(cls, name: str, description: str = "") -> Callable[[RuleFunction], RuleFunction]:
        """Decorator to register a function as a rule."""

        def decorator(func: RuleFunction) -> RuleFunction:
            if name in cls._rules:
                # We warn but don't stop, latest definition wins
                pass
            cls._rules[name] = RuleDefinition(name=name, func=func, description=description)
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


def execute_rule(name: str, **kwargs) -> Tuple[bool, str]:
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
        for param_name in sig.parameters:
            if param_name in kwargs:
                call_args[param_name] = kwargs[param_name]
            elif sig.parameters[param_name].default is not inspect.Parameter.empty:
                continue  # Use default
            elif sig.parameters[param_name].kind == inspect.Parameter.VAR_KEYWORD:
                call_args.update(kwargs)  # Pass everything to **kwargs
                break

        return definition.func(**call_args)
    except Exception as e:
        return False, f"Error executing rule '{name}': {e}"
