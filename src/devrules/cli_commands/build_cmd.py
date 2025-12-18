"""Enterprise build command."""

import os
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import toml
import typer

from devrules.config import load_config
from devrules.enterprise.builder import EnterpriseBuilder


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
        try:
            # Validate config file exists
            if not os.path.exists(config_file):
                typer.secho(
                    f"✘ Configuration file not found: {config_file}",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)

            # Get project root
            project_root = Path.cwd()
            if not (project_root / "pyproject.toml").exists():
                typer.secho(
                    "✘ Must be run from project root (pyproject.toml not found)",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)

            typer.secho("\n🏗️  Building enterprise package...", fg=typer.colors.CYAN, bold=True)

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
                typer.secho("📦 Embedding configuration...", fg=typer.colors.BLUE)
                config_path, encryption_key = builder.embed_config(
                    config_file,
                    encrypt=encrypt,
                    sensitive_fields=fields_list,
                )
                typer.secho(f"   ✓ Config embedded: {config_path}", fg=typer.colors.GREEN)

                # Save encryption key if used
                key_file = None
                if encryption_key:
                    key_file = project_root / output_dir / "encryption.key"
                    key_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(key_file, "wb") as f:
                        f.write(encryption_key)
                    typer.secho(f"   ✓ Encryption key saved: {key_file}", fg=typer.colors.GREEN)

                # Step 2: Modify package metadata
                typer.secho("📝 Modifying package metadata...", fg=typer.colors.BLUE)
                builder.modify_package_metadata(package_name, version_suffix)
                typer.secho("   ✓ Metadata updated", fg=typer.colors.GREEN)

                # Step 3: Build package
                typer.secho("🔨 Building package...", fg=typer.colors.BLUE)
                output_path = builder.build_package(output_dir)
                typer.secho(f"   ✓ Package built: {output_path}", fg=typer.colors.GREEN)

                # Step 4: Create distribution README
                typer.secho("📄 Creating distribution README...", fg=typer.colors.BLUE)
                readme_content = builder.create_distribution_readme(
                    package_name or "devrules-enterprise",
                    has_encryption=encryption_key is not None,
                )
                readme_path = output_path / "DISTRIBUTION_README.md"
                with open(readme_path, "w") as f:  # type: ignore
                    f.write(readme_content)
                typer.secho(f"   ✓ README created: {readme_path}", fg=typer.colors.GREEN)

                # Success message
                typer.secho(
                    "\n✅ Enterprise build completed successfully!",
                    fg=typer.colors.GREEN,
                    bold=True,
                )
                typer.secho("\n📦 Build artifacts:", fg=typer.colors.CYAN)
                typer.secho(f"   • Package: {output_path}/*.whl")
                if key_file:
                    typer.secho(f"   • Encryption key: {key_file}")
                    typer.secho(
                        f"   • README: {readme_path}\n",
                    )
                    typer.secho(
                        "⚠️  IMPORTANT: Keep encryption.key secure!",
                        fg=typer.colors.YELLOW,
                        bold=True,
                    )
                    typer.secho(
                        "   Set DEVRULES_ENTERPRISE_KEY environment variable for production use.\n"
                    )

            finally:
                # Restore pyproject.toml
                builder.restore_package_metadata(pyproject_backup)
                pyproject_backup.unlink()

                # Cleanup embedded config unless --keep-config
                if not keep_config:
                    builder.cleanup_embedded_config()

        except Exception as e:
            typer.secho(f"\n✘ Build failed: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

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
        try:
            # Load current config
            config = load_config(config_file)

            # Determine owner
            github_owner = owner or config.github.owner
            if not github_owner:
                typer.secho(
                    "✘ GitHub owner must be provided via --owner or configured in the config file",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)

            # Get GitHub token
            token = os.getenv("GH_TOKEN")
            if not token:
                typer.secho(
                    "✘ GH_TOKEN environment variable not set",
                    fg=typer.colors.RED,
                )
                typer.echo("  Set it with: export GH_TOKEN='your-github-token'")
                raise typer.Exit(code=1)

            # Determine config file path
            if config_file:
                config_path = Path(config_file)
            else:
                from devrules.config import find_config_file

                config_path = find_config_file()
                if not config_path:
                    config_path = Path(".devrules.toml")
                    if not config_path.exists():
                        typer.secho(
                            "✘ Configuration file not found. Run 'devrules init-config' first.",
                            fg=typer.colors.RED,
                        )
                        raise typer.Exit(code=1)

            typer.secho(
                f"\n🔍 Fetching GitHub Projects for {github_owner}...",
                fg=typer.colors.CYAN,
                bold=True,
            )

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
                    typer.secho(
                        "✘ Failed to fetch projects. Make sure 'gh' CLI is installed and authenticated.",
                        fg=typer.colors.RED,
                    )
                    if result.stderr:
                        typer.echo(result.stderr)
                    raise typer.Exit(code=1)

                if not result.stdout.strip():
                    typer.secho(f"✘ No projects found for {github_owner}", fg=typer.colors.YELLOW)
                    raise typer.Exit(code=0)

                projects_data = json.loads(result.stdout)
                if isinstance(projects_data, dict) and "projects" in projects_data:
                    projects_list = projects_data["projects"]
                else:
                    projects_list = projects_data

                if not projects_list:
                    typer.secho(f"✘ No projects found for {github_owner}", fg=typer.colors.YELLOW)
                    raise typer.Exit(code=0)

                # Filter projects if requested
                if filter_query:
                    filtered_projects = [
                        p
                        for p in projects_list
                        if filter_query.lower() in (p.get("title") or p.get("name", "")).lower()
                    ]
                    if not filtered_projects:
                        typer.secho(
                            f"✘ No projects match filter '{filter_query}'",
                            fg=typer.colors.YELLOW,
                        )
                        raise typer.Exit(code=0)
                    projects_list = filtered_projects

                typer.secho(f"✓ Found {len(projects_list)} projects", fg=typer.colors.GREEN)

            except json.JSONDecodeError as e:
                typer.secho(f"✘ Failed to parse projects data: {e}", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            except subprocess.TimeoutExpired:
                typer.secho("✘ Request timed out while fetching projects", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            except Exception as e:
                typer.secho(f"✘ Error fetching projects: {e}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

            # Load current config file to preserve formatting
            with open(config_path, "r") as f:
                config_data = toml.load(f)

            # Get existing projects
            existing_projects = config_data.get("github", {}).get("projects", {})

            typer.secho("\n📊 Available Projects:", fg=typer.colors.CYAN)
            typer.echo("   (Already configured projects will be marked with ✓)\n")

            # Show projects
            for idx, proj in enumerate(projects_list, 1):
                proj_number = proj.get("number")
                proj_title = proj.get("title") or proj.get("name", "")

                # Check if already configured
                is_configured = False
                for existing_value in existing_projects.values():
                    if f"#{proj_number}" in str(existing_value):
                        is_configured = True
                        break

                status = "✓" if is_configured else " "
                typer.echo(f"  [{status}] {idx:2d}. {proj_title} (#{proj_number})")

            typer.echo("\n" + "─" * 60)
            typer.secho("Selection options:", fg=typer.colors.CYAN)
            typer.echo("  • Single: 1")
            typer.echo("  • Multiple: 1,3,5")
            typer.echo("  • Range: 1-5")
            typer.echo("  • All: all")
            typer.echo("  • Skip: press Enter")
            typer.echo("─" * 60)

            selection = typer.prompt("\nYour selection", default="", show_default=False)

            if not selection.strip():
                typer.secho("No projects selected.", fg=typer.colors.YELLOW)
                raise typer.Exit(code=0)

            # Parse selection
            selected_projects = []
            if selection.lower() == "all":
                selected_projects = projects_list
            else:
                indices: set[int] = set()
                parts = selection.split(",")
                for part in parts:
                    part = part.strip()
                    if "-" in part:
                        try:
                            start, end = part.split("-")
                            indices.update(range(int(start), int(end) + 1))
                        except ValueError:
                            typer.secho(f"✘ Invalid range: {part}", fg=typer.colors.RED)
                            raise typer.Exit(code=1)
                    else:
                        try:
                            indices.add(int(part))
                        except ValueError:
                            typer.secho(f"✘ Invalid number: {part}", fg=typer.colors.RED)
                            raise typer.Exit(code=1)

                for idx in sorted(indices):
                    if 1 <= idx <= len(projects_list):
                        selected_projects.append(projects_list[idx - 1])

            if not selected_projects:
                typer.echo("No valid projects selected.")
                raise typer.Exit(code=0)

            # Add selected projects to config
            typer.secho(
                f"\n📝 Adding {len(selected_projects)} projects to configuration...",
                fg=typer.colors.CYAN,
            )

            if "github" not in config_data:
                config_data["github"] = {}
            if "projects" not in config_data["github"]:
                config_data["github"]["projects"] = {}

            added_count = 0
            skipped_count = 0

            for proj in selected_projects:
                proj_number = proj.get("number")
                proj_title = proj.get("title") or proj.get("name", "")
                project_value = f"{proj_title} (#{proj_number})"

                # Check if already configured
                already_exists = False
                for existing_value in existing_projects.values():
                    if f"#{proj_number}" in str(existing_value):
                        already_exists = True
                        break

                if already_exists:
                    typer.secho(
                        f"   ⊝ Skipped (already configured): {project_value}",
                        fg=typer.colors.YELLOW,
                    )
                    skipped_count += 1
                else:
                    # Generate a unique key from project title
                    key = proj_title.lower().replace(" ", "_").replace("-", "_")
                    # Remove special characters
                    key = "".join(c for c in key if c.isalnum() or c == "_")

                    # Ensure uniqueness
                    counter = 1
                    base_key = key
                    while key in config_data["github"]["projects"]:
                        key = f"{base_key}_{counter}"
                        counter += 1

                    config_data["github"]["projects"][key] = project_value
                    typer.secho(f"   ✓ Added: {project_value}", fg=typer.colors.GREEN)
                    added_count += 1

            if added_count == 0:
                typer.secho(
                    "\n✓ No new projects to add (all were already configured)",
                    fg=typer.colors.GREEN,
                )
                raise typer.Exit(code=0)

            # Write updated config
            with open(config_path, "w") as f:
                toml.dump(config_data, f)

            typer.secho(
                f"\n✅ Successfully added {added_count} projects to {config_path}",
                fg=typer.colors.GREEN,
                bold=True,
            )

            # Show summary of added projects
            typer.secho("\n📋 Added projects:", fg=typer.colors.CYAN)
            for proj in selected_projects:
                proj_number = proj.get("number")
                proj_title = proj.get("title") or proj.get("name", "")

                # Check if it was added or skipped
                was_skipped = False
                for existing_value in existing_projects.values():
                    if f"#{proj_number}" in str(existing_value):
                        was_skipped = True
                        break

                if not was_skipped:
                    typer.echo(f"   • {proj_title} (#{proj_number})")

            typer.echo("\n💡 Next steps:")
            typer.echo("  • View config: cat .devrules.toml")
            typer.echo("  • List issues: devrules list-issues --project <project-name>")
            typer.echo("  • Dashboard: devrules dashboard")

        except typer.Exit:
            raise
        except Exception as e:
            typer.secho(f"\n✘ Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    return {
        "build_enterprise": build_enterprise,
        "add_github_projects": add_github_projects,
    }
