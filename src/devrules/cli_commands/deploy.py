"""Deployment CLI commands for DevRules."""

import urllib.parse
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import typer
from typer_di import Depends
from yaspin import yaspin

from devrules.cli_commands.prompters.factory import get_default_prompter
from devrules.config import Config, load_config
from devrules.core.deployment_service import check_deployment_readiness, execute_deployment
from devrules.core.deployment_service import get_deployed_branch as _get_deployed_branch
from devrules.core.deployment_service import rollback_deployment
from devrules.core.enum import DevRulesEvent
from devrules.core.git_service import get_author, get_current_branch, get_current_repo_name
from devrules.core.permission_service import can_deploy_to_environment
from devrules.messages import deploy as msg
from devrules.notifications import emit
from devrules.notifications.events import DeployEvent
from devrules.utils.decorators import emit_events, ensure_git_repo

prompter = get_default_prompter()


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    """Register deployment commands.

    Args:
        app: Typer application instance.

    Returns:
        Dictionary mapping command names to their functions.
    """

    @app.command()
    @emit_events(DevRulesEvent.PRE_DEPLOY, DevRulesEvent.POST_DEPLOY)
    @ensure_git_repo()
    def deploy(
        environment: str = typer.Argument(..., help="Target environment (dev, staging, prod)"),
        branch: Optional[str] = typer.Option(
            None,
            "--branch",
            "-b",
            help="Branch to deploy (defaults to current branch)",
        ),
        skip_checks: bool = typer.Option(
            False,
            "--skip-checks",
            help="Skip migration and readiness checks",
        ),
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Force deployment without confirmation",
        ),
        config: Config = Depends(load_config),
    ):
        """Deploy a solution to a specific environment.

        This command follows the deployment workflow:
        1. Verify no migration conflicts
        2. Check currently deployed branch
        3. Confirm deployment with user
        4. Execute Jenkins deployment job
        5. Handle failures with rollback option
        """
        prompter.header("Deploy branch")

        # Validate environment configuration
        if environment not in config.deployment.environments:
            available = ", ".join(config.deployment.environments.keys())
            prompter.error(
                "Environment '{environment}' not configured",
            )
            prompter.info(f"Available environments: {available}")
            raise typer.Exit(code=1)

        env_config = config.deployment.environments[environment]

        # Permission check for deployment (--force does NOT bypass this)
        is_permitted, permission_msg = can_deploy_to_environment(environment, config)
        if permission_msg and is_permitted:
            # Warning case - allowed but with warning
            prompter.warning(permission_msg)
        elif not is_permitted:
            prompter.error(permission_msg)
            prompter.info(
                "Note: --force flag bypasses readiness checks only, not role-based permissions."
            )
            raise prompter.exit(1)

        # Determine branch to deploy
        if branch is None:
            branch = get_current_branch()
            prompter.info(f"Using current branch: {branch}")

        repo_path = str(Path.cwd())

        # Step 1: Get currently deployed branch
        with yaspin(text=f"Checking currently deployed branch in {environment}...") as spinner:
            deployed_branch = _get_deployed_branch(environment, config)
            spinner.stop()

        if deployed_branch:
            prompter.info(f"Currently deployed: {deployed_branch}")
        else:
            prompter.warning(
                f"Could not determine deployed branch, assuming: {env_config.default_branch}",
            )
            deployed_branch = env_config.default_branch

        # Step 3: Check deployment readiness
        if not skip_checks:
            with yaspin(text="Checking migration conflicts..."):
                is_ready, message = check_deployment_readiness(
                    repo_path, branch, environment, config
                )

            if not is_ready:
                prompter.error(f"Not ready: {message}")
                if not force:
                    raise prompter.exit(code=1)
                else:
                    prompter.warning(
                        "Proceeding anyway due to --force flag",
                    )
            else:
                prompter.success(message)

        # Step 4: Confirm deployment
        if config.deployment.require_confirmation and not force:
            prompter.info(f"Environment:      {environment}")
            prompter.info(f"Branch to deploy: {branch}")
            prompter.info(f"Current branch:   {deployed_branch}")
            prompter.info(f"Jenkins job:      {env_config.jenkins_job_name}")
            confirmed = prompter.confirm(
                msg.CONFIRM_DEPLOYMENT.format(branch, environment),
                default=False,
            )
            if not confirmed:
                prompter.error(msg.DEPLOYMENT_CANCELLED)
                raise prompter.exit(code=0)

        # Step 5: Execute deployment
        prompter.info(msg.DEPLOYING_TO_ENVIRONMENT.format(branch, environment))
        success, message = execute_deployment(branch, environment, config)

        if success:
            prompter.success(message)
            with yaspin(text="💬 Emitting deployment event...") as spinner:
                author = get_author()
                repo = config.github.repo or get_current_repo_name()
                spinner.stop()
                try:
                    emit(
                        DeployEvent(
                            repo=repo, branch=branch, environment=environment, author=author
                        )
                    )
                except RuntimeError as e:
                    prompter.warning(f"Failed to emit deployment event: {e}")
                    prompter.warning("Deployment will continue without event emission")
                else:
                    prompter.success("Deployment event emitted successfully")
            prompter.info(
                f"You can monitor the deployment at: {config.deployment.jenkins_url}/job/{env_config.jenkins_job_name.split('/')[0]}/job/{urllib.parse.quote(branch, safe='')}/"
            )
        else:
            prompter.error(
                f"Deployment failed: {message}",
            )

            # Offer rollback if auto_rollback is enabled
            if config.deployment.auto_rollback_on_failure:
                should_rollback = prompter.confirm(
                    f"¿Desea desplegar la rama '{deployed_branch}' para evitar bloquear el uso en '{environment}'?",
                    default=True,
                )

                if should_rollback:
                    prompter.info(f"🔄 Desplegando {deployed_branch} en {environment}...")
                    rollback_success, rollback_message = rollback_deployment(
                        environment, deployed_branch, config
                    )
                    if rollback_success:
                        prompter.success(
                            f"Rollback successful: {rollback_message}",
                        )
                    else:
                        prompter.error(
                            f"Rollback failed: {rollback_message}",
                        )
                        raise prompter.exit(1)

            raise prompter.exit(1)

    @app.command()
    @ensure_git_repo()
    def check_deployment(
        environment: str = typer.Argument(..., help="Target environment"),
        branch: Optional[str] = typer.Option(
            None,
            "--branch",
            "-b",
            help="Branch to check (defaults to current branch)",
        ),
        config: Config = Depends(load_config),
    ):
        """Check if a branch is ready for deployment without deploying.

        This performs all pre-deployment checks:
        - Migration conflict detection
        - Deployment readiness validation
        - Currently deployed branch information
        """
        prompter.header("Checking deployment readiness")

        # Determine branch
        if branch is None:
            branch = get_current_branch()

        # Validate environment
        if environment not in config.deployment.environments:
            available = ", ".join(config.deployment.environments.keys())
            prompter.error(f"Environment '{environment}' not configured")
            prompter.info(f"Available environments: {available}")
            raise prompter.exit(code=1)

        repo_path = str(Path.cwd())

        # Get deployed branch
        with yaspin(text="Getting deployed branch..."):
            deployed_branch = _get_deployed_branch(environment, config)

        if deployed_branch:
            prompter.info(f"Currently deployed branch: {deployed_branch}")
        else:
            prompter.error("Could not detect deployed branch")
            raise prompter.exit(1)

        # Check readiness
        with yaspin(text="Checking migration conflicts..."):
            is_ready, message = check_deployment_readiness(
                repo_path, branch, environment, config, deployed_branch=deployed_branch
            )

        if is_ready:
            prompter.success("No migrations conflicts detected")
            prompter.success(f"Branch '{branch}' is ready for deployment to '{environment}'")
        else:
            prompter.error(message)
            raise prompter.exit(code=1)

    @app.command()
    @ensure_git_repo()
    def get_deployed_branch(
        environment: str = typer.Argument(..., help="Target environment (dev, staging, prod)"),
        config: Config = Depends(load_config),
    ):
        """Get the currently deployed branch for the given environment."""
        prompter.header("Get deployed branch")
        # Get deployed branch
        with yaspin(text="Getting deployed branch..."):
            deployed_branch = _get_deployed_branch(environment, config)
        prompter.info(f"Currently deployed branch on {environment}: {deployed_branch}")

    return {
        "deploy": deploy,
        "check_deployment": check_deployment,
        "get_deployed_branch": get_deployed_branch,
    }
