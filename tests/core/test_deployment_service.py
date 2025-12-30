"""Test suite for deployment service migration conflict detection."""

import json
import tempfile
from pathlib import Path
from typing import Generator

import pytest
import vcr
from git import Repo

from devrules.config import Config, EnvironmentConfig
from devrules.core.deployment_service import check_migration_conflicts, get_deployed_branch

vcr_instance = vcr.VCR(
    cassette_library_dir="tests/core/cassettes",
    filter_headers=["authorization"],
    decode_compressed_response=True,
)


@pytest.fixture
def git_repo() -> Generator[Repo, None, None]:
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Repo.init(tmpdir)

        # Configure git user for commits
        with repo.config_writer() as config:
            config.set_value("user", "name", "Test User")
            config.set_value("user", "email", "test@example.com")

        # Create initial commit
        readme = Path(tmpdir) / "README.md"
        readme.write_text("# Test Repository")
        repo.index.add([str(readme)])
        repo.index.commit("Initial commit")

        yield repo


@pytest.fixture
def config() -> Config:
    """Create test configuration."""
    from devrules.config import load_config

    config = load_config()
    config.deployment.migration_detection_enabled = True
    config.deployment.migration_paths = ["migrations/", "db/migrations/"]
    return config


def create_migration_file(
    repo: Repo, path: str, filename: str, content: str = "# Migration"
) -> None:
    """Helper to create a migration file and commit it."""
    migration_dir = Path(repo.working_dir) / path
    migration_dir.mkdir(parents=True, exist_ok=True)

    migration_file = migration_dir / filename
    migration_file.write_text(content)

    repo.index.add([str(migration_file)])
    repo.index.commit(f"Add migration {filename}")


