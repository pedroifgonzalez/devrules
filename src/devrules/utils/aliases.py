import typer

ALIAS_MAP = {
    "check_branch": ["cb"],
    "check_commit": ["cc"],
    "check_pr": ["cpr"],
    "init_config": ["init"],
    "create_branch": ["nb"],
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
}


def register_command_aliases(app: typer.Typer, namespace: dict) -> None:
    """Register short aliases for commonly used commands.

    The caller passes its ``globals()`` so we can resolve functions by
    their names without depending on this module's global namespace.
    """

    for func_name, aliases in ALIAS_MAP.items():
        func = namespace.get(func_name)
        if func is None:
            continue
        for alias in aliases:
            app.command(name=alias)(func)
