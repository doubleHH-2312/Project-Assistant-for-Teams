from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from project_assistant.modules.daily_reports.models import WorkStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class DailyReportCreate(ApiModel):
    project_id: str = Field(alias="projectId")
    work_item_id: str = Field(alias="workItemId")
    report_date: date = Field(alias="reportDate")
    status: WorkStatus
    work_summary: str = Field(alias="workSummary", min_length=1, max_length=4000)
    blocker: str | None = Field(default=None, max_length=4000)
    next_action: str = Field(alias="nextAction", min_length=1, max_length=2000)


class DailyReportUpdate(ApiModel):
    status: WorkStatus | None = None
    work_summary: str | None = Field(
        default=None, alias="workSummary", min_length=1, max_length=4000
    )
    blocker: str | None = Field(default=None, max_length=4000)
    next_action: str | None = Field(
        default=None, alias="nextAction", min_length=1, max_length=2000
    )


class DailyReportRead(ApiModel):
    id: str
    user_id: str = Field(alias="userId")
    project_id: str = Field(alias="projectId")
    work_item_id: str = Field(alias="workItemId")
    report_date: date = Field(alias="reportDate")
    status: WorkStatus
    work_summary: str = Field(alias="workSummary")
    blocker: str | None
    effective_blocker: str | None = Field(alias="effectiveBlocker")
    next_action: str = Field(alias="nextAction")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
