from datetime import UTC, date, datetime
from importlib import import_module

import pytest

from project_assistant.integrations.llm.provider import MockLLMProvider
from project_assistant.modules.audit.models import WorkItemStatusEvent
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.weekly_reports.models import (
    ReportScope,
    WeeklyReport,
    WeeklyReportStatus,
)


def _evidence_module():  # type: ignore[no-untyped-def]
    try:
        return import_module("project_assistant.modules.weekly_reports.evidence")
    except ModuleNotFoundError:
        pytest.fail("Weekly evidence builder is not implemented")


def _weekly(
    report_id: str,
    scope: ReportScope,
    team_id: str,
    status: WeeklyReportStatus,
    content: dict,
    subject_user_id: str | None = None,
) -> WeeklyReport:
    recorded_at = datetime(2026, 10, 3, 9, tzinfo=UTC)
    return WeeklyReport(
        id=report_id,
        scope=scope,
        subject_user_id=subject_user_id,
        team_id=team_id,
        week_start=date(2026, 9, 28),
        week_end=date(2026, 10, 2),
        content_json=content,
        missing_contributors=[],
        input_record_ids=[],
        generation_source="MOCK",
        generation_metadata={},
        status=status,
        template_id="template-1",
        template_version=1,
        created_by="user-1",
        confirmed_at=(
            recorded_at if status == WeeklyReportStatus.CONFIRMED else None
        ),
        created_at=recorded_at,
        updated_at=recorded_at,
    )


def test_member_evidence_groups_tasks_by_project_and_retains_exact_blocker_event() -> None:
    module = _evidence_module()
    recorded_at = datetime(2026, 10, 4, 2, tzinfo=UTC)
    report = DailyReport(
        id="daily-1",
        team_id="team-1",
        user_id="user-1",
        project_id="project-a",
        work_item_id="item-1",
        report_date=date(2026, 10, 2),
        status=WorkStatus.BLOCKED,
        work_summary="Waiting for access",
        blocker=None,
        next_action="Escalate",
        submitted_at=recorded_at,
    )
    event = WorkItemStatusEvent(
        id="event-1",
        daily_report_id=report.id,
        action_invocation_id="invocation-1",
        team_id=report.team_id,
        project_id=report.project_id,
        work_item_id=report.work_item_id,
        user_id=report.user_id,
        status=WorkStatus.BLOCKED,
        effective_blocker="Waiting for access",
        business_date=report.report_date,
        recorded_at=recorded_at,
        local_datetime=datetime(2026, 10, 4, 9, tzinfo=UTC),
        local_date=date(2026, 10, 4),
        timezone="Asia/Ho_Chi_Minh",
        source="TEAMS",
    )

    bundle = module.build_member_evidence([report], [event])

    assert bundle.payload == [
        {
            "teamId": "team-1",
            "projectId": "project-a",
            "tasks": [
                {
                    "dailyReportId": "daily-1",
                    "workItemId": "item-1",
                    "businessDate": "2026-10-02",
                    "status": "BLOCKED",
                    "workSummary": "Waiting for access",
                    "effectiveBlocker": "Waiting for access",
                    "nextAction": "Escalate",
                    "blockerEvents": [
                        {
                            "eventId": "event-1",
                            "recordedDate": "2026-10-04",
                            "effectiveBlocker": "Waiting for access",
                        }
                    ],
                    "evidenceIds": ["daily-1", "event-1"],
                }
            ],
        }
    ]
    assert [(ref.source_type, ref.source_id) for ref in bundle.references] == [
        ("DAILY_REPORT", "daily-1"),
        ("STATUS_EVENT", "event-1"),
    ]


