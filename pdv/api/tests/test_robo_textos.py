"""Textos e efeitos colaterais do robô e utilitários do domínio, sem banco.

Complementa test_dominio.py: aqui as mensagens são conferidas por inteiro,
porque o texto que o cliente lê é parte do comportamento (RF-07, RF-08).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from pdv_api.dominio import robo
from pdv_api.dominio.canal import CanalEmMemoria, ErroCanal
from pdv_api.dominio.dinheiro import interpretar_valor_brl
from pdv_api.dominio.horario import Faixa, descrever_proxima_abertura, proxima_abertura
from pdv_api.dominio.lgpd import FiltroDadosPessoais, instalar_filtro, mascarar_telefone

TAMBAQUI = robo.ItemVista("t", "Tambaqui assado", 4590)
SUCO = robo.ItemVista("s", "Suco de cupuaçu", 890)
CTX = robo.Contexto(
    nome_restaurante="Sabor do Rio",
    categorias=(
        robo.CategoriaVista("c1", "Peixes", (TAMBAQUI,)),
        robo.CategoriaVista("c2", "Bebidas", (SUCO,)),
    ),
    aberto=True,
)


def rodar(*textos, ctx=CTX, conversa=None):
    conv = conversa or robo.Conversa()
    res = None
    for t in textos:
        res = robo.processar(conv, t, ctx)
        conv = res.conversa
    return res


DOIS_ITENS = ("oi", "1", "1", "2", "1", "2", "1", "1")  # 2 Tambaqui + 1 Suco


def test_texto_dos_itens():
    assert rodar("oi", "1").texto == "Peixes:\n1 - Tambaqui assado — R$ 45,90\n0 - Voltar"


def test_texto_do_carrinho_completo():
    assert rodar(*DOIS_ITENS).texto == (
        "Seu carrinho:\n"
        "2 × Tambaqui assado — R$ 91,80\n"
        "1 × Suco de cupuaçu — R$ 8,90\n"
        "Subtotal: R$ 100,70\n"
        "\n"
        "1 - Adicionar mais itens, 2 - Remover item, 3 - Finalizar pedido, 0 - Cancelar"
    )


def test_texto_da_lista_de_remocao():
    assert rodar(*DOIS_ITENS, "2").texto == "Qual item remover?\n1 - 2 × Tambaqui assado\n2 - 1 × Suco de cupuaçu\n0 - Voltar"


@pytest.mark.parametrize("entrada,erro", [("0", False), ("9", True), ("x", True)])
def test_remover_sem_escolher_volta_ao_carrinho(entrada, erro):
    res = rodar(*DOIS_ITENS, "2", entrada)
    assert res.conversa.estado is robo.Estado.CARRINHO
    assert len(res.conversa.carrinho) == 2
    assert (res.respostas[0] == robo.MSG_OPCAO_INVALIDA) is erro


def test_remover_primeira_linha():
    res = rodar(*DOIS_ITENS, "2", "1")
    assert [l["item_id"] for l in res.conversa.carrinho] == ["s"]


def test_resumo_retirada_pix():
    assert rodar(*DOIS_ITENS, "3", "1", "1").texto == (
        "Resumo do pedido:\n"
        "2 × Tambaqui assado — R$ 91,80\n"
        "1 × Suco de cupuaçu — R$ 8,90\n"
        "Total: R$ 100,70\n"
        "Retirada no local\n"
        "Pagamento: Pix\n"
        "\n"
        "1 - Confirmar pedido, 2 - Voltar ao carrinho, 0 - Cancelar"
    )


def test_resumo_entrega_cartao_e_dinheiro():
    base = ("oi", "1", "1", "1", "3", "2", "Rua das Flores, 123")
    cartao = rodar(*base, "3").texto
    assert "Entrega em: Rua das Flores, 123\nPagamento: Cartão na entrega/retirada\n" in cartao
    dinheiro = rodar(*base, "2", "50").texto
    assert "Pagamento: Dinheiro (troco para R$ 50,00)\n" in dinheiro


def test_texto_do_troco():
    assert rodar("oi", "1", "1", "1", "3", "1", "2").texto == (
        'Total R$ 45,90. Troco para quanto? Envie o valor (ex.: 50) ou "sem troco".'
    )


@pytest.mark.parametrize("texto", ["sem troco", "SEM TROCO", " sem   troco ", "nao preciso de troco", "não preciso de troco"])
def test_variacoes_de_sem_troco(texto):
    res = rodar("oi", "1", "1", "1", "3", "1", "2", texto)
    assert res.conversa.estado is robo.Estado.CONFIRMACAO
    assert res.conversa.dados["troco_para"] is None


def test_trocar_para_cartao_apaga_troco_anterior():
    res = rodar("oi", "1", "1", "1", "3", "1", "2", "50", "2", "3", "1", "3", "1")
    assert res.pedido.pagamento == "cartao" and res.pedido.troco_para_centavos is None


def test_retirada_depois_de_entrega_apaga_endereco():
    res = rodar("oi", "1", "1", "1", "3", "2", "Rua das Flores, 123", "1", "2", "3", "1", "1", "1")
    assert res.pedido.tipo == "retirada" and res.pedido.endereco is None


def test_quantidade_limpa_item_pendente():
    res = rodar("oi", "1", "1", "2")
    assert res.conversa.dados == {"categoria_id": "c1"}


def test_finalizar_com_carrinho_esvaziado_por_indisponibilidade():
    conv = rodar("oi", "1", "1", "2").conversa
    so_bebidas = robo.Contexto("Sabor do Rio", (CTX.categorias[1],), aberto=True)
    res = robo.processar(conv, "2", so_bebidas)  # pede para remover com carrinho já vazio
    assert res.respostas == [
        "Tambaqui assado ficou indisponível e foi removido do carrinho.",
        robo.MSG_CARRINHO_VAZIO,
        "Escolha uma categoria:\n1 - Bebidas",
    ]
    assert res.conversa.estado is robo.Estado.CATEGORIAS


def test_item_pendente_sem_nome_salvo():
    conv = robo.Conversa(estado=robo.Estado.QUANTIDADE, dados={"item_id": "sumiu"})
    res = robo.processar(conv, "2", CTX)
    assert res.respostas[0] == "O item ficou indisponível."
    assert "item_id" not in res.conversa.dados


def test_cardapio_vazio_mantem_carrinho():
    vazio = robo.Contexto("Sabor do Rio", (), aberto=True)
    conv = robo.Conversa(estado=robo.Estado.CARRINHO, carrinho=[{"item_id": "t", "nome": "Tambaqui assado", "quantidade": 1}])
    res = robo.processar(conv, "1", vazio)
    assert res.texto == (
        "Tambaqui assado ficou indisponível e foi removido do carrinho.\n\n"
        "No momento nosso cardápio está indisponível. Tente novamente mais tarde."
    )
    assert res.conversa.estado is robo.Estado.INICIO


def test_mensagem_vazia_ou_none_no_inicio():
    assert robo.processar(robo.Conversa(), None, CTX).respostas[0].startswith("Olá!")  # type: ignore[arg-type]
    assert rodar("oi", "").respostas[0] == robo.MSG_OPCAO_INVALIDA


# ---------------------------------------------------------------- utilitários


@pytest.mark.parametrize(
    "entrada,saida", [("1234", "*****-1234"), ("12-34", "*****-1234"), ("(92) 99123-4567", "*****-4567")]
)
def test_mascarar_telefone_bordas(entrada, saida):
    assert mascarar_telefone(entrada) == saida


def test_filtro_sempre_deixa_o_registro_passar_e_limpa_args():
    reg = logging.LogRecord("x", logging.INFO, __file__, 1, "tel %s", ("5592991234567",), None)
    assert FiltroDadosPessoais().filter(reg) is True
    assert reg.getMessage() == "tel *****-4567" and reg.args is None
    sem_tel = logging.LogRecord("x", logging.INFO, __file__, 1, "pedido %s", (12,), None)
    assert FiltroDadosPessoais().filter(sem_tel) is True and sem_tel.args == (12,)


def test_instalar_filtro_no_logger_e_handlers_sem_duplicar():
    logger = logging.getLogger(f"teste.{uuid.uuid4()}")
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    instalar_filtro(logger)
    instalar_filtro(logger)
    assert sum(isinstance(f, FiltroDadosPessoais) for f in logger.filters) == 1
    assert sum(isinstance(f, FiltroDadosPessoais) for f in handler.filters) == 1


@pytest.mark.parametrize("texto,valor", [("5 0", 5000), ("0,01", 1), ("R$ 1 000", 100000)])
def test_valores_com_espaco_e_centavo(texto, valor):
    assert interpretar_valor_brl(texto) == valor


def test_canal_em_memoria():
    canal = CanalEmMemoria()
    rid = uuid.uuid4()
    canal.enviar(rid, "559200000000", "oi")
    assert canal.enviadas[0].restaurante_id == rid
    canal.falhar_envio = True
    with pytest.raises(ErroCanal, match="falha simulada"):
        canal.enviar(rid, "559200000000", "oi")


MAO = ZoneInfo("America/Manaus")


def test_proxima_abertura_no_instante_exato_e_semana_seguinte():
    terca = [Faixa(1, time(11), time(23))]
    as_11 = datetime(2026, 10, 6, 11, 0, tzinfo=MAO)
    assert proxima_abertura(terca, as_11) == datetime(2026, 10, 13, 11, 0, tzinfo=MAO)
    assert descrever_proxima_abertura([], as_11) == "No momento não temos horário de funcionamento cadastrado."


def test_opcao_invalida_repete_o_menu_atual():
    assert rodar("oi", "1", "1", "1", "3", "9").texto == f"{robo.MSG_OPCAO_INVALIDA}\n\n{robo.TEXTO_TIPO}"
    assert rodar("oi", "1", "1", "1", "3", "1", "9").texto == f"{robo.MSG_OPCAO_INVALIDA}\n\n{robo.TEXTO_PAGAMENTO}"
    confirmacao = rodar("oi", "1", "1", "1", "3", "1", "1", "9")
    assert confirmacao.respostas[0] == robo.MSG_OPCAO_INVALIDA
    assert confirmacao.respostas[1].startswith("Resumo do pedido:")


def test_pix_ignora_troco_e_retirada_ignora_endereco_deixados_nos_dados():
    """Dados antigos na conversa não vazam para o pedido."""
    conv = robo.Conversa(
        estado=robo.Estado.CONFIRMACAO,
        carrinho=[{"item_id": "t", "nome": "Tambaqui assado", "quantidade": 1}],
        dados={"tipo": "retirada", "endereco": "Rua antiga, 10", "pagamento": "pix", "troco_para": 10000},
    )
    p = robo.processar(conv, "1", CTX).pedido
    assert p.endereco is None and p.troco_para_centavos is None
