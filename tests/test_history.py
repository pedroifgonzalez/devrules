import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from devrules.utils.history import HistoryManager, get_history_manager


class TestHistoryManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for history file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.history_path = Path(self.temp_dir.name) / "history.json"

        # Reset global manager
        with patch("devrules.utils.history._global_manager", None):
            self.manager = HistoryManager(storage_path=str(self.history_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_and_retrieve_entry(self):
        self.manager.add_entry("test_type", "value1")
        recent = self.manager.get_recent("test_type")
        self.assertEqual(recent, ["value1"])

    def test_add_multiple_entries(self):
        self.manager.add_entry("test_type", "value1")
        self.manager.add_entry("test_type", "value2")
        recent = self.manager.get_recent("test_type")
        # Should be most recent first
        self.assertEqual(recent, ["value2", "value1"])

    def test_deduplication(self):
        self.manager.add_entry("test_type", "value1")
        self.manager.add_entry("test_type", "value2")
        self.manager.add_entry("test_type", "value1")  # Add value1 again

        recent = self.manager.get_recent("test_type")
        # value1 should be moved to front, no duplicate
        self.assertEqual(recent, ["value1", "value2"])
        self.assertEqual(len(recent), 2)

    def test_max_entries(self):
        # Set small limit for testing
        self.manager.max_entries = 3

        for i in range(5):
            self.manager.add_entry("test_type", f"value{i}")

        recent = self.manager.get_recent("test_type")
        self.assertEqual(len(recent), 3)
        # Should contain 4, 3, 2 (most recent first)
        self.assertEqual(recent, ["value4", "value3", "value2"])

    def test_persistence(self):
        self.manager.add_entry("test_type", "persistent_value")

        # Create new manager pointing to same file
        new_manager = HistoryManager(storage_path=str(self.history_path))
        recent = new_manager.get_recent("test_type")
        self.assertEqual(recent, ["persistent_value"])

    def test_get_suggestions(self):
        values = ["apple", "banana", "apricot", "cherry"]
        for v in values:
            self.manager.add_entry("fruits", v)

        # Search for 'ap' (should match apple and apricot)
        suggestions = self.manager.get_suggestions("fruits", prefix="ap")
        # Note: 'cherry' was added last, so it's first in recent list.
        # But we are filtering. Order in list: cherry, apricot, banana, apple
        # Matches: apricot, apple
        self.assertIn("apple", suggestions)
        self.assertIn("apricot", suggestions)
        self.assertNotIn("banana", suggestions)

        # Empty prefix should return all (up to limit)
        all_suggestions = self.manager.get_suggestions("fruits", prefix="")
        self.assertEqual(len(all_suggestions), 4)

    def test_clear_history(self):
        self.manager.add_entry("type1", "val1")
        self.manager.add_entry("type2", "val2")

        # Clear specific type
        self.manager.clear("type1")
        self.assertEqual(self.manager.get_recent("type1"), [])
        self.assertEqual(self.manager.get_recent("type2"), ["val2"])

        # Clear all
        self.manager.clear()
        self.assertEqual(self.manager.get_recent("type2"), [])

    def test_global_manager(self):
        with patch("devrules.utils.history._global_manager", None):
            manager1 = get_history_manager()
            manager2 = get_history_manager()
            self.assertIs(manager1, manager2)


if __name__ == "__main__":
    unittest.main()
