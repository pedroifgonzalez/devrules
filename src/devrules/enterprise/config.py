"""Enterprise configuration management."""

from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, Optional

import toml

from devrules.enterprise.crypto import ConfigCrypto
from devrules.enterprise.integrity import IntegrityVerifier


class ConfigPriority(IntEnum):
    """Configuration priority levels."""

    DEFAULT = 0
    USER = 1
    ENTERPRISE = 2


class EnterpriseConfig:
    """Manages enterprise configuration loading and validation."""

    ENTERPRISE_CONFIG_NAME = ".devrules.enterprise.toml"
    INTEGRITY_FILE_NAME = ".integrity.hash"

    def __init__(self, package_dir: Optional[Path] = None):
        """Initialize enterprise config manager.

        Args:
            package_dir: Directory containing enterprise config. If None, uses package location.
        """
        if package_dir is None:
            package_dir = self._get_package_dir()
        self.package_dir = package_dir
        self.config_path = package_dir / self.ENTERPRISE_CONFIG_NAME
        self.integrity_path = package_dir / self.INTEGRITY_FILE_NAME

    @staticmethod
    def _get_package_dir() -> Path:
        """Get the package directory containing enterprise config.

        Returns:
            Path to enterprise package directory
        """
        # Get the directory where this module is located
        return Path(__file__).parent

    def is_enterprise_mode(self) -> bool:
        """Check if enterprise mode is enabled.

        Returns:
            True if enterprise config exists
        """
        return self.config_path.exists()

    def load_enterprise_config(self, decrypt: bool = True) -> Optional[Dict[str, Any]]:
        """Load enterprise configuration.

        Args:
            decrypt: Whether to decrypt encrypted fields

        Returns:
            Enterprise configuration dictionary or None if not found
        """
        if not self.is_enterprise_mode():
            return None

        try:
            config = toml.load(self.config_path)

            # Decrypt if requested and encryption is enabled
            if decrypt and self._is_encryption_enabled(config):
                crypto = ConfigCrypto()
                config = crypto.decrypt_selective(config)

            return config
        except Exception as e:
            print(f"Warning: Error loading enterprise config: {e}")
            return None

    def verify_integrity(self) -> bool:
        """Verify integrity of enterprise configuration.

        Returns:
            True if integrity check passes or is not enabled
        """
        if not self.is_enterprise_mode():
            return True

        try:
            config = toml.load(self.config_path)

            # Check if integrity verification is enabled
            if not self._is_integrity_enabled(config):
                return True

            # Verify hash
            if not self.integrity_path.exists():
                print("Warning: Integrity file not found")
                return False

            return IntegrityVerifier.verify_from_file(config, str(self.integrity_path))
        except Exception as e:
            print(f"Warning: Error verifying integrity: {e}")
            return False

    def is_locked(self) -> bool:
        """Check if enterprise configuration is locked.

        Returns:
            True if configuration is locked (prevents user overrides)
        """
        if not self.is_enterprise_mode():
            return False

        try:
            config = toml.load(self.config_path)
            return config.get("enterprise", {}).get("locked", False)
        except Exception:
            return False

    @staticmethod
    def _is_encryption_enabled(config: Dict[str, Any]) -> bool:
        """Check if encryption is enabled in config.

        Args:
            config: Configuration dictionary

        Returns:
            True if encryption is enabled
        """
        return "enterprise" in config and "encryption" in config["enterprise"]

    @staticmethod
    def _is_integrity_enabled(config: Dict[str, Any]) -> bool:
        """Check if integrity verification is enabled.

        Args:
            config: Configuration dictionary

        Returns:
            True if integrity check is enabled
        """
        return config.get("enterprise", {}).get("integrity_check", False)

    def get_sensitive_fields(self) -> list[str]:
        """Get list of sensitive fields from enterprise config.

        Returns:
            List of field paths marked as sensitive
        """
        if not self.is_enterprise_mode():
            return []

        try:
            config = toml.load(self.config_path)
            return config.get("enterprise", {}).get("encryption", {}).get("sensitive_fields", [])
        except Exception:
            return []


def is_enterprise_mode() -> bool:
    """Check if running in enterprise mode.

    Returns:
        True if enterprise configuration is present
    """
    enterprise_config = EnterpriseConfig()
    return enterprise_config.is_enterprise_mode()


def load_enterprise_config() -> Optional[Dict[str, Any]]:
    """Load enterprise configuration if available.

    Returns:
        Enterprise configuration or None
    """
    enterprise_config = EnterpriseConfig()
    return enterprise_config.load_enterprise_config()


def verify_enterprise_integrity() -> bool:
    """Verify enterprise configuration integrity.

    Returns:
        True if integrity check passes
    """
    enterprise_config = EnterpriseConfig()
    return enterprise_config.verify_integrity()
