"""Aplicação > Inspeção — resultados do modelo de visão computacional."""

from fastapi import APIRouter, Query

from app.api.v1.deps import InspectionDep
from app.schemas.common import Page, TimePoint
from app.schemas.inspection import InspectionDetail, InspectionStatistics, InspectionSummary

router = APIRouter(prefix="/inspections", tags=["inspeções"])


@router.get("", response_model=Page[InspectionSummary], summary="Tabela de inspeções")
async def list_inspections(
    service: InspectionDep, page: int = 1, page_size: int = 50
) -> Page[InspectionSummary]:
    return await service.list(page=page, page_size=page_size)


@router.get("/statistics", response_model=InspectionStatistics, summary="Percentual com avarias")
async def get_statistics(service: InspectionDep) -> InspectionStatistics:
    """Alimenta o gráfico de proporção: inspeções com avaria / total."""
    return await service.statistics()


@router.get("/timeseries", response_model=list[TimePoint], summary="Evolução das inspeções")
async def get_timeseries(
    service: InspectionDep,
    metric: str = Query("count", pattern="^(count|damages)$"),
) -> list[TimePoint]:
    return await service.timeseries(metric=metric)


@router.get("/{inspection_id}", response_model=InspectionDetail, summary="Detalhe da inspeção")
async def get_inspection(inspection_id: int, service: InspectionDep) -> InspectionDetail:
    return await service.detail(inspection_id)
