"""Test suite for deployment service migration conflict detection."""

import json
from pathlib import Path
from unittest.mock import patch
from urllib import parse

import pytest
import requests
from click.exceptions import Exit
from git import Repo

from devrules.config import Config, EnvironmentConfig
from devrules.core.deployment_service import (
    check_deployment_readiness,
    check_migration_conflicts,
    classify_env,
    execute_deployment,
    get_deployed_branch,
    rollback_deployment,
)


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


@pytest.mark.parametrize(
    "env, default_branch, pattern, branch_name, expected",
    [
        ("dev", "develop", "^(?!(main|staging)).*$", "staging-this-is-not-a-develop-branch", None),
        ("dev", "develop", "^(?!(main|staging)).*$", "feature/23-this-is-a-develop-branch", "dev"),
        ("staging", "", "^(staging)", "staging-this-is-a-staging-branch", "staging"),
    ],
)
def test_classify_env(env, default_branch, pattern, branch_name, expected, config: Config):
    config.deployment.environments[env] = EnvironmentConfig(
        default_branch=default_branch, name=env, pattern=pattern
    )
    output = classify_env(config, branch_name)
    assert output == expected


@pytest.mark.parametrize(
    "case, expected_readiness, expected_message",
    [
        ("Missing environment configuration", False, "Environment is not configured"),
        ("Missing Jenkins url", False, "Jenkins job name could not be resolved"),
        ("Deployed branch could not be resolved", False, "Deployed branch could not be resolved"),
        (
            "Migration conflicts detected",
            False,
            "Migration conflicts detected:\n  - migration_001.py",
        ),
        ("Ready for deployment", True, "Ready for deployment"),
    ],
)
def test_check_deployment_readiness(
    case: str, expected_readiness: str, expected_message: str, config: Config
):
    match case:
        case "Missing environment configuration":
            config.deployment.environments = {}
        case "Missing Jenkins url":
            config.github.repo = ""
            config.deployment.environments["dev"] = EnvironmentConfig(
                **{
                    "name": "dev",
                    "default_branch": "develop",
                    # missing job_name
                }
            )
        case "Deployed branch could not be resolved":
            config.github.repo = "test"  # job name solved with github repo
            config.deployment.environments["dev"] = EnvironmentConfig(
                **{
                    "name": "dev",
                    "default_branch": "develop",
                }
            )
            with patch("devrules.core.deployment_service.get_deployed_branch", return_value=None):
                readiness, message = check_deployment_readiness(
                    repo_path="", branch="test-branch", environment="dev", config=config
                )
                assert readiness == expected_readiness
                assert message == expected_message
                return
        case "Migration conflicts detected":
            config.github.repo = "test"
            config.deployment.environments["dev"] = EnvironmentConfig(
                **{
                    "name": "dev",
                    "default_branch": "develop",
                }
            )
            with patch(
                "devrules.core.deployment_service.get_deployed_branch", return_value="develop"
            ):
                with patch(
                    "devrules.core.deployment_service.check_migration_conflicts",
                    return_value=(True, ["migration_001.py"]),
                ):
                    readiness, message = check_deployment_readiness(
                        repo_path="test-repo",
                        branch="test-branch",
                        environment="dev",
                        config=config,
                    )
                    assert readiness == expected_readiness
                    assert message == expected_message
                    return
        case "Ready for deployment":
            config.github.repo = "test"
            config.deployment.environments["dev"] = EnvironmentConfig(
                **{
                    "name": "dev",
                    "default_branch": "develop",
                }
            )
            with patch(
                "devrules.core.deployment_service.get_deployed_branch", return_value="develop"
            ):
                with patch(
                    "devrules.core.deployment_service.check_migration_conflicts",
                    return_value=(False, []),
                ):
                    readiness, message = check_deployment_readiness(
                        repo_path="test-repo",
                        branch="test-branch",
                        environment="dev",
                        config=config,
                    )
                    assert readiness == expected_readiness
                    assert message == expected_message
                    return

    readiness, message = check_deployment_readiness(
        repo_path="test-repo", branch="test-branch", environment="dev", config=config
    )
    assert readiness == expected_readiness
    assert message == expected_message


