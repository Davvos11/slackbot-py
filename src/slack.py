from __future__ import annotations

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

if TYPE_CHECKING:
    from ns import Trip


def get_time(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    local = dt.astimezone(ZoneInfo("Europe/Amsterdam"))
    return local.strftime("%H:%M")


def format_slack_user(username: Optional[str]) -> str:
    if not username:
        return ""
    if username.startswith("<@") and username.endswith(">"):
        return username
    if username.startswith("@"):
        username = username[1:]
    return f"<@{username}>"


def send_trein_message(trips: list[Trip], amount: int, url: str, user_id: Optional[str] = None):
    blocks = []
    mention = format_slack_user(user_id)
    if mention:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{mention}, je trein update:",
                },
            }
        )
    non_cancelled = 0
    for trip in trips:
        if len(trip.legs) == 0:
            continue
        first_leg = trip.legs[0]
        time = get_time(first_leg.datetime_planned)
        if first_leg.datetime_actual is not None and first_leg.datetime_planned != first_leg.datetime_actual:
            time = f"~{time}~ {get_time(first_leg.datetime_actual)}"
        duration = f"{trip.duration_planned} minuten"
        if trip.duration_actual != trip.duration_planned:
            duration = f"~{trip.duration_planned}~ {trip.duration_actual} minuten"
        spoor = f"Spoor {first_leg.track_planned}"
        if first_leg.track_actual is not None and first_leg.track_actual != first_leg.track_planned:
            spoor = f"Spoor ~{first_leg.track_planned}~ {first_leg.track_actual}"
        cancelled = ""
        if trip.status != "NORMAL":
            cancelled = ":spannend: "
        title = f"{cancelled}{time} - {duration} - {spoor}"
        if trip.url:
            title = f"<{trip.url}|{title}>"
        text = f"*{title}*"
        if trip.message:
            text += f"\n{trip.message}"
        for leg in trip.legs:
            text += f"\n- {leg.description}"
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text,
                },
            }
        )
        blocks.append({"type": "divider"})
        if not trip.cancelled:
            non_cancelled += 1
        if non_cancelled >= amount:
            break
    payload = {
        "text": f"{mention} trein update".strip(),
        "blocks": blocks
    }
    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Open reisplanner",
                    },
                    "url": url,
                }
            ],
        }
    )

    webhook_url = os.getenv("SLACK_TREIN_WEBHOOK")
    result = requests.post(webhook_url, json=payload, timeout=10)
    result.raise_for_status()


def send_error_message(error: str):
    webhook_url = os.getenv("SLACK_TREIN_WEBHOOK")
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"```\n{error}\n```",
            },
        }]
    payload = {"text": f"Error bij trein update", "blocks": blocks}
    result = requests.post(webhook_url, json=payload, timeout=10)
    result.raise_for_status()
