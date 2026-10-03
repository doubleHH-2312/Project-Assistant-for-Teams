from importlib import import_module

import pytest

from project_assistant.modules.actions.contracts import ActionResult, ConversationType


def _presenters():  # type: ignore[no-untyped-def]
    try:
        return import_module("project_assistant.integrations.teams.presenters")
    except ModuleNotFoundError:
        pytest.fail("Teams presenters are not implemented")


def test_group_result_never_exposes_private_report_content() -> None:
    module = _presenters()
    result = ActionResult(
        kind="weekly_draft",
        message="Draft generated",
        data={"content": {"blockers": ["confidential blocker"]}},
        private=True,
    )

    presentation = module.present_action_result(
        result, ConversationType.TEAM_CHANNEL
    )

    assert "confidential blocker" not in presentation.shared_text
    assert presentation.shared_text == (
        "I prepared a private result. Continue in your personal chat with the bot."
    )
    assert presentation.private_card["data"]["content"]["blockers"] == [
        "confidential blocker"
    ]


def test_personal_result_can_render_structured_private_data() -> None:
    module = _presenters()
    result = ActionResult(
        kind="history",
        message="Daily Report history.",
        data={"dates": [{"date": "2026-10-02"}]},
    )

    presentation = module.present_action_result(result, ConversationType.PERSONAL)

    assert presentation.shared_text == "Daily Report history."
    assert presentation.private_card["data"]["dates"] == [
        {"date": "2026-10-02"}
    ]


def test_daily_form_card_contains_runtime_project_choices() -> None:
    module = _presenters()
    result = ActionResult(
        kind="form",
        message="Complete the Daily Report form.",
        data={
            "action": "daily",
            "teamId": "team-1",
            "projects": [{"id": "project-1", "name": "Project One"}],
            "workItems": [],
        },
    )

    presentation = module.present_action_result(result, ConversationType.PERSONAL)

    project_input = next(
        item
        for item in presentation.private_card["body"]
        if item.get("id") == "projectId"
    )
    assert project_input["choices"] == [
        {"title": "Project One", "value": "project-1"}
    ]
    assert presentation.private_card["actions"][0]["type"] == "Action.Execute"