class TestCheckMigrationConflicts:
    """Test cases for check_migration_conflicts function."""

    def test_no_conflicts_when_only_current_branch_has_migrations(
        self, git_repo: Repo, config: Config
    ):
        """Test no conflict when only the current branch has new migrations."""

        # Create main branch with initial state
        main_branch = git_repo.create_head("main")
        main_branch.checkout()

        # Create feature branch with new migration
        feature_branch = git_repo.create_head("feature")
        feature_branch.checkout()
        create_migration_file(git_repo, "migrations", "0001_initial.py")

        # Check for conflicts
        has_conflicts, conflicting_files = check_migration_conflicts(
            repo_path=str(git_repo.working_dir),
            current_branch="feature",
            deployed_branch="main",
            config=config,
        )

        assert not has_conflicts
        assert len(conflicting_files) == 1
        assert "migrations/0001_initial.py" in conflicting_files[0]

    def test_conflicts_when_both_branches_have_migrations(self, git_repo: Repo, config: Config):
        """Test conflict detection when both branches have new migrations."""
        # Create main branch with initial migration
        main_branch = git_repo.create_head("main")
        main_branch.checkout()
        create_migration_file(git_repo, "migrations", "0001_initial.py")

        # Create feature branch from main
        common_commit = git_repo.head.commit
        feature_branch = git_repo.create_head("feature", str(common_commit))

        # Add migration to feature branch
        feature_branch.checkout()
        create_migration_file(git_repo, "migrations", "0002_add_users.py")

        # Add different migration to main branch (simulating parallel development)
        main_branch.checkout()
        create_migration_file(git_repo, "migrations", "0002_add_products.py")

        # Check for conflicts from feature branch perspective
        has_conflicts, conflicting_files = check_migration_conflicts(
            repo_path=str(git_repo.working_dir),
            current_branch="feature",
            deployed_branch="main",
            config=config,
        )

        assert has_conflicts
        assert len(conflicting_files) > 0
        assert any("0002_add_users.py" in f for f in conflicting_files)

    def test_no_conflicts_when_no_new_migrations(self, git_repo: Repo, config: Config):
        """Test no conflicts when neither branch has new migrations."""
        # Create both branches with same migration state
        main_branch = git_repo.create_head("main")
        main_branch.checkout()
        create_migration_file(git_repo, "migrations", "0001_initial.py")

        feature_branch = git_repo.create_head("feature")
        feature_branch.checkout()

        # No new migrations added
        dummy_file = Path(git_repo.working_dir) / "app.py"
        dummy_file.write_text("print('hello')")
        git_repo.index.add([str(dummy_file)])
        git_repo.index.commit("Add app file")

        has_conflicts, conflicting_files = check_migration_conflicts(
            repo_path=str(git_repo.working_dir),
            current_branch="feature",
            deployed_branch="main",
            config=config,
        )

        assert not has_conflicts
        assert len(conflicting_files) == 0

    def test_multiple_migration_paths(self, git_repo: Repo, config: Config):
        """Test conflict detection across multiple migration directories."""
        # Create main branch
        main_branch = git_repo.create_head("main")
        main_branch.checkout()
        create_migration_file(git_repo, "migrations", "0001_initial.py")

        common_commit = git_repo.head.commit
        feature_branch = git_repo.create_head("feature", str(common_commit))

        # Add migrations in different paths on feature branch
        feature_branch.checkout()
        create_migration_file(git_repo, "migrations", "0002_users.py")
        create_migration_file(git_repo, "db/migrations", "0001_products.py")

        # Add migration to main in different path
        main_branch.checkout()
        create_migration_file(git_repo, "db/migrations", "0001_orders.py")

        has_conflicts, conflicting_files = check_migration_conflicts(
            repo_path=str(git_repo.working_dir),
            current_branch="feature",
            deployed_branch="main",
            config=config,
        )

        assert has_conflicts
        assert len(conflicting_files) == 2  # Both feature migrations detected

    def test_migration_detection_disabled(self, git_repo: Repo, config: Config):
        """Test that conflicts are not detected when feature is disabled."""
        # Disable migration detection
        config.deployment.migration_detection_enabled = False

        # Create scenario that would normally have conflicts
        main_branch = git_repo.create_head("main")
        main_branch.checkout()
        create_migration_file(git_repo, "migrations", "0001_initial.py")

        common_commit = git_repo.head.commit
        feature_branch = git_repo.create_head("feature", str(common_commit))

        feature_branch.checkout()
        create_migration_file(git_repo, "migrations", "0002_feature.py")

        main_branch.checkout()
        create_migration_file(git_repo, "migrations", "0002_main.py")

        has_conflicts, conflicting_files = check_migration_conflicts(
            repo_path=str(git_repo.working_dir),
            current_branch="feature",
            deployed_branch="main",
            config=config,
        )

        assert not has_conflicts
        assert len(conflicting_files) == 0

    def test_nonexistent_migration_path(self, git_repo: Repo, config: Config):
        """Test handling of migration paths that don't exist."""
        # Configure with non-existent path
        config.deployment.migration_paths = ["nonexistent/migrations/"]

        main_branch = git_repo.create_head("main")
        main_branch.checkout()

        feature_branch = git_repo.create_head("feature")
        feature_branch.checkout()

        has_conflicts, conflicting_files = check_migration_conflicts(
            repo_path=str(git_repo.working_dir),
            current_branch="feature",
            deployed_branch="main",
            config=config,
        )

        # Should handle gracefully
        assert not has_conflicts
        assert len(conflicting_files) == 0

    def test_sequential_migrations_no_conflict(self, git_repo: Repo, config: Config):
        """Test that sequential migrations (no parallel development) don't conflict."""
        # Main branch with initial migrations
        main_branch = git_repo.create_head("main")
        main_branch.checkout()
        create_migration_file(git_repo, "migrations", "0001_initial.py")
        create_migration_file(git_repo, "migrations", "0002_add_users.py")

        # Feature branch created from latest main
        feature_branch = git_repo.create_head("feature")
        feature_branch.checkout()
        create_migration_file(git_repo, "migrations", "0003_add_products.py")

        has_conflicts, conflicting_files = check_migration_conflicts(
            repo_path=str(git_repo.working_dir),
            current_branch="feature",
            deployed_branch="main",
            config=config,
        )

        # Feature extends main linearly, no conflict
        assert not has_conflicts
        assert len(conflicting_files) == 1  # Only the new migration
        assert "0003_add_products.py" in conflicting_files[0]


MOCK_JENKINS_REPONSE = {
    "_class": "org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject",
    "jobs": [
        {
            "_class": "org.jenkinsci.plugins.workflow.job.WorkflowJob",
            "name": "develop",
            "lastSuccessfulBuild": {
                "_class": "org.jenkinsci.plugins.workflow.job.WorkflowRun",
                "number": 1,
                "result": "SUCCESS",
                "timestamp": 1767063737.091073,
            },
        },
        {
            "_class": "org.jenkinsci.plugins.workflow.job.WorkflowJob",
            "name": "feature/51-track-test-coverage-and-cover-at-least-90-of-code",
            "lastSuccessfulBuild": {
                "_class": "org.jenkinsci.plugins.workflow.job.WorkflowRun",
                "number": 1,
                "result": "SUCCESS",
                "timestamp": 1767063762.392831,
            },
        },
        {
            "_class": "org.jenkinsci.plugins.workflow.job.WorkflowJob",
            "name": "staging-51-track-test-coverage-and-cover-at-least-90-of-code",
            "lastSuccessfulBuild": {
                "_class": "org.jenkinsci.plugins.workflow.job.WorkflowRun",
                "number": 1,
                "result": "SUCCESS",
                "timestamp": 1763510179771,
            },
        },
        {
            "_class": "org.jenkinsci.plugins.workflow.job.WorkflowJob",
            "name": "feature/add-cicd-integration",
        },
    ],
}

