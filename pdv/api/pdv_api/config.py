"""Configuração lida do ambiente. A API recusa iniciar com segredos fracos."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

JWT_SECRET_MIN = 32
GATEWAY_TOKEN_MIN = 16


class ConfigInvalida(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    database_url: str
    jwt_secret: str
    gateway_token: str
    gateway_url: str = "http://wa-gateway:3001"
    cors_origens: tuple[str, ...] = field(default_factory=tuple)
    login_max_tentativas: int = 5
    login_max_tentativas_ip: int = 30
    login_janela_min: int = 15

    def __post_init__(self) -> None:
        if len(self.jwt_secret) < JWT_SECRET_MIN:
            raise ConfigInvalida(f"JWT_SECRET precisa ter pelo menos {JWT_SECRET_MIN} caracteres")
        if len(self.gateway_token) < GATEWAY_TOKEN_MIN:
            raise ConfigInvalida(f"GATEWAY_TOKEN precisa ter pelo menos {GATEWAY_TOKEN_MIN} caracteres")
        if not self.database_url:
            raise ConfigInvalida("DATABASE_URL é obrigatório")

    @classmethod
    def do_ambiente(cls) -> Config:
        origens = tuple(o.strip() for o in os.environ.get("CORS_ORIGENS", "").split(",") if o.strip())
        return cls(
            database_url=os.environ.get("DATABASE_URL", ""),
            jwt_secret=os.environ.get("JWT_SECRET", ""),
            gateway_token=os.environ.get("GATEWAY_TOKEN", ""),
            gateway_url=os.environ.get("GATEWAY_URL", "http://wa-gateway:3001"),
            cors_origens=origens,
        )
