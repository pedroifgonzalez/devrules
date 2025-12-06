"""CLI commands package for DevRules.

This module owns the main Typer app and wires all sub-command modules
in ``devrules.cli_commands.*``. The public entrypoint ``devrules.cli``
can import and re-export this ``app`` to preserve backwards
compatibility.
"""

import typer

from devrules.cli_commands import branch, commit, config_cmd, dashboard, deploy, pr, project
from devrules.utils.aliases import register_command_aliases

app = typer.Typer(help="DevRules CLI — Enforce development guidelines.")

namespace = {}
namespace.update(branch.register(app))
namespace.update(commit.register(app))
namespace.update(pr.register(app))
namespace.update(project.register(app))
namespace.update(config_cmd.register(app))
namespace.update(dashboard.register(app))
namespace.update(deploy.register(app))

register_command_aliases(app, namespace)
