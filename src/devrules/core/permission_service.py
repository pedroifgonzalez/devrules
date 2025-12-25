"""Permission service for role-based access control.

This module provides functions for resolving user permissions based on
role assignments and checking authorization for status transitions and
deployments.
"""

import subprocess
from typing import Optional, Tuple

from devrules.config import Config, RoleConfig


def get_current_username() -> str:
    """Get current username via git config user.name.

    Returns:
        The git user.name, or "Unknown User" if not configured.
    """
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "Unknown User"


def get_user_role(config: Config) -> Tuple[Optional[str], Optional[RoleConfig]]:
    """Get user's role name and configuration.

    Determines the current user's role by:
    1. Looking up their username in user_assignments
    2. Falling back to default_role if set
    3. Returning (None, None) if no role found

    Args:
        config: The application configuration.

    Returns:
        Tuple of (role_name, role_config) or (None, None) if no role found.
    """
    permissions = config.permissions

    # If no roles configured, return None (permissive mode)
    if not permissions.roles:
        return None, None

    username = get_current_username()

    # Look up user's assigned role
    role_name = permissions.user_assignments.get(username)

    # Fall back to default role if user not assigned
    if role_name is None:
        role_name = permissions.default_role

    # Get role configuration
    if role_name and role_name in permissions.roles:
        return role_name, permissions.roles[role_name]

    return None, None


def can_transition_status(status: str, config: Config) -> Tuple[bool, str]:
    """Check if current user can transition to the given status.

    Behavior:
    - If no permissions.roles configured: allow with no message (permissive default)
    - If user has a role: check if status is in allowed_statuses
    - If user has no role and no default_role: allow with warning

    Args:
        status: Target status to transition to.
        config: The application configuration.

    Returns:
        Tuple of (is_allowed, message).
    """
    permissions = config.permissions

    # Permissive default when no roles configured
    if not permissions.roles:
        return True, ""

    role_name, role_config = get_user_role(config)

    # No role found - allow with warning
    if role_config is None:
        username = get_current_username()
        return True, f"Warning: User '{username}' has no assigned role. Allowing action."

    # Check if status is allowed
    if not role_config.allowed_statuses:
        return (
            False,
            f"Role '{role_name}' is not allowed to transition to any status.",
        )

    if status in role_config.allowed_statuses:
        return True, ""

    allowed = ", ".join(role_config.allowed_statuses)
    return (
        False,
        f"Role '{role_name}' cannot transition to status '{status}'. "
        f"Allowed statuses: {allowed}",
    )


def can_deploy_to_environment(environment: str, config: Config) -> Tuple[bool, str]:
    """Check if current user can deploy to the given environment.

    Behavior:
    - If no permissions.roles configured: allow with no message (permissive default)
    - If user has a role: check if environment is in deployable_environments
    - If user has no role and no default_role: allow with warning

    Args:
        environment: Target environment to deploy to.
        config: The application configuration.

    Returns:
        Tuple of (is_allowed, message).
    """
    permissions = config.permissions

    # Permissive default when no roles configured
    if not permissions.roles:
        return True, ""

    role_name, role_config = get_user_role(config)

    # No role found - allow with warning
    if role_config is None:
        username = get_current_username()
        return True, f"Warning: User '{username}' has no assigned role. Allowing action."

    # Check if environment is allowed
    if not role_config.deployable_environments:
        return (
            False,
            f"Role '{role_name}' is not allowed to deploy to any environment.",
        )

    if environment in role_config.deployable_environments:
        return True, ""

    allowed = ", ".join(role_config.deployable_environments)
    return (
        False,
        f"Role '{role_name}' cannot deploy to environment '{environment}'. "
        f"Allowed environments: {allowed}",
    )
