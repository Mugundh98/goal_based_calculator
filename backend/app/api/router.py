"""Collects every route module under the /api prefix."""

from fastapi import APIRouter

from app.api.routes import auth, funds, goals, health, market, profile, risk, simulations

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(profile.router)
api_router.include_router(risk.router)
api_router.include_router(goals.router)
api_router.include_router(simulations.router)
api_router.include_router(funds.router)
api_router.include_router(market.router)
