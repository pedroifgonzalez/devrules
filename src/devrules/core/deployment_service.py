"""Deployment service for managing deployments across environments."""

import os
import re
import urllib.parse
from pathlib import Path
from typing import List, Optional, Tuple

import requests
import typer

from devrules.config import Config, EnvironmentConfig
from devrules.core.git_service import get_files_difference_between_branches_in_path


def get_jenkins_auth(config: Config) -> Tuple[Optional[str], Optional[str]]:
    """Get Jenkins authentication from config or environment variables.

    Returns:
        Tuple of (username, token)
    """
    user = config.deployment.jenkins_user or os.getenv("JENKINS_USER")
    token = config.deployment.jenkins_token or os.getenv("JENKINS_TOKEN")
    if not user or not token:
        typer.secho(
            "⚠ No authentication credentials found",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)
    return user, token


def get_environment_config(config: Config, environment: str):
    """Get configuration for a specific deployment environment.

    Args:
        config: Application configuration containing deployment settings.
        environment: Name of the target environment (e.g., dev, staging, prod).

    Returns:
        The matching EnvironmentConfig or None if not configured. Emits an error message
        when the environment is missing.
    """
    env_config = config.deployment.environments.get(environment)
    if not env_config:
        typer.secho(
            f"✘ Environment '{environment}' not configured",
            fg=typer.colors.RED,
        )
        return None
    return env_config


def get_jenkins_url(config: Config):
    """Resolve the Jenkins base URL from configuration.

    Args:
        config: Application configuration containing deployment settings.

    Returns:
        Jenkins URL string if available, otherwise None. Emits an error message when
        the URL is not configured.
    """
    jenkins_url = config.deployment.jenkins_url
    if not jenkins_url:
        typer.secho(
            "✘ Jenkins URL not configured in .devrules.toml",
            fg=typer.colors.RED,
        )
        return None
    return jenkins_url


def get_jenkins_job_name(config: Config, env_config: EnvironmentConfig):
    """Determine the Jenkins job name for an environment.

    Prefers the job name defined in the environment config, falling back to the
    GitHub repository name if missing.

    Args:
        config: Application configuration.
        env_config: Environment-specific configuration.

    Returns:
        Job name string if it can be resolved, otherwise None. Emits an error message
        when no job name can be determined.
    """
    job_name = env_config.jenkins_job_name
    if not job_name:
        job_name = config.github.repo
        if not job_name:
            typer.secho(
                "✘ jenkins_job_name not set and github.repo not configured",
                fg=typer.colors.RED,
            )
            return None
    return job_name


def check_migration_conflicts(
    repo_path: str, current_branch: str, deployed_branch: str, config: Config
) -> Tuple[bool, List[str]]:
    """Check for migration conflicts between current and deployed branches.

    Args:
        repo_path: Path to the repository
        current_branch: Branch to deploy
        deployed_branch: Currently deployed branch
        config: Configuration object

    Returns:
        Tuple of (has_conflicts, list_of_conflicting_files)
    """
    if not config.deployment.migration_detection_enabled:
        return False, []

    conflicting_files = []

    # Get list of migration files in current branch
    for migration_path in config.deployment.migration_paths:
        full_path = Path(repo_path) / migration_path

        if not full_path.exists():
            continue

        # Get migration files added/modified in current branch vs deployed branch
        files = get_files_difference_between_branches_in_path(
            path=migration_path,
            repo_path=repo_path,
            base_branch=deployed_branch,
            target_branch=current_branch,
        )

        conflicting_files.extend(files)

    # Check if deployed branch also has new migrations
    if conflicting_files:
        for migration_path in config.deployment.migration_paths:
            files = get_files_difference_between_branches_in_path(
                path=migration_path,
                repo_path=repo_path,
                base_branch=current_branch,
                target_branch=deployed_branch,
            )
            if files:
                # Both branches have new migrations - potential conflict
                return True, conflicting_files

    return False, conflicting_files


def classify_env(config: Config, branch_name: str) -> Optional[str]:
    """Map a branch name to an environment using configured patterns.

    Args:
        config: Application configuration containing environments.
        branch_name: Name of the branch to classify.

    Returns:
        Matching environment name, or None if no pattern matches.
    """
    for env in config.deployment.environments.values():
        if env.pattern and re.match(env.pattern, branch_name):
            return env.name
    return None


