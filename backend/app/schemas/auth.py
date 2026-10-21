from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

# "Forgot password" works without e-mail: a question chosen from this list, answered at sign-up.
SECURITY_QUESTIONS = (
    "What was the name of your first school?",
    "In which city were you born?",
    "What was the name of your first pet?",
    "What is your mother's maiden name?",
    "What was the make of your first vehicle?",
    "What is your favourite childhood dish?",
)

Password = Annotated[str, Field(min_length=8, max_length=128)]
Answer = Annotated[str, Field(min_length=2, max_length=100)]


def check_password(value: str) -> str:
    if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
        raise ValueError("Password must contain at least one letter and one digit")
    return value


def check_question(value: str | None) -> str | None:
    if value is not None and value not in SECURITY_QUESTIONS:
        raise ValueError("Choose one of the listed security questions")
    return value


class UserCreate(BaseModel):
    email: EmailStr
    password: Password
    full_name: str = Field(min_length=2, max_length=120)
    # Optional in the API (older clients, tests); the sign-up form always asks for them.
    security_question: str | None = None
    security_answer: Answer | None = None

    @field_validator("email")
    @classmethod
    def lower_case_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("password")
    @classmethod
    def password_has_letter_and_digit(cls, value: str) -> str:
        return check_password(value)

    @field_validator("security_question")
    @classmethod
    def listed_question(cls, value: str | None) -> str | None:
        return check_question(value)

    @model_validator(mode="after")
    def question_with_answer(self) -> "UserCreate":
        if (self.security_question is None) != (self.security_answer is None):
            raise ValueError("Give both the security question and its answer")
        return self


class UserRead(BaseModel):
    """Public view of a user. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    created_at: datetime
    security_question: str | None = None  # the user's own question (never the answer)


class NameUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter your name")
        return value


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: Password

    @field_validator("new_password")
    @classmethod
    def password_has_letter_and_digit(cls, value: str) -> str:
        return check_password(value)


class SecurityQuestionSet(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    question: str
    answer: Answer

    @field_validator("question")
    @classmethod
    def listed_question(cls, value: str) -> str:
        return check_question(value)  # type: ignore[return-value]


class ForgotPasswordStart(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def lower_case_email(cls, value: str) -> str:
        return value.lower()


class ForgotPasswordQuestion(BaseModel):
    question: str


class PasswordReset(ForgotPasswordStart):
    answer: str = Field(min_length=1, max_length=100)
    new_password: Password

    @field_validator("new_password")
    @classmethod
    def password_has_letter_and_digit(cls, value: str) -> str:
        return check_password(value)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
