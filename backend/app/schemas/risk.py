from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field

from app.finance.risk_profile import explanation

RiskCategory = Literal["conservative", "moderate", "aggressive"]


class OptionOut(BaseModel):
    id: str
    text: str  # points are deliberately not exposed, so answers aren't steered


class QuestionOut(BaseModel):
    id: str
    text: str
    options: list[OptionOut]


class QuestionnaireOut(BaseModel):
    version: str
    questions: list[QuestionOut]


class AssessmentInput(BaseModel):
    answers: dict[str, str]  # {question_id: option_id}


class FactorOut(BaseModel):
    key: str
    label: str
    value: str
    points: int
    max_points: int


class AssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    questionnaire_version: str
    answers: dict[str, str]
    tolerance_score: int
    capacity_score: int
    final_score: int
    category: RiskCategory
    capacity_breakdown: list[FactorOut]
    created_at: datetime

    @computed_field
    @property
    def explanation(self) -> str:
        return explanation(self.tolerance_score, self.capacity_score)
