"""Porta CanalMensagens (RT-03, ADR-0002) e implementação em memória."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID


class ErroCanal(Exception):
    """Falha ao falar com o canal (gateway fora do ar, sessão caída...)."""


class CanalMensagens(Protocol):
    def enviar(self, restaurante_id: UUID, telefone: str, texto: str) -> None: ...

    def iniciar_sessao(self, restaurante_id: UUID) -> None: ...

    def encerrar_sessao(self, restaurante_id: UUID) -> None: ...


@dataclass
class MensagemEnviada:
    restaurante_id: UUID
    telefone: str
    texto: str


@dataclass
class CanalEmMemoria:
    """Usado nos testes e no simulador local; guarda o que foi enviado."""

    enviadas: list[MensagemEnviada] = field(default_factory=list)
    sessoes: set[UUID] = field(default_factory=set)
    falhar_envio: bool = False

    def enviar(self, restaurante_id: UUID, telefone: str, texto: str) -> None:
        if self.falhar_envio:
            raise ErroCanal(f"falha simulada ao enviar para {telefone}: {texto}")
        self.enviadas.append(MensagemEnviada(restaurante_id, telefone, texto))

    def iniciar_sessao(self, restaurante_id: UUID) -> None:
        self.sessoes.add(restaurante_id)

    def encerrar_sessao(self, restaurante_id: UUID) -> None:
        self.sessoes.discard(restaurante_id)

    def para(self, telefone: str) -> list[str]:
        return [m.texto for m in self.enviadas if m.telefone == telefone]
