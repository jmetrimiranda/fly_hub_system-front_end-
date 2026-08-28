"""Pages > Datasets — coletas cruas, galeria, resplit e envio ao Roboflow."""

from fastapi import APIRouter, Response, status
from fastapi.responses import FileResponse

from app.api.v1.deps import CredentialDep, DatasetDep, RoboflowDep
from app.models.enums import SplitName
from app.schemas.common import ErrorResponse, Page
from app.schemas.dataset import (
    DatasetDetail,
    DatasetImageOut,
    DatasetSummary,
    DeleteDatasetRequest,
    DeleteImagesRequest,
    DeleteImagesResult,
    ResplitResult,
    RoboflowCredentialCreate,
    RoboflowCredentialOut,
    RoboflowUploadRequest,
    RoboflowUploadResult,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])

ERRORS = {
    404: {"model": ErrorResponse, "description": "Dataset ou imagem inexistente"},
    409: {"model": ErrorResponse, "description": "Conflito com o estado atual"},
}

# A imagem de um dataset nunca muda depois de gravada: o nome do arquivo carrega
# o índice do quadro e cada versão tem a sua pasta. Um ano de cache economiza a
# rerequisição de quinhentas miniaturas a cada troca de aba.
IMAGE_CACHE = {"Cache-Control": "public, max-age=31536000, immutable"}


# --- listagem ----------------------------------------------------------------


@router.get("", response_model=Page[DatasetSummary], summary="Listar coletas")
async def list_datasets(
    service: DatasetDep, page: int = 1, page_size: int = 50
) -> Page[DatasetSummary]:
    return await service.list(page=page, page_size=page_size)


# --- credenciais do Roboflow -------------------------------------------------
# Declaradas antes de `/{dataset_id}` porque `roboflow` casaria com o parâmetro
# de caminho e a rota nunca seria alcançada.


@router.get(
    "/roboflow/credentials",
    response_model=list[RoboflowCredentialOut],
    summary="Credenciais salvas do Roboflow",
)
async def list_credentials(service: CredentialDep) -> list[RoboflowCredentialOut]:
    """Rótulo, workspace, projeto e último uso. **Nunca** a chave."""
    return await service.list()


@router.post(
    "/roboflow/credentials",
    response_model=RoboflowCredentialOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "SECRET_KEY ausente"},
        409: {"model": ErrorResponse, "description": "Rótulo já usado"},
    },
    summary="Gravar credencial do Roboflow",
)
async def create_credential(
    payload: RoboflowCredentialCreate, service: CredentialDep
) -> RoboflowCredentialOut:
    """A chave é cifrada antes de tocar o banco. A resposta não a devolve."""
    return await service.create(payload)


