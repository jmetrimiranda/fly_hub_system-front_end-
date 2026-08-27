"""Dependências compartilhadas pelas rotas."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.collection_service import CollectionService
from app.services.dashboard_service import DashboardService
from app.services.dataset_service import DatasetService
from app.services.flight_service import FlightService
from app.services.inspection_service import InspectionService
from app.services.roboflow_service import RoboflowService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_flight_service(session: SessionDep) -> FlightService:
    return FlightService(session)


def get_collection_service(session: SessionDep) -> CollectionService:
    return CollectionService(session)


def get_dataset_service(session: SessionDep) -> DatasetService:
    return DatasetService(session)


def get_roboflow_service(session: SessionDep) -> RoboflowService:
    return RoboflowService(session)


def get_inspection_service(session: SessionDep) -> InspectionService:
    return InspectionService(session)


def get_dashboard_service(session: SessionDep) -> DashboardService:
    return DashboardService(session)


FlightDep = Annotated[FlightService, Depends(get_flight_service)]
CollectionDep = Annotated[CollectionService, Depends(get_collection_service)]
DatasetDep = Annotated[DatasetService, Depends(get_dataset_service)]
RoboflowDep = Annotated[RoboflowService, Depends(get_roboflow_service)]
InspectionDep = Annotated[InspectionService, Depends(get_inspection_service)]
DashboardDep = Annotated[DashboardService, Depends(get_dashboard_service)]
