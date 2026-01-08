"""Tests for the GitHub service."""

import os
from unittest.mock import MagicMock, patch

import pytest
import typer

from devrules.config import GitHubConfig
from devrules.core.github_service import ensure_gh_installed, fetch_pr_info
from devrules.dtos.github import PRInfo


class TestEnsureGhInstalled:
    """Tests for ensure_gh_installed function."""

    @patch("shutil.which")
    def test_gh_installed(self, mock_which):
        """Test when gh CLI is installed."""
        mock_which.return_value = "/usr/bin/gh"
        ensure_gh_installed()
        mock_which.assert_called_once_with("gh")

    @patch("shutil.which")
    @patch("typer.secho")
    def test_gh_not_installed(self, mock_secho, mock_which):
        """Test when gh CLI is not installed."""
        mock_which.return_value = None

        with pytest.raises(typer.Exit) as exc_info:
            ensure_gh_installed()

        assert exc_info.value.exit_code == 1
        mock_which.assert_called_once_with("gh")
        mock_secho.assert_called_once()
        assert "not installed" in mock_secho.call_args[0][0]


class TestFetchPrInfo:
    """Tests for fetch_pr_info function."""

    @pytest.fixture
    def github_config(self):
        """Create a test GitHub configuration."""
        return GitHubConfig(api_url="https://api.github.com", timeout=30)

    @pytest.fixture
    def mock_pr_response(self):
        """Create a mock PR response."""
        return {"additions": 150, "deletions": 50, "changed_files": 5, "title": "Add new feature"}

    @patch.dict(os.environ, {}, clear=True)
    def test_fetch_pr_info_no_token(self, github_config):
        """Test fetch_pr_info when GH_TOKEN is not set."""
        with pytest.raises(ValueError, match="GH_TOKEN environment variable not set"):
            fetch_pr_info("owner", "repo", 123, github_config)

    @patch("requests.get")
    @patch.dict(os.environ, {"GH_TOKEN": "test-token"})
    def test_fetch_pr_info_success(self, mock_get, github_config, mock_pr_response):
        """Test successful PR info fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_pr_response
        mock_get.return_value = mock_response

        result = fetch_pr_info("owner", "repo", 123, github_config)

        assert isinstance(result, PRInfo)
        assert result.additions == 150
        assert result.deletions == 50
        assert result.changed_files == 5
        assert result.title == "Add new feature"

        mock_get.assert_called_once_with(
            "https://api.github.com/repos/owner/repo/pulls/123",
            headers={"Authorization": "Bearer test-token"},
            timeout=30,
        )

    @patch("requests.get")
    @patch.dict(os.environ, {"GH_TOKEN": "test-token"})
    def test_fetch_pr_info_api_error(self, mock_get, github_config):
        """Test fetch_pr_info when GitHub API returns an error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response

        with pytest.raises(Exception, match="GitHub API error: 404"):
            fetch_pr_info("owner", "repo", 123, github_config)

    @patch("requests.get")
    @patch.dict(os.environ, {"GH_TOKEN": "test-token"})
    def test_fetch_pr_info_unauthorized(self, mock_get, github_config):
        """Test fetch_pr_info with unauthorized access."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_get.return_value = mock_response

        with pytest.raises(Exception, match="GitHub API error: 401"):
            fetch_pr_info("owner", "repo", 123, github_config)

    @patch("requests.get")
    @patch.dict(os.environ, {"GH_TOKEN": "test-token"})
    def test_fetch_pr_info_missing_fields(self, mock_get, github_config):
        """Test fetch_pr_info with missing fields in response (should use defaults)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        result = fetch_pr_info("owner", "repo", 123, github_config)

        assert result.additions == 0
        assert result.deletions == 0
        assert result.changed_files == 0
        assert result.title == ""

    @patch("requests.get")
    @patch.dict(os.environ, {"GH_TOKEN": "test-token"})
    def test_fetch_pr_info_partial_fields(self, mock_get, github_config):
        """Test fetch_pr_info with partial fields in response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"additions": 100, "title": "Partial PR"}
        mock_get.return_value = mock_response

        result = fetch_pr_info("owner", "repo", 123, github_config)

        assert result.additions == 100
        assert result.deletions == 0
        assert result.changed_files == 0
        assert result.title == "Partial PR"

    @patch("requests.get")
    @patch.dict(os.environ, {"GH_TOKEN": "test-token"})
    def test_fetch_pr_info_custom_api_url(self, mock_get, mock_pr_response):
        """Test fetch_pr_info with custom API URL."""
        custom_config = GitHubConfig(api_url="https://github.enterprise.com/api/v3", timeout=60)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_pr_response
        mock_get.return_value = mock_response

        result = fetch_pr_info("owner", "repo", 456, custom_config)

        assert isinstance(result, PRInfo)
        mock_get.assert_called_once_with(
            "https://github.enterprise.com/api/v3/repos/owner/repo/pulls/456",
            headers={"Authorization": "Bearer test-token"},
            timeout=60,
        )

    @patch("requests.get")
    @patch.dict(os.environ, {"GH_TOKEN": "test-token"})
    def test_fetch_pr_info_different_pr_numbers(self, mock_get, github_config, mock_pr_response):
        """Test fetch_pr_info with different PR numbers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_pr_response
        mock_get.return_value = mock_response

        fetch_pr_info("owner", "repo", 1, github_config)
        assert "pulls/1" in mock_get.call_args[0][0]

        fetch_pr_info("owner", "repo", 9999, github_config)
        assert "pulls/9999" in mock_get.call_args[0][0]

    @patch("requests.get")
    @patch.dict(os.environ, {"GH_TOKEN": "test-token"})
    def test_fetch_pr_info_uses_timeout(self, mock_get, github_config, mock_pr_response):
        """Test that fetch_pr_info respects the timeout configuration."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_pr_response
        mock_get.return_value = mock_response

        custom_config = GitHubConfig(api_url="https://api.github.com", timeout=45)
        fetch_pr_info("owner", "repo", 123, custom_config)

        assert mock_get.call_args[1]["timeout"] == 45
