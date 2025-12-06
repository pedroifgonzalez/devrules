"""Tests for deployment service."""

from unittest.mock import MagicMock, patch

from src.devrules.config import Config, DeploymentConfig, EnvironmentConfig
from src.devrules.core.deployment_service import check_migration_conflicts, get_deployed_branch


def test_check_migration_conflicts_disabled():
    """Test that migration check is skipped when disabled."""
    config = Config(
        branch=MagicMock(),
        commit=MagicMock(),
        pr=MagicMock(),
        github=MagicMock(),
        deployment=DeploymentConfig(migration_detection_enabled=False),
    )

    has_conflicts, files = check_migration_conflicts("/fake/repo", "feature/123", "main", config)

    assert has_conflicts is False
    assert files == []


@patch("subprocess.run")
def test_check_migration_conflicts_no_conflicts(mock_run):
    """Test migration check when there are no conflicts."""
    # Mock git diff to return no files
    mock_run.return_value = MagicMock(stdout="", returncode=0)

    config = Config(
        branch=MagicMock(),
        commit=MagicMock(),
        pr=MagicMock(),
        github=MagicMock(),
        deployment=DeploymentConfig(
            migration_detection_enabled=True,
            migration_paths=["migrations/"],
        ),
    )

    has_conflicts, files = check_migration_conflicts("/fake/repo", "feature/123", "main", config)

    assert has_conflicts is False
    assert files == []


@patch("pathlib.Path.exists")
@patch("subprocess.run")
def test_check_migration_conflicts_with_new_migrations(mock_run, mock_exists):
    """Test migration check when current branch has new migrations."""
    # Mock Path.exists to return True
    mock_exists.return_value = True

    # First call: current branch has new migrations
    # Second call: deployed branch has no new migrations
    mock_run.side_effect = [
        MagicMock(stdout="migrations/001_initial.py\n", returncode=0),
        MagicMock(stdout="", returncode=0),
    ]

    config = Config(
        branch=MagicMock(),
        commit=MagicMock(),
        pr=MagicMock(),
        github=MagicMock(),
        deployment=DeploymentConfig(
            migration_detection_enabled=True,
            migration_paths=["migrations/"],
        ),
    )

    has_conflicts, files = check_migration_conflicts("/fake/repo", "feature/123", "main", config)

    # No conflict because only current branch has new migrations
    assert has_conflicts is False
    assert len(files) == 1
    assert "migrations/001_initial.py" in files


@patch("pathlib.Path.exists")
@patch("subprocess.run")
def test_check_migration_conflicts_both_branches_have_migrations(mock_run, mock_exists):
    """Test migration check when both branches have new migrations."""
    # Mock Path.exists to return True
    mock_exists.return_value = True

    # Both branches have new migrations - this is a conflict
    mock_run.side_effect = [
        MagicMock(stdout="migrations/001_initial.py\n", returncode=0),
        MagicMock(stdout="migrations/002_other.py\n", returncode=0),
    ]

    config = Config(
        branch=MagicMock(),
        commit=MagicMock(),
        pr=MagicMock(),
        github=MagicMock(),
        deployment=DeploymentConfig(
            migration_detection_enabled=True,
            migration_paths=["migrations/"],
        ),
    )

    has_conflicts, files = check_migration_conflicts("/fake/repo", "feature/123", "main", config)

    # Conflict because both branches have new migrations
    assert has_conflicts is True
    assert len(files) == 1


@patch("src.devrules.core.deployment_service.requests.get")
def test_get_deployed_branch_success(mock_get):
    """Test getting deployed branch from Jenkins."""
    # Mock Jenkins API response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "actions": [
            {
                "_class": "hudson.model.ParametersAction",
                "parameters": [{"name": "BRANCH_NAME", "value": "origin/main"}],
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    env_config = EnvironmentConfig(
        name="dev",
        default_branch="develop",
        jenkins_job_name="deploy-dev",
    )

    config = Config(
        branch=MagicMock(),
        commit=MagicMock(),
        pr=MagicMock(),
        github=MagicMock(),
        deployment=DeploymentConfig(
            jenkins_url="https://jenkins.example.com",
            environments={"dev": env_config},
        ),
    )

    branch = get_deployed_branch("dev", config)

    # Should strip origin/ prefix
    assert branch == "main"


def test_get_deployed_branch_environment_not_configured():
    """Test getting deployed branch when environment is not configured."""
    config = Config(
        branch=MagicMock(),
        commit=MagicMock(),
        pr=MagicMock(),
        github=MagicMock(),
        deployment=DeploymentConfig(environments={}),
    )

    branch = get_deployed_branch("nonexistent", config)

    assert branch is None
