"""RF-01 cadastro de restaurante, RF-02 login (RT-02, SEC-01)."""

from __future__ import annotations


from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from pdv_api.config import Config
from pdv_api.dependencias import obter_config, obter_relogio, obter_sessao, usuario_atual
from pdv_api.erros import ErroApi, nao_autenticado
from pdv_api.relogio import Relogio
from pdv_api.repositorios import RepoAutenticacao, RepoRestaurantes, RepoUsuarios, limite_janela
from pdv_api.seguranca import Principal, emitir_token, hash_senha, verificar_senha

router = APIRouter(tags=["autenticação"])

SENHA_MIN = 8


class NovoRestaurante(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    admin_email: EmailStr
    admin_senha: str = Field(min_length=SENHA_MIN, max_length=128)
    fuso: str = "America/Manaus"

    @field_validator("fuso")
    @classmethod
    def _fuso_valido(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("fuso inválido") from exc
        return v


class Login(BaseModel):
    email: str = Field(max_length=254)
    senha: str = Field(max_length=128)


@router.post("/restaurantes", status_code=201)
def cadastrar_restaurante(dados: NovoRestaurante, sessao: Session = Depends(obter_sessao)) -> dict:
    auth = RepoAutenticacao(sessao)
    if auth.email_em_uso(dados.admin_email):
        raise ErroApi(409, "email_em_uso", "e-mail já cadastrado")
    restaurante = RepoRestaurantes(sessao).criar(dados.nome.strip(), dados.fuso)
    RepoUsuarios(sessao, restaurante.id).criar(dados.admin_email, hash_senha(dados.admin_senha), "admin")
    sessao.commit()
    return {"restaurante_id": str(restaurante.id)}


@router.post("/auth/login")
def login(
    dados: Login,
    request: Request,
    sessao: Session = Depends(obter_sessao),
    relogio: Relogio = Depends(obter_relogio),
    config: Config = Depends(obter_config),
) -> dict:
    agora = relogio.agora()
    email = dados.email.strip().lower()
    ip = request.client.host if request.client else "?"
    chave = f"{email}|{ip}"
    auth = RepoAutenticacao(sessao)
    if auth.falhas_recentes(chave, limite_janela(agora, config.login_janela_min)) >= config.login_max_tentativas:
        raise ErroApi(429, "muitas_tentativas", "muitas tentativas; aguarde alguns minutos")

    usuario = auth.usuario_por_email(email)
    senha_ok = verificar_senha(usuario.senha_hash if usuario else None, dados.senha)
    if usuario is None or not senha_ok or not usuario.ativo:
        auth.registrar_falha(chave, agora)
        sessao.commit()
        raise nao_autenticado()

    auth.limpar_falhas(chave, antes_de=limite_janela(agora, config.login_janela_min))
    sessao.commit()
    principal = Principal(usuario.id, usuario.restaurante_id, usuario.papel)
    return {
        "token": emitir_token(principal, agora, config.jwt_secret),
        "papel": usuario.papel,
        "restaurante_id": str(usuario.restaurante_id),
    }


@router.get("/auth/eu")
def eu(principal: Principal = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)) -> dict:
    restaurante = RepoRestaurantes(sessao).obter(principal.restaurante_id)
    usuario = RepoUsuarios(sessao, principal.restaurante_id).obter(principal.usuario_id)
    return {
        "usuario_id": str(principal.usuario_id),
        "email": usuario.email if usuario else "",
        "papel": principal.papel,
        "restaurante_id": str(principal.restaurante_id),
        "restaurante_nome": restaurante.nome if restaurante else "",
        "fuso": restaurante.fuso if restaurante else "",
    }


