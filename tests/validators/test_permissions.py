"""Tests for role-based permissions system."""

from unittest.mock import patch

import pytest

from devrules.config import Config, PermissionsConfig, RoleConfig
from devrules.core.permission_service import (
    can_deploy_to_environment,
    can_transition_status,
    get_user_role,
)
from devrules.validators.deployment_permission import validate_deployment_permission
from devrules.validators.status_permission import validate_status_transition


@pytest.fixture
def base_config_components():
    from devrules.config import BranchConfig, CommitConfig, PRConfig

    return {
        "branch": BranchConfig(pattern=".*", prefixes=["feature"]),
        "commit": CommitConfig(tags=["FIX"], pattern=".*"),
        "pr": PRConfig(),
    }


@pytest.fixture
def config_with_roles(base_config_components):
    """Create a config with permissions."""
    from devrules.config import BranchConfig, CommitConfig, PRConfig

    developer_role = RoleConfig(allowed_statuses=["In Progress"], deployable_environments=["dev"])
    maintainer_role = RoleConfig(
        allowed_statuses=["In Progress", "Done"],
        deployable_environments=["dev", "staging", "prod"],
    )

    return Config(
        branch=BranchConfig(pattern=".*", prefixes=["feature"]),
        commit=CommitConfig(tags=["FIX"], pattern=".*"),
        pr=PRConfig(),
        permissions=PermissionsConfig(
            roles={"developer": developer_role, "maintainer": maintainer_role},
            default_role="developer",
            user_assignments={"John Doe": "maintainer"},
        ),
    )


class TestPermissionsConfig:
    """Test permission configuration loading."""

    def test_default_permissions_empty(self):
        """Test that default config has empty permissions."""
        # Create minimal config data inline to avoid loading real config
        from devrules.config import BranchConfig, CommitConfig, PRConfig

        config = Config(
            branch=BranchConfig(pattern=".*", prefixes=["feature"]),
            commit=CommitConfig(tags=["FIX"], pattern=".*"),
            pr=PRConfig(),
            permissions=PermissionsConfig(),
        )

        assert config.permissions.roles == {}
        assert config.permissions.default_role is None
        assert config.permissions.user_assignments == {}

    def test_permissions_with_roles(self):
        """Test creating permissions with roles."""
        developer_role = RoleConfig(
            allowed_statuses=["In Progress"], deployable_environments=["dev"]
        )
        maintainer_role = RoleConfig(
            allowed_statuses=["In Progress", "Done"],
            deployable_environments=["dev", "staging", "prod"],
        )

        permissions = PermissionsConfig(
            roles={"developer": developer_role, "maintainer": maintainer_role},
            default_role="developer",
            user_assignments={"John Doe": "maintainer"},
        )

        assert len(permissions.roles) == 2
        assert permissions.default_role == "developer"
        assert permissions.user_assignments["John Doe"] == "maintainer"


class TestGetUserRole:
    """Test user role resolution."""

    @pytest.fixture
    def config_without_roles(self):
        """Create a config without permissions."""
        from devrules.config import BranchConfig, CommitConfig, PRConfig

        return Config(
            branch=BranchConfig(pattern=".*", prefixes=["feature"]),
            commit=CommitConfig(tags=["FIX"], pattern=".*"),
            pr=PRConfig(),
            permissions=PermissionsConfig(),
        )

    @patch("devrules.core.permission_service.get_current_username")
    def test_get_user_role_assigned(self, mock_username, config_with_roles):
        """Test user with assigned role."""
        mock_username.return_value = "John Doe"
        role_name, role_config = get_user_role(config_with_roles)

        assert role_name == "maintainer"
        assert role_config is not None
        assert "prod" in role_config.deployable_environments

    @patch("devrules.core.permission_service.get_current_username")
    def test_get_user_role_default(self, mock_username, config_with_roles):
        """Test user falling back to default role."""
        mock_username.return_value = "Unknown User"
        role_name, role_config = get_user_role(config_with_roles)

        assert role_name == "developer"
        assert role_config is not None
        assert "dev" in role_config.deployable_environments

    def test_get_user_role_no_roles_configured(self, config_without_roles):
        """Test permissive mode when no roles configured."""
        role_name, role_config = get_user_role(config_without_roles)

        assert role_name is None
        assert role_config is None


