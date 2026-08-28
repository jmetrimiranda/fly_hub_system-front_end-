"""Manutenção: o que existe para arrumar o estado da instalação, não para operar.

Hoje só a demonstração. Fica num router separado porque não pertence a domínio
nenhum: apagar o seed toca datasets, inspeções, notas e métricas ao mesmo tempo,
e pendurar isso em `/datasets` faria a rota de um domínio mexer nos outros três.
"""

from fastapi import APIRouter

from app.api.v1.deps import DemoDataDep
from app.schemas.common import ErrorResponse
from app.services.demo_data_service import DemoDataSummary

router = APIRouter(prefix="/admin", tags=["manutenção"])


@router.get("/seed", response_model=DemoDataSummary, summary="Quanto há de demonstração")
async def demo_summary(service: DemoDataDep) -> DemoDataSummary:
    """Contagem por tabela. É o que o modal de confirmação mostra antes de apagar."""
    return await service.summary()


@router.delete(
    "/seed",
    response_model=DemoDataSummary,
    responses={409: {"model": ErrorResponse, "description": "Conflito com o estado atual"}},
    summary="Remover os dados de demonstração",
)
async def clear_demo(service: DemoDataDep) -> DemoDataSummary:
    """Apaga **apenas** linhas com `source="seed"`. Devolve quanto saiu.

    Coleta real não é tocada — a marca é gravada no INSERT, não deduzida
    depois. Ver `services/demo_data_service.py`.
    """
    return await service.clear()
