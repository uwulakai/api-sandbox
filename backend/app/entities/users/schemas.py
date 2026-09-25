from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=8, max_length=128)


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