@pytest.mark.parametrize(
    "case, expected_message",
    [
        ("Missing environment configuration", "Environment is not configured"),
        ("Missing jenkins job name", "Jenkins job name could not be resolved"),
        ("Missing Jenkins url", "Jenkins URL is not configured"),
        ("Missing auth", "Auth token is not configured"),
        (
            "Response raises error (404)",
            "Job or branch not found. URL: https://url-test/job/job-test/job/test-branch/build",
        ),
        ("Response raises another error", "Failed to trigger Jenkins job: Error"),
        ("Response raises timeout", "Failed to trigger Jenkins job: Timeout"),
    ],
)
def test_execute_deployment_fails(case: str, expected_message: str, config: Config, requests_mock):
    def configure_mocked_valid_config():
        config.deployment.jenkins_url = "https://url-test"
        config.deployment.environments["dev"] = EnvironmentConfig(
            **{
                "name": "dev",
                "default_branch": "develop",
                "jenkins_job_name": "job-test",
            }
        )
        config.deployment.jenkins_user = "user-test"
        config.deployment.jenkins_token = "token-test"

        encoded_branch = parse.quote("test-branch", safe="")
        api_url = f"{config.deployment.jenkins_url}/job/{config.deployment.environments['dev'].jenkins_job_name}/job/{encoded_branch}/build"
        return api_url

    match case:
        case "Missing environment configuration":
            config.deployment.environments = {}
        case "Missing jenkins job name":
            config.github.repo = ""
            config.deployment.environments["dev"] = EnvironmentConfig(
                **{
                    "name": "dev",
                    "default_branch": "develop",
                    # missing job_name
                }
            )
        case "Missing Jenkins url":
            config.github.repo = "repo-test"
            config.deployment.jenkins_url = ""
            config.deployment.environments["dev"] = EnvironmentConfig(
                **{
                    "name": "dev",
                    "default_branch": "develop",
                }
            )
        case "Missing auth":
            config.github.repo = "repo-test"
            config.deployment.jenkins_url = "url-test"
            config.deployment.environments["dev"] = EnvironmentConfig(
                **{
                    "name": "dev",
                    "default_branch": "develop",
                }
            )
            config.deployment.jenkins_user = ""
            config.deployment.jenkins_token = ""

            with pytest.raises(Exit):
                execute_deployment(branch="test-branch", environment="dev", config=config)
            return
        case "Response raises error (404)":
            api_url = configure_mocked_valid_config()
            requests_mock.post(
                api_url,
                status_code=404,
            )
        case "Response raises another error":
            api_url = configure_mocked_valid_config()
            requests_mock.post(
                api_url,
                status_code=500,
                text="Error",
            )
        case "Response raises timeout":
            api_url = configure_mocked_valid_config()
            with patch(
                "devrules.core.deployment_service.requests.post",
                side_effect=requests.exceptions.Timeout("Timeout"),
            ):
                status, message = execute_deployment(
                    branch="test-branch", environment="dev", config=config
                )
            assert not status
            assert message == expected_message
            return

    status, message = execute_deployment(branch="test-branch", environment="dev", config=config)
    assert not status
    assert message == expected_message


@pytest.mark.parametrize(
    "branch_name, job_name, expected_message",
    [
        ("test-branch", "job-test", "Deployment job 'job-test' triggered for branch 'test-branch'"),
        (
            "feature/test-branch",
            "job-test",
            "Deployment job 'job-test' triggered for branch 'feature/test-branch'",
        ),
        (
            "feature/test-branch",
            "job-test-2",
            "Deployment job 'job-test-2' triggered for branch 'feature/test-branch'",
        ),
    ],
)
def test_execute_deployment_success(
    config: Config, requests_mock, branch_name: str, job_name: str, expected_message: str
):
    config.deployment.jenkins_url = "https://url-test"
    config.deployment.environments["dev"] = EnvironmentConfig(
        **{
            "name": "dev",
            "default_branch": "develop",
            "jenkins_job_name": job_name,
        }
    )
    config.deployment.jenkins_user = "user-test"
    config.deployment.jenkins_token = "token-test"

    encoded_branch = parse.quote(branch_name, safe="")
    api_url = f"{config.deployment.jenkins_url}/job/{config.deployment.environments['dev'].jenkins_job_name}/job/{encoded_branch}/build"
    requests_mock.post(
        api_url,
        status_code=200,
    )
    status, message = execute_deployment(branch=branch_name, environment="dev", config=config)
    assert status
    assert message == expected_message

    status, message = rollback_deployment(
        target_branch=branch_name, environment="dev", config=config
    )
    assert status
    assert message == expected_message
