"""Tests for the permission service."""

import subprocess
from unittest.mock import patch

from devrules.config import Config, PermissionsConfig, RoleConfig
from devrules.core.permission_service import (
    can_deploy_to_environment,
    can_transition_status,
    get_current_username,
    get_user_role,
)


class TestGetCurrentUsername:
    """Tests for get_current_username function."""

    @patch("subprocess.run")
    def test_get_current_username_success(self, mock_run):
        """Test successful retrieval of username."""
        mock_run.return_value.stdout = "John Doe\n"
        result = get_current_username()
        assert result == "John Doe"
        mock_run.assert_called_once_with(
            ["git", "config", "user.name"],
            check=True,
            capture_output=True,
            text=True,
        )

    @patch("subprocess.run")
    def test_get_current_username_with_spaces(self, mock_run):
        """Test username with leading/trailing spaces."""
        mock_run.return_value.stdout = "  Alice Smith  \n"
        result = get_current_username()
        assert result == "Alice Smith"

    @patch("subprocess.run")
    def test_get_current_username_subprocess_error(self, mock_run):
        """Test when git config fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        result = get_current_username()
        assert result == "Unknown User"

    @patch("subprocess.run")
    def test_get_current_username_file_not_found(self, mock_run):
        """Test when git is not installed."""
        mock_run.side_effect = FileNotFoundError()
        result = get_current_username()
        assert result == "Unknown User"

    @patch("subprocess.run")
    def test_get_current_username_os_error(self, mock_run):
        """Test when subprocess raises OSError."""
        mock_run.side_effect = OSError("Permission denied")
        result = get_current_username()
        assert result == "Unknown User"


class TestGetUserRole:
    """Tests for get_user_role function."""

    def test_get_user_role_no_roles_configured(self):
        """Test when no roles are configured (permissive mode)."""
        config = Config(
            branch=None,  # Not needed for this test
            commit=None,  # Not needed for this test
            pr=None,  # Not needed for this test
            permissions=PermissionsConfig(),
        )
        role_name, role_config = get_user_role(config)
        assert role_name is None
        assert role_config is None

    @patch("devrules.core.permission_service.get_current_username")
    def test_get_user_role_direct_assignment(self, mock_get_username):
        """Test user directly assigned to a role."""
        mock_get_username.return_value = "alice"
        roles = {
            "developer": RoleConfig(
                allowed_statuses=["In Progress", "Done"], deployable_environments=["staging"]
            )
        }
        config = Config(
            branch=None,
            commit=None,
            pr=None,
            permissions=PermissionsConfig(roles=roles, user_assignments={"alice": "developer"}),
        )
        role_name, role_config = get_user_role(config)
        assert role_name == "developer"
        assert role_config.allowed_statuses == ["In Progress", "Done"]
        assert role_config.deployable_environments == ["staging"]

    @patch("devrules.core.permission_service.get_current_username")
    def test_get_user_role_default_role_fallback(self, mock_get_username):
        """Test fallback to default role when user not assigned."""
        mock_get_username.return_value = "bob"
        roles = {
            "reviewer": RoleConfig(
                allowed_statuses=["QA Testing"], deployable_environments=["production"]
            )
        }
        config = Config(
            branch=None,
            commit=None,
            pr=None,
            permissions=PermissionsConfig(roles=roles, default_role="reviewer"),
        )
        role_name, role_config = get_user_role(config)
        assert role_name == "reviewer"
        assert role_config.allowed_statuses == ["QA Testing"]

    @patch("devrules.core.permission_service.get_current_username")
    def test_get_user_role_no_assignment_no_default(self, mock_get_username):
        """Test when user has no assignment and no default role."""
        mock_get_username.return_value = "charlie"
        roles = {"admin": RoleConfig(allowed_statuses=["*"])}
        config = Config(
            branch=None, commit=None, pr=None, permissions=PermissionsConfig(roles=roles)
        )
        role_name, role_config = get_user_role(config)
        assert role_name is None
        assert role_config is None

    @patch("devrules.core.permission_service.get_current_username")
    def test_get_user_role_invalid_role_assignment(self, mock_get_username):
        """Test when user is assigned to a non-existent role."""
        mock_get_username.return_value = "diana"
        roles = {"developer": RoleConfig(allowed_statuses=["In Progress"])}
        config = Config(
            branch=None,
            commit=None,
            pr=None,
            permissions=PermissionsConfig(roles=roles, user_assignments={"diana": "nonexistent"}),
        )
        role_name, role_config = get_user_role(config)
        assert role_name is None
        assert role_config is None

    @patch("devrules.core.permission_service.get_current_username")
    def test_get_user_role_invalid_default_role(self, mock_get_username):
        """Test when default role doesn't exist."""
        mock_get_username.return_value = "eve"
        roles = {"user": RoleConfig(allowed_statuses=["Backlog"])}
        config = Config(
            branch=None,
            commit=None,
            pr=None,
            permissions=PermissionsConfig(roles=roles, default_role="nonexistent"),
        )
        role_name, role_config = get_user_role(config)
        assert role_name is None
        assert role_config is None


