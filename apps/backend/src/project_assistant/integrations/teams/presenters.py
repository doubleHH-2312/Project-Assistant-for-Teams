import json
from dataclasses import dataclass
from typing import Any

from project_assistant.modules.actions.contracts import (
    ActionResult,
    ConversationType,
)

from .cards import load_card


@dataclass(frozen=True, slots=True)
class TeamsPresentation:
    shared_text: str
    private_card: dict[str, Any]


def present_action_result(
    result: ActionResult, conversation_type: ConversationType
) -> TeamsPresentation:
    private_card = _result_card(result)
    if result.private and conversation_type != ConversationType.PERSONAL:
        return TeamsPresentation(
            shared_text=(
                "I prepared a private result. Continue in your personal chat with the bot."
            ),
            private_card=private_card,
        )
    return TeamsPresentation(
        shared_text=result.message or "Action completed.",
        private_card=private_card,
    )


def _result_card(result: ActionResult) -> dict[str, Any]:
    data = dict(result.data)
    action = str(data.get("action", ""))
    if result.kind == "form" and action == "daily":
        card = load_card("daily", data)
        _set_choices(card, "projectId", data.get("projects", []))
        return card
    if result.kind == "team_selection":
        card = load_card("team-selector", data)
        team_ids = data.get("teamIds", [])
        _set_choices(
            card,
            "teamId",
            [{"id": team_id, "name": team_id} for team_id in team_ids],
        )
        return card
    if result.kind in {
        "weekly_draft",
        "weekly_team_draft",
        "weekly_multi_team_draft",
    }:
        card = load_card("weekly-review", data)
        _set_input_value(card, "content", json.dumps(data.get("content", {}), indent=2))
        return card
    card = load_card("summary", data)
    card["body"].append(
        {
            "type": "TextBlock",
            "text": result.message or "Action completed.",
            "wrap": True,
        }
    )
    return card


def _set_choices(
    card: dict[str, Any], input_id: str, options: object
) -> None:
    if not isinstance(options, list):
        return
    for element in card.get("body", []):
        if element.get("id") == input_id:
            element.pop("choices.data", None)
            element["choices"] = [
                {
                    "title": str(option.get("name", option.get("id", ""))),
                    "value": str(option.get("id", "")),
                }
                for option in options
                if isinstance(option, dict) and option.get("id")
            ]


def _set_input_value(card: dict[str, Any], input_id: str, value: str) -> None:
    for element in card.get("body", []):
        if element.get("id") == input_id:
            element["value"] = value
