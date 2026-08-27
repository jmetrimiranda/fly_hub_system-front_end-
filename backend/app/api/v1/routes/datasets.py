"""Pages > Datasets — coletas cruas e envio ao Roboflow."""

from fastapi import APIRouter, status

from app.api.v1.deps import DatasetDep, RoboflowDep
from app.schemas.common import ErrorResponse, Page
from app.schemas.dataset import (
    DatasetDetail,
    DatasetImageOut,
    DatasetSummary,
    RoboflowUploadResult,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=Page[DatasetSummary], summary="Listar coletas")
async def list_datasets(
    service: DatasetDep, page: int = 1, page_size: int = 50
) -> Page[DatasetSummary]:
    return await service.list(page=page, page_size=page_size)


@router.get("/{dataset_id}", response_model=DatasetDetail, summary="Detalhe de uma coleta")
async def get_dataset(dataset_id: int, service: DatasetDep) -> DatasetDetail:
    return await service.detail(dataset_id)


@router.get(
    "/{dataset_id}/images",
    response_model=Page[DatasetImageOut],
    summary="Imagens originais da coleta",
)
async def list_images(
    dataset_id: int, service: DatasetDep, page: int = 1, page_size: int = 60
) -> Page[DatasetImageOut]:
    """Frames **sem** inferência aplicada — este fluxo é separado do de inspeção."""
    return await service.images(dataset_id, page=page, page_size=page_size)


@router.post(
    "/{dataset_id}/roboflow",
    response_model=RoboflowUploadResult,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse, "description": "Roboflow não configurado"},
        409: {"model": ErrorResponse, "description": "Dataset não está salvo"},
        502: {"model": ErrorResponse, "description": "Falha na API do Roboflow"},
    },
    summary="Enviar para o Roboflow",
)
async def send_to_roboflow(dataset_id: int, service: RoboflowDep) -> RoboflowUploadResult:
    """Envia as imagens já particionadas em train/valid/test pelo backend."""
    return await service.upload(dataset_id)
