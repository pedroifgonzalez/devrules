"""Enterprise build command."""

import os
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import typer

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

    return {"build_enterprise": build_enterprise}
