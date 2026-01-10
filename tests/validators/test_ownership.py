"""Tests for ownership.py."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.devrules.validators.ownership import (
    _get_branch_owner,
    _get_current_user,
    _get_merge_base,
    list_user_owned_branches,
    validate_branch_ownership,
)


@pytest.fixture
def mock_subprocess_run():
    """Fixture to mock subprocess.run."""
    with patch("subprocess.run") as mock_run:
        yield mock_run


class TestValidateBranchOwnership:
    """Test validate_branch_ownership function."""

    @pytest.mark.parametrize(
        "branch,expected_valid,expected_message",
        [
            ("main", True, "Shared branch — ownership check skipped"),
            ("master", True, "Shared branch — ownership check skipped"),
            ("develop", True, "Shared branch — ownership check skipped"),
            ("release/v1.0", True, "Shared branch — ownership check skipped"),
            (
                "feature/xyz",
                False,
                "Unable to determine current developer identity. Configure it with 'git config --global user.name \"Your Name\"' or set the USER environment variable.",
            ),
        ],
    )
    def test_shared_branches_and_no_user(
        self, branch, expected_valid, expected_message, mock_subprocess_run
    ):
        """Test shared branches and no user identity."""
        mock_subprocess_run.return_value.stdout = ""

        with patch.dict("os.environ", {}, clear=True):
            result = validate_branch_ownership(branch)
            assert result == (expected_valid, expected_message)

    def test_non_shared_branch_no_history(self, mock_subprocess_run):
        """Test non-shared branch with no history after base."""
        branch = "feature/new"

        # Mock git config
        mock_subprocess_run.side_effect = [
            MagicMock(stdout="Test User\n", returncode=0),  # git config user.name
            MagicMock(stdout="abc123\n", returncode=0),  # git merge-base
            MagicMock(stdout="", returncode=0),  # git log (empty)
        ]

        with patch.dict("os.environ", {"USER": "Test User"}):
            result = validate_branch_ownership(branch)
            assert result == (True, "New branch with no history after base — first commit allowed")

    def test_non_shared_branch_owned_by_user(self, mock_subprocess_run):
        """Test non-shared branch owned by current user."""
        branch = "feature/owned"

        mock_subprocess_run.side_effect = [
            MagicMock(stdout="Test User\n", returncode=0),  # git config user.name
            MagicMock(stdout="abc123\n", returncode=0),  # git merge-base
            MagicMock(stdout="Test User\nOther User\n", returncode=0),  # git log
        ]

        with patch.dict("os.environ", {"USER": "Test User"}):
            result = validate_branch_ownership(branch)
            assert result == (True, "Current user matches branch owner")

    def test_non_shared_branch_not_owned_by_user(self, mock_subprocess_run):
        """Test non-shared branch not owned by current user."""
        branch = "feature/owned"

        mock_subprocess_run.side_effect = [
            MagicMock(stdout="Current User\n", returncode=0),  # git config user.name
            MagicMock(stdout="abc123\n", returncode=0),  # git merge-base
            MagicMock(stdout="Owner User\nOther User\n", returncode=0),  # git log
        ]

        with patch.dict("os.environ", {"USER": "Current User"}):
            result = validate_branch_ownership(branch)
            assert result == (
                False,
                "You are not allowed to commit on this branch. Branch owner: Owner User, your identity: Current User",
            )

    def test_merge_base_failure(self, mock_subprocess_run):
        """Test when merge-base fails."""
        branch = "feature/test"

        mock_subprocess_run.side_effect = [
            MagicMock(stdout="Test User\n", returncode=0),  # git config user.name
            MagicMock(
                stdout="", returncode=1, stderr="fatal: no common ancestor"
            ),  # git merge-base fails
            MagicMock(stdout="Test User\n", returncode=0),  # git log HEAD
        ]

        with patch.dict("os.environ", {"USER": "Test User"}):
            result = validate_branch_ownership(branch)
            assert result == (True, "Current user matches branch owner")

    def test_merge_base_raises_error(self, mock_subprocess_run):
        """Test when merge-base raises an error."""
        branch = "feature/test"

        mock_subprocess_run.side_effect = [
            MagicMock(stdout="Test User\n", returncode=0),  # git config user.name
            subprocess.CalledProcessError(1, ["git", "merge-base"]),  # git merge-base fails
            MagicMock(stdout="Test User\n", returncode=0),  # git log HEAD
        ]

        with patch.dict("os.environ", {"USER": "Test User"}):
            result = validate_branch_ownership(branch)
            assert result == (True, "Current user matches branch owner")


class TestGetCurrentUser:
    """Test _get_current_user function."""

    def test_git_config_success(self, mock_subprocess_run):
        """Test getting user from git config."""
        mock_subprocess_run.return_value = MagicMock(stdout="Git User\n", returncode=0)

        result = _get_current_user()
        assert result == "Git User"
        mock_subprocess_run.assert_called_once_with(
            ["git", "config", "user.name"], capture_output=True, text=True
        )

    def test_git_config_empty_fallback_to_env(self, mock_subprocess_run):
        """Test fallback to USER env var when git config empty."""
        mock_subprocess_run.return_value = MagicMock(stdout="", returncode=0)

        with patch.dict("os.environ", {"USER": "Env User"}):
            result = _get_current_user()
            assert result == "Env User"

    def test_git_config_empty_no_env(self, mock_subprocess_run):
        """Test empty result when git config empty and no USER env."""
        mock_subprocess_run.return_value = MagicMock(stdout="", returncode=0)

        with patch.dict("os.environ", {}, clear=True):
            result = _get_current_user()
            assert result == ""


class TestGetMergeBase:
    """Test _get_merge_base function."""

    def test_success(self, mock_subprocess_run):
        """Test successful merge-base."""
        mock_subprocess_run.return_value = MagicMock(stdout="abc123\n", returncode=0)

        result = _get_merge_base("feature/branch")
        assert result == "abc123"
        mock_subprocess_run.assert_called_once_with(
            ["git", "merge-base", "develop", "feature/branch"],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_failure(self, mock_subprocess_run):
        """Test merge-base failure."""
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, ["git", "merge-base"])

        result = _get_merge_base("feature/branch")
        assert result == ""


class TestGetBranchOwner:
    """Test _get_branch_owner function."""

    def test_shared_branch(self):
        """Test shared branch returns SHARED."""
        result = _get_branch_owner("main", "Test User")
        assert result == "SHARED"

        result = _get_branch_owner("release/v1.0", "Test User")
        assert result == "SHARED"

    def test_non_shared_with_history(self, mock_subprocess_run):
        """Test non-shared branch with commit history."""
        mock_subprocess_run.side_effect = [
            MagicMock(stdout="abc123\n", returncode=0),  # git merge-base
            MagicMock(stdout="Owner User\nOther User\n", returncode=0),  # git log
        ]

        result = _get_branch_owner("feature/branch", "Current User")
        assert result == "Owner User"

    def test_non_shared_no_history_new_branch(self, mock_subprocess_run):
        """Test non-shared branch with no history (new branch)."""
        mock_subprocess_run.side_effect = [
            MagicMock(stdout="abc123\n", returncode=0),  # git merge-base
            MagicMock(stdout="", returncode=0),  # git log (empty)
            MagicMock(stdout="def456\n", returncode=0),  # git rev-parse develop
            MagicMock(stdout="def456\n", returncode=0),  # git rev-parse branch (same as develop)
        ]

        result = _get_branch_owner("feature/new", "Current User")
        assert result == "Current User"

    def test_non_shared_no_history_merged_branch(self, mock_subprocess_run):
        """Test non-shared branch with no unique history (merged branch)."""
        mock_subprocess_run.side_effect = [
            MagicMock(stdout="abc123\n", returncode=0),  # git merge-base
            MagicMock(stdout="", returncode=0),  # git log (empty)
            MagicMock(stdout="def456\n", returncode=0),  # git rev-parse develop
            MagicMock(stdout="ghi789\n", returncode=0),  # git rev-parse branch (different)
            MagicMock(stdout="Tip Author\n", returncode=0),  # git log -1 branch
        ]

        result = _get_branch_owner("feature/merged", "Current User")
        assert result == "Tip Author"

    def test_non_shared_no_history_rev_parse_failure(self, mock_subprocess_run):
        """Test rev-parse failure falls back to current user."""
        mock_subprocess_run.side_effect = [
            MagicMock(stdout="abc123\n", returncode=0),  # git merge-base
            MagicMock(stdout="", returncode=0),  # git log (empty)
            subprocess.CalledProcessError(1, ["git", "rev-parse"]),  # git rev-parse develop fails
        ]

        result = _get_branch_owner("feature/error", "Current User")
        assert result == "Current User"


class TestListUserOwnedBranches:
    """Test list_user_owned_branches function."""

    def test_success(self, mock_subprocess_run):
        """Test listing owned branches."""
        mock_subprocess_run.side_effect = [
            MagicMock(stdout="Test User\n", returncode=0),  # git config user.name
            MagicMock(
                stdout="main\nfeature/owned\nfeature/other\n", returncode=0
            ),  # git for-each-ref
            # For main: _get_branch_owner -> SHARED
            MagicMock(stdout="abc123\n", returncode=0),  # merge-base for feature/owned
            MagicMock(stdout="Test User\n", returncode=0),  # log for feature/owned
            # For feature/other: owner is Other User
            MagicMock(stdout="def456\n", returncode=0),  # merge-base for feature/other
            MagicMock(stdout="Other User\n", returncode=0),  # log for feature/other
        ]

        with patch("src.devrules.validators.ownership._get_branch_owner") as mock_get_owner:
            mock_get_owner.side_effect = ["SHARED", "Test User", "Other User"]

            result = list_user_owned_branches()
            assert result == ["feature/owned"]

    def test_no_user_identity(self, mock_subprocess_run):
        """Test when unable to determine user identity."""
        mock_subprocess_run.return_value = MagicMock(stdout="", returncode=0)

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(
                RuntimeError, match="Unable to determine current developer identity"
            ):
                list_user_owned_branches()