class TestCanTransitionStatus:
    """Tests for can_transition_status function."""

    def test_can_transition_status_no_roles_configured(self):
        """Test permissive mode when no roles are configured."""
        config = Config(branch=None, commit=None, pr=None, permissions=PermissionsConfig())
        allowed, message = can_transition_status("In Progress", config)
        assert allowed is True
        assert message == ""

    @patch("devrules.core.permission_service.get_current_username")
    @patch("devrules.core.permission_service.get_user_role")
    def test_can_transition_status_no_role_found(self, mock_get_user_role, mock_get_username):
        """Test when user has no role (allows with warning)."""
        mock_get_user_role.return_value = (None, None)
        mock_get_username.return_value = "alice"
        roles = {"developer": RoleConfig(allowed_statuses=["In Progress", "Done"])}
        config = Config(
            branch=None, commit=None, pr=None, permissions=PermissionsConfig(roles=roles)
        )
        allowed, message = can_transition_status("QA Testing", config)
        assert allowed is True
        assert message == "Warning: User 'alice' has no assigned role. Allowing action."

    @patch("devrules.core.permission_service.get_user_role")
    def test_can_transition_status_allowed_status(self, mock_get_user_role):
        """Test when status is allowed for the user's role."""
        role_config = RoleConfig(allowed_statuses=["In Progress", "Done", "QA Testing"])
        mock_get_user_role.return_value = ("developer", role_config)
        roles = {"developer": role_config}
        config = Config(
            branch=None, commit=None, pr=None, permissions=PermissionsConfig(roles=roles)
        )
        allowed, message = can_transition_status("Done", config)
        assert allowed is True
        assert message == ""

    @patch("devrules.core.permission_service.get_user_role")
    def test_can_transition_status_denied_status(self, mock_get_user_role):
        """Test when status is not allowed for the user's role."""
        role_config = RoleConfig(allowed_statuses=["In Progress", "Done"])
        mock_get_user_role.return_value = ("developer", role_config)
        roles = {"developer": role_config}
        config = Config(
            branch=None, commit=None, pr=None, permissions=PermissionsConfig(roles=roles)
        )
        allowed, message = can_transition_status("QA Testing", config)
        assert allowed is False
        assert "Role 'developer' cannot transition to status 'QA Testing'" in message
        assert "Allowed statuses: In Progress, Done" in message

    @patch("devrules.core.permission_service.get_user_role")
    def test_can_transition_status_empty_allowed_statuses(self, mock_get_user_role):
        """Test when role has no allowed statuses."""
        role_config = RoleConfig(allowed_statuses=[])
        mock_get_user_role.return_value = ("readonly", role_config)
        roles = {"readonly": role_config}
        config = Config(
            branch=None, commit=None, pr=None, permissions=PermissionsConfig(roles=roles)
        )
        allowed, message = can_transition_status("In Progress", config)
        assert allowed is False
        assert message == "Role 'readonly' is not allowed to transition to any status."


class TestCanDeployToEnvironment:
    """Tests for can_deploy_to_environment function."""

    def test_can_deploy_to_environment_no_roles_configured(self):
        """Test permissive mode when no roles are configured."""
        config = Config(branch=None, commit=None, pr=None, permissions=PermissionsConfig())
        allowed, message = can_deploy_to_environment("staging", config)
        assert allowed is True
        assert message == ""

    @patch("devrules.core.permission_service.get_current_username")
    @patch("devrules.core.permission_service.get_user_role")
    def test_can_deploy_to_environment_no_role_found(self, mock_get_user_role, mock_get_username):
        """Test when user has no role (allows with warning)."""
        mock_get_user_role.return_value = (None, None)
        mock_get_username.return_value = "bob"
        roles = {"deployer": RoleConfig(deployable_environments=["staging", "production"])}
        config = Config(
            branch=None, commit=None, pr=None, permissions=PermissionsConfig(roles=roles)
        )
        allowed, message = can_deploy_to_environment("production", config)
        assert allowed is True
        assert message == "Warning: User 'bob' has no assigned role. Allowing action."

    @patch("devrules.core.permission_service.get_user_role")
    def test_can_deploy_to_environment_allowed_environment(self, mock_get_user_role):
        """Test when environment is allowed for the user's role."""
        role_config = RoleConfig(deployable_environments=["staging", "production", "qa"])
        mock_get_user_role.return_value = ("deployer", role_config)
        roles = {"deployer": role_config}
        config = Config(
            branch=None, commit=None, pr=None, permissions=PermissionsConfig(roles=roles)
        )
        allowed, message = can_deploy_to_environment("production", config)
        assert allowed is True
        assert message == ""

    @patch("devrules.core.permission_service.get_user_role")
    def test_can_deploy_to_environment_denied_environment(self, mock_get_user_role):
        """Test when environment is not allowed for the user's role."""
        role_config = RoleConfig(deployable_environments=["staging", "qa"])
        mock_get_user_role.return_value = ("deployer", role_config)
        roles = {"deployer": role_config}
        config = Config(
            branch=None, commit=None, pr=None, permissions=PermissionsConfig(roles=roles)
        )
        allowed, message = can_deploy_to_environment("production", config)
        assert allowed is False
        assert "Role 'deployer' cannot deploy to environment 'production'" in message
        assert "Allowed environments: staging, qa" in message

    @patch("devrules.core.permission_service.get_user_role")
    def test_can_deploy_to_environment_empty_allowed_environments(self, mock_get_user_role):
        """Test when role has no deployable environments."""
        role_config = RoleConfig(deployable_environments=[])
        mock_get_user_role.return_value = ("viewer", role_config)
        roles = {"viewer": role_config}
        config = Config(
            branch=None, commit=None, pr=None, permissions=PermissionsConfig(roles=roles)
        )
        allowed, message = can_deploy_to_environment("staging", config)
        assert allowed is False
        assert message == "Role 'viewer' is not allowed to deploy to any environment."
