"""Deployment CLI commands for DevRules."""

from pathlib import Path
from typing import Any, Callable, Dict, Optional

import typer

from devrules.config import load_config
from devrules.core.deployment_service import (
    check_deployment_readiness,
    check_migration_conflicts,
    execute_deployment,
    get_deployed_branch,
    rollback_deployment,
)
from devrules.core.git_service import ensure_git_repo, get_current_branch
from devrules.messages import deploy as msg
from devrules.utils.typer import add_typer_block_message


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command()
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
    ):
        """Deploy a solution to a specific environment.

        This command follows the deployment workflow:
        1. Verify no migration conflicts
        2. Check currently deployed branch
        3. Confirm deployment with user
        4. Execute Jenkins deployment job
        5. Handle failures with rollback option
        """
        ensure_git_repo()
        config = load_config(None)

        # Validate environment configuration
        if environment not in config.deployment.environments:
            available = ", ".join(config.deployment.environments.keys())
            typer.secho(
                f"✘ Environment '{environment}' not configured",
                fg=typer.colors.RED,
            )
            typer.echo(f"Available environments: {available}")
            raise typer.Exit(code=1)

        env_config = config.deployment.environments[environment]

        # Determine branch to deploy
        if branch is None:
            branch = get_current_branch()
            typer.echo(f"📌 Using current branch: {branch}")

        repo_path = str(Path.cwd())

        # Step 1: Get currently deployed branch
        typer.echo(f"\n🔍 Checking currently deployed branch in {environment}...")
        deployed_branch = get_deployed_branch(environment, config)

        if deployed_branch:
            typer.secho(
                f"✔ Currently deployed: {deployed_branch}",
                fg=typer.colors.GREEN,
            )
        else:
            typer.secho(
                f"⚠ Could not determine deployed branch, assuming: {env_config.default_branch}",
                fg=typer.colors.YELLOW,
            )
            deployed_branch = env_config.default_branch

        # Step 2: Check for migration conflicts (unless skipped)
        if not skip_checks and config.deployment.migration_detection_enabled:
            typer.echo("\n🔍 Checking for migration conflicts...")
            has_conflicts, conflicting_files = check_migration_conflicts(
                repo_path, branch, deployed_branch, config
            )

            if has_conflicts:
                typer.secho(
                    "⚠ Migration conflicts detected!",
                    fg=typer.colors.YELLOW,
                    bold=True,
                )
                typer.echo("\nConflicting migration files:")
                for file in conflicting_files:
                    typer.echo(f"  - {file}")

                typer.echo("\n⚠ Both branches have new migrations. This may cause issues.")

                if not force:
                    should_continue = typer.confirm(
                        "\nDo you want to continue anyway?",
                        default=False,
                    )
                    if not should_continue:
                        typer.echo("Deployment cancelled.")
                        raise typer.Exit(code=0)
            elif conflicting_files:
                typer.secho(
                    f"✔ Found {len(conflicting_files)} new migration(s), no conflicts",
                    fg=typer.colors.GREEN,
                )
            else:
                typer.secho(
                    "✔ No migration changes detected",
                    fg=typer.colors.GREEN,
                )

        # Step 3: Check deployment readiness
        if not skip_checks:
            typer.echo("\n🔍 Checking deployment readiness...")
            is_ready, message = check_deployment_readiness(repo_path, branch, environment, config)

            if not is_ready:
                typer.secho(f"✘ Not ready: {message}", fg=typer.colors.RED)
                if not force:
                    raise typer.Exit(code=1)
                else:
                    typer.secho(
                        "⚠ Proceeding anyway due to --force flag",
                        fg=typer.colors.YELLOW,
                    )
            else:
                typer.secho(f"✔ {message}", fg=typer.colors.GREEN)

        # Step 4: Confirm deployment
        if config.deployment.require_confirmation and not force:
            add_typer_block_message(
                header="📋 Deployment Summary",
                subheader="",
                messages=[
                    f"Environment:      {environment}",
                    f"Branch to deploy: {branch}",
                    f"Current branch:   {deployed_branch}",
                    f"Jenkins job:      {env_config.jenkins_job_name}",
                ],
            )

            confirmed = typer.confirm(
                msg.CONFIRM_DEPLOYMENT.format(branch, environment),
                default=False,
            )

            if not confirmed:
                typer.echo(msg.DEPLOYMENT_CANCELLED)
                raise typer.Exit(code=0)

        # Step 5: Execute deployment
        typer.echo(f"\n{msg.DEPLOYING_TO_ENVIRONMENT.format(branch, environment)}")
        success, message = execute_deployment(branch, environment, config)

        if success:
            typer.secho(
                f"\n✔ {message}",
                fg=typer.colors.GREEN,
                bold=True,
            )
            typer.echo(
                f"\n💡 Monitor the deployment at: {config.deployment.jenkins_url}/job/{env_config.jenkins_job_name}"
            )
        else:
            typer.secho(
                f"\n✘ Deployment failed: {message}",
                fg=typer.colors.RED,
                bold=True,
            )

            # Offer rollback if auto_rollback is enabled
            if config.deployment.auto_rollback_on_failure:
                should_rollback = typer.confirm(
                    f"\n¿Desea desplegar la rama '{deployed_branch}' para evitar bloquear el uso en '{environment}'?",
                    default=True,
                )

                if should_rollback:
                    typer.echo(f"\n🔄 Desplegando {deployed_branch} en {environment}...")
                    rollback_success, rollback_message = rollback_deployment(
                        environment, deployed_branch, config
                    )

                    if rollback_success:
                        typer.secho(
                            f"✔ Rollback successful: {rollback_message}",
                            fg=typer.colors.GREEN,
                        )
                    else:
                        typer.secho(
                            f"✘ Rollback failed: {rollback_message}",
                            fg=typer.colors.RED,
                        )
                        raise typer.Exit(code=1)

            raise typer.Exit(code=1)

    @app.command()
    def check_deployment(
        environment: str = typer.Argument(..., help="Target environment"),
        branch: Optional[str] = typer.Option(
            None,
            "--branch",
            "-b",
            help="Branch to check (defaults to current branch)",
        ),
    ):
        """Check if a branch is ready for deployment without deploying.

        This performs all pre-deployment checks:
        - Migration conflict detection
        - Deployment readiness validation
        - Currently deployed branch information
        """
        ensure_git_repo()
        config = load_config(None)

        # Validate environment
        if environment not in config.deployment.environments:
            available = ", ".join(config.deployment.environments.keys())
            typer.secho(
                f"✘ Environment '{environment}' not configured",
                fg=typer.colors.RED,
            )
            typer.echo(f"Available environments: {available}")
            raise typer.Exit(code=1)

        # Determine branch
        if branch is None:
            branch = get_current_branch()

        repo_path = str(Path.cwd())

        typer.secho(
            f"\n🔍 Checking deployment readiness for '{branch}' → '{environment}'",
            fg=typer.colors.CYAN,
            bold=True,
        )

        # Get deployed branch
        typer.echo("\n📌 Currently deployed branch:")
        deployed_branch = get_deployed_branch(environment, config)
        if deployed_branch:
            typer.secho(f"   {deployed_branch}", fg=typer.colors.GREEN)
        else:
            typer.secho("   Unknown", fg=typer.colors.YELLOW)
            deployed_branch = config.deployment.environments[environment].default_branch

        # Check readiness
        is_ready, message = check_deployment_readiness(repo_path, branch, environment, config)

        typer.echo("\n📋 Deployment Status:")
        if is_ready:
            typer.secho(f"   ✔ {message}", fg=typer.colors.GREEN)
            typer.echo(f"\n✅ Branch '{branch}' is ready for deployment to '{environment}'")
        else:
            typer.secho(f"   ✘ {message}", fg=typer.colors.RED)
            typer.echo(f"\n❌ Branch '{branch}' is NOT ready for deployment")
            raise typer.Exit(code=1)

    return {
        "deploy": deploy,
        "check_deployment": check_deployment,
    }
