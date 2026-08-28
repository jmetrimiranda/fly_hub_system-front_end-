"""Cifragem simétrica das credenciais guardadas no banco.

A chave do Roboflow dá acesso de escrita ao workspace inteiro de anotação. Ela
entra pelo formulário, é cifrada aqui e volta a texto claro só no instante do
upload, dentro do processo. Nunca em resposta de API, nunca em log, nunca
mascarada — "mascarada" ainda é vazamento parcial e convida a completar o
resto.

`SECRET_KEY` é o segredo do processo, não a chave em si: `Fernet` exige 32
bytes em base64 url-safe, e derivar por SHA-256 aceita qualquer texto no `.env`
sem exigir que o operador saiba gerar uma chave no formato do `cryptography`.
A derivação é determinística de propósito — o mesmo `.env` decifra o mesmo
banco depois de um reinício.

Sem `SECRET_KEY` a aplicação **não inventa uma**: gravar cifrado com um segredo
efêmero produziria um banco que deixa de abrir no reinício seguinte, e gravar
em claro é pior ainda. Recusa e explica.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.errors import SecretKeyMissingError


@lru_cache
def _fernet() -> Fernet:
    if not settings.secret_configured:
        raise SecretKeyMissingError()
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext: str) -> str:
    """Texto claro → token Fernet, pronto para uma coluna de texto."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    """Token → texto claro.

    `InvalidToken` significa que o `SECRET_KEY` mudou depois da gravação. O erro
    diz isso em palavras: a alternativa é o operador achar que a credencial
    está corrompida e passar a tarde investigando o banco.
    """
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretKeyMissingError(
            "A credencial não pôde ser decifrada: o SECRET_KEY atual não é o "
            "mesmo que a gravou. Cadastre a credencial de novo."
        ) from exc
