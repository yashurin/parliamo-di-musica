import re

from pydantic import BaseModel, EmailStr, Field, field_validator

_PASSWORD_MIN_LENGTH = 8


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=_PASSWORD_MIN_LENGTH, max_length=128)
    password_confirm: str = Field(min_length=_PASSWORD_MIN_LENGTH, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain at least one number")
        return value

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, value: str, info) -> str:
        password = info.data.get("password")
        if password is not None and value != password:
            raise ValueError("Passwords do not match")
        return value


class RegisterResponse(BaseModel):
    message: str
    email: EmailStr