"""Dependências FastAPI: sessão, relógio, canal, usuário autenticado e papéis."""

from __future__ import annotations

import hmac
from collections.abc import Callable, Iterator

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from pdv_api.config import Config
from pdv_api.dominio.canal import CanalMensagens
from pdv_api.erros import nao_autenticado, proibido
from pdv_api.relogio import Relogio
from pdv_api.repositorios import RepoAutenticacao
from pdv_api.seguranca import Principal, TokenInvalido, ler_token


def obter_sessao(request: Request) -> Iterator[Session]:
    fabrica = request.app.state.fabrica_sessao
    sessao: Session = fabrica()
    try:
        yield sessao
    finally:
        sessao.close()


def obter_relogio(request: Request) -> Relogio:
    return request.app.state.relogio


def obter_canal(request: Request) -> CanalMensagens:
    return request.app.state.canal


def obter_config(request: Request) -> Config:
    return request.app.state.config


def usuario_atual(
    authorization: str | None = Header(default=None),
    sessao: Session = Depends(obter_sessao),
    relogio: Relogio = Depends(obter_relogio),
    config: Config = Depends(obter_config),
) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise nao_autenticado("token ausente")
    try:
        principal = ler_token(authorization[7:].strip(), relogio.agora(), config.jwt_secret)
    except TokenInvalido as exc:
        raise nao_autenticado(str(exc)) from exc
    usuario = RepoAutenticacao(sessao).usuario_por_id(principal.usuario_id)
    # usuário desativado ou trocado de restaurante perde o acesso na hora (BDD-AUT-03)
    if usuario is None or not usuario.ativo or usuario.restaurante_id != principal.restaurante_id:
        raise nao_autenticado("usuário inativo")
    return Principal(usuario.id, usuario.restaurante_id, usuario.papel)


def exigir(*papeis: str) -> Callable[..., Principal]:
    def _verificar(principal: Principal = Depends(usuario_atual)) -> Principal:
        if principal.papel not in papeis:
            raise proibido()
        return principal

    return _verificar


TODOS = ("admin", "atendente", "cozinha")


def token_gateway_valido(
    x_gateway_token: str | None = Header(default=None),
    config: Config = Depends(obter_config),
) -> None:
    if not x_gateway_token or not hmac.compare_digest(x_gateway_token.encode(), config.gateway_token.encode()):
        raise nao_autenticado("X-Gateway-Token inválido")
