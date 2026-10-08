"""Testes unitários do domínio puro (alvo do teste de mutação)."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from pdv_api.dominio import robo
from pdv_api.dominio.dinheiro import formatar_brl, interpretar_valor_brl, total_centavos
from pdv_api.dominio.horario import Faixa, descrever_proxima_abertura, esta_aberto, proxima_abertura
from pdv_api.dominio.status import StatusPedido as S
from pdv_api.dominio.status import mensagem_status, pode_avancar, pode_cancelar

MAO = ZoneInfo("America/Manaus")

# ---------------------------------------------------------------- dinheiro (RN-02)


@pytest.mark.parametrize(
    "centavos,texto",
    [(0, "R$ 0,00"), (5, "R$ 0,05"), (1290, "R$ 12,90"), (123456, "R$ 1.234,56"), (100000000, "R$ 1.000.000,00"), (-990, "-R$ 9,90")],
)
def test_formatar_brl(centavos, texto):
    assert formatar_brl(centavos) == texto


@pytest.mark.parametrize(
    "texto,centavos",
    [
        ("50", 5000),
        ("50,00", 5000),
        ("50,5", 5050),
        ("50.50", 5050),
        ("R$ 50", 5000),
        ("r$50,90", 5090),
        ("1.000", 100000),
        ("1.000,25", 100025),
        (" 38,70 ", 3870),
        ("100000", 10000000),
    ],
)
def test_interpretar_valor_valido(texto, centavos):
    assert interpretar_valor_brl(texto) == centavos


@pytest.mark.parametrize("texto", ["", "abc", "0", "0,00", "-50", "50,505", "1.00.0", "100001", "5O", "50,"])
def test_interpretar_valor_invalido(texto):
    assert interpretar_valor_brl(texto) is None


def test_total_sem_arredondamento():
    assert total_centavos([(1290, 3)]) == 3870
    assert total_centavos([(4590, 2), (890, 1)]) == 10070
    assert total_centavos([]) == 0


# ---------------------------------------------------------------- status (RN-09)

TODOS = list(S)
VALIDAS = {(S.RECEBIDO, S.EM_PREPARO), (S.EM_PREPARO, S.PRONTO), (S.PRONTO, S.FINALIZADO)}


@pytest.mark.parametrize("atual", TODOS)
@pytest.mark.parametrize("novo", TODOS)
def test_matriz_de_transicoes(atual, novo):
    assert pode_avancar(atual, novo) is ((atual, novo) in VALIDAS)


@pytest.mark.parametrize("atual", TODOS)
def test_cancelamento_so_antes_de_pronto(atual):
    assert pode_cancelar(atual) is (atual in (S.RECEBIDO, S.EM_PREPARO))


def test_mensagens_de_status():
    assert mensagem_status(3, S.EM_PREPARO, "retirada") == "Seu pedido #3 está em preparo."
    assert mensagem_status(3, S.PRONTO, "retirada") == "Seu pedido #3 está pronto! Pode vir retirar."
    assert mensagem_status(3, S.PRONTO, "entrega") == "Seu pedido #3 está pronto e vai sair para entrega."
    assert mensagem_status(3, S.FINALIZADO, "entrega") == "Pedido #3 finalizado. Obrigado pela preferência!"
    assert mensagem_status(3, S.CANCELADO, "entrega", "x y z") == "Seu pedido #3 foi cancelado. Motivo: x y z"
    assert mensagem_status(3, S.RECEBIDO, "entrega") == "Pedido #3: Recebido."


# ---------------------------------------------------------------- horário (RN-07)

TER_A_DOM = [Faixa(d, time(11), time(23)) for d in range(1, 7)]


def _mao(dia, h, m=0):
    return datetime(2026, 10, dia, h, m, tzinfo=MAO)  # 05 = segunda, 06 = terça


@pytest.mark.parametrize(
    "momento,aberto",
    [
        (_mao(6, 10, 59), False),
        (_mao(6, 11, 0), True),
        (_mao(6, 22, 59), True),
        (_mao(6, 23, 0), False),
        (_mao(5, 12, 0), False),
        (_mao(11, 12, 0), True),  # domingo
    ],
)
def test_esta_aberto(momento, aberto):
    assert esta_aberto(TER_A_DOM, momento) is aberto


def test_proxima_abertura():
    assert proxima_abertura(TER_A_DOM, _mao(5, 12)) == _mao(6, 11)
    assert proxima_abertura(TER_A_DOM, _mao(6, 9)) == _mao(6, 11)
    assert proxima_abertura(TER_A_DOM, _mao(6, 23, 1)) == _mao(7, 11)
    assert proxima_abertura(TER_A_DOM, _mao(11, 23, 30)) == _mao(13, 11)  # domingo → terça
    assert proxima_abertura([], _mao(6, 12)) is None
    so_segunda = [Faixa(0, time(8), time(9))]
    assert proxima_abertura(so_segunda, _mao(5, 8, 30)) == _mao(12, 8)  # uma semana depois


def test_descrever_proxima_abertura():
    assert descrever_proxima_abertura(TER_A_DOM, _mao(6, 9)) == "Abrimos hoje às 11:00."
    assert descrever_proxima_abertura(TER_A_DOM, _mao(5, 12)) == "Abrimos amanhã às 11:00."
    assert descrever_proxima_abertura(TER_A_DOM, _mao(11, 23, 30)) == "Abrimos terça-feira às 11:00."
    assert "não temos horário" in descrever_proxima_abertura([], _mao(6, 12))


# ---------------------------------------------------------------- robô (máquina de estados)

TAMBAQUI = robo.ItemVista("t", "Tambaqui assado", 4590)
PIRARUCU = robo.ItemVista("p", "Pirarucu", 5290)
SUCO = robo.ItemVista("s", "Suco de cupuaçu", 890)
CTX = robo.Contexto(
    nome_restaurante="Sabor do Rio",
    categorias=(
        robo.CategoriaVista("c1", "Peixes", (TAMBAQUI, PIRARUCU)),
        robo.CategoriaVista("c2", "Bebidas", (SUCO,)),
    ),
    aberto=True,
    texto_proxima_abertura="Abrimos amanhã às 11:00.",
)


def rodar(*textos, ctx=CTX, conversa=None):
    conv = conversa or robo.Conversa()
    res = None
    for t in textos:
        res = robo.processar(conv, t, ctx)
        conv = res.conversa
    return res


def test_fluxo_completo_retirada_pix():
    res = rodar("oi", "1", "1", "2", "1", "2", "1", "1", "3", "1", "1", "1")
    p = res.pedido
    assert p is not None
    assert p.total_centavos == 10070 and p.tipo == "retirada" and p.endereco is None
    assert p.pagamento == "pix" and p.troco_para_centavos is None
    assert [(l.item.id, l.quantidade) for l in p.linhas] == [("t", 2), ("s", 1)]
    assert res.conversa.estado is robo.Estado.INICIO and res.conversa.carrinho == []


def test_fluxo_entrega_dinheiro_troco():
    res = rodar("oi", "1", "1", "1", "3", "2", "Rua das Flores, 123", "2", "50", "1")
    p = res.pedido
    assert p.tipo == "entrega" and p.endereco == "Rua das Flores, 123"
    assert p.pagamento == "dinheiro" and p.troco_para_centavos == 5000


def test_cartao_nao_tem_troco():
    res = rodar("oi", "1", "1", "1", "3", "1", "3", "1")
    assert res.pedido.pagamento == "cartao" and res.pedido.troco_para_centavos is None


def test_sem_troco_no_dinheiro():
    res = rodar("oi", "1", "1", "1", "3", "1", "2", "sem troco", "1")
    assert res.pedido.pagamento == "dinheiro" and res.pedido.troco_para_centavos is None


def test_troco_igual_ao_total_aceito_e_um_centavo_a_menos_recusado():
    base = ("oi", "1", "1", "1", "3", "1", "2")
    assert rodar(*base, "45,89").conversa.estado is robo.Estado.TROCO
    assert rodar(*base, "45,90").conversa.estado is robo.Estado.CONFIRMACAO


def test_endereco_limites():
    base = ("oi", "1", "1", "1", "3", "2")
    assert rodar(*base, "x" * 9).conversa.estado is robo.Estado.ENDERECO
    assert rodar(*base, "x" * 10).conversa.estado is robo.Estado.PAGAMENTO
    assert rodar(*base, "x" * 300).conversa.estado is robo.Estado.PAGAMENTO
    assert rodar(*base, "x" * 301).conversa.estado is robo.Estado.ENDERECO
    res = rodar(*base, "  Rua   das    Flores 10  ")
    assert res.conversa.dados["endereco"] == "Rua das Flores 10"


@pytest.mark.parametrize("qtd,ok", [("1", True), ("20", True), ("0", False), ("21", False), ("05", True)])
def test_limites_de_quantidade(qtd, ok):
    res = rodar("oi", "1", "1", qtd)
    assert (res.conversa.estado is robo.Estado.CARRINHO) is ok


def test_soma_ate_20_permitida():
    res = rodar("oi", "1", "1", "15", "1", "1", "1", "5")
    assert res.conversa.carrinho == [{"item_id": "t", "nome": "Tambaqui assado", "quantidade": 20}]
    res = rodar("oi", "1", "1", "15", "1", "1", "1", "6")
    assert res.conversa.estado is robo.Estado.QUANTIDADE
    assert "Envie um número de 1 a 5." in res.texto


def test_fechado_reinicia_conversa_e_nao_mostra_menu():
    conv = rodar("oi", "1", "1", "2").conversa
    fechado = robo.Contexto("Sabor do Rio", CTX.categorias, aberto=False, texto_proxima_abertura="Abrimos amanhã às 11:00.")
    res = robo.processar(conv, "3", fechado)
    assert res.respostas == ["Olá! O Sabor do Rio está fechado agora. Abrimos amanhã às 11:00."]
    assert res.conversa.estado is robo.Estado.INICIO and res.conversa.carrinho == [] and res.pedido is None


def test_expirada_recomeca_com_aviso():
    conv = rodar("oi", "1", "1", "2").conversa
    ctx = robo.Contexto("Sabor do Rio", CTX.categorias, aberto=True, expirou=True)
    res = robo.processar(conv, "3", ctx)
    assert res.respostas[0] == robo.MSG_EXPIROU
    assert res.conversa.estado is robo.Estado.CATEGORIAS and res.conversa.carrinho == []


def test_expirada_no_inicio_so_cumprimenta():
    ctx = robo.Contexto("Sabor do Rio", CTX.categorias, aberto=True, expirou=True)
    res = robo.processar(robo.Conversa(), "oi", ctx)
    assert res.respostas[0].startswith("Olá! Bem-vindo(a)")


def test_item_pendente_indisponivel_na_quantidade():
    conv = rodar("oi", "1", "1").conversa  # pedindo quantidade de Tambaqui
    sem_tambaqui = robo.Contexto(
        "Sabor do Rio", (robo.CategoriaVista("c1", "Peixes", (PIRARUCU,)), CTX.categorias[1]), aberto=True
    )
    res = robo.processar(conv, "2", sem_tambaqui)
    assert res.respostas[0] == "Tambaqui assado ficou indisponível."
    assert res.conversa.estado is robo.Estado.CATEGORIAS and res.conversa.carrinho == []


def test_categoria_que_sumiu_volta_as_categorias():
    conv = rodar("oi", "2").conversa  # dentro de Bebidas
    so_peixes = robo.Contexto("Sabor do Rio", (CTX.categorias[0],), aberto=True)
    res = robo.processar(conv, "1", so_peixes)
    assert res.conversa.estado is robo.Estado.CATEGORIAS


def test_preco_muda_depois_do_troco_pede_troco_de_novo():
    conv = rodar("oi", "1", "1", "1", "3", "1", "2", "46").conversa
    mais_caro = robo.Contexto(
        "Sabor do Rio",
        (robo.CategoriaVista("c1", "Peixes", (robo.ItemVista("t", "Tambaqui assado", 5000),)),),
        aberto=True,
    )
    res = robo.processar(conv, "1", mais_caro)
    assert res.pedido is None and res.conversa.estado is robo.Estado.TROCO
    assert "Total R$ 50,00" in res.texto


def test_opcoes_invalidas_mantem_estado():
    assert rodar("oi", "1", "1", "1", "3", "9").conversa.estado is robo.Estado.TIPO
    assert rodar("oi", "1", "1", "1", "3", "1", "9").conversa.estado is robo.Estado.PAGAMENTO
    assert rodar("oi", "1", "1", "1", "3", "1", "1", "9").conversa.estado is robo.Estado.CONFIRMACAO
    assert rodar("oi", "1", "1", "1", "2", "9").conversa.estado is robo.Estado.CARRINHO
    assert rodar("oi", "1", "9").conversa.estado is robo.Estado.ITENS


def test_textos_de_menu():
    res = rodar("oi", "1", "1", "1", "3", "1", "2", "sem troco")
    resumo = res.respostas[-1]
    assert "Pagamento: Dinheiro (sem troco)" in resumo
    assert resumo.endswith("1 - Confirmar pedido, 2 - Voltar ao carrinho, 0 - Cancelar")
    assert robo.texto_categorias(CTX, robo.Conversa(carrinho=[{"item_id": "t", "nome": "x", "quantidade": 1}])).endswith(
        "0 - Ver carrinho"
    )