def test_team_and_multiteam_evidence_use_only_confirmed_direct_inputs() -> None:
    module = _evidence_module()
    projects = [
        {
            "projectId": "project-a",
            "completedTasks": [
                {"text": "Shipped API", "evidenceIds": ["daily-1"]}
            ],
            "inProgressTasks": [],
            "blockers": [],
            "risks": [],
            "issues": [],
            "lessonsLearned": [],
            "nextActions": [],
        }
    ]
    confirmed_member = _weekly(
        "member-confirmed",
        ReportScope.MEMBER,
        "team-a",
        WeeklyReportStatus.CONFIRMED,
        {"projects": projects},
        "user-1",
    )
    draft_member = _weekly(
        "member-draft",
        ReportScope.MEMBER,
        "team-a",
        WeeklyReportStatus.GENERATED,
        {"projects": [{"projectId": "must-not-appear"}]},
        "user-2",
    )
    team_bundle = module.build_team_evidence([confirmed_member, draft_member])

    assert [item["memberReportId"] for item in team_bundle.payload] == [
        "member-confirmed"
    ]
    assert team_bundle.payload[0]["projects"] == projects
    assert [ref.source_id for ref in team_bundle.references] == ["member-confirmed"]

    confirmed_team = _weekly(
        "team-confirmed",
        ReportScope.TEAM,
        "team-a",
        WeeklyReportStatus.CONFIRMED,
        {"projects": projects},
    )
    draft_team = _weekly(
        "team-draft",
        ReportScope.TEAM,
        "team-b",
        WeeklyReportStatus.GENERATED,
        {"projects": [{"projectId": "must-not-appear"}]},
    )
    multi_bundle = module.build_multiteam_evidence([confirmed_team, draft_team])

    assert multi_bundle.payload == [
        {
            "teamReportId": "team-confirmed",
            "teamId": "team-a",
            "projects": projects,
            "evidenceIds": ["team-confirmed"],
        }
    ]
    assert [ref.source_id for ref in multi_bundle.references] == ["team-confirmed"]


def test_generated_content_rejects_unknown_project_and_evidence_ids() -> None:
    module = _evidence_module()
    invented_project = {
        "projects": [
            {
                "projectId": "project-invented",
                "completedTasks": [
                    {"text": "Invented fact", "evidenceIds": ["daily-1"]}
                ],
            }
        ]
    }
    invented_evidence = {
        "projects": [
            {
                "projectId": "project-a",
                "completedTasks": [
                    {"text": "Invented fact", "evidenceIds": ["daily-invented"]}
                ],
            }
        ]
    }

    with pytest.raises(ValueError, match="unknown Project"):
        module.validate_evidence_references(
            invented_project,
            {"daily-1"},
            allowed_team_ids={"team-1"},
            allowed_project_ids={"project-a"},
        )
    with pytest.raises(ValueError, match="unknown evidence"):
        module.validate_evidence_references(
            invented_evidence,
            {"daily-1"},
            allowed_team_ids={"team-1"},
            allowed_project_ids={"project-a"},
        )


@pytest.mark.asyncio
async def test_mock_provider_generates_project_sections_without_inventing_evidence() -> None:
    schema = {
        "type": "object",
        "required": ["projects"],
        "properties": {"projects": {"type": "array"}},
        "additionalProperties": False,
    }
    evidence = [
        {
            "teamId": "team-1",
            "projectId": "project-a",
            "tasks": [
                {
                    "dailyReportId": "daily-1",
                    "workItemId": "OPS-001",
                    "businessDate": "2026-10-02",
                    "status": "DONE",
                    "workSummary": "Implemented validation",
                    "effectiveBlocker": None,
                    "nextAction": "Start integration",
                    "blockerEvents": [],
                    "evidenceIds": ["daily-1"],
                }
            ],
        }
    ]

    result = await MockLLMProvider().generate(schema, evidence)

    project = result.content["projects"][0]
    assert project["projectId"] == "project-a"
    assert project["completedTasks"] == [
        {"text": "OPS-001: Implemented validation", "evidenceIds": ["daily-1"]}
    ]
    assert project["nextActions"] == [
        {"text": "OPS-001: Start integration", "evidenceIds": ["daily-1"]}
    ]
    assert project["risks"] == []
    assert project["issues"] == []
    assert project["lessonsLearned"] == []
