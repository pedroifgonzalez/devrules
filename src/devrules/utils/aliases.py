"""Command aliases registry."""

import typer

ALIAS_MAP = {
    "check_pr": ["cpr"],
    "init_config": ["init"],
    "create_branch": ["nb"],
    "switch_branch": ["sb"],
    "commit": ["ci"],
    "create_pr": ["pr"],
    "list_owned_branches": ["lob"],
    "delete_branch": ["db"],
    "delete_merged": ["dm"],
    "update_issue_status": ["uis"],
    "list_issues": ["li"],
    "describe_issue": ["di"],
    "dashboard": ["dash"],
    "deploy": ["dep"],
    "check_deployment": ["cd"],
    "build_enterprise": ["be"],
    "install_hooks": ["ih"],
    "uninstall_hooks": ["uh"],
    "functional_group_status": ["fgs"],
    "add_functional_group": ["afg"],
    "set_cursor": ["sc"],
    "remove_functional_group": ["rfg"],
    "clear_functional_groups": ["clfg"],
    "sync_cursor": ["scf"],
    "config_edit": ["cfg", "conf"],
    "config_get": ["cget"],
    "config_set": ["cset"],
}


def register_command_aliases(app: typer.Typer, namespace: dict) -> None:
    """Register short aliases for commonly used commands.

    The caller passes its ``globals()`` so we can resolve functions by
    their names without depending on this module's global namespace.
    """

    # Track registered aliases to prevent collisions
    registered_aliases: set[str] = set()

    for func_name, aliases in ALIAS_MAP.items():
        func = namespace.get(func_name)

        if func is None:
            # Emit warning for missing target function
            typer.secho(
                f"Warning: Alias target '{func_name}' not found in namespace.",
                fg=typer.colors.YELLOW,
                err=True,
            )
            continue

        for alias in aliases:
            if alias in registered_aliases:
                # Emit warning/error for collision
                typer.secho(
                    f"Warning: Alias '{alias}' (for {func_name}) collides with already registered alias.",
                    fg=typer.colors.RED,
                    err=True,
                )
                continue

            # Check if command name already exists in app
            # (Note: Typer doesn't expose an easy public API to check existing commands on the app instance
            # without inspecting internal structures, but we can at least ensure we don't map duplicates within ALIAS_MAP)

            app.command(name=alias)(func)
            registered_aliases.add(alias)
