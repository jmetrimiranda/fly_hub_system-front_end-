"""Consultas e agregações do domínio Inspeção."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError
from app.models.enums import NoteStatus
from app.models.inspection import Inspection, SapNote
from app.schemas.common import Page, TimePoint
from app.schemas.inspection import (
    DamageOut,
    InspectionDetail,
    InspectionStatistics,
    InspectionSummary,
)


class InspectionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _open_notes_subquery(self):
        return (
            select(func.count(SapNote.id))
            .where(SapNote.inspection_id == Inspection.id, SapNote.status == NoteStatus.OPEN)
            .correlate(Inspection)
            .scalar_subquery()
        )

    async def list(self, page: int = 1, page_size: int = 50) -> Page[InspectionSummary]:
        open_notes = self._open_notes_subquery()
        total = await self._session.scalar(select(func.count(Inspection.id))) or 0
        rows = (
            await self._session.execute(
                select(Inspection, open_notes.label("open_notes"))
                .order_by(Inspection.inspected_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return Page(
            items=[
                InspectionSummary(
                    id=inspection.id,
                    code=inspection.code,
                    inspected_at=inspection.inspected_at,
                    flight_time_seconds=inspection.flight_time_seconds,
                    damage_count=inspection.damage_count,
                    open_note_count=open_count,
                    status=inspection.status,
                    source=inspection.source,
                )
                for inspection, open_count in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def detail(self, inspection_id: int) -> InspectionDetail:
        inspection = (
            await self._session.execute(
                select(Inspection)
                .options(selectinload(Inspection.damages), selectinload(Inspection.notes))
                .where(Inspection.id == inspection_id)
            )
        ).scalar_one_or_none()
        if inspection is None:
            raise NotFoundError(f"Inspeção {inspection_id} não encontrada.")

        return InspectionDetail(
            id=inspection.id,
            code=inspection.code,
            inspected_at=inspection.inspected_at,
            flight_time_seconds=inspection.flight_time_seconds,
            damage_count=inspection.damage_count,
            open_note_count=sum(1 for note in inspection.notes if note.status == NoteStatus.OPEN),
            status=inspection.status,
            source=inspection.source,
            model_version=inspection.model_version,
            asset_tag=inspection.asset_tag,
            damages=[DamageOut.model_validate(damage) for damage in inspection.damages],
        )

    async def statistics(self) -> InspectionStatistics:
        """Base do gráfico de percentual de inspeções com avaria."""
        row = (
            await self._session.execute(
                select(
                    func.count(Inspection.id),
                    func.sum(case((Inspection.damage_count > 0, 1), else_=0)),
                    func.coalesce(func.avg(cast(Inspection.damage_count, Float)), 0.0),
                    func.min(Inspection.inspected_at),
                    func.max(Inspection.inspected_at),
                )
            )
        ).one()

        total, with_damage, average, start, end = row
        total = total or 0
        with_damage = int(with_damage or 0)
        return InspectionStatistics(
            total=total,
            with_damage=with_damage,
            without_damage=total - with_damage,
            damage_ratio=round(with_damage / total, 4) if total else 0.0,
            average_damage_per_inspection=round(float(average or 0.0), 2),
            period_start=start,
            period_end=end,
        )

    async def timeseries(self, metric: str = "count") -> list[TimePoint]:
        """metric='count' → evolução das inspeções; 'damages' → avarias por dia."""
        day = func.date(Inspection.inspected_at).label("day")
        value = (
            func.count(Inspection.id)
            if metric == "count"
            else func.coalesce(func.sum(Inspection.damage_count), 0)
        )
        rows = (
            await self._session.execute(select(day, value).group_by(day).order_by(day))
        ).all()
        return [
            TimePoint(
                date=datetime.fromisoformat(str(row_day)) if isinstance(row_day, str) else row_day,
                value=float(row_value),
            )
            for row_day, row_value in rows
        ]
