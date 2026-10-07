from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Any

from project_assistant.modules.audit.models import WorkItemStatusEvent
from project_assistant.modules.daily_reports.models import DailyReport
from project_assistant.modules.weekly_reports.models import (
    ReportScope,
    WeeklyReport,
    WeeklyReportStatus,
)


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    source_type: str
    source_id: str
    team_id: str
    project_id: str | None
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    payload: list[dict[str, Any]]
    references: tuple[EvidenceReference, ...]


def build_member_evidence(
    reports: list[DailyReport],
    events: list[WorkItemStatusEvent],
) -> EvidenceBundle:
    events_by_report: dict[str, list[WorkItemStatusEvent]] = {}
    for event in events:
        events_by_report.setdefault(event.daily_report_id, []).append(event)
    projects: dict[tuple[str, str], list[dict[str, Any]]] = {}
    references: list[EvidenceReference] = []
    for report in sorted(
        reports,
        key=lambda item: (item.team_id, item.project_id, item.report_date, item.work_item_id),
    ):
        related_events = sorted(
            events_by_report.get(report.id, []),
            key=lambda item: (item.recorded_at, item.id),
        )
        evidence_ids = [report.id, *(event.id for event in related_events)]
        projects.setdefault((report.team_id, report.project_id), []).append(
            {
                "dailyReportId": report.id,
                "workItemId": report.work_item_id,
                "businessDate": report.report_date.isoformat(),
                "status": report.status.value,
                "workSummary": report.work_summary,
                "effectiveBlocker": report.effective_blocker,
                "nextAction": report.next_action,
                "blockerEvents": [
                    {
                        "eventId": event.id,
                        "recordedDate": event.local_date.isoformat(),
                        "effectiveBlocker": event.effective_blocker,
                    }
                    for event in related_events
                    if event.effective_blocker is not None
                ],
                "evidenceIds": evidence_ids,
            }
        )
        references.append(
            EvidenceReference(
                source_type="DAILY_REPORT",
                source_id=report.id,
                team_id=report.team_id,
                project_id=report.project_id,
                recorded_at=report.submitted_at
                or datetime.combine(report.report_date, time.min, tzinfo=UTC),
            )
        )
        references.extend(
            EvidenceReference(
                source_type="STATUS_EVENT",
                source_id=event.id,
                team_id=event.team_id,
                project_id=event.project_id,
                recorded_at=event.recorded_at,
            )
            for event in related_events
        )
    payload = [
        {"teamId": team_id, "projectId": project_id, "tasks": tasks}
        for (team_id, project_id), tasks in sorted(projects.items())
    ]
    return EvidenceBundle(payload=payload, references=tuple(references))


def build_team_evidence(reports: list[WeeklyReport]) -> EvidenceBundle:
    eligible = sorted(
        (
            report
            for report in reports
            if report.scope == ReportScope.MEMBER
            and report.status == WeeklyReportStatus.CONFIRMED
            and report.team_id is not None
        ),
        key=lambda item: (item.subject_user_id or "", item.id),
    )
    return EvidenceBundle(
        payload=[
            {
                "memberReportId": report.id,
                "subjectUserId": report.subject_user_id,
                "teamId": report.team_id,
                "projects": report.content_json.get("projects", []),
                "evidenceIds": [report.id],
            }
            for report in eligible
        ],
        references=tuple(_weekly_reference(report) for report in eligible),
    )


def build_multiteam_evidence(reports: list[WeeklyReport]) -> EvidenceBundle:
    eligible = sorted(
        (
            report
            for report in reports
            if report.scope == ReportScope.TEAM
            and report.status == WeeklyReportStatus.CONFIRMED
            and report.team_id is not None
        ),
        key=lambda item: (item.team_id or "", item.id),
    )
    return EvidenceBundle(
        payload=[
            {
                "teamReportId": report.id,
                "teamId": report.team_id,
                "projects": report.content_json.get("projects", []),
                "evidenceIds": [report.id],
            }
            for report in eligible
        ],
        references=tuple(_weekly_reference(report) for report in eligible),
    )


def _weekly_reference(report: WeeklyReport) -> EvidenceReference:
    assert report.team_id is not None
    recorded_at = report.confirmed_at or report.created_at
    if recorded_at is None:
        recorded_at = datetime.combine(report.week_end, time.max, tzinfo=UTC)
    return EvidenceReference(
        source_type="WEEKLY_REPORT",
        source_id=report.id,
        team_id=report.team_id,
        project_id=None,
        recorded_at=recorded_at,
    )


def validate_evidence_references(
    content: dict[str, Any],
    allowed_source_ids: set[str],
    *,
    allowed_team_ids: set[str] | None = None,
    allowed_project_ids: set[str] | None = None,
) -> None:
    factual_sections = {
        "completedTasks",
        "inProgressTasks",
        "blockers",
        "risks",
        "issues",
        "lessonsLearned",
        "nextActions",
    }

    def visit(value: Any, parent_key: str | None = None) -> None:
        if isinstance(value, dict):
            team_id = value.get("teamId")
            if (
                isinstance(team_id, str)
                and allowed_team_ids is not None
                and team_id not in allowed_team_ids
            ):
                raise ValueError("Generated report references an unknown Team")
            project_id = value.get("projectId")
            if (
                isinstance(project_id, str)
                and allowed_project_ids is not None
                and project_id not in allowed_project_ids
            ):
                raise ValueError("Generated report references an unknown Project")
            for key, nested in value.items():
                visit(nested, key)
            return
        if not isinstance(value, list):
            return
        if parent_key in factual_sections:
            for item in value:
                if not isinstance(item, dict):
                    raise ValueError("Generated report items must be objects")
                evidence_ids = item.get("evidenceIds")
                if not isinstance(evidence_ids, list) or not evidence_ids:
                    raise ValueError("Every generated report item needs evidenceIds")
                if any(
                    not isinstance(source_id, str) or source_id not in allowed_source_ids
                    for source_id in evidence_ids
                ):
                    raise ValueError("Generated report references unknown evidence")
        for item in value:
            visit(item, parent_key)

    visit(content)


def collect_scope_ids(evidence: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    team_ids: set[str] = set()
    project_ids: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            team_id = value.get("teamId")
            project_id = value.get("projectId")
            if isinstance(team_id, str):
                team_ids.add(team_id)
            if isinstance(project_id, str):
                project_ids.add(project_id)
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(evidence)
    return team_ids, project_ids
