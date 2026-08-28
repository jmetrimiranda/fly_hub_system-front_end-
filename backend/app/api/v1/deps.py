"""Dependências compartilhadas pelas rotas."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.integrations.flight_source import FlightSource, get_flight_source
from app.services.collection_service import CollectionService
from app.services.dashboard_service import DashboardService
from app.services.dataset_service import DatasetService
from app.services.demo_data_service import DemoDataService
from app.services.flight_service import FlightService
from app.services.inspection_service import InspectionService
from app.services.model_service import ModelService
from app.services.roboflow_credentials_service import RoboflowCredentialService
from app.services.roboflow_service import RoboflowService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


# A fonte é única no processo e escolhida pela configuração: `fake` hoje,
# `mqtt` quando o FlightHub Sync entrar. Ver flight_source/__init__.py.
FlightSourceDep = Annotated[FlightSource, Depends(get_flight_source)]


def get_flight_service(session: SessionDep, source: FlightSourceDep) -> FlightService:
    return FlightService(session, source=source)


def get_collection_service(session: SessionDep) -> CollectionService:
    return CollectionService(session)


def get_dataset_service(session: SessionDep) -> DatasetService:
    return DatasetService(session)


def get_demo_data_service(session: SessionDep) -> DemoDataService:
    return DemoDataService(session)


def get_roboflow_service(session: SessionDep) -> RoboflowService:
    return RoboflowService(session)


def get_roboflow_credentials(session: SessionDep) -> RoboflowCredentialService:
    return RoboflowCredentialService(session)


def get_model_service(session: SessionDep) -> ModelService:
    return ModelService(session)


def get_inspection_service(session: SessionDep) -> InspectionService:
    return InspectionService(session)


def get_dashboard_service(session: SessionDep) -> DashboardService:
    return DashboardService(session)


FlightDep = Annotated[FlightService, Depends(get_flight_service)]
CollectionDep = Annotated[CollectionService, Depends(get_collection_service)]
DatasetDep = Annotated[DatasetService, Depends(get_dataset_service)]
DemoDataDep = Annotated[DemoDataService, Depends(get_demo_data_service)]
RoboflowDep = Annotated[RoboflowService, Depends(get_roboflow_service)]
CredentialDep = Annotated[RoboflowCredentialService, Depends(get_roboflow_credentials)]
InspectionDep = Annotated[InspectionService, Depends(get_inspection_service)]
ModelDep = Annotated[ModelService, Depends(get_model_service)]
DashboardDep = Annotated[DashboardService, Depends(get_dashboard_service)]
