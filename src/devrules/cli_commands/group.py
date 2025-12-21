"""CLI commands for managing Functional Groups."""

from typing import Any, Callable, Dict, Iterable, Optional

import toml
import typer

from devrules.config import find_config_file, load_config
from devrules.utils import gum
from devrules.utils.typer import add_typer_block_message


def _build_group_data_with_gum(
    description: str,
    base_branch: str,
    branch_pattern: str,
) -> Optional[Dict[str, Any]]:
    """Build group data interactively using gum.

    Args:
        description: Default group description
        base_branch: Default base branch name
        branch_pattern: Default branch pattern

    Returns:
        Group data dictionary or None if cancelled
    """
    # Ask for description
    desc = gum.input_text(
        header="Group description",
        placeholder="e.g., Feature group for payments",
        default=description,
    )
    if desc is None:
        return None

    # Ask for base branch
    base = gum.input_text(
        header="Base branch",
        placeholder="e.g., develop, main",
        default=base_branch,
    )
    if not base:
        return None

    # Ask for branch pattern
    pattern = gum.input_text(
        header="Branch pattern (regex)",
        placeholder="e.g., feature/.* (leave empty for no pattern)",
        default=branch_pattern,
    )
    if pattern is None:
        pattern = ""

    group_data: Dict[str, Any] = {
        "description": desc,
        "base_branch": base,
        "branch_pattern": pattern,
    }

    add_cursor = gum.confirm("Do you want to set an integration cursor?", default=False)
    if add_cursor:
        branch = gum.input_text(
            header="Integration cursor branch",
            placeholder="e.g., feature/my-branch",
        )
        if not branch:
            return None

        env = gum.input_text(
            header="Integration cursor environment",
            placeholder="Environment name",
            default="dev",
        )
        if not env:
            env = "dev"

        group_data["integration_cursor"] = {
            "branch": branch,
            "environment": env,
        }

    return group_data


def _build_group_data_with_typer(
    description: str,
    base_branch: str,
    branch_pattern: str,
) -> Optional[Dict[str, Any]]:
    """Build group data interactively using typer prompts (fallback).

    Args:
        description: Default group description
        base_branch: Default base branch name
        branch_pattern: Default branch pattern

    Returns:
        Group data dictionary or None if cancelled
    """
    # Ask for description
    desc = typer.prompt("Group description", default=description or "")

    # Ask for base branch
    base = typer.prompt("Base branch", default=base_branch)

    # Ask for branch pattern
    pattern = typer.prompt("Branch pattern (regex, empty for none)", default=branch_pattern or "")

    group_data: Dict[str, Any] = {
        "description": desc,
        "base_branch": base,
        "branch_pattern": pattern,
    }

    add_cursor = typer.confirm("Do you want to set an integration cursor?", default=False)
    if add_cursor:
        branch = typer.prompt("Integration cursor branch")
        env = typer.prompt("Integration cursor environment", default="dev")

        group_data["integration_cursor"] = {
            "branch": branch,
            "environment": env,
        }

    return group_data


