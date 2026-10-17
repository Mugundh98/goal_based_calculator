"""Collects every route module under the /api prefix."""

from fastapi import APIRouter

from app.api.routes import (
    admin,
    auth,
    chat,
    funds,
    goals,
    health,
    market,
    ml,
    portfolio,
    profile,
    recommendations,
    reports,
    retirement,
    risk,
    simulations,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(profile.router)
api_router.include_router(risk.router)
api_router.include_router(goals.router)
api_router.include_router(simulations.router)
api_router.include_router(recommendations.router)
api_router.include_router(retirement.router)
api_router.include_router(portfolio.router)
api_router.include_router(funds.router)
api_router.include_router(market.router)
api_router.include_router(ml.router)
api_router.include_router(chat.router)
api_router.include_router(reports.router)
api_router.include_router(admin.router)
