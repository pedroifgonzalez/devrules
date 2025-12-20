"""CLI commands package for DevRules.

This module owns the main Typer app and wires all sub-command modules
in ``devrules.cli_commands.*``. The public entrypoint ``devrules.cli``
can import and re-export this ``app`` to preserve backwards
compatibility.
"""

from typing import Any, Callable, Dict

import typer

from devrules.cli_commands import (
    branch,
    build_cmd,
    commit,
    config_cmd,
    dashboard,
    deploy,
    group,
    hook_commands,
    pr,
    project,
)
from devrules.utils.aliases import register_command_aliases

app = typer.Typer(help="DevRules - Development guidelines enforcement tool")

# Register all commands
namespace: Dict[str, Callable[..., Any]] = {}
namespace.update(branch.register(app))
namespace.update(commit.register(app))
namespace.update(pr.register(app))
namespace.update(project.register(app))
namespace.update(config_cmd.register(app))
namespace.update(hook_commands.register(app))
namespace.update(dashboard.register(app))
namespace.update(build_cmd.register(app))
namespace.update(deploy.register(app))
namespace.update(group.register(app))


register_command_aliases(app, namespace)


@app.command()
def shell():
    """Launch interactive DevRules shell (REPL mode)."""
    from devrules.shell import run_shell

    run_shell()
