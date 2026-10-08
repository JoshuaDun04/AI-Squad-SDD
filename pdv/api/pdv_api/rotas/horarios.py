"""RF-05 horário de funcionamento (dia_semana: 0 = segunda ... 6 = domingo)."""

from __future__ import annotations

from datetime import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, StrictInt, field_validator, model_validator
from sqlalchemy.orm import Session

from pdv_api.dependencias import TODOS, exigir, obter_relogio, obter_sessao
from pdv_api.dominio.horario import descrever_proxima_abertura, esta_aberto
from pdv_api.erros import ErroApi
from pdv_api.relogio import Relogio
from pdv_api.repositorios import RepoHorarios, RepoRestaurantes
from pdv_api.seguranca import Principal
from pdv_api.servicos.comum import agora_local, faixas

router = APIRouter(prefix="/horarios", tags=["horários"])


def _hora(v: str) -> time:
    try:
        h, mnt = v.split(":")
        return time(int(h), int(mnt))
    except (ValueError, AttributeError) as exc:
        raise ValueError("use HH:MM") from exc


class FaixaEntrada(BaseModel):
    dia_semana: StrictInt = Field(ge=0, le=6)
    abre: str
    fecha: str

    @field_validator("abre", "fecha")
    @classmethod
    def _formato(cls, v: str) -> str:
        _hora(v)
        return v

    @model_validator(mode="after")
    def _ordem(self) -> "FaixaEntrada":
        if _hora(self.fecha) <= _hora(self.abre):
            raise ValueError("fecha deve ser depois de abre")
        return self


def _saida(h) -> dict:
    return {"dia_semana": h.dia_semana, "abre": h.abre.strftime("%H:%M"), "fecha": h.fecha.strftime("%H:%M")}


@router.get("")
def listar(
    p: Principal = Depends(exigir(*TODOS)),
    sessao: Session = Depends(obter_sessao),
    relogio: Relogio = Depends(obter_relogio),
) -> dict:
    horarios = RepoHorarios(sessao, p.restaurante_id).listar()
    restaurante = RepoRestaurantes(sessao).obter(p.restaurante_id)
    local = agora_local(restaurante, relogio.agora())
    fx = faixas(horarios)
    return {
        "fuso": restaurante.fuso,
        "aberto_agora": esta_aberto(fx, local),
        "proxima_abertura": descrever_proxima_abertura(fx, local),
        "faixas": [_saida(h) for h in horarios],
    }


@router.put("")
def substituir(
    entrada: list[FaixaEntrada], p: Principal = Depends(exigir("admin")), sessao: Session = Depends(obter_sessao)
) -> list[dict]:
    dias = [f.dia_semana for f in entrada]
    if len(dias) != len(set(dias)):
        raise ErroApi(422, "dia_repetido", "informe no máximo uma faixa por dia da semana")
    novos = RepoHorarios(sessao, p.restaurante_id).substituir(
        [(f.dia_semana, _hora(f.abre), _hora(f.fecha)) for f in entrada]
    )
    sessao.commit()
    return [_saida(h) for h in sorted(novos, key=lambda h: h.dia_semana)]
