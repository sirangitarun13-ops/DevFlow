"""Request and response schemas for authentication."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("A valid email address is required")
        return normalized


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str


class UserRead(BaseModel):
    id: str
    full_name: str
    email: str
    account_status: str
    roles: list[RoleRead]


class UserDirectoryRead(BaseModel):
    """Safe Developer representation used by project managers when building a team."""

    id: UUID
    full_name: str
    email: str
    account_status: str
    roles: list[RoleRead]


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
