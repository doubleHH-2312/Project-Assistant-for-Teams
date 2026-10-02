from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from project_assistant.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), default="legacy-tenant", index=True)
    external_user_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
