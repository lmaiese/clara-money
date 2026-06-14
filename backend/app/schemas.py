from pydantic import BaseModel, EmailStr, field_validator
from typing import Literal
import uuid


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ProfilePatch(BaseModel):
    age: int | None = None
    monthly_income: int | None = None
    monthly_expenses: int | None = None
    liquid_savings: int | None = None
    existing_investments: int | None = None
    goal: Literal["growth", "house", "pension"] | None = None
    horizon_years: int | None = None
    onboarding_step: int | None = None

    @field_validator("age")
    @classmethod
    def validate_age(cls, v: int | None) -> int | None:
        if v is not None and not (18 <= v <= 75):
            raise ValueError("age must be between 18 and 75")
        return v

    @field_validator("monthly_income")
    @classmethod
    def validate_income(cls, v: int | None) -> int | None:
        if v is not None and not (0 < v <= 50000):
            raise ValueError("monthly_income must be between 1 and 50000")
        return v

    @field_validator("monthly_expenses")
    @classmethod
    def validate_expenses(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("monthly_expenses must be > 0")
        return v

    @field_validator("liquid_savings", "existing_investments")
    @classmethod
    def validate_non_negative(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("value must be >= 0")
        return v

    model_config = {"extra": "forbid"}


class ProfileResponse(BaseModel):
    user_id: uuid.UUID
    age: int | None
    monthly_income: int | None
    monthly_expenses: int | None
    liquid_savings: int | None
    existing_investments: int | None
    goal: str | None
    horizon_years: int | None
    onboarding_step: int

    model_config = {"from_attributes": True}
