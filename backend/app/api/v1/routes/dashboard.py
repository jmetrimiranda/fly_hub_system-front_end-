"""Dashboard — página inicial da aplicação."""

from fastapi import APIRouter

from app.api.v1.deps import DashboardDep, InspectionDep
from app.schemas.common import Page
from app.schemas.dashboard import DamageSeries, DashboardSummary
from app.schemas.inspection import InspectionSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary, summary="Os quatro cards do Dashboard")
async def get_summary(service: DashboardDep) -> DashboardSummary:
    """Conexão de voo, total de inspeções, notas abertas e MAPE em uma resposta."""
    return await service.summary()


@router.get("/damage-series", response_model=DamageSeries, summary="Avarias por inspeção")
async def get_damage_series(service: DashboardDep) -> DamageSeries:
    """Série do gráfico abaixo da tabela: X = data, Y = avarias detectadas."""
    return await service.damage_series()


@router.get(
    "/inspections",
    response_model=Page[InspectionSummary],
    summary="Tabela 'Inspeções Realizadas'",
)
async def get_recent_inspections(
    service: InspectionDep, page: int = 1, page_size: int = 10
) -> Page[InspectionSummary]:
    return await service.list(page=page, page_size=page_size)
