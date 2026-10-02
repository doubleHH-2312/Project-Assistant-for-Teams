from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from project_assistant.core.database import Base


class UserRole(StrEnum):
    MEMBER = "MEMBER"
    LEAD = "LEAD"
    PM = "PM"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    external_user_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", native_enum=False)
    )
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
