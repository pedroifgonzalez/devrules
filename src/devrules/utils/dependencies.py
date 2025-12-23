from pathlib import Path
from typing import Annotated, Optional

from typer import Option

from devrules.config import Config, load_config


def get_config(
    config_file: Annotated[
        Optional[Path], Option("--config", "-c", help="Path to config file")
    ] = None,
) -> Config:
    return load_config(config_file)
