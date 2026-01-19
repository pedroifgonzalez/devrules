"""Logging setup and configuration."""

import sys

from loguru import logger

from devrules.config import Config


def configure_logging(config: Config) -> None:
    """Configure logging based on the provided configuration.

    Args:
        config: The application configuration object.
    """
    logging_config = config.logging

    if not logging_config.enabled:
        # If disabled, disable logging for the package
        logger.disable("devrules")
        return

    # Remove default handler before configuring sinks
    logger.remove()

    # Enable logging for the package
    logger.enable("devrules")

    level_str = logging_config.level.upper()

    # Use the configured format or a sensible default
    log_format = logging_config.format
    if not log_format:
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )

    logger.add(
        sys.stderr,
        level=level_str,
        format=log_format,
        colorize=True,
    )

    logger.debug(f"Logging configured with level: {level_str}")
