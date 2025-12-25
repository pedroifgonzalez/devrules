"""Status transition permission validation.

This module validates if the current user has permission to transition
an issue to a specific status based on their role configuration.
"""

from typing import Tuple

from devrules.config import Config
from devrules.core.permission_service import can_transition_status


def validate_status_transition(target_status: str, config: Config) -> Tuple[bool, str]:
    """Validate if current user can transition to the given status.

    Uses the permission service to check if the user's role allows
    transitioning to the target status.

    Args:
        target_status: The status to transition to.
        config: The application configuration.

    Returns:
        Tuple of (is_valid, message) following existing validator pattern.
        - (True, "") for allowed transitions
        - (True, warning) if allowed with warning (no role assigned)
        - (False, error_message) for denied transitions
    """
    return can_transition_status(target_status, config)
