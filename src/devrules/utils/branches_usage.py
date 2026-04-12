"""Branch usage tracking and ranking.

Stores branch usage frequency and recency to provide intelligent ordering
based on most used or most recently used branches.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional


@dataclass
class BranchEntry:
    """Represents usage statistics for a branch."""

    name: str
    count: int = 1
    last_used: str = field(default_factory=lambda: datetime.now().isoformat())


class BranchUsageManager:
    """Manages branch usage counters and recency tracking."""

    def __init__(
        self,
        storage_path: Optional[str] = None,
        max_entries: int = 100,
    ):
        """Initialize the BranchUsageManager."""
        if storage_path is None:
            storage_path = os.path.expanduser("~/.devrules/branches.json")
        else:
            storage_path = os.path.expanduser(storage_path)

        self.storage_path = Path(storage_path)
        self.max_entries = max_entries
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        """Ensure the storage directory exists."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, dict]:
        """Load branch usage data from storage."""
        if not self.storage_path.exists():
            return {}

        try:
            with open(self.storage_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save(self, data: dict[str, dict]) -> None:
        """Save branch usage data to storage."""
        try:
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass

    # ─────────────────────────────────────────────
    # Core API
    # ─────────────────────────────────────────────

    def register_usage(self, branch_name: str) -> None:
        """Increment usage counter and update last used timestamp."""
        if not branch_name or not branch_name.strip():
            return

        branch_name = branch_name.strip()
        data = self._load()

        if branch_name in data:
            data[branch_name]["count"] += 1
            data[branch_name]["last_used"] = datetime.now().isoformat()
        else:
            entry = BranchEntry(name=branch_name)
            data[branch_name] = {
                "count": entry.count,
                "last_used": entry.last_used,
            }

        # Trim if exceeding max_entries (keep most recent)
        if len(data) > self.max_entries:
            sorted_by_recent = sorted(
                data.items(),
                key=lambda item: item[1]["last_used"],
                reverse=True,
            )
            data = dict(sorted_by_recent[: self.max_entries])

        self._save(data)

    # ─────────────────────────────────────────────
    # Ordering methods
    # ─────────────────────────────────────────────

    def get_branches(
        self,
        branch_names: list[str],
        order_by: Literal["most_used", "most_recent"] = "most_used",
    ) -> list[str]:
        """
        Return provided branch names ordered by usage or recency.

        Args:
            branch_names: List of branch names to sort
            order_by: Sorting strategy

        Returns:
            Ordered list of branch names
        """
        data = self._load()

        def sort_key(name: str):
            entry = data.get(name)
            if not entry:
                return (0, "")  # Unknown branches go last

            if order_by == "most_used":
                return (entry["count"], entry["last_used"])
            else:
                return (0, entry["last_used"])

        reverse = True  # Highest count or most recent first

        return sorted(branch_names, key=sort_key, reverse=reverse)

    def get_top_used(self, limit: int = 10) -> list[str]:
        """Return top N most used branches globally."""
        data = self._load()

        sorted_items = sorted(
            data.items(),
            key=lambda item: item[1]["count"],
            reverse=True,
        )

        return [name for name, _ in sorted_items[:limit]]

    def get_recent(self, limit: int = 10) -> list[str]:
        """Return top N most recently used branches globally."""
        data = self._load()

        sorted_items = sorted(
            data.items(),
            key=lambda item: item[1]["last_used"],
            reverse=True,
        )

        return [name for name, _ in sorted_items[:limit]]

    def clear(self) -> None:
        """Clear all stored branch statistics."""
        self._save({})
