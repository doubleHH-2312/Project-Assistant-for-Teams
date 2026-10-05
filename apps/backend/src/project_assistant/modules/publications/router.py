from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.core.auth import get_authorization_service, get_current_user
from project_assistant.core.database import get_session
from project_assistant.modules.memberships.service import AuthorizationService
from project_assistant.modules.publications.repository import SqlAlchemyPublicationRepository
from project_assistant.modules.publications.service import PublicationService
from project_assistant.modules.users.models import User

router = APIRouter(prefix="/weekly-reports", tags=["weekly-reports"])


class PublicationModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class PublicationRequest(PublicationModel):
    conversation_id: str = Field(alias="conversationId", min_length=1, max_length=256)


class PublicationRead(PublicationModel):
    id: str
    weekly_report_id: str = Field(alias="weeklyReportId")
    actor_id: str = Field(alias="actorId")
    conversation_id: str = Field(alias="conversationId")
    idempotency_key: str = Field(alias="idempotencyKey")
    published_at: datetime = Field(alias="publishedAt")


async def get_publication_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[AuthorizationService, Depends(get_authorization_service)],
) -> PublicationService:
    return PublicationService(SqlAlchemyPublicationRepository(session), authorization)


@router.post(
    "/{report_id}/publish",
    response_model=PublicationRead,
    status_code=status.HTTP_201_CREATED,
)
async def publish_weekly_report(
    report_id: str,
    request: PublicationRequest,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[PublicationService, Depends(get_publication_service)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=256),
    ],
) -> PublicationRead:
    publication = await service.publish(
        actor, report_id, request.conversation_id, idempotency_key
    )
    return PublicationRead.model_validate(publication)
