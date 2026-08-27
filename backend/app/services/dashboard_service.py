"""Agrega os quatro cards do Dashboard em uma única resposta.

Quatro cards não precisam de quatro requisições: eles aparecem juntos e mudam
juntos. Uma chamada, um estado de carregamento, uma invalidação de cache.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NoteStatus
from app.models.inspection import Inspection, ModelMetric, SapNote
from app.schemas.dashboard import ConnectionCard, DamageSeries, DashboardSummary, MetricCard
from app.services.flight_service import FlightService
from app.services.inspection_service import InspectionService


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def summary(self) -> DashboardSummary:
        connected = (await FlightService(self._session).get_status()).connected

        inspections = await self._session.scalar(select(func.count(Inspection.id))) or 0
        open_notes = (
            await self._session.scalar(
                select(func.count(SapNote.id)).where(SapNote.status == NoteStatus.OPEN)
            )
            or 0
        )
        mape = await self._session.scalar(
            select(ModelMetric.value)
            .where(ModelMetric.metric == "mape", ModelMetric.is_current.is_(True))
            .order_by(ModelMetric.measured_at.desc())
            .limit(1)
        )

        return DashboardSummary(
            flight_connection=ConnectionCard(
                connected=connected, label="Conectado" if connected else "Desconectado"
            ),
            inspection_count=MetricCard(value=float(inspections), label="Quantidade de inspeções"),
            open_notes=MetricCard(value=float(open_notes), label="Notas abertas"),
            mape=MetricCard(value=float(mape or 0.0), label="MAPE", unit="%"),
        )

    async def damage_series(self) -> DamageSeries:
        points = await InspectionService(self._session).timeseries(metric="damages")
        return DamageSeries(points=points)
