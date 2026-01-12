import unittest
from unittest.mock import MagicMock, Mock, patch

from devrules.utils import gum


class TestGumUtilities(unittest.TestCase):
    @patch("devrules.utils.gum.GUM_AVAILABLE", False)
    def test_is_available_false(self):
        self.assertFalse(gum.is_available())

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    def test_is_available_true(self):
        self.assertTrue(gum.is_available())

    @patch("devrules.utils.gum.GUM_AVAILABLE", False)
    def test_choose_gum_not_available(self):
        result = gum.choose(["option1", "option2"])
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    def test_choose_empty_options(self):
        result = gum.choose([])
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_choose_single_selection_success(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="option1\n")
        result = gum.choose(["option1", "option2"], header="Choose one")
        self.assertEqual(result, "option1")
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertIn("gum", call_args)
        self.assertIn("choose", call_args)
        self.assertIn("--header", call_args)
        self.assertIn("Choose one", call_args)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_choose_multiple_selection(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="option1\noption2\n")
        result = gum.choose(["option1", "option2", "option3"], limit=2)
        self.assertEqual(result, ["option1", "option2"])

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_choose_no_limit(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="option1\noption2\n")
        result = gum.choose(["option1", "option2", "option3"], limit=0)
        self.assertEqual(result, ["option1", "option2"])
        call_args = mock_run.call_args[0][0]
        self.assertIn("--no-limit", call_args)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_choose_cancelled(self, mock_run):
        mock_run.return_value = Mock(returncode=1, stdout="")
        result = gum.choose(["option1", "option2"])
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_choose_exception(self, mock_run):
        mock_run.side_effect = Exception("Test error")
        result = gum.choose(["option1", "option2"])
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", False)
    def test_input_text_gum_not_available(self):
        result = gum.input_text(placeholder="Enter text")
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_input_text_success(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="user input\n")
        result = gum.input_text(
            placeholder="Enter text", header="Input", default="default", char_limit=100
        )
        self.assertEqual(result, "user input")
        call_args = mock_run.call_args[0][0]
        self.assertIn("--placeholder", call_args)
        self.assertIn("--header", call_args)
        self.assertIn("--value", call_args)
        self.assertIn("--char-limit", call_args)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_input_text_cancelled(self, mock_run):
        mock_run.return_value = Mock(returncode=1, stdout="")
        result = gum.input_text()
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_input_text_exception(self, mock_run):
        mock_run.side_effect = Exception("Test error")
        result = gum.input_text()
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", False)
    def test_write_gum_not_available(self):
        result = gum.write(placeholder="Write text")
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_write_success(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="multiline\ntext\n")
        result = gum.write(placeholder="Write", header="Header", char_limit=500)
        self.assertEqual(result, "multiline\ntext")
        call_args = mock_run.call_args[0][0]
        self.assertIn("gum", call_args)
        self.assertIn("write", call_args)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_write_cancelled(self, mock_run):
        mock_run.return_value = Mock(returncode=1, stdout="")
        result = gum.write()
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_write_exception(self, mock_run):
        mock_run.side_effect = Exception("Test error")
        result = gum.write()
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", False)
    def test_input_text_with_history_gum_not_available(self):
        result = gum.input_text_with_history("test_type")
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("devrules.utils.gum.get_history_manager")
    @patch("subprocess.run")
    def test_input_text_with_history_no_history(self, mock_run, mock_get_history):
        mock_history = MagicMock()
        mock_history.get_recent.return_value = []
        mock_get_history.return_value = mock_history

        mock_run.return_value = Mock(returncode=0, stdout="new value\n")
        result = gum.input_text_with_history("test_type", placeholder="Enter")
        self.assertEqual(result, "new value")
        mock_history.add_entry.assert_called_once_with("test_type", "new value")

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("devrules.utils.gum.get_history_manager")
    @patch("subprocess.run")
    def test_input_text_with_history_with_history_select_new(self, mock_run, mock_get_history):
        mock_history = MagicMock()
        mock_history.get_recent.return_value = ["old1", "old2"]
        mock_get_history.return_value = mock_history

        mock_run.side_effect = [
            Mock(returncode=0, stdout="[Enter new value]\n"),
            Mock(returncode=0, stdout="new value\n"),
        ]
        result = gum.input_text_with_history("test_type", default="default_val")
        self.assertEqual(result, "new value")
        mock_history.add_entry.assert_called_once_with("test_type", "new value")

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("devrules.utils.gum.get_history_manager")
    @patch("subprocess.run")
    def test_input_text_with_history_with_history_select_existing(self, mock_run, mock_get_history):
        mock_history = MagicMock()
        mock_history.get_recent.return_value = ["old1", "old2"]
        mock_get_history.return_value = mock_history

        mock_run.side_effect = [
            Mock(returncode=0, stdout="old1\n"),
            Mock(returncode=0, stdout="old1 edited\n"),
        ]
        result = gum.input_text_with_history("test_type")
        self.assertEqual(result, "old1 edited")

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("devrules.utils.gum.get_history_manager")
    @patch("subprocess.run")
    def test_input_text_with_history_filter_cancelled(self, mock_run, mock_get_history):
        mock_history = MagicMock()
        mock_history.get_recent.return_value = ["old1"]
        mock_get_history.return_value = mock_history

        mock_run.return_value = Mock(returncode=1, stdout="")
        result = gum.input_text_with_history("test_type")
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("devrules.utils.gum.get_history_manager")
    @patch("subprocess.run")
    def test_input_text_with_history_no_save(self, mock_run, mock_get_history):
        mock_history = MagicMock()
        mock_history.get_recent.return_value = []
        mock_get_history.return_value = mock_history

        mock_run.return_value = Mock(returncode=0, stdout="value\n")
        result = gum.input_text_with_history("test_type", save_to_history=False)
        self.assertEqual(result, "value")
        mock_history.add_entry.assert_not_called()

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("devrules.utils.gum.get_history_manager")
    @patch("subprocess.run")
    def test_input_text_with_history_exception_fallback(self, mock_run, mock_get_history):
        mock_history = MagicMock()
        mock_history.get_recent.return_value = ["old1"]
        mock_get_history.return_value = mock_history

        mock_run.side_effect = [
            Exception("Filter failed"),
            Mock(returncode=0, stdout="fallback\n"),
        ]
        result = gum.input_text_with_history("test_type")
        self.assertEqual(result, "fallback")

    @patch("devrules.utils.gum.GUM_AVAILABLE", False)
    def test_confirm_gum_not_available(self):
        result = gum.confirm("Are you sure?")
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_confirm_yes(self, mock_run):
        mock_run.return_value = Mock(returncode=0)
        result = gum.confirm("Are you sure?", default=True)
        self.assertTrue(result)
        call_args = mock_run.call_args[0][0]
        self.assertIn("--default=yes", call_args)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_confirm_no(self, mock_run):
        mock_run.return_value = Mock(returncode=1)
        result = gum.confirm("Are you sure?")
        self.assertFalse(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_confirm_exception(self, mock_run):
        mock_run.side_effect = Exception("Test error")
        result = gum.confirm("Are you sure?")
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", False)
    @patch("subprocess.run")
    def test_spin_gum_not_available(self, mock_run):
        mock_run.return_value = Mock(returncode=0)
        result = gum.spin("Loading", ["echo", "test"])
        self.assertEqual(result, 0)
        mock_run.assert_called_once_with(["echo", "test"])

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_spin_success(self, mock_run):
        mock_run.return_value = Mock(returncode=0)
        result = gum.spin("Loading", ["echo", "test"])
        self.assertEqual(result, 0)
        call_args = mock_run.call_args[0][0]
        self.assertIn("gum", call_args)
        self.assertIn("spin", call_args)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_spin_exception_fallback(self, mock_run):
        mock_run.side_effect = [Exception("Gum failed"), Mock(returncode=0)]
        result = gum.spin("Loading", ["echo", "test"])
        self.assertEqual(result, 0)
        self.assertEqual(mock_run.call_count, 2)

    @patch("devrules.utils.gum.GUM_AVAILABLE", False)
    def test_filter_list_gum_not_available(self):
        result = gum.filter_list(["opt1", "opt2"])
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    def test_filter_list_empty_options(self):
        result = gum.filter_list([])
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_filter_list_success(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="option1\n")
        result = gum.filter_list(["option1", "option2"], placeholder="Search", header="Filter")
        self.assertEqual(result, "option1")
        call_args = mock_run.call_args[0][0]
        self.assertIn("--placeholder", call_args)
        self.assertIn("--header", call_args)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_filter_list_cancelled(self, mock_run):
        mock_run.return_value = Mock(returncode=1, stdout="")
        result = gum.filter_list(["option1", "option2"])
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_filter_list_exception(self, mock_run):
        mock_run.side_effect = Exception("Test error")
        result = gum.filter_list(["option1", "option2"])
        self.assertIsNone(result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", False)
    def test_style_gum_not_available(self):
        result = gum.style("test text", foreground=82, bold=True)
        self.assertEqual(result, "test text")

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_style_success(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="styled text\n")
        result = gum.style(
            "test",
            foreground=82,
            background=0,
            bold=True,
            italic=True,
            border="rounded",
            border_foreground=99,
            padding="1 2",
            margin="1",
        )
        self.assertEqual(result, "styled text")
        call_args = mock_run.call_args[0][0]
        self.assertIn("--foreground", call_args)
        self.assertIn("--background", call_args)
        self.assertIn("--bold", call_args)
        self.assertIn("--italic", call_args)
        self.assertIn("--border", call_args)
        self.assertIn("--border-foreground", call_args)
        self.assertIn("--padding", call_args)
        self.assertIn("--margin", call_args)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_style_exception(self, mock_run):
        mock_run.side_effect = Exception("Test error")
        result = gum.style("test text")
        self.assertEqual(result, "test text")

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("devrules.utils.gum.style")
    def test_print_styled_with_gum(self, mock_style):
        mock_style.return_value = "styled"
        with patch("builtins.print") as mock_print:
            gum.print_styled("test", foreground=82, bold=True)
            mock_style.assert_called_once_with("test", foreground=82, bold=True)
            mock_print.assert_called_once_with("styled")

    @patch("devrules.utils.gum.GUM_AVAILABLE", False)
    def test_print_styled_without_gum(self):
        with patch("builtins.print") as mock_print:
            gum.print_styled("test", foreground=82, bold=True)
            mock_print.assert_called_once_with("test")

    @patch("devrules.utils.gum.print_styled")
    def test_success(self, mock_print_styled):
        gum.success("Success message")
        mock_print_styled.assert_called_once_with("✔ Success message", foreground=82, bold=True)

    @patch("devrules.utils.gum.print_styled")
    def test_error(self, mock_print_styled):
        gum.error("Error message")
        mock_print_styled.assert_called_once_with("✘ Error message", foreground=196, bold=True)

    @patch("devrules.utils.gum.print_styled")
    def test_warning(self, mock_print_styled):
        gum.warning("Warning message")
        mock_print_styled.assert_called_once_with("⚠ Warning message", foreground=214)

    @patch("devrules.utils.gum.print_styled")
    def test_info(self, mock_print_styled):
        gum.info("Info message")
        mock_print_styled.assert_called_once_with("ℹ Info message", foreground=81)

    @patch("devrules.utils.gum.GUM_AVAILABLE", False)
    def test_table_gum_not_available(self):
        rows = [["cell1", "cell2"], ["cell3", "cell4"]]
        headers = ["Header1", "Header2"]
        result = gum.table(rows, headers)
        self.assertIn("Header1", result)
        self.assertIn("cell1", result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    def test_table_empty_rows(self):
        result = gum.table([])
        self.assertEqual(result, "")

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_table_success(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="formatted table\n")
        rows = [["cell1", "cell2"]]
        headers = ["H1", "H2"]
        result = gum.table(rows, headers, border="rounded", border_foreground=99)
        self.assertEqual(result, "formatted table")

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_table_gum_fails_fallback(self, mock_run):
        mock_run.return_value = Mock(returncode=1, stdout="")
        rows = [["cell1", "cell2"]]
        headers = ["H1", "H2"]
        result = gum.table(rows, headers)
        self.assertIn("H1", result)

    @patch("devrules.utils.gum.GUM_AVAILABLE", True)
    @patch("subprocess.run")
    def test_table_exception_fallback(self, mock_run):
        mock_run.side_effect = Exception("Test error")
        rows = [["cell1", "cell2"]]
        result = gum.table(rows)
        self.assertIn("cell1", result)

    def test_simple_table_with_headers(self):
        rows = [["a", "b"], ["c", "d"]]
        headers = ["Col1", "Col2"]
        result = gum._simple_table(rows, headers)
        self.assertIn("Col1", result)
        self.assertIn("│", result)

    def test_simple_table_without_headers(self):
        rows = [["a", "b"], ["c", "d"]]
        result = gum._simple_table(rows, None)
        self.assertIn("a", result)
        self.assertIn("│", result)

    def test_simple_table_empty(self):
        result = gum._simple_table([])
        self.assertEqual(result, "")

    @patch("devrules.utils.gum.table")
    def test_print_table(self, mock_table):
        mock_table.return_value = "table output"
        with patch("builtins.print") as mock_print:
            gum.print_table([["a", "b"]], ["H1", "H2"])
            mock_print.assert_called_once_with("table output")

    @patch("devrules.utils.gum.style")
    def test_print_stick_header(self, mock_style):
        mock_style.return_value = "styled"
        with patch("builtins.print") as mock_print:
            gum.print_stick_header("Header")
            self.assertEqual(mock_print.call_count, 2)

    @patch("devrules.utils.gum.print_styled")
    def test_print_list(self, mock_print_styled):
        gum.print_list("Header", ["item1", "item2"])
        self.assertEqual(mock_print_styled.call_count, 3)


if __name__ == "__main__":
    unittest.main()
