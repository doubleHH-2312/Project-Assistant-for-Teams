import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

_CARDS_ROOT = Path(__file__).resolve().parents[5] / "teams-app" / "adaptive-cards"


def load_card(name: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    if not name.replace("-", "").isalnum():
        raise ValueError("Invalid Adaptive Card name")
    path = _CARDS_ROOT / f"{name}.json"
    card = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    if card.get("type") != "AdaptiveCard":
        raise ValueError(f"{name} is not an Adaptive Card")
    rendered = deepcopy(card)
    if data:
        rendered["data"] = data
    return rendered


def welcome_card() -> dict[str, Any]:
    return load_card("summary", {"action": "help", "mode": "welcome"})
