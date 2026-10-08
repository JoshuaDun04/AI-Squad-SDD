"""Senhas (Argon2), JWT de 8 h e limite de tentativas de login (RT-02, SEC-01)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

PAPEIS = ("admin", "atendente", "cozinha")
VALIDADE_TOKEN = timedelta(hours=8)
_ALGORITMO = "HS256"

_hasher = PasswordHasher()
# Hash fixo para gastar o mesmo tempo quando o e-mail não existe
_HASH_FALSO = _hasher.hash("senha-que-nao-existe-#")


def usar_hasher_rapido() -> None:
    """Só para testes: Argon2 com custo mínimo para a suíte rodar rápido."""
    global _hasher, _HASH_FALSO
    _hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    _HASH_FALSO = _hasher.hash("senha-que-nao-existe-#")


def hash_senha(senha: str) -> str:
    return _hasher.hash(senha)


def verificar_senha(senha_hash: str | None, senha: str) -> bool:
    try:
        return _hasher.verify(senha_hash or _HASH_FALSO, senha) and senha_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


@dataclass(frozen=True)
class Principal:
    usuario_id: uuid.UUID
    restaurante_id: uuid.UUID
    papel: str


def emitir_token(principal: Principal, agora: datetime, segredo: str) -> str:
    payload = {
        "sub": str(principal.usuario_id),
        "usuario_id": str(principal.usuario_id),
        "restaurante_id": str(principal.restaurante_id),
        "papel": principal.papel,
        "iat": int(agora.timestamp()),
        "exp": int((agora + VALIDADE_TOKEN).timestamp()),
    }
    return jwt.encode(payload, segredo, algorithm=_ALGORITMO)


class TokenInvalido(Exception):
    pass


def ler_token(token: str, agora: datetime, segredo: str) -> Principal:
    """Valida assinatura com PyJWT e expiração pelo relógio injetável (VAL-04)."""
    try:
        dados = jwt.decode(
            token,
            segredo,
            algorithms=[_ALGORITMO],
            options={"verify_exp": False, "verify_iat": False, "require": ["exp", "usuario_id", "restaurante_id", "papel"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenInvalido("token inválido") from exc
    if int(dados["exp"]) <= int(agora.timestamp()):
        raise TokenInvalido("token expirado")
    if dados["papel"] not in PAPEIS:
        raise TokenInvalido("papel inválido")
    try:
        return Principal(uuid.UUID(dados["usuario_id"]), uuid.UUID(dados["restaurante_id"]), dados["papel"])
    except ValueError as exc:
        raise TokenInvalido("token inválido") from exc
