from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr


class RegistrationPending(BaseModel):
    status: Literal["verification_required"] = "verification_required"
    resend_after_seconds: int


class VerifyEmailRequest(BaseModel):
    token: SecretStr = Field(min_length=43, max_length=43)
    password: SecretStr = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, password: SecretStr) -> SecretStr:
        if len(password.get_secret_value().encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return password


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr


class TokenResponse(BaseModel):
    token: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool


class MessageResponse(BaseModel):
    message: str
