"""CLI commands for managing Functional Groups."""

from typing import Any, Callable, Dict, Optional

import toml
import typer

from devrules.cli_commands.prompters.factory import get_default_prompter
from devrules.config import find_config_file, load_config
from devrules.core.git_service import get_current_branch
from devrules.utils.decorators import ensure_git_repo
from devrules.utils.typer import add_typer_block_message

prompter = get_default_prompter()


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
    # Ask for description
    desc = prompter.input_text(
        header="Group description",
        placeholder="e.g., Feature group for payments",
        default=description,
    )
    if desc is None:
        return None

    # Ask for base branch
    base = prompter.input_text(
        header="Base branch",
        placeholder="e.g., develop, main",
        default=base_branch,
    )
    if not base:
        return None

    # Ask for branch pattern
    pattern = prompter.input_text(
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

    add_cursor = prompter.confirm("Do you want to set an integration cursor?", default=False)
    if add_cursor:
        branch = prompter.input_text(
            header="Integration cursor branch",
            placeholder="e.g., feature/my-branch",
        )
        if not branch:
            return None

        env = prompter.input_text(
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


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    """Register functional group commands.

    Args:
        app: Typer application instance.

    Returns:
        Dictionary mapping command names to their functions.
    """

    @app.command("functional-group-status")
    def status():
        """Show the status of all defined functional groups."""
        prompter.header("Show functional group status")
        config = load_config()

        if not config.functional_groups:
            prompter.warning("No functional groups defined in configuration.")
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
        prompter.header("Add functional group")
        # Prompt for name if not provided
        if not name:
            name = (
                prompter.input_text(
                    header="Group name",
                    placeholder="e.g., payments, auth, notifications",
                )
                or ""
            )

        if not name:
            prompter.error("Group name is required.")
            raise prompter.exit(code=1)

        config_path = find_config_file()
        if not config_path:
            prompter.error("Configuration file not found")
            raise prompter.exit(code=1)

        # Load raw toml to preserve comments and structure as much as possible
        try:
            data = toml.load(config_path)
        except Exception as e:
            prompter.error(f"Error loading config file: {e}")
            raise prompter.exit(code=1)

        # Ensure functional_groups section exists
        if "functional_groups" not in data:
            data["functional_groups"] = {}

        # Check if group already exists
        if name in data["functional_groups"]:
            prompter.error(f"Functional group '{name}' already exists in configuration.")
            raise prompter.exit(code=1)

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
                prompter.error("Operation cancelled.")
                raise prompter.exit(code=0)
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
            prompter.success(
                f"Added functional group '{name}' with base branch '{group_data['base_branch']}'",
            )
        except Exception as e:
            prompter.error(f"Error writing to config file: {e}")
            raise prompter.exit(code=1)

    @app.command("set-cursor")
    def set_cursor(
        group_name: str = typer.Argument(None, help="Functional group name"),
        branch: str = typer.Argument(None, help="Branch name for the cursor"),
        environment: str = typer.Option(None, "--env", "-e", help="Environment name"),
    ):
        """Update the integration cursor for a functional group."""
        prompter.header("Update functional group cursor")
        config_path = find_config_file()
        if not config_path:
            prompter.error("Configuration file not found")
            raise prompter.exit(code=1)

        # Load raw toml to preserve comments and structure as much as possible
        try:
            data = toml.load(config_path)
        except Exception as e:
            prompter.error(f"Error loading config file: {e}")
            raise prompter.exit(code=1)

        # Handle interactive group selection
        if not group_name:
            if "functional_groups" not in data or not data["functional_groups"]:
                prompter.warning("No functional groups defined in configuration.")
                raise prompter.exit(code=0)

            group_names = list(data["functional_groups"].keys())
            # TODO: fix
            group_name = prompter.choose(group_names, header="Select functional group:")  # type: ignore

        if not group_name or not isinstance(group_name, str):
            prompter.error("Group name is required.")
            raise prompter.exit(code=1)

        if "functional_groups" not in data or group_name not in data["functional_groups"]:
            prompter.error(f"Functional group '{group_name}' not found in configuration.")
            raise prompter.exit(code=1)

        # Handle interactive branch input
        if not branch:
            branch = (
                prompter.input_text(
                    header="Cursor branch",
                    placeholder="e.g., feature/latest-stable",
                    default=data["functional_groups"][group_name]
                    .get("integration_cursor", {})
                    .get("branch", ""),
                )
                or ""
            )

        if not branch:
            prompter.error("Branch name is required.")
            raise prompter.exit(code=1)

        # Determine default environment from configuration
        current_env = (
            data["functional_groups"][group_name]
            .get("integration_cursor", {})
            .get("environment", "dev")
        )

        # Handle interactive environment input if not provided
        if not environment:
            environment = (
                prompter.input_text(
                    header="Integration cursor environment",
                    placeholder="Environment name",
                    default=current_env,
                )
                or ""
            )

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
            prompter.success(
                f"Updated cursor for group '{group_name}' to '{branch}' ({environment}).",
            )
        except Exception as e:
            prompter.error(f"Error writing to config file: {e}")
            raise prompter.exit(code=1)

    @app.command("remove-functional-group")
    def remove_functional_group(
        name: str = typer.Argument("", help="Name of the functional group to remove"),
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    ):
        """Remove a functional group and its integration cursor from the configuration."""
        prompter.header("Remove functional group")
        # Prompt for name if not provided
        if not name:
            config = load_config()
            if not config.functional_groups:
                prompter.warning("No functional groups defined in configuration.")
                raise prompter.exit(code=0)

            group_names = list(config.functional_groups.keys())
            # TODO: fix
            name = prompter.choose(group_names, header="Select group to remove:")  # type: ignore

        if not name:
            prompter.error("Group name is required.")
            raise prompter.exit(code=1)

        config_path = find_config_file()
        if not config_path:
            prompter.error("Configuration file not found")
            raise prompter.exit(code=1)

        try:
            data = toml.load(config_path)
        except Exception as e:
            prompter.error(f"Error loading config file: {e}")
            raise prompter.exit(code=1)

        if "functional_groups" not in data or name not in data["functional_groups"]:
            prompter.error(f"Functional group '{name}' not found in configuration.")
            raise prompter.exit(code=1)

        # Confirm deletion
        if not force:
            confirmed = prompter.confirm(f"Remove functional group '{name}'?", default=False)
            if not confirmed:
                prompter.warning("Operation cancelled.")
                raise prompter.exit(code=0)

        # Remove the group
        del data["functional_groups"][name]

        try:
            with open(config_path, "w") as f:
                toml.dump(data, f)
            prompter.success(f"Removed functional group '{name}'.")
        except Exception as e:
            prompter.error(f"Error writing to config file: {e}")
            raise prompter.exit(code=1)

    @app.command("clear-functional-groups")
    def clear_functional_groups(
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    ):
        """Remove all functional groups and their integration cursors from the configuration."""
        prompter.header("Remove all functional groups")
        config_path = find_config_file()
        if not config_path:
            prompter.error("Configuration file not found")
            raise prompter.exit(code=1)

        try:
            data = toml.load(config_path)
        except Exception as e:
            prompter.error(f"Error loading config file: {e}")
            raise prompter.exit(code=1)

        if "functional_groups" not in data or not data["functional_groups"]:
            prompter.warning("No functional groups defined in configuration.")
            raise prompter.exit(code=0)

        group_count = len(data["functional_groups"])

        # Confirm deletion
        if not force:
            confirmed = prompter.confirm(
                f"Remove all {group_count} functional group(s)?", default=False
            )
            if not confirmed:
                prompter.warning("Operation cancelled.")
                raise prompter.exit(code=0)

        # Clear all groups
        data["functional_groups"] = {}

        try:
            with open(config_path, "w") as f:
                toml.dump(data, f)
            prompter.success(f"Removed {group_count} functional group(s).")
        except Exception as e:
            prompter.error(f"Error writing to config file: {e}")
            raise prompter.exit(code=1)

    @app.command("sync-cursor")
    @ensure_git_repo()
    def sync_cursor(
        group_name: str = typer.Argument(None, help="Functional group name (inferred if omitted)"),
        dry_run: bool = typer.Option(
            False, "--dry-run", help="Show commands without executing them"
        ),
    ):
        """Sync base branch and update integration cursor (interactive)."""
        prompter.header("Sync base branch and update integration cursor")
        import re
        import subprocess

        current_branch = get_current_branch()
        config = load_config()

        if not config.functional_groups:
            prompter.error("No functional groups defined.")
            raise prompter.exit(code=1)

        # 1. Determine Functional Group
        selected_group_name = group_name
        selected_group = None

        if selected_group_name:
            if selected_group_name not in config.functional_groups:
                prompter.error(f"Group '{selected_group_name}' not found.")
                raise prompter.exit(code=1)
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
                prompter.info(f"Inferred group: {selected_group_name}")
                selected_group = config.functional_groups[selected_group_name]
            else:
                # Ambiguous or no match, ask user
                group_list = list(config.functional_groups.keys())
                selected_group_name = prompter.choose(
                    group_list, header="Select functional group to sync:"
                )
                if not selected_group_name or not isinstance(selected_group_name, str):
                    prompter.error("No group selected.")
                    raise prompter.exit(code=1)
                selected_group = config.functional_groups[selected_group_name]

        # 2. Get configuration
        base_branch = selected_group.base_branch
        cursor_config = selected_group.integration_cursor

        if not cursor_config or not cursor_config.branch:
            prompter.error(
                f"No integration cursor defined for group '{selected_group_name}'.",
            )
            raise prompter.exit(code=1)

        cursor_branch = cursor_config.branch
        prompter.info(f"Syncing workflow for '{selected_group_name}'")
        prompter.info(f"Base Branch: {base_branch}")
        prompter.info(f"Cursor Branch: {cursor_branch}")

        def run_step(description: str, command: list[str], check: bool = True):
            should_run = prompter.confirm(f"Do you want to {description}?", default=True)

            if not should_run:
                prompter.warning("Skipping...")
                return False

            cmd_str = " ".join(command)
            prompter.info(f"Running: {cmd_str}")

            if dry_run:
                return True

            try:
                subprocess.run(command, check=check)
                prompter.success("Done")
                return True
            except subprocess.CalledProcessError as e:
                prompter.error(f"Command failed: {e}")
                raise prompter.exit(code=1)

        run_step(f"checkout base branch '{base_branch}'", ["git", "checkout", base_branch])
        run_step(f"pull latest changes for '{base_branch}'", ["git", "pull", "origin", base_branch])
        run_step(
            f"merge changes from '{current_branch}'", ["git", "merge", "--no-ff", current_branch]
        )
        run_step(f"push '{base_branch}' to origin", ["git", "push", "origin", base_branch])
        run_step(
            f"checkout integration cursor '{cursor_branch}'", ["git", "checkout", cursor_branch]
        )
        run_step(
            f"pull latest changes for '{cursor_branch}'", ["git", "pull", "origin", cursor_branch]
        )
        run_step(
            f"merge changes from '{base_branch}' into '{cursor_branch}'",
            ["git", "merge", "--no-ff", base_branch],
        )

        prompter.success("Sync workflow completed!")

        # Optional: Switch back to original branch? User didn't ask for it, but it's polite.
        # "Assume that i have a branch created on..."
        # I'll ask.
        if current_branch != base_branch and current_branch != cursor_branch:
            switch_back = prompter.confirm(
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
