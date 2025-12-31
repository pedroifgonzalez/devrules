"""Tests for the custom rules engine."""

import pytest

from devrules.config import CustomRulesConfig
from devrules.core.rules_engine import RuleRegistry, discover_rules, execute_rule, rule


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
