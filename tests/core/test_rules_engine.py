"""Tests for the custom rules engine."""

from unittest.mock import MagicMock, patch

import pytest

from devrules.config import CustomRulesConfig
from devrules.core.rules_engine import (
    RuleRegistry,
    discover_rules,
    execute_rule,
    prompt_for_rule_arguments,
    rule,
)


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear registry before each test."""
    RuleRegistry.clear()
    yield


def test_register_and_list_rules():
    """Test registering rules via decorator and listing them."""

    @rule(name="test-rule", description="A test rule")
    def my_rule():
        return True, "Passed"

    rules = RuleRegistry.list_rules()
    assert len(rules) == 1
    assert rules[0].name == "test-rule"
    assert rules[0].description == "A test rule"
    assert rules[0].func == my_rule


def test_register_rule_overwrite():
    """Test registering a rule with the same name overwrites previous one."""

    @rule(name="duplicate-rule")
    def first_rule():
        return True, "First"

    # Register another rule with the same name
    @rule(name="duplicate-rule", description="Updated rule")
    def second_rule():
        return True, "Second"

    rules = RuleRegistry.list_rules()
    assert len(rules) == 1
    assert rules[0].name == "duplicate-rule"
    assert rules[0].description == "Updated rule"  # Latest wins
    assert rules[0].func == second_rule


def test_execute_rule_success():
    """Test successful rule execution."""

    @rule(name="success-rule")
    def my_rule():
        return True, "Success"

    success, msg = execute_rule("success-rule")
    assert success is True
    assert msg == "Success"


def test_execute_rule_failure():
    """Test failed rule execution."""

    @rule(name="fail-rule")
    def my_rule():
        return False, "Failed"

    success, msg = execute_rule("fail-rule")
    assert success is False
    assert msg == "Failed"


def test_execute_rule_not_found():
    """Test execution of non-existent rule."""
    success, msg = execute_rule("non-existent")
    assert success is False
    assert "not found" in msg


def test_execute_rule_with_args():
    """Test execution with arguments injection."""

    @rule(name="args-rule")
    def my_rule(foo):
        return True, f"Value: {foo}"

    success, msg = execute_rule("args-rule", foo="bar", other="ignored")
    assert success is True
    assert msg == "Value: bar"


def test_execute_rule_with_kwargs():
    """Test execution with **kwargs."""

    @rule(name="kwargs-rule")
    def my_rule(**kwargs):
        return True, f"Foo: {kwargs.get('foo')}"

    success, msg = execute_rule("kwargs-rule", foo="baz")
    assert success is True
    assert msg == "Foo: baz"


def test_execute_rule_with_positional_args():
    """Test execution with positional arguments."""

    @rule(name="positional-rule")
    def my_rule(a, b, c):
        return True, f"{a}-{b}-{c}"

    success, msg = execute_rule("positional-rule", "x", "y", "z")
    assert success is True
    assert msg == "x-y-z"


def test_execute_rule_with_mixed_args():
    """Test execution with both positional and keyword arguments."""

    @rule(name="mixed-rule")
    def my_rule(pos1, pos2, kw1=None, kw2=None):
        return True, f"{pos1},{pos2},{kw1},{kw2}"

    success, msg = execute_rule("mixed-rule", "a", "b", kw1="c", kw2="d", extra="ignored")
    assert success is True
    assert msg == "a,b,c,d"


def test_execute_rule_with_defaults():
    """Test execution with default parameter values."""

    @rule(name="default-rule")
    def my_rule(required, optional="default"):
        return True, f"{required}-{optional}"

    success, msg = execute_rule("default-rule", required="test")
    assert success is True
    assert msg == "test-default"


def test_execute_rule_with_varargs():
    """Test execution with *args parameter."""

    @rule(name="varargs-rule")
    def my_rule(first, *args):
        return True, f"{first}:{','.join(args)}"

    success, msg = execute_rule("varargs-rule", "start", "a", "b", "c")
    assert success is True
    assert msg == "start:a,b,c"


def test_execute_rule_exception_handling():
    """Test exception handling during rule execution."""

    @rule(name="exception-rule")
    def my_rule():
        raise ValueError("Test error")

    success, msg = execute_rule("exception-rule")
    assert success is False
    assert "Error executing rule 'exception-rule': Test error" in msg


def test_execute_rule_missing_required_arg():
    """Test execution when required argument is missing."""

    @rule(name="required-arg-rule")
    def my_rule(required_param):
        return True, f"Got: {required_param}"

    success, msg = execute_rule("required-arg-rule")
    assert success is False
    assert "Missing required argument: required_param" in msg


def test_discovery_from_path(tmp_path):
    """Test discovering rules from a file path."""
    rule_file = tmp_path / "custom_check.py"
    rule_file.write_text(
        """
from devrules.core.rules_engine import rule

