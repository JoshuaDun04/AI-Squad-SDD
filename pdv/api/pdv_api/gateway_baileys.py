"""Adaptador HTTP da porta CanalMensagens para o serviço wa-gateway (ADR-0002)."""

from __future__ import annotations

from uuid import UUID

import httpx

from pdv_api.dominio.canal import ErroCanal


class GatewayBaileys:
    def __init__(self, url_base: str, token: str, timeout: float = 10.0, cliente: httpx.Client | None = None) -> None:
        self._cliente = cliente or httpx.Client(
            base_url=url_base.rstrip("/"), timeout=timeout, headers={"X-Gateway-Token": token}
        )

    def _chamar(self, metodo: str, caminho: str, json: dict | None = None) -> None:
        try:
            resp = self._cliente.request(metodo, caminho, json=json)
        except httpx.HTTPError as exc:
            raise ErroCanal(f"gateway inacessível: {type(exc).__name__}") from None
        if resp.status_code >= 400:
            raise ErroCanal(f"gateway respondeu {resp.status_code}")

    def enviar(self, restaurante_id: UUID, telefone: str, texto: str) -> None:
        self._chamar("POST", "/mensagens", {"restaurante_id": str(restaurante_id), "telefone": telefone, "texto": texto})

    def iniciar_sessao(self, restaurante_id: UUID) -> None:
        self._chamar("POST", f"/sessoes/{restaurante_id}")

    def encerrar_sessao(self, restaurante_id: UUID) -> None:
        self._chamar("DELETE", f"/sessoes/{restaurante_id}")
