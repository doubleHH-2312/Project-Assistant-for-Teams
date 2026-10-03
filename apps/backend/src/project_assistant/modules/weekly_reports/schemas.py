from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from project_assistant.modules.weekly_reports.models import ReportScope, WeeklyReportStatus


class WeeklyApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class WeeklyGenerateRequest(WeeklyApiModel):
    team_id: str | None = Field(default=None, alias="teamId")
    team_ids: list[str] = Field(default_factory=list, alias="teamIds")
    scope: ReportScope
    week_start: date = Field(alias="weekStart")
    subject_user_id: str | None = Field(default=None, alias="subjectUserId")

    @model_validator(mode="after")
    def validate_subject(self) -> "WeeklyGenerateRequest":
        self.team_ids = sorted(set(self.team_ids))
        if self.scope == ReportScope.MULTI_TEAM:
            if self.team_id is not None:
                raise ValueError("Multi-team reports cannot have one teamId")
            if len(self.team_ids) < 2:
                raise ValueError("Multi-team reports require at least two Teams")
            if self.subject_user_id is not None:
                raise ValueError("Multi-team reports cannot have a subject user")
            return self
        if self.team_id is None:
            raise ValueError("Member and Team reports require teamId")
        if self.team_ids:
            raise ValueError("Member and Team reports cannot have teamIds")
        if self.scope == ReportScope.TEAM and self.subject_user_id is not None:
            raise ValueError("Team reports cannot have a subject user")
        return self


class WeeklyUpdateRequest(WeeklyApiModel):
    content_json: dict[str, Any] = Field(alias="contentJson")


class WeeklyReportRead(WeeklyApiModel):
    id: str
    scope: ReportScope
    subject_user_id: str | None = Field(alias="subjectUserId")
    team_id: str | None = Field(alias="teamId")
    team_ids: list[str] = Field(default_factory=list, alias="teamIds")
    week_start: date = Field(alias="weekStart")
    week_end: date = Field(alias="weekEnd")
    content_json: dict[str, Any] = Field(alias="contentJson")
    missing_contributors: list[str] = Field(alias="missingContributors")
    input_record_ids: list[str] = Field(alias="inputRecordIds")
    generation_source: str = Field(alias="generationSource")
    generation_metadata: dict[str, Any] = Field(alias="generationMetadata")
    status: WeeklyReportStatus
    template_id: str = Field(alias="templateId")
    template_version: int = Field(alias="templateVersion")
    supersedes_id: str | None = Field(alias="supersedesId")
    confirmed_at: datetime | None = Field(alias="confirmedAt")
