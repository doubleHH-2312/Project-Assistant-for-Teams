from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.modules.audit.models import ActionInvocation


class SqlAlchemyAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_idempotency_key(self, key: str) -> ActionInvocation | None:
        return await self.session.scalar(
            select(ActionInvocation).where(ActionInvocation.idempotency_key == key)
        )

    async def get(self, invocation_id: str) -> ActionInvocation | None:
        return await self.session.get(ActionInvocation, invocation_id)

    async def save(self, invocation: ActionInvocation) -> ActionInvocation:
        self.session.add(invocation)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            replay = await self.find_by_idempotency_key(invocation.idempotency_key)
            if replay is not None:
                return replay
            raise
        await self.session.refresh(invocation)
        return invocation
