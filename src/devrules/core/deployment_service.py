"""Deployment service for managing deployments across environments."""

import json
import os
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

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
        typer.secho(
            f"⚠ Warning: Could not check migration conflicts: {e}",
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
    job_name = env_config.jenkins_job_name
    user, token = get_jenkins_auth(config)

    if not jenkins_url:
        typer.secho(
            "✘ Jenkins URL not configured in .devrules.toml",
            fg=typer.colors.RED,
        )
        return None

    # Build Jenkins API URL
    api_url = f"{jenkins_url}/job/{job_name}/lastSuccessfulBuild/api/json"

    try:
        # Use curl to fetch Jenkins build info
        cmd = ["curl", "-s"]

        if user and token:
            cmd.extend(["-u", f"{user}:{token}"])

        cmd.append(api_url)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )

        build_info = json.loads(result.stdout)

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

    except subprocess.CalledProcessError as e:
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
    job_name = env_config.jenkins_job_name
    user, token = get_jenkins_auth(config)

    # Build Jenkins API URL for triggering build
    api_url = f"{jenkins_url}/job/{job_name}/buildWithParameters"

    try:
        # Trigger Jenkins build
        cmd = ["curl", "-X", "POST", "-s"]

        if user and token:
            cmd.extend(["-u", f"{user}:{token}"])

        # Add branch parameter (will be customizable later)
        cmd.extend(["-d", f"BRANCH={branch}"])
        cmd.append(api_url)

        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )

        typer.secho(
            f"✔ Deployment job triggered successfully for {environment}",
            fg=typer.colors.GREEN,
        )

        return True, f"Deployment job '{job_name}' triggered for branch '{branch}'"

    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to trigger Jenkins job: {e}"
        if e.stderr:
            error_msg += f"\n{e.stderr}"
        return False, error_msg


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
