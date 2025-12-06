from typing import Optional

from devrules.config import Config, load_config


def get_config(config_path: Optional[str]) -> Config:
    """Load configuration using the existing load_config helper.

    This centralizes config loading so commands can depend on a single
    abstraction instead of calling load_config directly everywhere.
    """

    return load_config(config_path)
