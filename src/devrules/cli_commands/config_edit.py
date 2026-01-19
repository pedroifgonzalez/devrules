"""CLI commands for editing configuration."""

from pathlib import Path
from typing import Any, Callable, Dict, Optional

import toml
import typer
from rich.console import Console
from rich.syntax import Syntax

from devrules.cli_commands.prompters.factory import get_default_prompter

prompter = get_default_prompter()
console = Console()


def _get_config_path() -> Path:
    """Get the path to the configuration file."""
    # Try to find .devrules.toml in current or parent directories
    current = Path.cwd()
    root = Path(current.anchor)
    while current != root:
        config_file = current / ".devrules.toml"
        if config_file.exists():
            return config_file
        current = current.parent

    # Check root as well
    config_file = root / ".devrules.toml"
    if config_file.exists():
        return config_file

    # Fallback to current directory for create/error
    return Path.cwd() / ".devrules.toml"


def _load_config(path: Path) -> Dict[str, Any]:
    """Load configuration from file."""
    if not path.exists():
        prompter.error(f"Configuration file not found: {path}")
        raise prompter.exit(code=1)

    try:
        return toml.load(path)  # type: ignore
    except Exception as e:
        prompter.error(f"Failed to parse configuration: {e}")
        raise prompter.exit(code=1)


def _save_config(path: Path, config: Dict[str, Any]) -> None:
    """Save configuration to file atomically."""
    import os
    import tempfile

    try:
        # Create temp file in same directory to ensure atomic move works across filesystems
        dir_path = path.parent
        with tempfile.NamedTemporaryFile("w", dir=dir_path, delete=False) as f:
            toml.dump(config, f)
            temp_path = Path(f.name)

        # Atomic replace
        os.replace(temp_path, path)
        prompter.success(f"Configuration saved to {path} (atomic)")
    except Exception as e:
        prompter.error(f"Failed to save configuration: {e}")
        # Build logic might leave a temp file if it crashes before replace, cleaning up tricky here without try/finally blocking
        # but for now this is much safer than partial write
        raise prompter.exit(code=1)


