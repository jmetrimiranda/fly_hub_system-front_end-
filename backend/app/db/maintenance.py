"""Manutenção pontual do banco, pela linha de comando.

    python -m app.db.maintenance prune-empty

Existe para o resíduo anterior à regra: até a coleta passar a se descartar
sozinha quando não grava quadro nenhum, cada tentativa frustrada deixava uma
linha de zero imagens ocupando um número de versão. Numa instalação nova este
comando não encontra nada, e é assim que deve ser — a correção definitiva está
em `collection_service._discard_empty`.
"""

import argparse
import asyncio

from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.services.dataset_service import DatasetService

log = get_logger(__name__)


async def prune_empty() -> None:
    async with SessionLocal() as session:
        removed = await DatasetService(session).prune_empty()
    if removed:
        print(f"Removidas {len(removed)} coleta(s) sem imagem: {', '.join(removed)}.")
        print("Os números de versão voltaram a ficar livres.")
    else:
        print("Nenhuma coleta vazia encontrada.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manutenção do banco.")
    parser.add_argument(
        "command",
        choices=["prune-empty"],
        help="prune-empty: remove coletas encerradas sem nenhuma imagem",
    )
    parser.parse_args()
    configure_logging()
    asyncio.run(prune_empty())


if __name__ == "__main__":
    main()
