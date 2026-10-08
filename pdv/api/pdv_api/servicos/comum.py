from __future__ import annotations

import logging
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from pdv_api import modelos as m
from pdv_api.dominio.canal import CanalMensagens
from pdv_api.dominio.horario import Faixa
from pdv_api.dominio.lgpd import mascarar_telefone

log = logging.getLogger("pdv_api")


def agora_local(restaurante: m.Restaurante, agora_utc: datetime) -> datetime:
    return agora_utc.astimezone(ZoneInfo(restaurante.fuso))


def faixas(horarios: list[m.Horario]) -> list[Faixa]:
    return [Faixa(h.dia_semana, h.abre, h.fecha) for h in horarios]


def enviar_sem_falhar(canal: CanalMensagens, restaurante_id: uuid.UUID, telefone: str, texto: str) -> bool:
    """Falha no envio não desfaz a operação; registra sem dado pessoal (RT-06).

    Não loga str(exc): a mensagem de erro pode carregar telefone e endereço.
    """
    try:
        canal.enviar(restaurante_id, telefone, texto)
        return True
    except Exception as exc:  # noqa: BLE001 - qualquer falha do canal
        log.warning(
            "falha ao enviar mensagem restaurante=%s cliente=%s erro=%s",
            restaurante_id,
            mascarar_telefone(telefone),
            type(exc).__name__,
        )
        return False