def _get_value(config: Dict[str, Any], path: str) -> Any:
    """Get value from nested dictionary using dot notation."""
    keys = path.split(".")
    current = config
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _set_value(config: Dict[str, Any], path: str, value: Any) -> None:
    """Set value in nested dictionary using dot notation."""
    keys = path.split(".")
    current = config
    for i, key in enumerate(keys[:-1]):
        if key not in current:
            current[key] = {}
        current = current[key]
        if not isinstance(current, dict):
            # Cannot traverse through non-dict
            raise ValueError(f"Key '{keys[i]}' is not a dictionary section")

    current[keys[-1]] = value


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    """Register configuration editing commands."""

    @app.command(name="config-get")
    def config_get(
        key_path: Optional[str] = typer.Argument(None, help="Key path (e.g. branch.pattern)"),
    ):
        """Get configuration value."""
        path = _get_config_path()
        config = _load_config(path)

        prompter.header("Get Configuration")

        if key_path:
            value = _get_value(config, key_path)
            if value is None:
                prompter.error(f"Key not found: {key_path}")
                raise prompter.exit(code=1)

            if isinstance(value, (dict, list)):
                # Pretty print complex structures
                import json

                prompter.info(f"Value for {key_path}:")
                console.print(json.dumps(value, indent=2))
            else:
                prompter.info(f"{key_path} = {value}")
        else:
            with open(path, "r") as f:
                syntax = Syntax(f.read(), "toml", theme="monokai", line_numbers=True)
                console.print(syntax)

    @app.command(name="config-set")
    def config_set(
        key_path: str = typer.Argument(..., help="Key path (e.g. branch.pattern)"),
        value: str = typer.Argument(..., help="New value"),
    ):
        """Set configuration value."""
        path = _get_config_path()
        config = _load_config(path)
        prompter.header("Set Configuration")

        # Type inference
        import json

        typed_value: Any = value

        # Try JSON parsing first for complex types (lists, dicts)
        try:
            typed_value = json.loads(value)
        except json.JSONDecodeError:
            # Fallback to simple inference
            if value.lower() == "true":
                typed_value = True
            elif value.lower() == "false":
                typed_value = False
            else:
                try:
                    typed_value = int(value)
                except ValueError:
                    try:
                        typed_value = float(value)
                    except ValueError:
                        typed_value = value

        old_value = _get_value(config, key_path)

        prompter.info(f"Path: {key_path}")
        prompter.info(f"Old Value: {old_value}")
        prompter.info(f"New Value: {typed_value} ({type(typed_value).__name__})")

        if prompter.confirm("Save changes?"):
            try:
                _set_value(config, key_path, typed_value)
                _save_config(path, config)
            except ValueError as e:
                prompter.error(str(e))
                raise prompter.exit(code=1)
        else:
            prompter.warning("Cancelled")

    @app.command(name="config-list")
    def config_list(section: Optional[str] = typer.Argument(None, help="Section to list")):
        """List configuration sections or keys."""
        path = _get_config_path()
        config = _load_config(path)

        target = config
        if section:
            target = _get_value(config, section)
            if target is None:
                prompter.error(f"Section not found: {section}")
                raise prompter.exit(code=1)

        if not isinstance(target, dict):
            prompter.error(f"'{section}' is a value, not a section. Use config-get to view it.")
            raise prompter.exit(code=1)

        prompter.header(f"Configuration List: {section if section else 'Root'}")

        # Display sections first
        sections = [k for k, v in target.items() if isinstance(v, dict)]
        if sections:
            prompter.print_styled("Sections:", bold=True, foreground=4)  # Blue
            for s in sorted(sections):
                prompter.indented_message(f"[{s}]")

        # Display values
        values = [k for k, v in target.items() if not isinstance(v, dict)]
        if values:
            if sections:
                print()  # Spacing
            prompter.print_styled("Values:", bold=True, foreground=2)  # Green
            max_len = max(len(k) for k in values) if values else 0
            for k in sorted(values):
                val = target[k]
                val_str = str(val)
                if len(val_str) > 50:
                    val_str = val_str[:47] + "..."
                prompter.indented_message(
                    f"{k.ljust(max_len + 2)} = {val_str}  ({type(val).__name__})"
                )

    @app.command(name="config-edit")
    def config_edit():
        """Interactive configuration editor."""
        path = _get_config_path()
        config = _load_config(path)

        current_path: list[str] = []
        prompter.header("Update Configuration")

        while True:
            # Navigate to current path
            current_dict = config
            for p in current_path:
                current_dict = current_dict[p]

            sections = sorted([k for k, v in current_dict.items() if isinstance(v, dict)])
            values = sorted([k for k, v in current_dict.items() if not isinstance(v, dict)])

            options = []
            option_map: Any = {}  # Map display string to key/action

            if current_path:
                back_opt = ".. (Back)"
                options.append(back_opt)
                option_map[back_opt] = "BACK"

            for s in sections:
                opt = f"[{s}]"
                options.append(opt)
                option_map[opt] = ("SECTION", s)

            for k in values:
                val = current_dict[k]
                opt = f"{k} = {val}"
                options.append(opt)
                option_map[opt] = ("VALUE", k)

            save_opt = "Save & Exit"
            cancel_opt = "Cancel & Exit"
            options.append(save_opt)
            options.append(cancel_opt)
            option_map[save_opt] = "SAVE"
            option_map[cancel_opt] = "CANCEL"

            selection = prompter.choose(options, "Select item to edit or navigate:", limit=1)

            if not selection:  # Cancelled
                return

            selection_str = selection if isinstance(selection, str) else selection[0]
            action = option_map.get(selection_str)

            if action == "CANCEL":
                prompter.warning("Exited without saving.")
                return

            if action == "SAVE":
                _save_config(path, config)
                return

            if action == "BACK":
                current_path.pop()
                continue

            if isinstance(action, tuple):
                act_type, target = action
                if act_type == "SECTION":
                    current_path.append(target)
                    continue

                if act_type == "VALUE":
                    key = target
                    current_val = current_dict[key]

                    new_val = None
                    if isinstance(current_val, bool):
                        # Toggle
                        options = ["True", "False"]
                        choice = prompter.choose(
                            options, f"Set {key} (Current: {current_val})", limit=1
                        )
                        if choice:
                            new_val = choice == "True" or (
                                isinstance(choice, list) and choice[0] == "True"
                            )
                    elif isinstance(current_val, list):
                        val_str = prompter.input_text(
                            "Edit list (comma separated)", default=",".join(map(str, current_val))
                        )
                        if val_str is not None:
                            new_val = [s.strip() for s in val_str.split(",")]
                    else:
                        # String/Int/Float
                        val_str = prompter.input_text(f"Edit {key}", default=str(current_val))
                        if val_str is not None:
                            # Type inference similar to config-set
                            if isinstance(current_val, int):
                                try:
                                    new_val = int(val_str)
                                except ValueError:
                                    prompter.error("Invalid integer")
                                    continue
                            elif isinstance(current_val, float):
                                try:
                                    new_val = float(val_str)
                                except ValueError:
                                    prompter.error("Invalid float")
                                    continue
                            else:
                                new_val = val_str

                    if new_val is not None:
                        current_dict[key] = new_val
                        prompter.success(f"Updated {key} to {new_val}")

    return {
        "config_get": config_get,
        "config_set": config_set,
        "config_list": config_list,
        "config_edit": config_edit,
    }
