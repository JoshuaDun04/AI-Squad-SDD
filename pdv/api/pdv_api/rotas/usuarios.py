"""RF-03 gestão de usuários (somente admin, somente do próprio restaurante)."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from pdv_api import modelos as m
from pdv_api.dependencias import exigir, obter_sessao
from pdv_api.erros import ErroApi, nao_encontrado
from pdv_api.repositorios import RepoAutenticacao, RepoUsuarios
from pdv_api.rotas.auth import SENHA_MIN
from pdv_api.seguranca import Principal, hash_senha

router = APIRouter(prefix="/usuarios", tags=["usuários"])

Papel = Literal["admin", "atendente", "cozinha"]


class NovoUsuario(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=SENHA_MIN, max_length=128)
    papel: Papel


class AlteraUsuario(BaseModel):
    senha: str | None = Field(default=None, min_length=SENHA_MIN, max_length=128)
    papel: Papel | None = None
    ativo: bool | None = None


def _saida(u: m.Usuario) -> dict:
    return {"id": str(u.id), "email": u.email, "papel": u.papel, "ativo": u.ativo}


@router.get("")
def listar(p: Principal = Depends(exigir("admin")), sessao: Session = Depends(obter_sessao)) -> list[dict]:
    return [_saida(u) for u in RepoUsuarios(sessao, p.restaurante_id).listar()]


@router.post("", status_code=201)
def criar(dados: NovoUsuario, p: Principal = Depends(exigir("admin")), sessao: Session = Depends(obter_sessao)) -> dict:
    if RepoAutenticacao(sessao).email_em_uso(dados.email):
        raise ErroApi(409, "email_em_uso", "e-mail já cadastrado")
    u = RepoUsuarios(sessao, p.restaurante_id).criar(dados.email, hash_senha(dados.senha), dados.papel)
    sessao.commit()
    return _saida(u)


@router.patch("/{usuario_id}")
def alterar(
    usuario_id: uuid.UUID,
    dados: AlteraUsuario,
    p: Principal = Depends(exigir("admin")),
    sessao: Session = Depends(obter_sessao),
) -> dict:
    u = RepoUsuarios(sessao, p.restaurante_id).obter(usuario_id)
    if u is None:
        raise nao_encontrado("usuário")
    if u.id == p.usuario_id and (dados.ativo is False or (dados.papel and dados.papel != "admin")):
        raise ErroApi(422, "auto_bloqueio", "o admin não pode desativar nem rebaixar a si mesmo")
    mudou_acesso = False
    if dados.senha is not None:
        u.senha_hash = hash_senha(dados.senha)
        mudou_acesso = True
    if dados.papel is not None and dados.papel != u.papel:
        u.papel = dados.papel
        mudou_acesso = True
    if dados.ativo is not None and dados.ativo != u.ativo:
        u.ativo = dados.ativo
        mudou_acesso = True
    if mudou_acesso:
        u.sessao_versao += 1  # tokens já emitidos deixam de valer (REV-13)
    sessao.commit()
    return _saida(u)
