"""Deployment permission validation.

This module validates if the current user has permission to deploy
to a specific environment based on their role configuration.
"""

from typing import Tuple

from devrules.config import Config
from devrules.core.permission_service import can_deploy_to_environment


def validate_deployment_permission(environment: str, config: Config) -> Tuple[bool, str]:
    """Validate if current user can deploy to the given environment.

    Uses the permission service to check if the user's role allows
    deploying to the target environment.

    Args:
        environment: Target environment to deploy to.
        config: The application configuration.

    Returns:
        Tuple of (is_valid, message) following existing validator pattern.
        - (True, "") for allowed deployments
        - (True, warning) if allowed with warning (no role assigned)
        - (False, error_message) for denied deployments
    """
    return can_deploy_to_environment(environment, config)
