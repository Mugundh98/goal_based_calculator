"""ORM models. Import every model here so Alembic can detect it."""

from app.core.database import Base
from app.models.goal import Goal
from app.models.profile import FinancialProfile
from app.models.risk import RiskAssessment
from app.models.user import User

__all__ = ["Base", "Goal", "FinancialProfile", "RiskAssessment", "User"]
