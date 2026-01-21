import unittest
from unittest.mock import MagicMock, patch

from devrules.core.enum import DevRulesEvent
from devrules.utils.decorators import emit_events, ensure_git_repo


class TestEnsureGitRepoDecorator(unittest.TestCase):
    @patch("devrules.utils.decorators.ensure_git_repo_")
    def test_ensure_git_repo_success(self, mock_ensure):
        mock_ensure.return_value = None

        @ensure_git_repo()
        def test_func(arg1, arg2):
            return arg1 + arg2

        result = test_func(1, 2)
        self.assertEqual(result, 3)
        mock_ensure.assert_called_once()

    @patch("devrules.utils.decorators.ensure_git_repo_")
    def test_ensure_git_repo_raises_exception(self, mock_ensure):
        mock_ensure.side_effect = SystemExit(1)

        @ensure_git_repo()
        def test_func():
            return "should not reach here"

        with self.assertRaises(SystemExit):
            test_func()


class TestEmitEventsDecorator(unittest.TestCase):
    @patch("devrules.adapters.prompters.factory.get_default_prompter")
    @patch("devrules.utils.decorators.attach_event")
    @patch("devrules.utils.decorators.prompt_for_rule_arguments")
    @patch("devrules.utils.decorators.execute_rule")
    def test_emit_events_no_custom_rules(
        self, mock_execute, mock_prompt_args, mock_attach, mock_get_prompter
    ):
        mock_prompter = MagicMock()
        mock_get_prompter.return_value = mock_prompter
        mock_attach.return_value = []

        @emit_events(DevRulesEvent.PRE_COMMIT)
        def test_func(arg):
            return arg * 2

        result = test_func(5)
        self.assertEqual(result, 10)
        mock_attach.assert_called_once_with(DevRulesEvent.PRE_COMMIT)
        mock_prompter.header.assert_not_called()

    @patch("devrules.adapters.prompters.factory.get_default_prompter")
    @patch("devrules.utils.decorators.attach_event")
    @patch("devrules.utils.decorators.prompt_for_rule_arguments")
    @patch("devrules.utils.decorators.execute_rule")
    def test_emit_events_with_custom_rules_success(
        self, mock_execute, mock_prompt_args, mock_attach, mock_get_prompter
    ):
        mock_prompter = MagicMock()
        mock_get_prompter.return_value = mock_prompter

        mock_rule = MagicMock()
        mock_rule.name = "test_rule"
        mock_attach.return_value = [mock_rule]

        mock_prompt_args.return_value = {"arg1": "value1"}
        mock_execute.return_value = (True, "Rule passed")

        @emit_events(DevRulesEvent.PRE_COMMIT)
        def test_func():
            return "success"

        result = test_func()
        self.assertEqual(result, "success")
        mock_prompter.header.assert_called_once_with("Running custom rules...")
        mock_prompter.info.assert_called_once_with("Running custom rule: test_rule")
        mock_prompt_args.assert_called_once_with("test_rule")
        mock_execute.assert_called_once_with("test_rule", arg1="value1")
        mock_prompter.success.assert_called_once_with("Rule passed")

    @patch("devrules.adapters.prompters.factory.get_default_prompter")
    @patch("devrules.utils.decorators.attach_event")
    @patch("devrules.utils.decorators.prompt_for_rule_arguments")
    @patch("devrules.utils.decorators.execute_rule")
    def test_emit_events_with_custom_rules_failure(
        self, mock_execute, mock_prompt_args, mock_attach, mock_get_prompter
    ):
        mock_prompter = MagicMock()
        mock_get_prompter.return_value = mock_prompter

        mock_rule = MagicMock()
        mock_rule.name = "failing_rule"
        mock_attach.return_value = [mock_rule]

        mock_prompt_args.return_value = {}
        mock_execute.return_value = (False, "Rule failed")

        @emit_events(DevRulesEvent.PRE_COMMIT)
        def test_func():
            return "should not reach"

        test_func()
        mock_prompter.error.assert_called_once_with("Rule failed")
        mock_prompter.exit.assert_called_once_with(1)

    @patch("devrules.adapters.prompters.factory.get_default_prompter")
    @patch("devrules.utils.decorators.attach_event")
    @patch("devrules.utils.decorators.prompt_for_rule_arguments")
    @patch("devrules.utils.decorators.execute_rule")
    def test_emit_events_multiple_rules(
        self, mock_execute, mock_prompt_args, mock_attach, mock_get_prompter
    ):
        mock_prompter = MagicMock()
        mock_get_prompter.return_value = mock_prompter

        mock_rule1 = MagicMock()
        mock_rule1.name = "rule1"
        mock_rule2 = MagicMock()
        mock_rule2.name = "rule2"
        mock_attach.return_value = [mock_rule1, mock_rule2]

        mock_prompt_args.return_value = {}
        mock_execute.return_value = (True, "Success\n")

        @emit_events([DevRulesEvent.PRE_COMMIT])
        def test_func():
            return "done"

        result = test_func()
        self.assertEqual(result, "done")
        self.assertEqual(mock_execute.call_count, 2)
        self.assertEqual(mock_prompter.success.call_count, 2)


if __name__ == "__main__":
    unittest.main()
