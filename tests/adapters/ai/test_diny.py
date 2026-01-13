"""Tests for Diny AI adapter."""

import subprocess
import unittest
from unittest.mock import Mock, patch

from devrules.adapters.ai import diny


class TestDinyAdapter(unittest.TestCase):
    """Test Diny AI adapter functionality."""

    @patch("devrules.adapters.ai.diny.DINY_AVAILABLE", False)
    def test_is_available_false(self):
        """Test is_available returns False when diny is not installed."""
        self.assertFalse(diny.is_available())

    @patch("devrules.adapters.ai.diny.DINY_AVAILABLE", True)
    def test_is_available_true(self):
        """Test is_available returns True when diny is installed."""
        self.assertTrue(diny.is_available())

    @patch("devrules.adapters.ai.diny.is_available")
    def test_generate_commit_message_not_available(self, mock_is_available):
        """Test generate_commit_message returns None when diny is not available."""
        mock_is_available.return_value = False
        result = diny.generate_commit_message()
        self.assertIsNone(result)

    @patch("devrules.adapters.ai.diny.is_available")
    @patch("subprocess.run")
    def test_generate_commit_message_success(self, mock_run, mock_is_available):
        """Test successful commit message generation."""
        mock_is_available.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="feat: add new feature\n\nDetailed description of the feature\n",
        )

        result = diny.generate_commit_message()

        self.assertEqual(result, "feat: add new feature\n\nDetailed description of the feature")
        mock_run.assert_called_once_with(
            ["diny", "commit", "--print"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

    @patch("devrules.adapters.ai.diny.is_available")
    @patch("subprocess.run")
    def test_generate_commit_message_with_custom_timeout(self, mock_run, mock_is_available):
        """Test commit message generation with custom timeout."""
        mock_is_available.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout="fix: bug fix\n")

        result = diny.generate_commit_message(timeout=60)

        self.assertEqual(result, "fix: bug fix")
        mock_run.assert_called_once_with(
            ["diny", "commit", "--print"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )

    @patch("devrules.adapters.ai.diny.is_available")
    @patch("subprocess.run")
    def test_generate_commit_message_timeout_expired(self, mock_run, mock_is_available):
        """Test commit message generation handles timeout gracefully."""
        mock_is_available.return_value = True
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["diny", "commit", "--print"], timeout=30
        )

        result = diny.generate_commit_message()

        self.assertIsNone(result)

    @patch("devrules.adapters.ai.diny.is_available")
    @patch("subprocess.run")
    def test_generate_commit_message_called_process_error(self, mock_run, mock_is_available):
        """Test commit message generation handles CalledProcessError gracefully."""
        mock_is_available.return_value = True
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["diny", "commit", "--print"],
            stderr="Error: failed to generate commit message",
        )

        result = diny.generate_commit_message()

        self.assertIsNone(result)

    @patch("devrules.adapters.ai.diny.is_available")
    @patch("subprocess.run")
    def test_generate_commit_message_generic_exception(self, mock_run, mock_is_available):
        """Test commit message generation handles generic exceptions gracefully."""
        mock_is_available.return_value = True
        mock_run.side_effect = Exception("Network error")

        result = diny.generate_commit_message()

        self.assertIsNone(result)

    @patch("devrules.adapters.ai.diny.is_available")
    @patch("subprocess.run")
    def test_generate_commit_message_empty_output(self, mock_run, mock_is_available):
        """Test commit message generation with empty output."""
        mock_is_available.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout="   \n\n  ")

        result = diny.generate_commit_message()

        self.assertEqual(result, "")

    @patch("devrules.adapters.ai.diny.is_available")
    @patch("subprocess.run")
    def test_generate_commit_message_strips_whitespace(self, mock_run, mock_is_available):
        """Test that commit message output is properly stripped."""
        mock_is_available.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="  \n  feat: add feature  \n\n  ",
        )

        result = diny.generate_commit_message()

        self.assertEqual(result, "feat: add feature")

    @patch("devrules.adapters.ai.diny.is_available")
    @patch("subprocess.run")
    def test_generate_commit_message_multiline_output(self, mock_run, mock_is_available):
        """Test commit message generation with multiline output."""
        mock_is_available.return_value = True
        commit_msg = """feat: implement new authentication system

- Add JWT token support
- Implement refresh token mechanism
- Add user session management

Closes #123"""
        mock_run.return_value = Mock(returncode=0, stdout=commit_msg + "\n")

        result = diny.generate_commit_message()

        self.assertEqual(result, commit_msg)

    @patch("devrules.adapters.ai.diny.is_available")
    @patch("subprocess.run")
    def test_generate_commit_message_unicode_characters(self, mock_run, mock_is_available):
        """Test commit message generation with unicode characters."""
        mock_is_available.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="feat: add internationalization support 🌍\n",
        )

        result = diny.generate_commit_message()

        self.assertEqual(result, "feat: add internationalization support 🌍")

    @patch("devrules.adapters.ai.diny.is_available")
    @patch("subprocess.run")
    def test_generate_commit_message_special_characters(self, mock_run, mock_is_available):
        """Test commit message generation with special characters."""
        mock_is_available.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="fix: handle \"quotes\" and 'apostrophes' in messages\n",
        )

        result = diny.generate_commit_message()

        self.assertEqual(result, "fix: handle \"quotes\" and 'apostrophes' in messages")


if __name__ == "__main__":
    unittest.main()
