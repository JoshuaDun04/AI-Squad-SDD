"""Formato único de erro: {"erro": "<codigo>", "detalhe": "<texto>"}."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErroApi(Exception):
    def __init__(self, status: int, erro: str, detalhe: str = "") -> None:
        super().__init__(detalhe or erro)
        self.status = status
        self.erro = erro
        self.detalhe = detalhe


def nao_encontrado(recurso: str = "recurso") -> ErroApi:
    return ErroApi(404, "nao_encontrado", f"{recurso} não encontrado")


def proibido() -> ErroApi:
    return ErroApi(403, "proibido", "seu papel não permite esta ação")


def nao_autenticado(detalhe: str = "credenciais inválidas") -> ErroApi:
    return ErroApi(401, "nao_autenticado", detalhe)


def registrar_tratadores(app: FastAPI) -> None:
    @app.exception_handler(ErroApi)
    async def _erro_api(_: Request, exc: ErroApi) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
        return JSONResponse({"erro": exc.erro, "detalhe": exc.detalhe}, status_code=exc.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
        partes = []
        for e in exc.errors():
            campo = ".".join(str(p) for p in e.get("loc", ()) if p != "body")
            partes.append(f"{campo}: {e.get('msg')}")
        return JSONResponse({"erro": "validacao", "detalhe": "; ".join(partes)}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        codigo = {404: "nao_encontrado", 405: "metodo_nao_permitido"}.get(exc.status_code, "erro_http")
        return JSONResponse({"erro": codigo, "detalhe": str(exc.detail)}, status_code=exc.status_code)
