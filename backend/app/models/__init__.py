"""ORM models. Import every model here so Alembic can detect it."""

from app.core.database import Base
from app.models.audit import AuditLog
from app.models.chat import ChatMessage, ChatSession, KbChunk, KbDocument, ToolCall
from app.models.goal import Goal
from app.models.market import Fund, FundMetrics, IndexHistory, InflationData, JobRun, NavHistory
from app.models.ml import FundCluster, FundPrediction, MLModel
from app.models.portfolio import Holding, Transaction
from app.models.profile import FinancialProfile
from app.models.recommendation import Recommendation
from app.models.retirement import RetirementPlan
from app.models.risk import RiskAssessment
from app.models.simulation import Simulation, SimulationResult
from app.models.user import User

__all__ = [
    "AuditLog",
    "Base",
    "ChatMessage",
    "ChatSession",
    "FinancialProfile",
    "Fund",
    "FundCluster",
    "FundMetrics",
    "FundPrediction",
    "Goal",
    "Holding",
    "IndexHistory",
    "InflationData",
    "JobRun",
    "KbChunk",
    "KbDocument",
    "MLModel",
    "NavHistory",
    "Recommendation",
    "RetirementPlan",
    "RiskAssessment",
    "Simulation",
    "SimulationResult",
    "ToolCall",
    "Transaction",
    "User",
]