def get_deployed_branch(environment: str, config: Config) -> Optional[str]:
    """Get the currently deployed branch for an environment from Jenkins.

    Args:
        environment: Environment name (dev, staging, prod)
        config: Configuration object

    Returns:
        Branch name or None if not found
    """
    env_config = get_environment_config(config, environment)
    if not env_config:
        return None

    jenkins_url = get_jenkins_url(config)
    if not jenkins_url:
        return None

    job_name = get_jenkins_job_name(config, env_config)
    if not job_name:
        return None

    try:
        user, token = get_jenkins_auth(config)
        auth = (user, token) if user and token else None
        if config.deployment.multibranch_pipeline:
            api_url = (
                f"{jenkins_url}/job/{job_name}/api/json?"
                "tree=jobs[name,lastSuccessfulBuild[number,result,timestamp]]"
            )
            response: requests.Response = requests.get(api_url, auth=auth, timeout=30)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                typer.secho(
                    f"⚠ Failed to fetch Jenkins job information: {e}",
                    fg=typer.colors.YELLOW,
                )
                return None

            job_info = response.json()

            target_env = environment
            candidates: list[dict] = []

            for job in job_info.get("jobs", []):
                branch_name = urllib.parse.unquote(job.get("name", ""))
                env_for_branch = classify_env(config, branch_name)

                if not env_for_branch or env_for_branch != target_env:
                    continue

                build = job.get("lastSuccessfulBuild")
                if not build:
                    continue

                candidates.append(
                    {
                        "branch": branch_name,
                        "timestamp": build.get("timestamp", 0),
                    }
                )

            if not candidates:
                return None

            selected = max(candidates, key=lambda x: x["timestamp"])
            return selected["branch"]

        typer.secho("Only multibranch pipelines are supported", fg=typer.colors.RED)
        return None
    except Exception as e:
        typer.secho(f"Error fetching Jenkins data: {e}", fg=typer.colors.RED)
        return None


def check_deployment_readiness(
    repo_path: str, branch: str, environment: str, config: Config
) -> Tuple[bool, str]:
    """Check if a branch is ready for deployment.

    Args:
        repo_path: Path to the repository
        branch: Branch to deploy
        environment: Target environment
        config: Configuration object

    Returns:
        Tuple of (is_ready, status_message)
    """
    # Check if environment is configured
    env_config = get_environment_config(config, environment)
    if not env_config:
        return False, "Environment is not configured"

    # Check if Jenkins is configured
    if not get_jenkins_job_name(config, env_config):
        return False, "Jenkins job name could not be resolved"

    # Get currently deployed branch
    deployed_branch = get_deployed_branch(environment, config)
    if not deployed_branch:
        return False, "Deployed branch could not be resolved"

    # Check for migration conflicts
    has_conflicts, conflicting_files = check_migration_conflicts(
        repo_path, branch, deployed_branch, config
    )

    if has_conflicts:
        files_str = "\n  - ".join(conflicting_files)
        return False, f"Migration conflicts detected:\n  - {files_str}"

    return True, "Ready for deployment"


def execute_deployment(branch: str, environment: str, config: Config) -> Tuple[bool, str]:
    """Execute deployment job in Jenkins.

    Args:
        branch: Branch to deploy
        environment: Target environment
        config: Configuration object

    Returns:
        Tuple of (success, message_or_error)
    """
    env_config = get_environment_config(config, environment)
    if not env_config:
        return False, "Environment is not configured"

    job_name = get_jenkins_job_name(config, env_config)
    if not job_name:
        return False, "Jenkins job name could not be resolved"

    jenkins_url = get_jenkins_url(config)
    if not jenkins_url:
        return False, "Jenkins URL is not configured"

    user, token = get_jenkins_auth(config)
    encoded_branch = urllib.parse.quote(branch, safe="")
    api_url = f"{jenkins_url}/job/{job_name}/job/{encoded_branch}/build"

    try:
        auth = (user, token) if user and token else None
        response = requests.post(api_url, auth=auth, timeout=30)
        response.raise_for_status()
        typer.secho(
            f"✔ Deployment job triggered successfully for {environment}",
            fg=typer.colors.GREEN,
        )
        return True, f"Deployment job '{job_name}' triggered for branch '{branch}'"

    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return False, f"Job or branch not found. URL: {api_url}"
        return False, f"Failed to trigger Jenkins job: {e.response.text}"
    except requests.RequestException as e:
        return False, f"Failed to trigger Jenkins job: {e}"


def rollback_deployment(environment: str, target_branch: str, config: Config) -> Tuple[bool, str]:
    """Rollback deployment to a specific branch.

    Args:
        environment: Target environment
        target_branch: Branch to rollback to
        config: Configuration object

    Returns:
        Tuple of (success, message)
    """
    typer.secho(
        f"🔄 Rolling back {environment} to branch '{target_branch}'...",
        fg=typer.colors.CYAN,
    )

    # Rollback is just another deployment to the target branch
    return execute_deployment(target_branch, environment, config)
