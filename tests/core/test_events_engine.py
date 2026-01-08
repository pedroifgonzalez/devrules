"""Tests for the events engine."""

import pytest

from devrules.core.enum import DevRulesEvent
from devrules.core.events_engine import attach_event
from devrules.core.rules_engine import RuleRegistry, rule


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear registry before each test."""
    RuleRegistry.clear()
    yield


def test_attach_event_no_rules():
    """Test attach_event when no rules are registered."""
    hooked_rules = attach_event(DevRulesEvent.PRE_COMMIT)
    assert hooked_rules == []


def test_attach_event_no_matching_hooks():
    """Test attach_event when rules exist but none match the event."""

    @rule(name="test-rule", hooks=[DevRulesEvent.POST_COMMIT])
    def my_rule():
        return True, "Passed"

    hooked_rules = attach_event(DevRulesEvent.PRE_COMMIT)
    assert hooked_rules == []


def test_attach_event_single_matching_rule():
    """Test attach_event with a single rule matching the event."""

    @rule(name="pre-commit-rule", hooks=[DevRulesEvent.PRE_COMMIT])
    def my_rule():
        return True, "Passed"

    hooked_rules = attach_event(DevRulesEvent.PRE_COMMIT)
    assert len(hooked_rules) == 1
    assert hooked_rules[0].name == "pre-commit-rule"


def test_attach_event_multiple_matching_rules():
    """Test attach_event with multiple rules matching the event."""

    @rule(name="rule-1", hooks=[DevRulesEvent.PRE_COMMIT])
    def rule_1():
        return True, "Rule 1"

    @rule(name="rule-2", hooks=[DevRulesEvent.PRE_COMMIT])
    def rule_2():
        return True, "Rule 2"

    @rule(name="rule-3", hooks=[DevRulesEvent.POST_COMMIT])
    def rule_3():
        return True, "Rule 3"

    hooked_rules = attach_event(DevRulesEvent.PRE_COMMIT)
    assert len(hooked_rules) == 2
    rule_names = [r.name for r in hooked_rules]
    assert "rule-1" in rule_names
    assert "rule-2" in rule_names
    assert "rule-3" not in rule_names


def test_attach_event_rule_with_multiple_hooks():
    """Test attach_event with a rule that has multiple hooks."""

    @rule(
        name="multi-hook-rule",
        hooks=[DevRulesEvent.PRE_COMMIT, DevRulesEvent.PRE_PUSH, DevRulesEvent.PRE_PR],
    )
    def my_rule():
        return True, "Passed"

    hooked_rules_pre_commit = attach_event(DevRulesEvent.PRE_COMMIT)
    assert len(hooked_rules_pre_commit) == 1
    assert hooked_rules_pre_commit[0].name == "multi-hook-rule"

    hooked_rules_pre_push = attach_event(DevRulesEvent.PRE_PUSH)
    assert len(hooked_rules_pre_push) == 1
    assert hooked_rules_pre_push[0].name == "multi-hook-rule"

    hooked_rules_post_commit = attach_event(DevRulesEvent.POST_COMMIT)
    assert len(hooked_rules_post_commit) == 0


def test_attach_event_rule_with_no_hooks():
    """Test attach_event with a rule that has no hooks defined."""

    @rule(name="no-hooks-rule")
    def my_rule():
        return True, "Passed"

    hooked_rules = attach_event(DevRulesEvent.PRE_COMMIT)
    assert hooked_rules == []


def test_attach_event_rule_with_empty_hooks():
    """Test attach_event with a rule that has an empty hooks list."""

    @rule(name="empty-hooks-rule", hooks=[])
    def my_rule():
        return True, "Passed"

    hooked_rules = attach_event(DevRulesEvent.PRE_COMMIT)
    assert hooked_rules == []


def test_attach_event_all_event_types():
    """Test attach_event with all different event types."""

    @rule(name="pre-commit-rule", hooks=[DevRulesEvent.PRE_COMMIT])
    def pre_commit_rule():
        return True, "Pre-commit"

    @rule(name="post-commit-rule", hooks=[DevRulesEvent.POST_COMMIT])
    def post_commit_rule():
        return True, "Post-commit"

    @rule(name="pre-push-rule", hooks=[DevRulesEvent.PRE_PUSH])
    def pre_push_rule():
        return True, "Pre-push"

    @rule(name="pre-pr-rule", hooks=[DevRulesEvent.PRE_PR])
    def pre_pr_rule():
        return True, "Pre-PR"

    @rule(name="pre-deploy-rule", hooks=[DevRulesEvent.PRE_DEPLOY])
    def pre_deploy_rule():
        return True, "Pre-deploy"

    @rule(name="post-deploy-rule", hooks=[DevRulesEvent.POST_DEPLOY])
    def post_deploy_rule():
        return True, "Post-deploy"

    assert len(attach_event(DevRulesEvent.PRE_COMMIT)) == 1
    assert len(attach_event(DevRulesEvent.POST_COMMIT)) == 1
    assert len(attach_event(DevRulesEvent.PRE_PUSH)) == 1
    assert len(attach_event(DevRulesEvent.PRE_PR)) == 1
    assert len(attach_event(DevRulesEvent.PRE_DEPLOY)) == 1
    assert len(attach_event(DevRulesEvent.POST_DEPLOY)) == 1


def test_attach_event_returns_rule_definitions():
    """Test that attach_event returns RuleDefinition objects with correct attributes."""

    @rule(
        name="detailed-rule", description="A detailed test rule", hooks=[DevRulesEvent.PRE_COMMIT]
    )
    def my_rule():
        return True, "Passed"

    hooked_rules = attach_event(DevRulesEvent.PRE_COMMIT)
    assert len(hooked_rules) == 1
    rule_def = hooked_rules[0]
    assert rule_def.name == "detailed-rule"
    assert rule_def.description == "A detailed test rule"
    assert rule_def.func == my_rule
    assert DevRulesEvent.PRE_COMMIT in rule_def.hooks
