from __future__ import annotations

import json
import urllib.request
from typing import Callable, Dict, Optional

from yaspin import yaspin

from ..events import DeployEvent, NotificationEvent
from .base import NotificationChannel


class SlackClient:
    def __init__(self, token: str):
        self.token = token

    def post_message(self, channel: str, payload: dict) -> None:
        data = json.dumps(
            {
                "channel": channel,
                **payload,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url="https://slack.com/api/chat.postMessage",
            data=data,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
            if not body.get("ok"):
                raise RuntimeError(f"Slack API error: {body}")


def resolve_slack_channel(event: NotificationEvent, channels_map: Dict[str, str]) -> Optional[str]:
    if isinstance(event, DeployEvent):
        channel = channels_map.get(event.type)
        if not channel:
            raise ValueError(f"No Slack channel configured for event type: {event.type}")
        return channel
    return None


class SlackChannel(NotificationChannel):
    def __init__(
        self,
        token: str,
        channel_resolver: Callable[[NotificationEvent, Dict[str, str]], Optional[str]],
        channels_map: Dict[str, str],
    ):
        self.client = SlackClient(token)
        self.channel_resolver = channel_resolver
        self.channels_map = channels_map

    def supports(self, event: NotificationEvent) -> bool:
        return isinstance(event, DeployEvent)

    def send(self, event: NotificationEvent) -> None:
        with yaspin(text="Resolving channel...", color="green") as spinner:
            try:
                channel = self.channel_resolver(event, self.channels_map)
            except ValueError as e:
                raise RuntimeError(f"Failed to resolve Slack channel: {e}") from e
            if not channel:
                spinner.fail("✘ Channel not configured, skipping message")
                raise RuntimeError("Slack channel not configured for this event type")
            spinner.ok("✔")

        with yaspin(text="Formatting message...", color="green") as spinner:
            payload = self._format_event(event)
            spinner.ok("✔")

        with yaspin(text="Posting message...", color="green") as spinner:
            self.client.post_message(channel, payload)
            spinner.ok("✔")

    def _format_event(self, event: NotificationEvent) -> dict:
        if isinstance(event, DeployEvent):
            return self._format_deploy_event(event)

        raise NotImplementedError(f"Unsupported event: {type(event)}")

    def _format_deploy_event(self, event: DeployEvent) -> dict:
        env_emoji = {
            "dev": "🧪",
            "staging": "🚦",
            "prod": "🚀",
        }.get(event.environment, "📦")

        return {
            "text": f"Deployment to {event.environment}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{env_emoji} Deployment started",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Branch:* `{event.branch}`\n*Environment:* `{event.environment}`\n*Author:* `{event.author}`",
                    },
                },
            ],
        }
