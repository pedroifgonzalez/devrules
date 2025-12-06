"""Enterprise package builder."""

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

import toml

from devrules.enterprise.crypto import ConfigCrypto
from devrules.enterprise.integrity import IntegrityVerifier


class EnterpriseBuilder:
    """Handles building enterprise packages with embedded configuration."""

    def __init__(self, project_root: Path):
        """Initialize builder.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = project_root
        self.enterprise_dir = project_root / "src" / "devrules" / "enterprise"

    def embed_config(
        self,
        config_path: str,
        encrypt: bool = True,
        sensitive_fields: Optional[List[str]] = None,
        encryption_key: Optional[bytes] = None,
    ) -> tuple[Path, Optional[bytes]]:
        """Embed configuration into package.

        Args:
            config_path: Path to configuration file
            encrypt: Whether to encrypt sensitive fields
            sensitive_fields: List of field paths to encrypt
            encryption_key: Encryption key to use (generates new if None)

        Returns:
            Tuple of (embedded_config_path, encryption_key)
        """
        # Load config
        config = toml.load(config_path)

        # Encrypt if requested
        key = encryption_key
        if encrypt:
            if key is None:
                key = ConfigCrypto.generate_key()

            crypto = ConfigCrypto(key)

            # Get sensitive fields from config or parameter
            fields_to_encrypt = sensitive_fields or config.get("enterprise", {}).get(
                "encryption", {}
            ).get("sensitive_fields", [])

            if fields_to_encrypt:
                config = crypto.encrypt_selective(config, fields_to_encrypt)

        # Generate integrity hash
        integrity_hash = IntegrityVerifier.generate_hash(config)

        # Ensure enterprise directory exists
        self.enterprise_dir.mkdir(parents=True, exist_ok=True)

        # Write config
        config_dest = self.enterprise_dir / ".devrules.enterprise.toml"
        with open(config_dest, "w") as f:
            toml.dump(config, f)

        # Write integrity file
        integrity_dest = self.enterprise_dir / ".integrity.hash"
        with open(integrity_dest, "w") as f:
            f.write(integrity_hash)

        return config_dest, key

    def modify_package_metadata(
        self, package_name: Optional[str] = None, version_suffix: str = "enterprise"
    ) -> None:
        """Modify package metadata for enterprise build.

        Args:
            package_name: New package name (e.g., 'devrules-mycompany')
            version_suffix: Suffix to add to version (e.g., 'enterprise')
        """
        pyproject_path = self.project_root / "pyproject.toml"
        pyproject = toml.load(pyproject_path)

        # Modify name if provided
        if package_name:
            pyproject["project"]["name"] = package_name

        # Add version suffix using PEP 440 local version identifier (+)
        current_version = pyproject["project"]["version"]
        if version_suffix and f"+{version_suffix}" not in current_version:
            pyproject["project"]["version"] = f"{current_version}+{version_suffix}"

        # Write back
        with open(pyproject_path, "w") as f:
            toml.dump(pyproject, f)

    def restore_package_metadata(self, backup_path: Path) -> None:
        """Restore original package metadata.

        Args:
            backup_path: Path to backup pyproject.toml
        """
        pyproject_path = self.project_root / "pyproject.toml"
        shutil.copy(backup_path, pyproject_path)

    def build_package(self, output_dir: str = "dist") -> Path:
        """Build the package.

        Args:
            output_dir: Output directory for build artifacts

        Returns:
            Path to output directory
        """
        output_path = self.project_root / output_dir

        # Run build
        subprocess.run(
            ["python", "-m", "build", "--outdir", str(output_path)],
            cwd=self.project_root,
            check=True,
        )

        return output_path

    def create_distribution_readme(self, package_name: str, has_encryption: bool = False) -> str:
        """Create README for distribution.

        Args:
            package_name: Name of the enterprise package
            has_encryption: Whether encryption is used

        Returns:
            README content
        """
        encryption_section = ""
        if has_encryption:
            encryption_section = """
## Encryption Key

This package uses encrypted configuration. The encryption key has been saved to `encryption.key`.

**IMPORTANT**: Keep this key secure! You have two options:

1. **Embed the key** (less secure): Include `encryption.key` in your distribution
2. **Use environment variable** (recommended): Set `DEVRULES_ENTERPRISE_KEY` environment variable

```bash
export DEVRULES_ENTERPRISE_KEY=$(cat encryption.key)
```
"""

        return f"""# {package_name} - Enterprise Build

This is an enterprise build of DevRules with embedded corporate configuration.

## Installation

### From Private PyPI
```bash
pip install {package_name}
```

### From Wheel File
```bash
pip install {package_name}-*.whl
```

### In requirements.txt
```
{package_name}>=0.1.0
```

### In pyproject.toml
```toml
[project]
dependencies = [
    "{package_name}>=0.1.0",
]
```
{encryption_section}

## Usage

Once installed, use `devrules` commands as normal. The corporate configuration will be automatically applied.

```bash
devrules check-branch feature/123-my-feature
devrules check-commit .git/COMMIT_EDITMSG
```

## Configuration

This enterprise build uses **locked corporate configuration**. User-level `.devrules.toml` files will be ignored to ensure compliance with corporate standards.

## Support

For issues or questions, contact your DevOps team.
"""

    def cleanup_embedded_config(self) -> None:
        """Remove embedded configuration files."""
        config_path = self.enterprise_dir / ".devrules.enterprise.toml"
        integrity_path = self.enterprise_dir / ".integrity.hash"

        if config_path.exists():
            config_path.unlink()
        if integrity_path.exists():
            integrity_path.unlink()
