"""Modelo de visão: estado, toggle da inferência e releitura do disco.

Três rotas e nenhuma delas recebe pesos. Quem entrega modelo copia o arquivo
para a pasta montada; a aplicação percebe sozinha. Um endpoint de upload
existiria só para transformar uma cópia de arquivo num formulário — ver
`models/README.md`.
"""

from fastapi import APIRouter

from app.api.v1.deps import ModelDep
from app.schemas.model import ModelState, ModelToggle

router = APIRouter(prefix="/model", tags=["modelo"])


@router.get("", response_model=ModelState, summary="Estado do modelo")
async def get_model(service: ModelDep) -> ModelState:
    """Pesos, classes, métricas do treino e se a inferência está ligada."""
    return await service.state()


@router.post("/toggle", response_model=ModelState, summary="Ligar/desligar a inferência")
async def toggle_model(payload: ModelToggle, service: ModelDep) -> ModelState:
    """Liga e desliga a inferência **sem descarregar os pesos**.

    A escolha é persistida: reiniciar o backend não religa sozinho um modelo
    que o operador desligou de propósito.
    """
    return await service.toggle(payload.enabled)


@router.post("/reload", response_model=ModelState, summary="Reler os pesos do disco")
async def reload_model(service: ModelDep) -> ModelState:
    """Força a releitura agora. Não mexe no toggle — são ações distintas."""
    return await service.reload()
