"""Logging estruturado.

Erro técnico vai para o log; o usuário recebe uma mensagem em português no
formato definido em `core/errors.py`. Os dois nunca se misturam.

O `httpx` é silenciado abaixo do WARNING, e não é por causa de ruído. Ele
registra a **URL completa** de cada requisição em INFO, e a API do Roboflow
exige a chave na query string: com o logger ligado, um lote de 500 imagens
escrevia a chave 500 vezes no log — que é exatamente onde ela não pode estar.
O ruído (uma linha por consulta ao MediaMTX, várias por segundo) é só o
benefício secundário.
"""

import logging
import sys

import structlog

from app.core.config import settings


NOISY_LOGGERS = ("httpx", "httpcore")


def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=settings.log_level)
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    processors.append(
        structlog.processors.JSONRenderer()
        if settings.is_production
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