def build_group_data_interactive(
    description: str,
    base_branch: str,
    branch_pattern: str,
) -> Optional[Dict[str, Any]]:
    """Build group data interactively using gum or typer fallback.

    Args:
        description: Group description
        base_branch: Base branch name
        branch_pattern: Branch pattern

    Returns:
        Group data dictionary or None if cancelled
    """
    if gum.is_available():
        return _build_group_data_with_gum(description, base_branch, branch_pattern)
    else:
        return _build_group_data_with_typer(description, base_branch, branch_pattern)


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command("functional-group-status")
    def status():
        """Show the status of all defined functional groups."""
        config = load_config()

        if not config.functional_groups:
            typer.secho("No functional groups defined in configuration.", fg=typer.colors.YELLOW)
            return

        messages = []
        for name, group in config.functional_groups.items():
            cursor_env = "-"
            target = group.base_branch

            if group.integration_cursor:
                cursor_env = group.integration_cursor.environment or "-"
                target = group.integration_cursor.branch

            messages.append(f"📦 {name}")
            messages.append(f"   Base Branch:         {group.base_branch}")
            messages.append(f"   Environment:         {cursor_env}")
            messages.append(f"   Next Merge Target:   {target}")
            messages.append("")

        add_typer_block_message(
            header="📊 Functional Groups Status",
            subheader="",
            messages=messages,
            indent_block=False,
        )

    @app.command("add-functional-group")
    def add_group(
        name: str = "",
        base_branch: str = "develop",
        branch_pattern: str = "",
        description: str = "",
        integration_cursor_branch: str = "",
        integration_cursor_env: str = "",
        interactive: bool = True,
    ):
        """Add a new functional group to the configuration file."""
        # Prompt for name if not provided
        if not name:
            if gum.is_available():
                name = (
                    gum.input_text(
                        header="Group name",
                        placeholder="e.g., payments, auth, notifications",
                    )
                    or ""
                )
            else:
                name = typer.prompt("Group name")

        if not name:
            typer.secho("Group name is required.", fg="red")
            raise typer.Exit(1)

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

        # Build group data
        if integration_cursor_branch:
            # Use provided values directly
            group_data: Dict[str, Any] = {
                "description": description,
                "base_branch": base_branch,
                "branch_pattern": branch_pattern,
                "integration_cursor": {
                    "branch": integration_cursor_branch,
                    "environment": integration_cursor_env or "dev",
                },
            }
        elif interactive:
            # Build interactively
            group_data_result = build_group_data_interactive(
                description, base_branch, branch_pattern
            )
            if group_data_result is None:
                typer.secho("Operation cancelled.", fg=typer.colors.YELLOW)
                raise typer.Exit(0)
            group_data = group_data_result
        else:
            # Non-interactive without cursor
            group_data = {
                "description": description,
                "base_branch": base_branch,
                "branch_pattern": branch_pattern,
            }

        data["functional_groups"][name] = group_data

        try:
            with open(config_path, "w") as f:
                toml.dump(data, f)
            typer.secho(
                f"Added functional group '{name}' with base branch '{group_data['base_branch']}'", fg="green"
            )
        except Exception as e:
            typer.secho(f"Error writing to config file: {e}", fg="red")
            raise typer.Exit(1)

    @app.command("set-cursor")
    def set_cursor(
        group_name: str = typer.Argument(None, help="Functional group name"),
        branch: str = typer.Argument(None, help="Branch name for the cursor"),
        environment: str = typer.Option(None, "--env", "-e", help="Environment name"),
    ):
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

        # Handle interactive group selection
        if not group_name:
            if "functional_groups" not in data or not data["functional_groups"]:
                typer.secho(
                    "No functional groups defined in configuration.", fg=typer.colors.YELLOW
                )
                raise typer.Exit(0)

            group_names = list(data["functional_groups"].keys())
            if gum.is_available():
                group_name = gum.choose(group_names, header="Select functional group:")
                if isinstance(group_name, list):
                    group_name = group_name[0] if group_name else None
            else:
                add_typer_block_message(
                    header="🎯 Set Cursor",
                    subheader="📋 Select a functional group:",
                    messages=[f"{idx}. {g}" for idx, g in enumerate(group_names, 1)],
                )
                choice = typer.prompt("Enter number", type=int)
                if 1 <= choice <= len(group_names):
                    group_name = group_names[choice - 1]

        if not group_name:
            typer.secho("Group name is required.", fg="red")
            raise typer.Exit(1)

        if "functional_groups" not in data or group_name not in data["functional_groups"]:
            typer.secho(f"Functional group '{group_name}' not found in configuration.", fg="red")
            raise typer.Exit(1)

        # Handle interactive branch input
        if not branch:
            if gum.is_available():
                branch = gum.input_text(
                    header="Cursor branch",
                    placeholder="e.g., feature/latest-stable",
                    default=data["functional_groups"][group_name]
                    .get("integration_cursor", {})
                    .get("branch", ""),
                )
            else:
                branch = typer.prompt("Cursor branch")

        if not branch:
            typer.secho("Branch name is required.", fg="red")
            raise typer.Exit(1)

        # Determine default environment from configuration
        current_env = (
            data["functional_groups"][group_name]
            .get("integration_cursor", {})
            .get("environment", "dev")
        )

        # Handle interactive environment input if not provided
        if not environment:
            if gum.is_available():
                environment = gum.input_text(
                    header="Integration cursor environment",
                    placeholder="Environment name",
                    default=current_env,
                )
            else:
                environment = typer.prompt("Integration cursor environment", default=current_env)

        if not environment:
            environment = current_env

        # Update the cursor
        data["functional_groups"][group_name]["integration_cursor"] = {
            "branch": branch,
            "environment": environment,
        }

        try:
            with open(config_path, "w") as f:
                toml.dump(data, f)
            typer.secho(
                f"Updated cursor for group '{group_name}' to '{branch}' ({environment}).",
                fg="green",
            )
        except Exception as e:
            typer.secho(f"Error writing to config file: {e}", fg="red")
            raise typer.Exit(1)

    @app.command("remove-functional-group")
    def remove_functional_group(
        name: str = typer.Argument("", help="Name of the functional group to remove"),
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    ):
        """Remove a functional group and its integration cursor from the configuration."""
        # Prompt for name if not provided
        if not name:
            config = load_config()
            if not config.functional_groups:
                typer.secho(
                    "No functional groups defined in configuration.", fg=typer.colors.YELLOW
                )
                raise typer.Exit(0)

            group_names = list(config.functional_groups.keys())
            if gum.is_available():
                name = gum.choose(group_names, header="Select group to remove:") or ""
                if isinstance(name, list):
                    name = name[0] if name else ""
            else:
                add_typer_block_message(
                    header="🗑 Remove Functional Group",
                    subheader="📋 Select a group to remove:",
                    messages=[f"{idx}. {g}" for idx, g in enumerate(group_names, 1)],
                )
                choice = typer.prompt("Enter number", type=int)
                if 1 <= choice <= len(group_names):
                    name = group_names[choice - 1]

        if not name:
            typer.secho("Group name is required.", fg="red")
            raise typer.Exit(1)

        config_path = find_config_file()
        if not config_path:
            typer.secho("Configuration file not found", fg="red")
            raise typer.Exit(1)

        try:
            data = toml.load(config_path)
        except Exception as e:
            typer.secho(f"Error loading config file: {e}", fg="red")
            raise typer.Exit(1)

        if "functional_groups" not in data or name not in data["functional_groups"]:
            typer.secho(f"Functional group '{name}' not found in configuration.", fg="red")
            raise typer.Exit(1)

        # Confirm deletion
        if not force:
            if gum.is_available():
                confirmed = gum.confirm(f"Remove functional group '{name}'?", default=False)
            else:
                confirmed = typer.confirm(f"Remove functional group '{name}'?", default=False)

            if not confirmed:
                typer.secho("Operation cancelled.", fg=typer.colors.YELLOW)
                raise typer.Exit(0)

        # Remove the group
        del data["functional_groups"][name]

        try:
            with open(config_path, "w") as f:
                toml.dump(data, f)
            typer.secho(f"Removed functional group '{name}'.", fg="green")
        except Exception as e:
            typer.secho(f"Error writing to config file: {e}", fg="red")
            raise typer.Exit(1)

    @app.command("clear-functional-groups")
    def clear_functional_groups(
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    ):
        """Remove all functional groups and their integration cursors from the configuration."""
        config_path = find_config_file()
        if not config_path:
            typer.secho("Configuration file not found", fg="red")
            raise typer.Exit(1)

        try:
            data = toml.load(config_path)
        except Exception as e:
            typer.secho(f"Error loading config file: {e}", fg="red")
            raise typer.Exit(1)

        if "functional_groups" not in data or not data["functional_groups"]:
            typer.secho("No functional groups defined in configuration.", fg=typer.colors.YELLOW)
            raise typer.Exit(0)

        group_count = len(data["functional_groups"])

        # Confirm deletion
        if not force:
            if gum.is_available():
                confirmed = gum.confirm(
                    f"Remove all {group_count} functional group(s)?", default=False
                )
            else:
                confirmed = typer.confirm(
                    f"Remove all {group_count} functional group(s)?", default=False
                )

            if not confirmed:
                typer.secho("Operation cancelled.", fg=typer.colors.YELLOW)
                raise typer.Exit(0)

        # Clear all groups
        data["functional_groups"] = {}

        try:
            with open(config_path, "w") as f:
                toml.dump(data, f)
            typer.secho(f"Removed {group_count} functional group(s).", fg="green")
        except Exception as e:
            typer.secho(f"Error writing to config file: {e}", fg="red")
            raise typer.Exit(1)

    @app.command("sync-cursor")
    def sync_cursor(
        group_name: str = typer.Argument(None, help="Functional group name (inferred if omitted)"),
        dry_run: bool = typer.Option(
            False, "--dry-run", help="Show commands without executing them"
        ),
    ):
        """Sync base branch and update integration cursor (interactive)."""
        import re
        import subprocess

        from devrules.core.git_service import ensure_git_repo, get_current_branch

        ensure_git_repo()
        current_branch = get_current_branch()
        config = load_config()

        if not config.functional_groups:
            typer.secho("No functional groups defined.", fg=typer.colors.RED)
            raise typer.Exit(1)

        # 1. Determine Functional Group
        selected_group_name = group_name
        selected_group = None

        if selected_group_name:
            if selected_group_name not in config.functional_groups:
                typer.secho(f"Group '{selected_group_name}' not found.", fg=typer.colors.RED)
                raise typer.Exit(1)
            selected_group = config.functional_groups[selected_group_name]
        else:
            # Try to infer from current branch
            matches = []
            for name, data in config.functional_groups.items():
                pattern = data.branch_pattern
                if pattern and re.match(pattern, current_branch):
                    matches.append(name)

            if len(matches) == 1:
                selected_group_name = matches[0]
                typer.secho(f"ℹ Inferred group: {selected_group_name}", fg=typer.colors.BLUE)
                selected_group = config.functional_groups[selected_group_name]
            else:
                # Ambiguous or no match, ask user
                group_list = list(config.functional_groups.keys())
                if gum.is_available():
                    selected_group_name = gum.choose(
                        group_list, header="Select functional group to sync:"
                    )
                    if isinstance(selected_group_name, list):
                        selected_group_name = (
                            selected_group_name[0] if selected_group_name else None
                        )
                else:
                    typer.secho("Could not infer group. Please select one:", fg=typer.colors.YELLOW)
                    for idx, g in enumerate(group_list, 1):
                        typer.echo(f"{idx}. {g}")
                    choice = typer.prompt("Enter number", type=int)
                    if 1 <= choice <= len(group_list):
                        selected_group_name = group_list[choice - 1]

                if not selected_group_name:
                    typer.secho("No group selected.", fg=typer.colors.RED)
                    raise typer.Exit(1)
                selected_group = config.functional_groups[selected_group_name]

        # 2. Get configuration
        base_branch = selected_group.base_branch
        cursor_config = selected_group.integration_cursor

        if not cursor_config or not cursor_config.branch:
            typer.secho(
                f"No integration cursor defined for group '{selected_group_name}'.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

        cursor_branch = cursor_config.branch
        typer.secho(
            f"\n🚀 Syncing workflow for '{selected_group_name}'", fg=typer.colors.GREEN, bold=True
        )
        typer.echo(f"  Base Branch: {base_branch}")
        typer.echo(f"  Cursor Branch: {cursor_branch}")
        typer.echo("")

        def run_step(description: str, command: list[str], check: bool = True):
            if gum.is_available():
                should_run = gum.confirm(f"Do you want to {description}?", default=True)
            else:
                should_run = typer.confirm(f"Do you want to {description}?", default=True)

            if not should_run:
                typer.secho("Skipping...", fg=typer.colors.YELLOW)
                return False

            cmd_str = " ".join(command)
            typer.secho(f"Running: {cmd_str}", fg=typer.colors.BLUE)

            if dry_run:
                return True

            try:
                subprocess.run(command, check=check)
                typer.secho("✔ Done", fg=typer.colors.GREEN)
                return True
            except subprocess.CalledProcessError as e:
                typer.secho(f"✘ Command failed: {e}", fg=typer.colors.RED)
                raise typer.Exit(1)

        run_step(f"checkout base branch '{base_branch}'", ["git", "checkout", base_branch])
        run_step(f"pull latest changes for '{base_branch}'", ["git", "pull", "origin", base_branch])
        run_step(f"merge changes from '{current_branch}'", ["git", "merge", "--no-ff", current_branch])
        run_step(f"push '{base_branch}' to origin", ["git", "push", "origin", base_branch])
        run_step(
            f"checkout integration cursor '{cursor_branch}'", ["git", "checkout", cursor_branch]
        )
        run_step(f"pull latest changes for '{cursor_branch}'", ["git", "pull", "origin", cursor_branch])
        run_step(f"merge changes from '{base_branch}' into '{cursor_branch}'", ["git", "merge", "--no-ff", base_branch])

        typer.secho("\n✨ Sync workflow completed!", fg=typer.colors.GREEN, bold=True)

        # Optional: Switch back to original branch? User didn't ask for it, but it's polite.
        # "Assume that i have a branch created on..."
        # I'll ask.
        if current_branch != base_branch and current_branch != cursor_branch:
            if gum.is_available():
                switch_back = gum.confirm(
                    f"Switch back to original branch '{current_branch}'?", default=True
                )
            else:
                switch_back = typer.confirm(
                    f"Switch back to original branch '{current_branch}'?", default=True
                )

            if switch_back:
                subprocess.run(["git", "checkout", current_branch], check=False)

    return {
        "functional_group_status": status,
        "add_functional_group": add_group,
        "set_cursor": set_cursor,
        "remove_functional_group": remove_functional_group,
        "clear_functional_groups": clear_functional_groups,
        "sync_cursor": sync_cursor,
    }
