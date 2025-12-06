"""Deployment service for managing deployments across environments."""

import json
import os
import subprocess
import urllib.parse
from pathlib import Path
from typing import List, Optional, Tuple

import requests
import typer

from devrules.config import Config


def get_jenkins_auth(config: Config) -> Tuple[Optional[str], Optional[str]]:
    """Get Jenkins authentication from config or environment variables.

    Returns:
        Tuple of (username, token)
    """
    user = config.deployment.jenkins_user or os.getenv("JENKINS_USER")
    token = config.deployment.jenkins_token or os.getenv("JENKINS_TOKEN")
    return user, token


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

    try:
        # Get list of migration files in current branch
        for migration_path in config.deployment.migration_paths:
            full_path = Path(repo_path) / migration_path

            if not full_path.exists():
                continue

            # Get migration files added/modified in current branch vs deployed branch
            result = subprocess.run(
                [
                    "git",
                    "diff",
                    "--name-only",
                    f"{deployed_branch}..{current_branch}",
                    "--",
                    str(migration_path),
                ],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            if result.stdout.strip():
                files = result.stdout.strip().split("\n")
                conflicting_files.extend(files)

        # Check if deployed branch also has new migrations
        if conflicting_files:
            for migration_path in config.deployment.migration_paths:
                result = subprocess.run(
                    [
                        "git",
                        "diff",
                        "--name-only",
                        f"{current_branch}..{deployed_branch}",
                        "--",
                        str(migration_path),
                    ],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                if result.stdout.strip():
                    # Both branches have new migrations - potential conflict
                    return True, conflicting_files

        return False, conflicting_files

    except subprocess.CalledProcessError as e:
        stderr = getattr(e, "stderr", "") or ""
        message = str(e)

        # If the error is due to a missing or unknown revision (e.g. the deployed
        # branch does not exist locally), treat it as "cannot check" but do not
        # block deployment.
        lowered_stderr = stderr.lower()
        if any(
            phrase in lowered_stderr
            for phrase in ["bad revision", "unknown revision", "ambiguous argument"]
        ):
            typer.secho(
                "⚠ Skipping migration conflict check: deployed branch not found in git history",
                fg=typer.colors.YELLOW,
            )
            return False, []

        typer.secho(
            f"⚠ Warning: Could not check migration conflicts: {message}",
            fg=typer.colors.YELLOW,
        )
        return False, []


def get_deployed_branch(environment: str, config: Config) -> Optional[str]:
    """Get the currently deployed branch for an environment from Jenkins.

    Args:
        environment: Environment name (dev, staging, prod)
        config: Configuration object

    Returns:
        Branch name or None if not found
    """
    env_config = config.deployment.environments.get(environment)
    if not env_config:
        typer.secho(
            f"✘ Environment '{environment}' not configured",
            fg=typer.colors.RED,
        )
        return None

    jenkins_url = config.deployment.jenkins_url

    # Use jenkins_job_name if set, otherwise use repo name
    job_name = env_config.jenkins_job_name
    if not job_name:
        job_name = config.github.repo
        if not job_name:
            typer.secho(
                "✘ jenkins_job_name not set and github.repo not configured",
                fg=typer.colors.RED,
            )
            return None

    user, token = get_jenkins_auth(config)

    if not jenkins_url:
        typer.secho(
            "✘ Jenkins URL not configured in .devrules.toml",
            fg=typer.colors.RED,
        )
        return None

    # Build Jenkins API URL based on multibranch_pipeline setting
    # For multibranch pipelines, we want the last successful build of the *job*,
    # regardless of which branch it was for. The branch is then inferred from
    # the build parameters/SCM info below.

    try:
        auth = (user, token) if user and token else None

        # Debug: Show if auth is being used
        if auth:
            typer.secho(
                f"🔑 Using authentication for user: {user}",
                fg=typer.colors.CYAN,
                dim=True,
            )
        else:
            typer.secho(
                "⚠ No authentication credentials found",
                fg=typer.colors.YELLOW,
            )

        if config.deployment.multibranch_pipeline:
            api_url = (
                f"{jenkins_url}/job/{job_name}/api/json?"
                "tree=jobs[name,lastSuccessfulBuild[number,result,timestamp]]"
            )

            response = requests.get(api_url, auth=auth, timeout=30)
            response.raise_for_status()

            job_info = response.json()

            def classify_env(branch_name: str) -> str:
                if branch_name == "main":
                    return "prod"
                if "staging" in branch_name:
                    return "staging"
                return "dev"

            target_env = environment
            if target_env == "production":
                target_env = "prod"

            candidate_jobs = []
            for job in job_info.get("jobs", []):
                raw_name = job.get("name") or ""
                name = urllib.parse.unquote(raw_name)
                env_for_branch = classify_env(name)
                last_build = job.get("lastSuccessfulBuild") or {}
                if env_for_branch == target_env and last_build.get("result") == "SUCCESS":
                    candidate_jobs.append(last_build | {"branch_name": name})

            if candidate_jobs:
                selected = max(candidate_jobs, key=lambda j: j.get("timestamp", 0))
                return selected["branch_name"]

            typer.secho(
                "⚠ Could not determine deployed branch from multibranch jobs",
                fg=typer.colors.YELLOW,
            )
            return env_config.default_branch
        else:
            api_url = f"{jenkins_url}/job/{job_name}/lastSuccessfulBuild/api/json"

            response = requests.get(api_url, auth=auth, timeout=30)
            response.raise_for_status()

            build_info = response.json()

            # Extract branch parameter from build actions
            for action in build_info.get("actions", []):
                if action.get("_class") == "hudson.model.ParametersAction":
                    for param in action.get("parameters", []):
                        if param.get("name") in ["BRANCH", "BRANCH_NAME", "GIT_BRANCH"]:
                            branch = param.get("value", "")
                            # Clean up branch name (remove origin/ prefix if present)
                            if branch.startswith("origin/"):
                                branch = branch[7:]
                            return branch

            # Fallback: try to get from git info
            for action in build_info.get("actions", []):
                if "lastBuiltRevision" in action:
                    branch_info = action.get("lastBuiltRevision", {}).get("branch", [])
                    if branch_info:
                        branch = branch_info[0].get("name", "")
                        if branch.startswith("origin/"):
                            branch = branch[7:]
                        return branch

            typer.secho(
                "⚠ Could not determine deployed branch from Jenkins build info",
                fg=typer.colors.YELLOW,
            )
            return env_config.default_branch

    except requests.HTTPError as e:
        if e.response.status_code == 401:
            typer.secho(
                "✘ Authentication failed (401 Unauthorized)",
                fg=typer.colors.RED,
            )
            typer.secho(
                "  Please check your Jenkins credentials in .devrules.toml or environment variables:",
                fg=typer.colors.YELLOW,
            )
            typer.secho(
                "  - JENKINS_USER or deployment.jenkins_user",
                fg=typer.colors.YELLOW,
            )
            typer.secho(
                "  - JENKINS_TOKEN or deployment.jenkins_token",
                fg=typer.colors.YELLOW,
            )
        elif e.response.status_code == 404:
            typer.secho(
                "✘ Jenkins job not found (404)",
                fg=typer.colors.RED,
            )
            typer.secho(
                f"  Job name: '{job_name}'",
                fg=typer.colors.YELLOW,
            )
            typer.secho(
                f"  URL: {api_url}",
                fg=typer.colors.YELLOW,
            )
            typer.secho(
                "  Possible issues:",
                fg=typer.colors.YELLOW,
            )
            typer.secho(
                "  1. Job name is incorrect in .devrules.toml",
                fg=typer.colors.WHITE,
            )
            typer.secho(
                "  2. Job is in a folder (use 'folder/job-name' format)",
                fg=typer.colors.WHITE,
            )
            typer.secho(
                "  3. Job has no successful builds yet",
                fg=typer.colors.WHITE,
            )
        else:
            typer.secho(
                f"✘ HTTP error fetching Jenkins build info: {e}",
                fg=typer.colors.RED,
            )
        return None
    except requests.RequestException as e:
        typer.secho(
            f"✘ Failed to fetch Jenkins build info: {e}",
            fg=typer.colors.RED,
        )
        return None
    except json.JSONDecodeError as e:
        typer.secho(
            f"✘ Failed to parse Jenkins response: {e}",
            fg=typer.colors.RED,
        )
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
    if environment not in config.deployment.environments:
        return False, f"Environment '{environment}' is not configured"

    # Check if Jenkins is configured
    if not config.deployment.jenkins_url:
        return False, "Jenkins URL is not configured"

    # Get currently deployed branch
    deployed_branch = get_deployed_branch(environment, config)
    if not deployed_branch:
        return False, "Could not determine currently deployed branch"

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
    env_config = config.deployment.environments.get(environment)
    if not env_config:
        return False, f"Environment '{environment}' not configured"

    jenkins_url = config.deployment.jenkins_url

    # Use jenkins_job_name if set, otherwise use repo name
    job_name = env_config.jenkins_job_name
    if not job_name:
        job_name = config.github.repo
        if not job_name:
            return False, "jenkins_job_name not set and github.repo not configured"

    user, token = get_jenkins_auth(config)

    # Build Jenkins API URL for triggering build
    if config.deployment.multibranch_pipeline:
        # Multibranch pipeline: /job/{job_name}/job/{branch}/build
        import urllib.parse

        encoded_branch = urllib.parse.quote(branch, safe="")
        api_url = f"{jenkins_url}/job/{job_name}/job/{encoded_branch}/build"
    else:
        # Regular job: /job/{job_name}/buildWithParameters
        api_url = f"{jenkins_url}/job/{job_name}/buildWithParameters"

    try:
        # Trigger Jenkins build using requests
        auth = (user, token) if user and token else None

        # For regular jobs, send branch as parameter
        # For multibranch, the branch is in the URL
        if config.deployment.multibranch_pipeline:
            response = requests.post(api_url, auth=auth, timeout=30)
        else:
            # Send branch parameter for regular jobs
            response = requests.post(api_url, auth=auth, data={"BRANCH": branch}, timeout=30)

        response.raise_for_status()

        typer.secho(
            f"✔ Deployment job triggered successfully for {environment}",
            fg=typer.colors.GREEN,
        )

        return True, f"Deployment job '{job_name}' triggered for branch '{branch}'"

    except requests.HTTPError as e:
        error_msg = f"Failed to trigger Jenkins job: {e}"
        if e.response.status_code == 404:
            error_msg += f"\nJob or branch not found. URL: {api_url}"
        return False, error_msg
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