@rule(name="file-rule")
def file_check():
    return True, "File check"
"""
    )

    config = CustomRulesConfig(paths=[str(rule_file)])
    discover_rules(config)

    rules = RuleRegistry.list_rules()
    assert len(rules) >= 1
    assert any(r.name == "file-rule" for r in rules)


def test_discovery_from_nonexistent_path(tmp_path, capsys):
    """Test discovering rules from non-existent path prints warning."""
    nonexistent_path = str(tmp_path / "nonexistent")

    config = CustomRulesConfig(paths=[nonexistent_path])
    discover_rules(config)

    captured = capsys.readouterr()
    assert "Warning: Rule path does not exist:" in captured.out
    assert nonexistent_path in captured.out


def test_discovery_from_directory(tmp_path):
    """Test discovering rules from a directory."""
    rule_dir = tmp_path / "rules"
    rule_dir.mkdir()
    (rule_dir / "check1.py").write_text(
        """
from devrules.core.rules_engine import rule
@rule(name="dir-rule-1")
def check1(): return True, ""
"""
    )
    (rule_dir / "__init__.py").write_text("")  # Should be ignored or loaded safely

    config = CustomRulesConfig(paths=[str(rule_dir)])
    discover_rules(config)

    rules = RuleRegistry.list_rules()
    assert any(r.name == "dir-rule-1" for r in rules)


def test_discovery_from_package_import_error(capsys):
    """Test discovering rules from packages with import errors."""

    config = CustomRulesConfig(packages=["nonexistent_package_xyz"])
    discover_rules(config)

    captured = capsys.readouterr()
    assert "Warning: Could not import rule package 'nonexistent_package_xyz'" in captured.out


def test_discovery_file_load_error(tmp_path, capsys):
    """Test discovering rules from files that fail to load."""
    bad_file = tmp_path / "bad_rule.py"
    bad_file.write_text("invalid python syntax {{{")  # Syntax error

    config = CustomRulesConfig(paths=[str(bad_file)])
    discover_rules(config)

    captured = capsys.readouterr()
    assert "Warning: Failed to load rule file" in captured.out
    assert str(bad_file) in captured.out


@patch("devrules.cli_commands.prompters.factory.get_default_prompter")
def test_prompt_for_rule_arguments_rule_not_found(mock_get_prompter):
    """Test prompt_for_rule_arguments when rule doesn't exist."""
    result = prompt_for_rule_arguments("nonexistent-rule")
    assert result == {}


@patch("devrules.cli_commands.prompters.factory.get_default_prompter")
def test_prompt_for_rule_arguments_success(mock_get_prompter):
    """Test successful prompting for rule arguments."""
    mock_prompter = MagicMock()
    mock_get_prompter.return_value = mock_prompter

    # Mock prompter input
    mock_prompter.input_text.side_effect = ["value1", "value2"]

    @rule(name="prompt-rule")
    def my_rule(param1: str, param2: int = 42):
        return True, f"{param1}-{param2}"

    result = prompt_for_rule_arguments("prompt-rule")

    assert result == {"param1": "value1", "param2": "value2"}
    assert mock_prompter.input_text.call_count == 2


@patch("devrules.cli_commands.prompters.factory.get_default_prompter")
def test_prompt_for_rule_arguments_with_ignore_defaults(mock_get_prompter):
    """Test prompting when rule has ignore_defaults=True."""
    mock_prompter = MagicMock()
    mock_get_prompter.return_value = mock_prompter

    # Mock prompter input - only param1 should be prompted, param2 uses default
    mock_prompter.input_text.return_value = "custom_value"

    @rule(name="ignore-defaults-rule", ignore_defaults=True)
    def my_rule(param1: str, param2: str = "default_value"):
        return True, f"{param1}-{param2}"

    result = prompt_for_rule_arguments("ignore-defaults-rule")

    assert result == {"param1": "custom_value", "param2": "default_value"}
    # Should only prompt for param1 since param2 has ignore_defaults=True
    mock_prompter.input_text.assert_called_once()


@patch("devrules.cli_commands.prompters.factory.get_default_prompter")
def test_prompt_for_rule_arguments_empty_input_error(mock_get_prompter):
    """Test prompting when user provides empty input for required parameter."""
    mock_prompter = MagicMock()
    mock_get_prompter.return_value = mock_prompter

    # Mock empty input then exit
    mock_prompter.input_text.return_value = ""
    mock_prompter.error = MagicMock()
    mock_prompter.exit = MagicMock(return_value={})

    @rule(name="required-param-rule")
    def my_rule(required: str):
        return True, required

    prompt_for_rule_arguments("required-param-rule")

    mock_prompter.error.assert_called_once_with(
        "No value provided for required argument 'required'"
    )
    mock_prompter.exit.assert_called_once_with(1)
