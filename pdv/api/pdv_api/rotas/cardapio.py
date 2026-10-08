"""RF-04 cardápio: categorias e itens (RN-02 preço em centavos > 0, RN-04 disponibilidade)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from sqlalchemy.orm import Session

from pdv_api import modelos as m
from pdv_api.dependencias import TODOS, exigir, obter_sessao
from pdv_api.erros import ErroApi, nao_encontrado
from pdv_api.repositorios import RepoCardapio
from pdv_api.seguranca import Principal

router = APIRouter(tags=["cardápio"])

PRECO_MAX = 10_000_000  # R$ 100.000,00


class _Estrito(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NovaCategoria(_Estrito):
    nome: str = Field(min_length=1, max_length=80)
    ordem: StrictInt = 0
    ativa: StrictBool = True


class AlteraCategoria(_Estrito):
    nome: str | None = Field(default=None, min_length=1, max_length=80)
    ordem: StrictInt | None = None
    ativa: StrictBool | None = None


class NovoItem(_Estrito):
    categoria_id: uuid.UUID
    nome: str = Field(min_length=1, max_length=120)
    descricao: str = Field(default="", max_length=500)
    # StrictInt: "12.90" ou 12.9 são recusados (BDD-CAR-03)
    preco_centavos: StrictInt = Field(gt=0, le=PRECO_MAX)
    disponivel: StrictBool = True
    ordem: StrictInt = 0


class AlteraItem(_Estrito):
    categoria_id: uuid.UUID | None = None
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    descricao: str | None = Field(default=None, max_length=500)
    preco_centavos: StrictInt | None = Field(default=None, gt=0, le=PRECO_MAX)
    disponivel: StrictBool | None = None
    ordem: StrictInt | None = None


def _cat(c: m.Categoria) -> dict:
    return {"id": str(c.id), "nome": c.nome, "ordem": c.ordem, "ativa": c.ativa}


def _item(i: m.Item) -> dict:
    return {
        "id": str(i.id),
        "categoria_id": str(i.categoria_id),
        "nome": i.nome,
        "descricao": i.descricao,
        "preco_centavos": i.preco_centavos,
        "disponivel": i.disponivel,
        "ordem": i.ordem,
    }


# ------------------------------------------------------------ categorias


@router.get("/categorias")
def listar_categorias(p: Principal = Depends(exigir(*TODOS)), sessao: Session = Depends(obter_sessao)) -> list[dict]:
    return [_cat(c) for c in RepoCardapio(sessao, p.restaurante_id).listar_categorias()]


@router.post("/categorias", status_code=201)
def criar_categoria(
    dados: NovaCategoria, p: Principal = Depends(exigir("admin")), sessao: Session = Depends(obter_sessao)
) -> dict:
    c = RepoCardapio(sessao, p.restaurante_id).criar_categoria(dados.nome.strip(), dados.ordem, dados.ativa)
    sessao.commit()
    return _cat(c)


@router.patch("/categorias/{categoria_id}")
def alterar_categoria(
    categoria_id: uuid.UUID,
    dados: AlteraCategoria,
    p: Principal = Depends(exigir("admin")),
    sessao: Session = Depends(obter_sessao),
) -> dict:
    c = RepoCardapio(sessao, p.restaurante_id).obter_categoria(categoria_id)
    if c is None:
        raise nao_encontrado("categoria")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        if valor is not None:
            setattr(c, campo, valor.strip() if isinstance(valor, str) else valor)
    sessao.commit()
    return _cat(c)


@router.delete("/categorias/{categoria_id}", status_code=204)
def remover_categoria(
    categoria_id: uuid.UUID, p: Principal = Depends(exigir("admin")), sessao: Session = Depends(obter_sessao)
) -> None:
    repo = RepoCardapio(sessao, p.restaurante_id)
    c = repo.obter_categoria(categoria_id)
    if c is None:
        raise nao_encontrado("categoria")
    if repo.categoria_tem_itens(c.id):
        raise ErroApi(409, "categoria_com_itens", "mova ou desative os itens antes; ou desative a categoria")
    repo.remover_categoria(c)
    sessao.commit()


# ------------------------------------------------------------ itens


@router.get("/itens")
def listar_itens(
    categoria_id: uuid.UUID | None = None,
    p: Principal = Depends(exigir(*TODOS)),
    sessao: Session = Depends(obter_sessao),
) -> list[dict]:
    return [_item(i) for i in RepoCardapio(sessao, p.restaurante_id).listar_itens(categoria_id)]


@router.post("/itens", status_code=201)
def criar_item(dados: NovoItem, p: Principal = Depends(exigir("admin")), sessao: Session = Depends(obter_sessao)) -> dict:
    repo = RepoCardapio(sessao, p.restaurante_id)
    if repo.obter_categoria(dados.categoria_id) is None:
        raise ErroApi(422, "categoria_invalida", "categoria não encontrada neste restaurante")
    campos = dados.model_dump()
    campos["nome"] = campos["nome"].strip()
    it = repo.criar_item(**campos)
    sessao.commit()
    return _item(it)


@router.patch("/itens/{item_id}")
def alterar_item(
    item_id: uuid.UUID,
    dados: AlteraItem,
    p: Principal = Depends(exigir("admin")),
    sessao: Session = Depends(obter_sessao),
) -> dict:
    repo = RepoCardapio(sessao, p.restaurante_id)
    it = repo.obter_item(item_id)
    if it is None:
        raise nao_encontrado("item")
    campos = {k: v for k, v in dados.model_dump(exclude_unset=True).items() if v is not None}
    if "categoria_id" in campos and repo.obter_categoria(campos["categoria_id"]) is None:
        raise ErroApi(422, "categoria_invalida", "categoria não encontrada neste restaurante")
    for campo, valor in campos.items():
        setattr(it, campo, valor.strip() if isinstance(valor, str) else valor)
    sessao.commit()
    return _item(it)
