import os

import pytest
import vcr

from devrules.notifications.channels.slack import SlackChannel
from devrules.notifications.events import DeployEvent

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
        branch="feature/vcr-test",
        environment="dev",
        author="devrules-test",
    )

    # Act (real HTTP call on first run)
    channel.send(event)

    assert True