NO_LAST_BUILD_MOCK_JENKINS_REPONSE = {
    "_class": "org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject",
    "jobs": [
        {
            "_class": "org.jenkinsci.plugins.workflow.job.WorkflowJob",
            "name": "staging-51-track-test-coverage-and-cover-at-least-90-of-code",
        },
        {
            "_class": "org.jenkinsci.plugins.workflow.job.WorkflowJob",
            "name": "feature/add-cicd-integration",
        },
    ],
}


@pytest.mark.parametrize(
    "case, env, expected_branch",
    [
        ("Wrong Environment", "wrong_env", None),
        ("Missing Jenkins URL", "dev", None),
        ("Not configured job name neither repo_name", "dev", None),
        ("Not auth set (user)", "dev", None),
        ("Not auth set (token)", "dev", None),
        ("No multibranch pipeline set", "dev", None),
        ("Response error", "dev", None),
        (
            "Valid response (dev)",
            "dev",
            "feature/51-track-test-coverage-and-cover-at-least-90-of-code",
        ),
        (
            "Valid response (staging)",
            "staging",
            "staging-51-track-test-coverage-and-cover-at-least-90-of-code",
        ),
        (
            "Valid response (no candidates)",
            "main",
            None,
        ),
        (
            "No candidates",
            "dev",
            None,
        ),
    ],
)
def test_get_deployed_branch(
    case: str,
    env: str,
    config: Config,
    expected_branch: str,
    requests_mock,
):
    def set_valid_mocked_config(config: Config):
        config.deployment.jenkins_url = "http://localhost:8080"
        config.deployment.jenkins_user = "test-user"
        config.deployment.jenkins_token = "test-token"
        config.deployment.multibranch_pipeline = True

    def set_valid_mocked_response(config: Config):
        dev_env = {
            "name": "dev",
            "default_branch": "develop",
            "pattern": "^(?!(main|staging)).*$",
            "jenkins_job_name": "test-job",
        }
        dev_env_config = EnvironmentConfig(**dev_env)
        config.deployment.environments["dev"] = dev_env_config

        staging_env = {
            "name": "staging",
            "default_branch": "",
            "pattern": "^(staging)",
            "jenkins_job_name": "test-job",
        }
        staging_env_config = EnvironmentConfig(**staging_env)
        config.deployment.environments["staging"] = staging_env_config

        prod_env = {
            "name": "prod",
            "default_branch": "main",
            "pattern": "^(main)$",
            "jenkins_job_name": "test-job",
        }
        prod_env_config = EnvironmentConfig(**prod_env)
        config.deployment.environments["prod"] = prod_env_config

        api_url = (
            f"{config.deployment.jenkins_url}/job/{dev_env_config.jenkins_job_name}/api/json?"
            "tree=jobs[name,lastSuccessfulBuild[number,result,timestamp]]"
        )
        requests_mock.get(
            api_url,
            text=json.dumps(MOCK_JENKINS_REPONSE),
        )

    match case:
        case "Wrong Environment":
            pass
        case "Missing Jenkins URL":
            config.deployment.jenkins_url = ""
        case "Not configured job name neither repo_name":
            env_config: EnvironmentConfig = config.deployment.environments["dev"]
            env_config.jenkins_job_name = ""
            config.github.repo = ""
        case "Not auth set (user)":
            config.deployment.jenkins_user = None
        case "Not auth set (token)":
            config.deployment.jenkins_token = None
        case "No multibranch pipeline set":
            config.deployment.multibranch_pipeline = False
        case "Response error":
            set_valid_mocked_config(config)
            env_config: EnvironmentConfig = config.deployment.environments["dev"]
            env_config.jenkins_job_name = "test-job"
            api_url = (
                f"{config.deployment.jenkins_url}/job/{env_config.jenkins_job_name}/api/json?"
                "tree=jobs[name,lastSuccessfulBuild[number,result,timestamp]]"
            )
            requests_mock.get(
                api_url,
                status_code=404,
            )
        case "Valid response (dev)":
            set_valid_mocked_config(config)
            set_valid_mocked_response(config)
        case "Valid response (staging)":
            set_valid_mocked_config(config)
            set_valid_mocked_response(config)
        case "Valid response (no candidates)":
            set_valid_mocked_config(config)
        case "No candidates":
            set_valid_mocked_config(config)
            set_valid_mocked_response(config)
            env_config: EnvironmentConfig = config.deployment.environments["dev"]
            env_config.jenkins_job_name = "test-job"
            api_url = (
                f"{config.deployment.jenkins_url}/job/{env_config.jenkins_job_name}/api/json?"
                "tree=jobs[name,lastSuccessfulBuild[number,result,timestamp]]"
            )
            requests_mock.get(
                api_url,
                text=json.dumps(NO_LAST_BUILD_MOCK_JENKINS_REPONSE),
            )
        case _:
            pass

    assert get_deployed_branch(env, config) == expected_branch
