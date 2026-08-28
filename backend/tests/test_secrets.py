"""O que nunca pode vazar: a chave do Roboflow.

Testes síncronos, em arquivo próprio — `test_datasets.py` marca o módulo
inteiro como `asyncio`, e um teste síncrono lá dentro só gera aviso.
"""


def test_the_key_is_scrubbed_from_anything_that_touched_a_url():
    """A API do Roboflow exige a chave na query string.

    Quem escreve a mensagem de erro é uma biblioteca de terceiro, e nenhuma
    promete não ecoar a URL. O que vai para o banco, para a tela e para o log
    passa por este filtro antes.
    """
    from app.integrations.roboflow.client import scrub

    leaked = (
        "Server error '500' for url "
        "'https://api.roboflow.com/dataset/postes/upload?api_key=SEGREDO&split=train'"
    )
    cleaned = scrub(leaked)
    assert "SEGREDO" not in cleaned
    assert "api_key=***" in cleaned
    assert "split=train" in cleaned  # o resto do diagnóstico continua legível
    assert scrub(cleaned) == cleaned  # idempotente

def test_httpx_does_not_log_request_urls():
    """O httpx registra a URL inteira em INFO — 500 imagens, 500 chaves no log."""
    import logging

    from app.core.logging import configure_logging

    configure_logging()
    assert logging.getLogger("httpx").level >= logging.WARNING
