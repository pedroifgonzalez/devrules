"""History management for interactive prompts.

Stores and retrieves previously entered values to improve user experience
by offering suggestions based on past inputs.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class HistoryEntry:
    """A single history entry."""

    value: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class HistoryManager:
    """Manages prompt history storage and retrieval."""

    def __init__(self, storage_path: Optional[str] = None, max_entries: int = 50):
        """Initialize history manager.

        Args:
            storage_path: Path to history file (default: ~/.devrules/history.json)
            max_entries: Maximum entries to keep per prompt type
        """
        if storage_path is None:
            storage_path = os.path.expanduser("~/.devrules/history.json")
        else:
            storage_path = os.path.expanduser(storage_path)

        self.storage_path = Path(storage_path)
        self.max_entries = max_entries
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        """Ensure the storage directory exists."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_history(self) -> dict[str, list[dict]]:
        """Load history from disk.

        Returns:
            Dictionary mapping prompt types to lists of entries
        """
        if not self.storage_path.exists():
            return {}

        try:
            with open(self.storage_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # If file is corrupted or unreadable, start fresh
            return {}

    def _save_history(self, history: dict[str, list[dict]]) -> None:
        """Save history to disk.

        Args:
            history: Dictionary mapping prompt types to lists of entries
        """
        try:
            with open(self.storage_path, "w") as f:
                json.dump(history, f, indent=2)
        except IOError:
            # Silently fail if we can't write - don't break user's workflow
            pass

    def add_entry(self, prompt_type: str, value: str) -> None:
        """Add a new history entry.

        Args:
            prompt_type: Type of prompt (e.g., 'branch_description', 'commit_message')
            value: Value to store
        """
        if not value or not value.strip():
            return

        value = value.strip()
        history = self._load_history()

        if prompt_type not in history:
            history[prompt_type] = []

        # Check if this exact value already exists
        existing_values = [entry.get("value") for entry in history[prompt_type]]
        if value in existing_values:
            # Remove the old entry so we can add it at the front
            history[prompt_type] = [
                entry for entry in history[prompt_type] if entry.get("value") != value
            ]

        # Add new entry at the front
        entry = HistoryEntry(value=value)
        history[prompt_type].insert(0, {"value": entry.value, "timestamp": entry.timestamp})

        # Trim to max entries
        history[prompt_type] = history[prompt_type][: self.max_entries]

        self._save_history(history)

    def get_recent(self, prompt_type: str, limit: int = 10) -> list[str]:
        """Get recent values for a prompt type.

        Args:
            prompt_type: Type of prompt
            limit: Maximum number of entries to return

        Returns:
            List of recent values (most recent first)
        """
        history = self._load_history()

        if prompt_type not in history:
            return []

        entries = history[prompt_type][:limit]
        return [entry.get("value", "") for entry in entries if entry.get("value")]

    def get_suggestions(self, prompt_type: str, prefix: str = "", limit: int = 10) -> list[str]:
        """Get filtered suggestions based on prefix.

        Args:
            prompt_type: Type of prompt
            prefix: Filter entries starting with this prefix
            limit: Maximum number of suggestions

        Returns:
            List of matching suggestions
        """
        recent = self.get_recent(prompt_type, limit=50)

        if not prefix:
            return recent[:limit]

        # Filter by prefix (case-insensitive)
        prefix_lower = prefix.lower()
        matches = [value for value in recent if value.lower().startswith(prefix_lower)]

        return matches[:limit]

    def clear(self, prompt_type: Optional[str] = None) -> None:
        """Clear history.

        Args:
            prompt_type: Type to clear, or None to clear all
        """
        if prompt_type is None:
            # Clear all history
            self._save_history({})
        else:
            # Clear specific type
            history = self._load_history()
            if prompt_type in history:
                del history[prompt_type]
                self._save_history(history)


# Global instance for easy access
_global_manager: Optional[HistoryManager] = None


def get_history_manager() -> HistoryManager:
    """Get the global history manager instance.

    Returns:
        Global HistoryManager instance
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = HistoryManager()
    return _global_manager
