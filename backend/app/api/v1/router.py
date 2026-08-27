"""Agrega os routers de domínio sob o prefixo /api/v1."""

from fastapi import APIRouter

from app.api.v1.routes import dashboard, datasets, flight, health, inspections

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(dashboard.router)
api_router.include_router(flight.router)
api_router.include_router(datasets.router)
api_router.include_router(inspections.router)
