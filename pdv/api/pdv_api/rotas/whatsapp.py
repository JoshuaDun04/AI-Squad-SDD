"""RF-06 conexão WhatsApp: iniciar sessão, ver QR e status."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from pdv_api.dependencias import exigir, obter_canal, obter_relogio, obter_sessao
from pdv_api.dominio.canal import CanalMensagens
from pdv_api.erros import ErroApi
from pdv_api.relogio import Relogio
from pdv_api.repositorios import RepoConexao
from pdv_api.seguranca import Principal

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
log = logging.getLogger("pdv_api.whatsapp")


@router.post("/conectar", status_code=202)
def conectar(
    p: Principal = Depends(exigir("admin")),
    sessao: Session = Depends(obter_sessao),
    relogio: Relogio = Depends(obter_relogio),
    canal: CanalMensagens = Depends(obter_canal),
) -> dict:
    conexao = RepoConexao(sessao, p.restaurante_id)
    atual = conexao.obter()
    if atual is not None and atual.status == "conectado":
        return {"status": "conectado"}  # nada a fazer; não regride o estado (REV-10)
    # Marca antes de chamar o gateway: o evento "conectado" ou o QR que ele mandar
    # depois prevalece sobre este estado, e não o contrário.
    conexao.definir("aguardando_qr", None, relogio.agora())
    sessao.commit()
    try:
        canal.iniciar_sessao(p.restaurante_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("gateway indisponível ao conectar restaurante=%s erro=%s", p.restaurante_id, type(exc).__name__)
        RepoConexao(sessao, p.restaurante_id).definir("desconectado", None, relogio.agora())
        sessao.commit()
        raise ErroApi(503, "gateway_indisponivel", "serviço de WhatsApp indisponível; tente de novo") from exc
    return {"status": "aguardando_qr"}


@router.post("/desconectar")
def desconectar(
    p: Principal = Depends(exigir("admin")),
    sessao: Session = Depends(obter_sessao),
    relogio: Relogio = Depends(obter_relogio),
    canal: CanalMensagens = Depends(obter_canal),
) -> dict:
    try:
        canal.encerrar_sessao(p.restaurante_id)
    except Exception as exc:  # noqa: BLE001
        # Sem confirmação do gateway o número pode continuar conectado: não mostra "desconectado" (REV-10)
        log.warning("gateway indisponível ao desconectar restaurante=%s erro=%s", p.restaurante_id, type(exc).__name__)
        raise ErroApi(503, "gateway_indisponivel", "serviço de WhatsApp indisponível; tente de novo") from exc
    RepoConexao(sessao, p.restaurante_id).definir("desconectado", None, relogio.agora())
    sessao.commit()
    return {"status": "desconectado"}


@router.get("/status")
def status(p: Principal = Depends(exigir("admin")), sessao: Session = Depends(obter_sessao)) -> dict:
    c = RepoConexao(sessao, p.restaurante_id).obter()
    if c is None:
        return {"status": "desconectado"}
    saida = {"status": c.status, "atualizado_em": c.atualizado_em.isoformat()}
    if c.status == "aguardando_qr" and c.qr_code:
        saida["qr_code_data_url"] = c.qr_code
    return saida
