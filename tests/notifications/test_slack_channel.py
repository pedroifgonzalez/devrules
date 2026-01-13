import os

import pytest
import vcr

from devrules.core.git_service import get_current_repo_name
from devrules.notifications.channels.slack import SlackChannel, resolve_slack_channel
from devrules.notifications.events import DeployEvent, NotificationEvent

vcr_instance = vcr.VCR(
    cassette_library_dir="tests/notifications/cassettes",
    filter_headers=["authorization"],
    decode_compressed_response=True,
)


@vcr_instance.use_cassette("slack_deploy.yaml")
def test_slack_channel_send_deploy_event_real():
    token = os.getenv("SLACK_TOKEN")
    channel_name = os.getenv("SLACK_CHANNEL")

    if not token or not channel_name:
        pytest.skip("Slack credentials not configured")

    channel = SlackChannel(
        token=token,
        channel_resolver=lambda event, channels_map: channel_name,
        channels_map={},
    )

    event = DeployEvent(
        repo=get_current_repo_name(),
        branch="feature/vcr-test",
        environment="dev",
        author="devrules-test",
    )

    # Act (real HTTP call on first run)
    channel.send(event)

    assert True


class TestResolveSlackChannel:
    def test_resolve_slack_channel_only_deploy_event_is_supported(self):
        # arrange
        class CustomEvent(NotificationEvent):
            pass

        # act
        channel = resolve_slack_channel(event=CustomEvent(), channels_map={})
        # assert
        assert channel is None

    def test_no_slack_channel_configured_for_event(self):
        # arrange(create supported event)
        deploy_event = DeployEvent(
            repo="devrules",
            branch="develop",
            author="pedroifgonzalez",
            environment="dev",
        )
        # act & assert
        with pytest.raises(ValueError):
            resolve_slack_channel(event=deploy_event, channels_map={})

    def test_channel_configured_for_event(self):
        # arrange(create supported event)
        deploy_event = DeployEvent(
            repo="devrules",
            branch="develop",
            author="pedroifgonzalez",
            environment="dev",
        )
        channel = resolve_slack_channel(
            event=deploy_event, channels_map={deploy_event.type: "#dev"}
        )
        # assert
        assert channel == "#dev"
