import json
from pathlib import Path

from project_assistant.integrations.teams.cards import load_card

CARDS = ("daily", "team-selector", "weekly-review", "summary")


def test_all_teams_cards_use_action_execute() -> None:
    for name in CARDS:
        card = load_card(name)
        assert card["type"] == "AdaptiveCard"
        assert all(action["type"] == "Action.Execute" for action in card["actions"])


def test_manifest_declares_bot_scopes_and_commands() -> None:
    manifest_path = Path("apps/teams-app/manifest/manifest.template.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    bot = manifest["bots"][0]
    assert set(bot["scopes"]) == {"personal", "groupChat", "team"}
    commands = {
        command["title"]
        for command_list in bot["commandLists"]
        for command in command_list["commands"]
    }
    assert {
        "help",
        "daily",
        "history",
        "daily-summary",
        "weekly",
        "weekly-team",
        "weekly-multi-team",
    }.issubset(commands)
