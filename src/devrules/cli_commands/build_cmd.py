"""Enterprise build command."""

import os
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import toml
import typer
from yaspin import yaspin

from devrules.cli_commands.prompters.factory import get_default_prompter
from devrules.config import load_config
from devrules.enterprise.builder import EnterpriseBuilder

prompter = get_default_prompter()


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    """Register enterprise build command.

    Args:
        app: Typer application instance

    Returns:
        Dictionary mapping command names to their functions
    """

    @app.command()
    def build_enterprise(
        config_file: str = typer.Option(
            ..., "--config", "-c", help="Path to enterprise configuration file"
        ),
        output_dir: str = typer.Option(
            "dist", "--output", "-o", help="Output directory for build artifacts"
        ),
        package_name: Optional[str] = typer.Option(
            None, "--name", "-n", help="Custom package name (e.g., devrules-mycompany)"
        ),
        encrypt: bool = typer.Option(
            True, "--encrypt/--no-encrypt", help="Encrypt sensitive fields"
        ),
        sensitive_fields: Optional[str] = typer.Option(
            None,
            "--sensitive",
            help="Comma-separated list of fields to encrypt (e.g., github.api_url,github.owner)",
        ),
        version_suffix: str = typer.Option(
            "enterprise", "--suffix", help="Version suffix for enterprise build"
        ),
        keep_config: bool = typer.Option(
            False,
            "--keep-config",
            help="Keep embedded config after build (for debugging)",
        ),
    ):
        """Build enterprise package with embedded configuration.

        This command creates a customized build of devrules with:
        - Embedded corporate configuration
        - Optional encryption of sensitive fields
        - Integrity verification
        - Locked configuration (prevents user overrides)

        Example:
            devrules build-enterprise \\
                --config .devrules.enterprise.toml \\
                --name devrules-mycompany \\
                --sensitive github.api_url,github.owner
        """
        prompter.header("Build enterprise")
        try:
            # Validate config file exists
            if not os.path.exists(config_file):
                prompter.error(
                    f"Configuration file not found: {config_file}",
                )
                raise prompter.exit(code=1)

            # Get project root
            project_root = Path.cwd()
            if not (project_root / "pyproject.toml").exists():
                prompter.error(
                    "Must be run from project root (pyproject.toml not found)",
                )
                raise prompter.exit(code=1)

            prompter.info("Building enterprise package...")

            # Initialize builder
            builder = EnterpriseBuilder(project_root)

            # Parse sensitive fields
            fields_list: Optional[List[str]] = None
            if sensitive_fields:
                fields_list = [f.strip() for f in sensitive_fields.split(",")]

            # Backup pyproject.toml
            pyproject_backup = project_root / "pyproject.toml.backup"
            shutil.copy(project_root / "pyproject.toml", pyproject_backup)

            try:
                # Step 1: Embed configuration
                prompter.info("Embedding configuration...")
                config_path, encryption_key = builder.embed_config(
                    config_file,
                    encrypt=encrypt,
                    sensitive_fields=fields_list,
                )
                prompter.success(f"Config embedded: {config_path}")

                # Save encryption key if used
                key_file = None
                if encryption_key:
                    key_file = project_root / output_dir / "encryption.key"
                    key_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(key_file, "wb") as f:
                        f.write(encryption_key)
                    prompter.success(f"Encryption key saved: {key_file}")

                # Step 2: Modify package metadata
                prompter.info("Modifying package metadata...")
                builder.modify_package_metadata(package_name, version_suffix)
                prompter.success("Metadata updated")

                # Step 3: Build package
                prompter.info("Building package...")
                output_path = builder.build_package(output_dir)
                prompter.success(f"Package built: {output_path}")

                # Step 4: Create distribution README
                prompter.info("Creating distribution README...")
                readme_content = builder.create_distribution_readme(
                    package_name or "devrules-enterprise",
                    has_encryption=encryption_key is not None,
                )
                readme_path = output_path / "DISTRIBUTION_README.md"
                with open(readme_path, "w") as f:  # type: ignore
                    f.write(readme_content)
                prompter.success(f"README created: {readme_path}")

                # Success message
                prompter.success(
                    "Enterprise build completed successfully!",
                )
                prompter.info(
                    "Build artifacts:",
                )
                prompter.indented_message(f"• Package: {output_path}/*.whl")
                if key_file:
                    prompter.indented_message(f"• Encryption key: {key_file}")
                    prompter.indented_message(f"• README: {readme_path}")
                    prompter.warning(
                        "IMPORTANT: Keep encryption.key secure!",
                    )
                    prompter.info(
                        "Set DEVRULES_ENTERPRISE_KEY environment variable for production use"
                    )

            finally:
                # Restore pyproject.toml
                builder.restore_package_metadata(pyproject_backup)
                pyproject_backup.unlink()

                # Cleanup embedded config unless --keep-config
                if not keep_config:
                    builder.cleanup_embedded_config()

        except Exception as e:
            prompter.error(f"Build failed: {e}")
            raise prompter.exit(code=1)

    @app.command()
    def add_github_projects(
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to configuration file (defaults to .devrules.toml)"
        ),
        owner: Optional[str] = typer.Option(
            None, "--owner", "-o", help="GitHub owner/organization (defaults to config)"
        ),
        filter_query: Optional[str] = typer.Option(
            None, "--filter", "-f", help="Filter projects by name (case-insensitive)"
        ),
    ):
        """Interactively fetch and add GitHub Projects to configuration.

        This command fetches all GitHub Projects from an owner/organization
        and allows you to select which ones to add to your configuration.

        Example:
            devrules add-github-projects --owner mycompany --filter backend
        """
        prompter.header("Add GitHub projects to DevRules config")
        try:
            # Load current config
            config = load_config(config_file)

            # Determine owner
            github_owner = owner or config.github.owner
            if not github_owner:
                prompter.error(
                    "GitHub owner must be provided via --owner or configured in the config file"
                )
                raise prompter.exit(code=1)

            # Get GitHub token
            token = os.getenv("GH_TOKEN")
            if not token:
                prompter.error(
                    "GH_TOKEN environment variable not set",
                )
                prompter.info("Set it with: export GH_TOKEN='your-github-token'")
                raise prompter.exit(code=1)

            # Determine config file path
            if config_file:
                config_path = Path(config_file)
            else:
                from devrules.config import find_config_file

                config_path = find_config_file()
                if not config_path:
                    config_path = Path(".devrules.toml")
                    if not config_path.exists():
                        prompter.error(
                            "Configuration file not found. Run 'devrules init-config' first.",
                        )
                        raise prompter.exit(code=1)

            with yaspin(
                text=f"Fetching GitHub Projects for {github_owner}...",
            ) as spinner:
                # Use gh CLI to fetch projects
                import json
                import subprocess

                try:
                    result = subprocess.run(
                        [
                            "gh",
                            "project",
                            "list",
                            "--owner",
                            github_owner,
                            "--format",
                            "json",
                            "--limit",
                            "100",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    if result.returncode != 0:
                        spinner.stop()
                        prompter.error(
                            "Failed to fetch projects. Make sure 'gh' CLI is installed and authenticated."
                        )
                        raise prompter.exit(code=1)

                    if not result.stdout.strip():
                        spinner.stop()
                        prompter.error(f"No projects found for {github_owner}")
                        raise prompter.exit(code=0)

                    projects_data = json.loads(result.stdout)
                    if isinstance(projects_data, dict) and "projects" in projects_data:
                        projects_list = projects_data["projects"]
                    else:
                        projects_list = projects_data

                    if not projects_list:
                        spinner.stop()
                        prompter.error(f"No projects found for {github_owner}")
                        raise prompter.exit(code=0)

                    # Filter projects if requested
                    if filter_query:
                        filtered_projects = [
                            p
                            for p in projects_list
                            if filter_query.lower() in (p.get("title") or p.get("name", "")).lower()
                        ]
                        if not filtered_projects:
                            spinner.stop()
                            prompter.warning(
                                f"No projects match filter '{filter_query}'",
                            )
                            raise prompter.exit(code=0)
                        projects_list = filtered_projects

                    spinner.stop()
                    prompter.success(f"Found {len(projects_list)} projects")

                except json.JSONDecodeError as e:
                    spinner.stop()
                    prompter.error(f"Failed to parse projects data: {e}")
                    raise prompter.exit(code=1)
                except subprocess.TimeoutExpired:
                    spinner.stop()
                    prompter.error("Request timed out while fetching projects")
                    raise prompter.exit(code=1)
                except Exception as e:
                    spinner.stop()
                    prompter.error(f"Error fetching projects: {e}")
                    raise prompter.exit(code=1)

            # Load current config file to preserve formatting
            with open(config_path, "r") as f:
                config_data = toml.load(f)

            # Get existing projects
            existing_projects = config_data.get("github", {}).get("projects", {})

            prompter.info("Available Projects:")

            # Load projects
            options = []
            selected_options = []
            for idx, proj in enumerate(projects_list, 1):
                proj_number = proj.get("number")
                proj_title = proj.get("title") or proj.get("name", "")

                # Check if already configured
                is_configured = False
                for existing_value in existing_projects.values():
                    if f"#{proj_number}" in str(existing_value):
                        is_configured = True
                        break

                options.append(proj_title)
                if is_configured:
                    selected_options.append(proj_title)

            selected_projects = prompter.choose(
                options=options,
                header="Select projects to add to configuration:",
                limit=0,
                defaults=selected_options,
            )
            selected_projects_values = []
            for proj in projects_list:
                proj_title = proj.get("title") or proj.get("name", "")
                if proj_title not in selected_projects:
                    continue
                proj_number = proj.get("number")
                project_value = f"{proj_title} (#{proj_number})"
                selected_projects_values.append((proj_title, project_value))

            if len(existing_projects) == len(selected_projects) == 1:
                prompter.info("Only one project exists. Auto selection was applied.")

            if not selected_projects:
                prompter.error("No projects selected.")
                raise prompter.exit(code=0)

            # Add selected projects to config
            prompter.info(
                f"Adding {len(selected_projects)} projects to configuration...",
            )

            if "github" not in config_data:
                config_data["github"] = {}
            if "projects" not in config_data["github"]:
                config_data["github"]["projects"] = {}

            added_count = 0
            skipped_count = 0

            for proj, project_value in selected_projects_values:
                # Generate a unique key from project title
                key = proj.lower().replace(" ", "_").replace("-", "_")
                # Remove special characters
                key = "".join(c for c in key if c.isalnum() or c == "_")

                # Check if already configured
                already_exists = False
                if key in existing_projects:
                    already_exists = True
                    break

                if already_exists:
                    prompter.warning(f"Skipped (already configured): {proj}")
                    skipped_count += 1
                else:
                    # Ensure uniqueness
                    counter = 1
                    base_key = key
                    while key in config_data["github"]["projects"]:
                        key = f"{base_key}_{counter}"
                        counter += 1

                    config_data["github"]["projects"][key] = project_value
                    prompter.success(f"Added: {proj}")
                    added_count += 1

            if added_count == 0:
                prompter.info(
                    "No new projects to add (all were already configured)",
                )
                raise prompter.exit(code=0)

            # Write updated config
            with open(config_path, "w") as f:
                toml.dump(config_data, f)

            enable_cache = prompter.confirm(
                "Enable GitHub Project metadata cache (faster project commands)?",
                default=bool(config_data.get("github", {}).get("project_cache_enabled", False)),
            )

            if enable_cache:
                if "github" not in config_data:
                    config_data["github"] = {}
                config_data["github"]["project_cache_enabled"] = True

                default_cache_path = config_data.get("github", {}).get("project_cache_path") or ""
                cache_path = prompter.input_text(
                    placeholder="Project cache path (leave empty for default)",
                    default=str(default_cache_path),
                ).strip()
                config_data["github"]["project_cache_path"] = cache_path or None

                # Persist cache settings before preloading so project_service sees it via load_config(None)
                with open(config_path, "w") as f:
                    toml.dump(config_data, f)

                preload_cache = prompter.confirm(
                    "Preload cache now for selected projects?",
                    default=True,
                )
                if preload_cache:
                    from devrules.core.project_service import get_project_id, get_status_field_id

                    with yaspin(text="Preloading project cache...") as spinner:
                        for exist in existing_projects:
                            proj_title = exist.get("title") or exist.get("name", "")
                            if proj_title not in selected_options:
                                continue
                            proj_number = exist.get("number")
                            if not proj_number:
                                continue
                            get_project_id(github_owner, str(proj_number))
                            get_status_field_id(github_owner, str(proj_number))
                        spinner.ok("✔")
            else:
                if "github" not in config_data:
                    config_data["github"] = {}
                config_data["github"]["project_cache_enabled"] = False

            with open(config_path, "w") as f:
                toml.dump(config_data, f)

            prompter.success(
                f"Successfully added {added_count} projects to {config_path}",
            )

            # Show summary of added projects
            prompter.info("Added projects:")
            for proj in selected_projects:
                # Check if it was added or skipped
                was_skipped = False
                for existing_value in existing_projects.values():
                    if f"#{proj_number}" in str(existing_value):
                        was_skipped = True
                        break

                if not was_skipped:
                    prompter.indented_message(f"• {proj}")

            prompter.info("Next steps:")
            prompter.indented_message("• View config: cat .devrules.toml")
            prompter.indented_message(
                "• List issues: devrules list-issues --project <project-name>"
            )
            prompter.indented_message("• Dashboard: devrules dashboard")

        except typer.Exit:
            raise
        except Exception as e:
            prompter.error(f" Error: {e}")
            raise prompter.exit(code=1)

    @app.command()
    def add_role(
        role_name: str = typer.Argument(..., help="Name of the role to add or edit"),
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to configuration file"
        ),
    ):
        """Add or update a role and its permissions interactively.

        This command allows you to define which statuses a role can transition to
        and which environments it can deploy to.
        """
        prompter.header("Add role to config")
        try:
            # Determine config file path
            if config_file:
                config_path = Path(config_file)
            else:
                from devrules.config import find_config_file

                config_path = find_config_file()
                if not config_path:
                    config_path = Path(".devrules.toml")
                    if not config_path.exists():
                        prompter.error(
                            "Configuration file not found. Run 'devrules init-config' first.",
                        )
                        raise prompter.exit(code=1)

            # Load current config to preserve formatting as much as possible
            with open(config_path, "r") as f:
                config_data = toml.load(f)

            if "permissions" not in config_data:
                config_data["permissions"] = {}
            if "roles" not in config_data["permissions"]:
                config_data["permissions"]["roles"] = {}

            # Get existing role data if it exists
            existing_role = config_data["permissions"]["roles"].get(role_name, {})

            prompter.info(f"Configuring permissions for role: {role_name}")

            # Get available statuses (from config or defaults)
            from devrules.cli_commands.project import _get_valid_statuses

            valid_statuses = _get_valid_statuses()

            # Select allowed statuses
            selected_statuses = prompter.choose(
                options=valid_statuses,
                header=f"Select allowed statuses for '{role_name}'",
                limit=0,
                defaults=existing_role.get("allowed_statuses", []),
            )
            if selected_statuses is None:
                selected_statuses = []
            elif isinstance(selected_statuses, str):
                selected_statuses = [selected_statuses]

            # Get available environments
            environments = list(config_data.get("deployment", {}).get("environments", {}).keys())
            if not environments:
                environments = ["dev", "staging", "prod"]

            selected_envs = prompter.choose(
                options=environments,
                header=f"Select deployable environments for '{role_name}'",
                limit=0,
                defaults=existing_role.get("deployable_environments", []),
            )
            if selected_envs is None:
                selected_envs = []
            elif isinstance(selected_envs, str):
                selected_envs = [selected_envs]

            # Update the role
            config_data["permissions"]["roles"][role_name] = {
                "allowed_statuses": selected_statuses,
                "deployable_environments": selected_envs,
            }

            # Save back to config
            with open(config_path, "w") as f:
                toml.dump(config_data, f)

            prompter.success(
                f"Role '{role_name}' updated successfully in {config_path}",
            )

        except Exception as e:
            prompter.error(f"Error configuring role: {e}")
            raise prompter.exit(code=1)

    @app.command()
    def assign_role(
        user: Optional[str] = typer.Option(
            None, "--user", "-u", help="GitHub username to assign role to"
        ),
        role: Optional[str] = typer.Option(None, "--role", "-r", help="Role name to assign"),
        config_file: Optional[str] = typer.Option(
            None, "--config", "-c", help="Path to configuration file"
        ),
    ):
        """Interactively assign a role to a GitHub user.

        Fetches users from current GitHub repository and roles from configuration.
        """
        prompter.header("Assigne role to user")
        try:
            from devrules.config import find_config_file

            # Determine config path
            if config_file:
                config_path = Path(config_file)
            else:
                config_path = find_config_file()
                if not config_path:
                    config_path = Path(".devrules.toml")

            # Load config data
            with open(config_path, "r") as f:
                config_data = toml.load(f)

            # Get available roles
            roles = list(config_data.get("permissions", {}).get("roles", {}).keys())
            if not roles:
                prompter.error(
                    "No roles defined in configuration. Run 'add-role' first.",
                )
                raise prompter.exit(code=1)

            # Fetch users from GitHub
            selected_user = user
            if not selected_user:
                with yaspin(text="Fetching collaborators from GitHub...") as spinner:
                    import json
                    import subprocess

                    try:
                        # Get github repo info from config
                        owner = config_data.get("github", {}).get("owner")
                        repo = config_data.get("github", {}).get("repo")

                        if not owner or not repo:
                            # Try to get from git remote if not in config
                            result = subprocess.run(
                                ["gh", "repo", "view", "--json", "owner,name"],
                                capture_output=True,
                                text=True,
                            )
                            if result.returncode == 0:
                                repo_info = json.loads(result.stdout)
                                owner = repo_info["owner"]["login"]
                                repo = repo_info["name"]

                        if not owner or not repo:
                            prompter.error("Could not determine GitHub owner/repo")
                            raise prompter.exit(code=1)

                        # Fetch collaborators with full names using GraphQL
                        query = """
                        query($owner: String!, $repo: String!) {
                        repository(owner: $owner, name: $repo) {
                            collaborators(first: 100) {
                            nodes {
                                login
                                name
                            }
                            }
                        }
                        }
                        """
                        result = subprocess.run(
                            [
                                "gh",
                                "api",
                                "graphql",
                                "-f",
                                f"owner={owner}",
                                "-f",
                                f"repo={repo}",
                                "-f",
                                f"query={query}",
                            ],
                            capture_output=True,
                            text=True,
                        )
                    except Exception as e:
                        prompter.error(f"Error fetching collaborators from GitHub: {e}")
                        raise prompter.exit(code=1)
                    spinner.ok("✔")

                if result.returncode != 0:
                    prompter.error("Failed to fetch collaborators from GitHub")
                    if result.stderr:
                        prompter.info(result.stderr)
                    raise prompter.exit(code=1)

                data = json.loads(result.stdout)
                nodes = (
                    data.get("data", {})
                    .get("repository", {})
                    .get("collaborators", {})
                    .get("nodes", [])
                )

                if not nodes:
                    prompter.warning("No collaborators found for this repository")
                    selected_user = prompter.input_text(
                        "Enter GitHub full name manually (should match git config user.name)"
                    )
                else:
                    # Create mapping for selection
                    # display_string -> {full_name, login}
                    user_map = {}
                    for node in nodes:
                        login = node["login"]
                        name = node.get("name") or login
                        display = f"{name} ({login})" if node.get("name") else login
                        user_map[display] = {"name": name, "login": login}

                    options = list(user_map.keys())

                    display_choice = prompter.choose(options, header="Select user to assign role")
                    if not display_choice:
                        prompter.error("No user selected")
                        raise prompter.exit(code=1)

                    selected_user = user_map[display_choice]["name"]

            # Selection role
            selected_role = role
            if not selected_role:
                selected_role = prompter.choose(roles, header=f"Assign role to '{selected_user}'")
                if not selected_role:
                    prompter.error("No role selected")
                    raise prompter.exit(code=1)

            # Update assignments
            if "permissions" not in config_data:
                config_data["permissions"] = {}
            if "user_assignments" not in config_data["permissions"]:
                config_data["permissions"]["user_assignments"] = {}

            config_data["permissions"]["user_assignments"][selected_user] = selected_role

            # Save back to config
            with open(config_path, "w") as f:
                toml.dump(config_data, f)

            prompter.success(
                f"User '{selected_user}' assigned to role '{selected_role}'",
            )

        except Exception as e:
            prompter.error(f"Error assigning role: {e}")
            raise prompter.exit(code=1)

    return {
        "build_enterprise": build_enterprise,
        "add_github_projects": add_github_projects,
        "add_role": add_role,
        "assign_role": assign_role,
    }