@router.delete(
    "/roboflow/credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    summary="Apagar credencial",
)
async def delete_credential(credential_id: int, service: CredentialDep) -> Response:
    await service.delete(credential_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- detalhe -----------------------------------------------------------------


@router.get("/{dataset_id}", response_model=DatasetDetail, responses=ERRORS, summary="Detalhe")
async def get_dataset(dataset_id: int, service: DatasetDep) -> DatasetDetail:
    """Distribuição, contagens **do disco** e avisos do último split."""
    return await service.detail(dataset_id)


@router.get(
    "/{dataset_id}/images",
    response_model=Page[DatasetImageOut],
    responses=ERRORS,
    summary="Imagens originais da coleta",
)
async def list_images(
    dataset_id: int,
    service: DatasetDep,
    split: SplitName | None = None,
    page: int = 1,
    page_size: int = 60,
) -> Page[DatasetImageOut]:
    """Frames **sem** inferência aplicada — este fluxo é separado do de inspeção."""
    return await service.images(dataset_id, split=split, page=page, page_size=page_size)


@router.get(
    "/{dataset_id}/images/{image_id}/thumb",
    responses={200: {"content": {"image/jpeg": {}}}, **ERRORS},
    response_class=FileResponse,
    summary="Miniatura (240 px)",
)
async def get_thumb(dataset_id: int, image_id: int, service: DatasetDep) -> FileResponse:
    """O que a grade pede. Gerada sob demanda e cacheada em disco."""
    path = await service.image_file(dataset_id, image_id, thumb=True)
    return FileResponse(path, media_type="image/jpeg", headers=IMAGE_CACHE)


@router.get(
    "/{dataset_id}/images/{image_id}/raw",
    responses={200: {"content": {"image/jpeg": {}}}, **ERRORS},
    response_class=FileResponse,
    summary="Imagem original em tamanho real",
)
async def get_raw_image(dataset_id: int, image_id: int, service: DatasetDep) -> FileResponse:
    """A imagem **como saiu do leitor**, sem sobreposição do modelo."""
    path = await service.image_file(dataset_id, image_id, thumb=False)
    return FileResponse(path, media_type="image/jpeg", headers=IMAGE_CACHE)


# --- edição ------------------------------------------------------------------


@router.post(
    "/{dataset_id}/images/delete",
    response_model=DeleteImagesResult,
    responses=ERRORS,
    summary="Excluir imagens",
)
async def delete_images(
    dataset_id: int, payload: DeleteImagesRequest, service: DatasetDep
) -> DeleteImagesResult:
    """Apaga da partição e de `raw/`. Irreversível — o modal diz isso.

    `POST` e não `DELETE` porque a exclusão em lote leva corpo, e corpo em
    `DELETE` é território cinzento que proxy e cliente HTTP tratam de formas
    diferentes.
    """
    return await service.delete_images(dataset_id, payload.image_ids)


@router.post(
    "/{dataset_id}/resplit",
    response_model=ResplitResult,
    responses=ERRORS,
    summary="Refazer o split a partir de raw/",
)
async def resplit(dataset_id: int, service: DatasetDep) -> ResplitResult:
    """Depois de excluir imagens, é o que faz as proporções voltarem a valer."""
    return await service.resplit(dataset_id)


@router.post(
    "/{dataset_id}/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERRORS,
    summary="Excluir o dataset inteiro",
)
async def delete_dataset(
    dataset_id: int, payload: DeleteDatasetRequest, service: DatasetDep
) -> Response:
    """Exige digitar a versão. Apaga o banco e a pasta, sem volta."""
    await service.delete_dataset(dataset_id, payload.confirm)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Roboflow ----------------------------------------------------------------


@router.post(
    "/{dataset_id}/roboflow",
    response_model=RoboflowUploadResult,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse, "description": "Credencial ausente ou SECRET_KEY não definida"},
        409: {"model": ErrorResponse, "description": "Dataset não está salvo ou já subindo"},
        **ERRORS,
    },
    summary="Enviar para o Roboflow",
)
async def send_to_roboflow(
    dataset_id: int, payload: RoboflowUploadRequest, service: RoboflowDep
) -> RoboflowUploadResult:
    """Dispara o envio e responde na hora. O progresso chega por SSE.

    As imagens vão com `split=train|valid|test` já decidido pelo backend. Não
    existe endpoint que aceite uma partição vinda do cliente.
    """
    return await service.start(dataset_id, payload)


@router.get(
    "/{dataset_id}/roboflow",
    response_model=RoboflowUploadResult,
    responses=ERRORS,
    summary="Progresso do envio",
)
async def roboflow_status(dataset_id: int, service: RoboflowDep) -> RoboflowUploadResult:
    return await service.status(dataset_id)


@router.post(
    "/{dataset_id}/roboflow/cancel",
    response_model=RoboflowUploadResult,
    responses=ERRORS,
    summary="Cancelar o envio",
)
async def cancel_roboflow(dataset_id: int, service: RoboflowDep) -> RoboflowUploadResult:
    """Para depois da imagem atual. O que já subiu não volta a subir."""
    return await service.cancel(dataset_id)
