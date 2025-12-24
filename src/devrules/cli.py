"""Command-line interface for DevRules."""

from devrules.cli_commands import app
from devrules.config import load_config

config = load_config()


if __name__ == "__main__":
    app()
