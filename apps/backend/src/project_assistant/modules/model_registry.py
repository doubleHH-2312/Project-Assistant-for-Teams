"""Import all ORM models so metadata discovery is deterministic."""

from project_assistant.modules.actions.results import ActionResultRecord
from project_assistant.modules.audit.models import ActionInvocation, WorkItemStatusEvent
from project_assistant.modules.daily_reports.models import DailyReport
from project_assistant.modules.memberships.models import TeamMembership
from project_assistant.modules.notifications.models import (
    NotificationLog,
    TeamsConversation,
    TeamsConversationBinding,
)
from project_assistant.modules.projects.models import Project
from project_assistant.modules.publications.models import ReportPublication
from project_assistant.modules.teams.models import Team
from project_assistant.modules.templates.models import ReportTemplate
from project_assistant.modules.users.models import User
from project_assistant.modules.weekly_reports.models import (
    ReportEvidenceLink,
    WeeklyReport,
    WeeklyReportTeam,
)
from project_assistant.modules.work_items.models import WorkItem

__all__ = [
    "ActionInvocation",
    "ActionResultRecord",
    "DailyReport",
    "TeamMembership",
    "NotificationLog",
    "Project",
    "ReportTemplate",
    "ReportEvidenceLink",
    "ReportPublication",
    "Team",
    "TeamsConversation",
    "TeamsConversationBinding",
    "User",
    "WeeklyReport",
    "WeeklyReportTeam",
    "WorkItem",
    "WorkItemStatusEvent",
]