class TestCanTransitionStatus:
    """Test status transition permission checks."""

    @pytest.fixture
    def config_without_roles(self):
        """Create config without permissions."""
        from devrules.config import BranchConfig, CommitConfig, PRConfig

        return Config(
            branch=BranchConfig(pattern=".*", prefixes=["feature"]),
            commit=CommitConfig(tags=["FIX"], pattern=".*"),
            pr=PRConfig(),
            permissions=PermissionsConfig(),
        )

    @patch("devrules.core.permission_service.get_current_username")
    def test_allowed_status_transition(self, mock_username, config_with_roles):
        """Test transition to allowed status."""
        mock_username.return_value = "Test User"
        is_allowed, msg = can_transition_status("In Progress", config_with_roles)

        assert is_allowed is True
        assert msg == ""

    @patch("devrules.core.permission_service.get_current_username")
    def test_denied_status_transition(self, mock_username, config_with_roles):
        """Test transition to denied status."""
        mock_username.return_value = "Test User"
        is_allowed, msg = can_transition_status("Done", config_with_roles)

        assert is_allowed is False
        assert "cannot transition" in msg
        assert "Done" in msg

    def test_permissive_when_no_roles(self, config_without_roles):
        """Test permissive mode when no roles configured."""
        is_allowed, msg = can_transition_status("Any Status", config_without_roles)

        assert is_allowed is True
        assert msg == ""


class TestCanDeployToEnvironment:
    """Test deployment permission checks."""

    @pytest.fixture
    def config_with_roles(self):
        """Create config with permissions."""
        from devrules.config import BranchConfig, CommitConfig, PRConfig

        developer_role = RoleConfig(
            allowed_statuses=["In Progress"],
            deployable_environments=["dev"],
        )

        return Config(
            branch=BranchConfig(pattern=".*", prefixes=["feature"]),
            commit=CommitConfig(tags=["FIX"], pattern=".*"),
            pr=PRConfig(),
            permissions=PermissionsConfig(
                roles={"developer": developer_role},
                default_role="developer",
            ),
        )

    @patch("devrules.core.permission_service.get_current_username")
    def test_allowed_deployment(self, mock_username, config_with_roles):
        """Test deployment to allowed environment."""
        mock_username.return_value = "Test User"
        is_allowed, msg = can_deploy_to_environment("dev", config_with_roles)

        assert is_allowed is True
        assert msg == ""

    @patch("devrules.core.permission_service.get_current_username")
    def test_denied_deployment(self, mock_username, config_with_roles):
        """Test deployment to denied environment."""
        mock_username.return_value = "Test User"
        is_allowed, msg = can_deploy_to_environment("prod", config_with_roles)

        assert is_allowed is False
        assert "cannot deploy" in msg
        assert "prod" in msg


class TestValidators:
    """Test validator functions."""

    @pytest.fixture
    def config_without_roles(self):
        """Create config without permissions."""
        from devrules.config import BranchConfig, CommitConfig, PRConfig

        return Config(
            branch=BranchConfig(pattern=".*", prefixes=["feature"]),
            commit=CommitConfig(tags=["FIX"], pattern=".*"),
            pr=PRConfig(),
            permissions=PermissionsConfig(),
        )

    def test_validate_status_transition_wrapper(self, config_without_roles):
        """Test status validator wraps permission service correctly."""
        is_valid, msg = validate_status_transition("Any", config_without_roles)

        assert is_valid is True
        assert msg == ""

    def test_validate_deployment_permission_wrapper(self, config_without_roles):
        """Test deployment validator wraps permission service correctly."""
        is_valid, msg = validate_deployment_permission("dev", config_without_roles)

        assert is_valid is True
        assert msg == ""
