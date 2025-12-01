"""Encryption utilities for enterprise configuration."""

import base64
import os
from typing import Any, Dict, List

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class ConfigCrypto:
    """Handles encryption and decryption of configuration values."""

    ENCRYPTED_PREFIX = "ENC:"
    SALT_SIZE = 16
    ITERATIONS = 100000

    def __init__(self, key: bytes | None = None):
        """Initialize crypto handler.

        Args:
            key: Encryption key (32 bytes). If None, will try to load from environment.
        """
        if key is None:
            key = self._load_key_from_env()
        self.key = key
        self.fernet = Fernet(key) if key else None

    @staticmethod
    def generate_key() -> bytes:
        """Generate a new encryption key.

        Returns:
            32-byte encryption key suitable for Fernet
        """
        return Fernet.generate_key()

    @staticmethod
    def derive_key(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
        """Derive encryption key from password using PBKDF2.

        Args:
            password: Password to derive key from
            salt: Salt for key derivation. If None, generates random salt.

        Returns:
            Tuple of (derived_key, salt)
        """
        if salt is None:
            salt = os.urandom(ConfigCrypto.SALT_SIZE)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=ConfigCrypto.ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt

    def _load_key_from_env(self) -> bytes | None:
        """Load encryption key from environment variable.

        Returns:
            Encryption key or None if not found
        """
        key_str = os.getenv("DEVRULES_ENTERPRISE_KEY")
        if key_str:
            return key_str.encode()
        return None

    def encrypt_field(self, value: str) -> str:
        """Encrypt a single field value.

        Args:
            value: Plain text value to encrypt

        Returns:
            Encrypted value with ENC: prefix

        Raises:
            ValueError: If encryption key is not set
        """
        if not self.fernet:
            raise ValueError("Encryption key not set")

        encrypted = self.fernet.encrypt(value.encode())
        encoded = base64.b64encode(encrypted).decode()
        return f"{self.ENCRYPTED_PREFIX}{encoded}"

    def decrypt_field(self, encrypted_value: str) -> str:
        """Decrypt a single field value.

        Args:
            encrypted_value: Encrypted value with ENC: prefix

        Returns:
            Decrypted plain text value

        Raises:
            ValueError: If encryption key is not set or value is not encrypted
        """
        if not self.fernet:
            raise ValueError("Encryption key not set")

        if not encrypted_value.startswith(self.ENCRYPTED_PREFIX):
            raise ValueError(f"Value does not have {self.ENCRYPTED_PREFIX} prefix")

        encoded = encrypted_value[len(self.ENCRYPTED_PREFIX) :]
        encrypted = base64.b64decode(encoded)
        return self.fernet.decrypt(encrypted).decode()

    def is_encrypted(self, value: str) -> bool:
        """Check if a value is encrypted.

        Args:
            value: Value to check

        Returns:
            True if value is encrypted
        """
        return isinstance(value, str) and value.startswith(self.ENCRYPTED_PREFIX)

    def encrypt_selective(self, config: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        """Encrypt specific fields in configuration.

        Args:
            config: Configuration dictionary
            fields: List of field paths to encrypt (dot notation, e.g., 'github.api_url')

        Returns:
            Configuration with encrypted fields
        """
        result = config.copy()

        for field_path in fields:
            self._encrypt_field_path(result, field_path.split("."))

        return result

    def _encrypt_field_path(self, config: Dict[str, Any], path: List[str]) -> None:
        """Encrypt a field at the given path.

        Args:
            config: Configuration dictionary (modified in place)
            path: List of keys representing the path to the field
        """
        if len(path) == 1:
            key = path[0]
            if key in config and isinstance(config[key], str):
                config[key] = self.encrypt_field(config[key])
        else:
            key = path[0]
            if key in config and isinstance(config[key], dict):
                self._encrypt_field_path(config[key], path[1:])

    def decrypt_selective(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt all encrypted fields in configuration.

        Args:
            config: Configuration dictionary with encrypted fields

        Returns:
            Configuration with decrypted fields
        """
        result = {}

        for key, value in config.items():
            if isinstance(value, dict):
                result[key] = self.decrypt_selective(value)
            elif isinstance(value, str) and self.is_encrypted(value):
                result[key] = self.decrypt_field(value)  # type: ignore
            else:
                result[key] = value

        return result

    def save_key(self, filepath: str) -> None:
        """Save encryption key to file.

        Args:
            filepath: Path to save key file
        """
        if not self.key:
            raise ValueError("No key to save")

        with open(filepath, "wb") as f:
            f.write(self.key)

    @staticmethod
    def load_key(filepath: str) -> bytes:
        """Load encryption key from file.

        Args:
            filepath: Path to key file

        Returns:
            Encryption key
        """
        with open(filepath, "rb") as f:
            return f.read()
