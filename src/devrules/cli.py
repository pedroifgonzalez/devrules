"""Command-line interface for DevRules."""

from devrules.cli_commands import app
from devrules.config import load_config
from devrules.logging_setup import configure_logging

config = load_config()
configure_logging(config)


if __name__ == "__main__":
    app()
