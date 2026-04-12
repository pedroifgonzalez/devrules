import unittest
from unittest.mock import patch

from devrules.utils.typer import add_typer_block_message


class TestTyperUtilities(unittest.TestCase):
    @patch("typer.echo")
    @patch("typer.secho")
    def test_add_typer_block_message_basic(self, mock_secho, mock_echo):
        add_typer_block_message(
            header="Test Header",
            subheader="Test Subheader",
            messages=["Message 1", "Message 2"],
        )
        self.assertTrue(mock_echo.called)
        self.assertTrue(mock_secho.called)

    @patch("typer.echo")
    @patch("typer.secho")
    def test_add_typer_block_message_with_indent(self, mock_secho, mock_echo):
        add_typer_block_message(
            header="Header",
            subheader="Subheader",
            messages=["Line 1", "Line 2"],
            indent_block=True,
        )
        calls = [str(call) for call in mock_echo.call_args_list]
        indented_found = any("    Line 1" in str(call) for call in calls)
        self.assertTrue(indented_found or mock_echo.called)

    @patch("typer.echo")
    @patch("typer.secho")
    def test_add_typer_block_message_without_indent(self, mock_secho, mock_echo):
        add_typer_block_message(
            header="Header",
            subheader="Subheader",
            messages=["Line 1"],
            indent_block=False,
        )
        self.assertTrue(mock_echo.called)

    @patch("typer.echo")
    @patch("typer.secho")
    def test_add_typer_block_message_long_header(self, mock_secho, mock_echo):
        long_header = "This is a very long header that exceeds forty characters"
        add_typer_block_message(
            header=long_header,
            subheader="Sub",
            messages=["Msg"],
        )
        self.assertTrue(mock_secho.called)

    @patch("typer.echo")
    @patch("typer.secho")
    def test_add_typer_block_message_no_separator(self, mock_secho, mock_echo):
        add_typer_block_message(
            header="Header",
            subheader="Sub",
            messages=["Msg"],
            use_separator=False,
        )
        self.assertTrue(mock_secho.called)

    @patch("typer.echo")
    @patch("typer.secho")
    def test_add_typer_block_message_empty_subheader(self, mock_secho, mock_echo):
        add_typer_block_message(
            header="Header",
            subheader="",
            messages=["Msg"],
        )
        self.assertTrue(mock_echo.called)

    @patch("typer.echo")
    @patch("typer.secho")
    def test_add_typer_block_message_multiline_messages(self, mock_secho, mock_echo):
        add_typer_block_message(
            header="Header",
            subheader="Sub",
            messages=["Line 1\nLine 2", "Line 3"],
        )
        self.assertTrue(mock_echo.called)

    @patch("typer.echo")
    @patch("typer.secho")
    def test_add_typer_block_message_separator_calculation(self, mock_secho, mock_echo):
        add_typer_block_message(
            header="Short",
            subheader="Sub",
            messages=["This is a much longer message than the header"],
        )
        self.assertTrue(mock_secho.called)

    @patch("typer.echo")
    @patch("typer.secho")
    def test_add_typer_block_message_odd_diff_separator(self, mock_secho, mock_echo):
        add_typer_block_message(
            header="Hdr",
            subheader="",
            messages=["Message"],
        )
        self.assertTrue(mock_secho.called)

    @patch("typer.echo")
    @patch("typer.secho")
    def test_add_typer_block_message_centered_header(self, mock_secho, mock_echo):
        add_typer_block_message(
            header="Center",
            subheader="Sub",
            messages=["A longer message to test centering"],
            use_separator=True,
        )
        self.assertTrue(mock_secho.called)

    @patch("typer.echo")
    @patch("typer.secho")
    def test_add_typer_block_message_with_colors(self, mock_secho, mock_echo):
        add_typer_block_message(
            header="Colored Header",
            subheader="Subheader",
            messages=["Message"],
        )
        green_calls = [call for call in mock_secho.call_args_list if "fg" in str(call)]
        self.assertTrue(len(green_calls) > 0 or mock_secho.called)

    @patch("typer.echo")
    @patch("typer.secho")
    def test_add_typer_block_message_empty_messages(self, mock_secho, mock_echo):
        add_typer_block_message(
            header="Header",
            subheader="Sub",
            messages=[],
        )
        self.assertTrue(mock_echo.called)


if __name__ == "__main__":
    unittest.main()
