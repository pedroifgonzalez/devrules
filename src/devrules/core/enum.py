"""Module containing enums for DevRules."""

from enum import Enum


class DevRulesEvent(str, Enum):
    """Enum for DevRules events."""

    PRE_COMMIT = "pre_commit"
    POST_COMMIT = "post_commit"
    PRE_PUSH = "pre_push"
    PRE_PR = "pre_pull_request"
    PRE_DEPLOY = "pre_deploy"
    POST_DEPLOY = "post_deploy"
