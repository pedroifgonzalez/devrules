"""Module containing related logic for events"""

from devrules.core.enum import DevRulesEvent
from devrules.core.rules_engine import RuleDefinition, RuleRegistry


def attach_event(event: DevRulesEvent) -> list[RuleDefinition]:
    """
    Attach an event to trigger registered rules.

    Args:
        event: The event to emit
    """
    hooked_rules = []
    for rule in RuleRegistry.list_rules():
        if rule.hooks and event in rule.hooks:
            hooked_rules.append(rule)
    return hooked_rules
