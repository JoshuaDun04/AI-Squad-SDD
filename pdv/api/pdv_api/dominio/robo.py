"""Robô de menu guiado como máquina de estados pura (ADR-0003, RF-07, RF-08).

Entrada: estado da conversa, texto do cliente e um Contexto montado pelo
serviço (cardápio disponível, se está aberto, se a conversa expirou).
Saída: novo estado, respostas ao cliente e, se confirmado, o pedido.

Nada aqui acessa banco, relógio ou WhatsApp, por isso é testável isoladamente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pdv_api.dominio.dinheiro import formatar_brl, interpretar_valor_brl, total_centavos

QTD_MIN = 1
QTD_MAX = 20  # RN-05
ENDERECO_MIN = 10
ENDERECO_MAX = 300

MSG_QTD_INVALIDA = "Envie um número de 1 a 20."
MSG_OPCAO_INVALIDA = "Opção inválida."
MSG_ENDERECO = "Envie o endereço completo para entrega (rua, número, bairro e uma referência)."
MSG_EXPIROU = "Seu carrinho expirou depois de 30 minutos sem resposta. Vamos começar de novo."
MSG_CARRINHO_VAZIO = "Seu carrinho está vazio."
MSG_CANCELADO = "Pedido cancelado. Quando quiser, é só mandar uma mensagem."

PAGAMENTOS = {"1": "pix", "2": "dinheiro", "3": "cartao"}
ROTULO_PAGAMENTO = {"pix": "Pix", "dinheiro": "Dinheiro", "cartao": "Cartão na entrega/retirada"}


class Estado(StrEnum):
    INICIO = "INICIO"
    CATEGORIAS = "CATEGORIAS"
    ITENS = "ITENS"
    QUANTIDADE = "QUANTIDADE"
    CARRINHO = "CARRINHO"
    REMOVER = "REMOVER"
    TIPO = "TIPO"
    ENDERECO = "ENDERECO"
    PAGAMENTO = "PAGAMENTO"
    TROCO = "TROCO"
    CONFIRMACAO = "CONFIRMACAO"


# Estados em que o cliente já está fechando o pedido; se o carrinho muda
# (item ficou indisponível), voltamos ao carrinho para ele revisar.
_ESTADOS_FECHAMENTO = {Estado.TIPO, Estado.ENDERECO, Estado.PAGAMENTO, Estado.TROCO, Estado.CONFIRMACAO}


@dataclass(frozen=True)
class ItemVista:
    id: str
    nome: str
    preco_centavos: int


@dataclass(frozen=True)
class CategoriaVista:
    id: str
    nome: str
    itens: tuple[ItemVista, ...]


@dataclass(frozen=True)
class Contexto:
    nome_restaurante: str
    categorias: tuple[CategoriaVista, ...]  # só ativas e com itens disponíveis, em ordem
    aberto: bool
    texto_proxima_abertura: str = ""
    expirou: bool = False

    def item(self, item_id: str) -> ItemVista | None:
        for cat in self.categorias:
            for it in cat.itens:
                if it.id == item_id:
                    return it
        return None


@dataclass
class Conversa:
    estado: Estado = Estado.INICIO
    carrinho: list[dict[str, Any]] = field(default_factory=list)  # {item_id, nome, quantidade}
    dados: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LinhaPedido:
    item: ItemVista
    quantidade: int


@dataclass(frozen=True)
class PedidoConfirmado:
    linhas: tuple[LinhaPedido, ...]
    tipo: str  # "retirada" | "entrega"
    endereco: str | None
    pagamento: str  # "pix" | "dinheiro" | "cartao"
    troco_para_centavos: int | None
    total_centavos: int


@dataclass
class Resultado:
    conversa: Conversa
    respostas: list[str]
    pedido: PedidoConfirmado | None = None

    @property
    def texto(self) -> str:
        return "\n\n".join(self.respostas)


# ---------------------------------------------------------------- utilidades


def _opcao(texto: str) -> int | None:
    t = texto.strip()
    return int(t) if re.fullmatch(r"\d{1,3}", t) else None


def _linhas(conversa: Conversa, ctx: Contexto) -> list[LinhaPedido]:
    linhas = []
    for linha in conversa.carrinho:
        item = ctx.item(linha["item_id"])
        if item is not None:
            linhas.append(LinhaPedido(item, int(linha["quantidade"])))
    return linhas


def _total(conversa: Conversa, ctx: Contexto) -> int:
    return total_centavos((l.item.preco_centavos, l.quantidade) for l in _linhas(conversa, ctx))


def texto_categorias(ctx: Contexto, conversa: Conversa) -> str:
    linhas = ["Escolha uma categoria:"]
    linhas += [f"{i} - {cat.nome}" for i, cat in enumerate(ctx.categorias, start=1)]
    if conversa.carrinho:
        linhas.append("0 - Ver carrinho")
    return "\n".join(linhas)


def texto_itens(cat: CategoriaVista) -> str:
    linhas = [f"{cat.nome}:"]
    linhas += [
        f"{i} - {it.nome} — {formatar_brl(it.preco_centavos)}" for i, it in enumerate(cat.itens, start=1)
    ]
    linhas.append("0 - Voltar")
    return "\n".join(linhas)


def texto_carrinho(conversa: Conversa, ctx: Contexto) -> str:
    linhas = ["Seu carrinho:"]
    for l in _linhas(conversa, ctx):
        linhas.append(f"{l.quantidade} × {l.item.nome} — {formatar_brl(l.item.preco_centavos * l.quantidade)}")
    linhas.append(f"Subtotal: {formatar_brl(_total(conversa, ctx))}")
    linhas.append("")
    linhas.append("1 - Adicionar mais itens, 2 - Remover item, 3 - Finalizar pedido, 0 - Cancelar")
    return "\n".join(linhas)


def texto_resumo(conversa: Conversa, ctx: Contexto) -> str:
    d = conversa.dados
    linhas = ["Resumo do pedido:"]
    for l in _linhas(conversa, ctx):
        linhas.append(f"{l.quantidade} × {l.item.nome} — {formatar_brl(l.item.preco_centavos * l.quantidade)}")
    linhas.append(f"Total: {formatar_brl(_total(conversa, ctx))}")
    if d.get("tipo") == "entrega":
        linhas.append(f"Entrega em: {d.get('endereco')}")
    else:
        linhas.append("Retirada no local")
    pagamento = ROTULO_PAGAMENTO[d["pagamento"]]
    if d.get("pagamento") == "dinheiro":
        troco = d.get("troco_para")
        pagamento += f" (troco para {formatar_brl(troco)})" if troco else " (sem troco)"
    linhas.append(f"Pagamento: {pagamento}")
    linhas.append("")
    linhas.append("1 - Confirmar pedido, 2 - Voltar ao carrinho, 0 - Cancelar")
    return "\n".join(linhas)


TEXTO_TIPO = "Como você quer receber?\n1 - Retirada no local\n2 - Entrega"
TEXTO_PAGAMENTO = "Forma de pagamento:\n1 - Pix\n2 - Dinheiro\n3 - Cartão na entrega/retirada"


def _texto_troco(total: int) -> str:
    return f'Total {formatar_brl(total)}. Troco para quanto? Envie o valor (ex.: 50) ou "sem troco".'


# ---------------------------------------------------------------- transições


def _ir_categorias(conversa: Conversa, ctx: Contexto, respostas: list[str]) -> Resultado:
    if not ctx.categorias:
        respostas.append("No momento nosso cardápio está indisponível. Tente novamente mais tarde.")
        return Resultado(Conversa(carrinho=conversa.carrinho), respostas)
    conversa.estado = Estado.CATEGORIAS
    respostas.append(texto_categorias(ctx, conversa))
    return Resultado(conversa, respostas)


def _ir_carrinho(conversa: Conversa, ctx: Contexto, respostas: list[str]) -> Resultado:
    if not conversa.carrinho:
        respostas.append(MSG_CARRINHO_VAZIO)
        return _ir_categorias(conversa, ctx, respostas)
    conversa.estado = Estado.CARRINHO
    respostas.append(texto_carrinho(conversa, ctx))
    return Resultado(conversa, respostas)


def _remover_indisponiveis(conversa: Conversa, ctx: Contexto) -> list[str]:
    """RN-04: item que ficou indisponível sai do carrinho com aviso."""
    avisos = []
    mantidos = []
    for linha in conversa.carrinho:
        if ctx.item(linha["item_id"]) is None:
            avisos.append(f"{linha['nome']} ficou indisponível e foi removido do carrinho.")
        else:
            mantidos.append(linha)
    conversa.carrinho = mantidos
    pendente = conversa.dados.get("item_id")
    if conversa.estado == Estado.QUANTIDADE and pendente and ctx.item(pendente) is None:
        avisos.append(f"{conversa.dados.get('item_nome', 'O item')} ficou indisponível.")
        conversa.dados.pop("item_id", None)
        conversa.estado = Estado.CATEGORIAS
    return avisos


def processar(conversa: Conversa, texto: str, ctx: Contexto) -> Resultado:
    texto = (texto or "").strip()

    # RN-07: fora do horário não mostra menu nem aceita pedido
    if not ctx.aberto:
        msg = f"Olá! O {ctx.nome_restaurante} está fechado agora. {ctx.texto_proxima_abertura}".strip()
        return Resultado(Conversa(), [msg])

    # RN-06: expiração avaliada na chegada da mensagem
    if ctx.expirou and conversa.estado != Estado.INICIO:
        return _ir_categorias(Conversa(), ctx, [MSG_EXPIROU])

    estado_antes = conversa.estado
    respostas: list[str] = _remover_indisponiveis(conversa, ctx)
    if respostas and estado_antes in _ESTADOS_FECHAMENTO:
        return _ir_carrinho(conversa, ctx, respostas)
    if estado_antes == Estado.QUANTIDADE and conversa.estado != Estado.QUANTIDADE:
        return _ir_categorias(conversa, ctx, respostas)

    handler = _HANDLERS[conversa.estado]
    return handler(conversa, texto, ctx, respostas)


def _inicio(conversa: Conversa, texto: str, ctx: Contexto, respostas: list[str]) -> Resultado:
    respostas.append(f"Olá! Bem-vindo(a) ao {ctx.nome_restaurante}.")
    return _ir_categorias(conversa, ctx, respostas)


def _categorias(conversa: Conversa, texto: str, ctx: Contexto, respostas: list[str]) -> Resultado:
    op = _opcao(texto)
    if op == 0 and conversa.carrinho:
        return _ir_carrinho(conversa, ctx, respostas)
    if op is None or not 1 <= op <= len(ctx.categorias):
        respostas.append(MSG_OPCAO_INVALIDA)
        return _ir_categorias(conversa, ctx, respostas)
    cat = ctx.categorias[op - 1]
    conversa.estado = Estado.ITENS
    conversa.dados["categoria_id"] = cat.id
    respostas.append(texto_itens(cat))
    return Resultado(conversa, respostas)


def _categoria_atual(conversa: Conversa, ctx: Contexto) -> CategoriaVista | None:
    cid = conversa.dados.get("categoria_id")
    return next((c for c in ctx.categorias if c.id == cid), None)


def _itens(conversa: Conversa, texto: str, ctx: Contexto, respostas: list[str]) -> Resultado:
    cat = _categoria_atual(conversa, ctx)
    if cat is None:  # categoria ficou sem itens disponíveis
        return _ir_categorias(conversa, ctx, respostas)
    op = _opcao(texto)
    if op == 0:
        return _ir_categorias(conversa, ctx, respostas)
    if op is None or not 1 <= op <= len(cat.itens):
        respostas.append(MSG_OPCAO_INVALIDA)
        respostas.append(texto_itens(cat))
        return Resultado(conversa, respostas)
    item = cat.itens[op - 1]
    conversa.estado = Estado.QUANTIDADE
    conversa.dados["item_id"] = item.id
    conversa.dados["item_nome"] = item.nome
    respostas.append(f"Quantas unidades de {item.nome}? (1 a 20)")
    return Resultado(conversa, respostas)


def _quantidade(conversa: Conversa, texto: str, ctx: Contexto, respostas: list[str]) -> Resultado:
    # _remover_indisponiveis já tirou o cliente daqui se o item sumiu do cardápio
    item = ctx.item(conversa.dados["item_id"])
    assert item is not None
    qtd = int(texto) if re.fullmatch(r"\d{1,3}", texto) else None
    if qtd is None or not QTD_MIN <= qtd <= QTD_MAX:
        respostas.append(MSG_QTD_INVALIDA)
        return Resultado(conversa, respostas)
    existente = next((l for l in conversa.carrinho if l["item_id"] == item.id), None)
    ja_tem = int(existente["quantidade"]) if existente else 0
    if ja_tem + qtd > QTD_MAX:
        respostas.append(
            f"O limite é {QTD_MAX} unidades de {item.nome} por pedido e já há {ja_tem} no carrinho. "
            f"Envie um número de 1 a {QTD_MAX - ja_tem}."
        )
        return Resultado(conversa, respostas)
    if existente:
        existente["quantidade"] = ja_tem + qtd
    else:
        conversa.carrinho.append({"item_id": item.id, "nome": item.nome, "quantidade": qtd})
    conversa.dados.pop("item_id", None)
    conversa.dados.pop("item_nome", None)
    return _ir_carrinho(conversa, ctx, respostas)


def _carrinho(conversa: Conversa, texto: str, ctx: Contexto, respostas: list[str]) -> Resultado:
    op = _opcao(texto)
    if op == 1:
        return _ir_categorias(conversa, ctx, respostas)
    if op == 2:
        if not conversa.carrinho:
            return _ir_carrinho(conversa, ctx, respostas)
        conversa.estado = Estado.REMOVER
        linhas = ["Qual item remover?"]
        linhas += [f"{i} - {l['quantidade']} × {l['nome']}" for i, l in enumerate(conversa.carrinho, start=1)]
        linhas.append("0 - Voltar")
        respostas.append("\n".join(linhas))
        return Resultado(conversa, respostas)
    if op == 3:
        if not conversa.carrinho:
            respostas.append(MSG_CARRINHO_VAZIO)
            return _ir_categorias(conversa, ctx, respostas)
        conversa.estado = Estado.TIPO
        respostas.append(TEXTO_TIPO)
        return Resultado(conversa, respostas)
    if op == 0:
        respostas.append(MSG_CANCELADO)
        return Resultado(Conversa(), respostas)
    respostas.append(MSG_OPCAO_INVALIDA)
    return _ir_carrinho(conversa, ctx, respostas)


def _remover(conversa: Conversa, texto: str, ctx: Contexto, respostas: list[str]) -> Resultado:
    op = _opcao(texto)
    if op is not None and 1 <= op <= len(conversa.carrinho):
        conversa.carrinho.pop(op - 1)
        return _ir_carrinho(conversa, ctx, respostas)
    if op != 0:
        respostas.append(MSG_OPCAO_INVALIDA)
    return _ir_carrinho(conversa, ctx, respostas)


def _tipo(conversa: Conversa, texto: str, ctx: Contexto, respostas: list[str]) -> Resultado:
    op = _opcao(texto)
    if op == 1:
        conversa.dados["tipo"] = "retirada"
        conversa.dados.pop("endereco", None)
        conversa.estado = Estado.PAGAMENTO
        respostas.append(TEXTO_PAGAMENTO)
    elif op == 2:
        conversa.dados["tipo"] = "entrega"
        conversa.estado = Estado.ENDERECO
        respostas.append(MSG_ENDERECO)
    else:
        respostas += [MSG_OPCAO_INVALIDA, TEXTO_TIPO]
    return Resultado(conversa, respostas)


def _endereco(conversa: Conversa, texto: str, ctx: Contexto, respostas: list[str]) -> Resultado:
    endereco = " ".join(texto.split())
    if not ENDERECO_MIN <= len(endereco) <= ENDERECO_MAX:
        respostas.append(MSG_ENDERECO)
        return Resultado(conversa, respostas)
    conversa.dados["endereco"] = endereco
    conversa.estado = Estado.PAGAMENTO
    respostas.append(TEXTO_PAGAMENTO)
    return Resultado(conversa, respostas)


def _pagamento(conversa: Conversa, texto: str, ctx: Contexto, respostas: list[str]) -> Resultado:
    forma = PAGAMENTOS.get(texto.strip())
    if forma is None:
        respostas += [MSG_OPCAO_INVALIDA, TEXTO_PAGAMENTO]
        return Resultado(conversa, respostas)
    conversa.dados["pagamento"] = forma
    conversa.dados.pop("troco_para", None)
    if forma == "dinheiro":
        conversa.estado = Estado.TROCO
        respostas.append(_texto_troco(_total(conversa, ctx)))
        return Resultado(conversa, respostas)
    conversa.estado = Estado.CONFIRMACAO
    respostas.append(texto_resumo(conversa, ctx))
    return Resultado(conversa, respostas)


def _eh_sem_troco(texto: str) -> bool:
    return " ".join(texto.lower().split()) in {"sem troco", "nao preciso de troco", "não preciso de troco"}


def _troco(conversa: Conversa, texto: str, ctx: Contexto, respostas: list[str]) -> Resultado:
    total = _total(conversa, ctx)
    if _eh_sem_troco(texto):
        conversa.dados["troco_para"] = None
    else:
        valor = interpretar_valor_brl(texto)
        if valor is None or valor < total:  # RN-08
            respostas.append(
                f'O troco precisa ser para um valor maior ou igual a {formatar_brl(total)}, ou envie "sem troco".'
            )
            return Resultado(conversa, respostas)
        conversa.dados["troco_para"] = valor
    conversa.estado = Estado.CONFIRMACAO
    respostas.append(texto_resumo(conversa, ctx))
    return Resultado(conversa, respostas)


def _confirmacao(conversa: Conversa, texto: str, ctx: Contexto, respostas: list[str]) -> Resultado:
    op = _opcao(texto)
    if op == 2:
        return _ir_carrinho(conversa, ctx, respostas)
    if op == 0:
        respostas.append(MSG_CANCELADO)
        return Resultado(Conversa(), respostas)
    if op != 1:
        return Resultado(conversa, [MSG_OPCAO_INVALIDA, texto_resumo(conversa, ctx)])

    # Carrinho não fica vazio aqui: item indisponível devolve o cliente ao carrinho antes
    linhas = tuple(_linhas(conversa, ctx))
    total = _total(conversa, ctx)
    d = conversa.dados
    troco = d.get("troco_para") if d.get("pagamento") == "dinheiro" else None
    if troco is not None and troco < total:  # preço mudou depois do troco informado
        conversa.estado = Estado.TROCO
        respostas.append(_texto_troco(total))
        return Resultado(conversa, respostas)
    pedido = PedidoConfirmado(
        linhas=linhas,
        tipo=d["tipo"],
        endereco=d.get("endereco") if d.get("tipo") == "entrega" else None,
        pagamento=d["pagamento"],
        troco_para_centavos=troco,
        total_centavos=total,
    )
    # A mensagem "Pedido #N recebido" é montada pelo serviço, que conhece o número.
    return Resultado(Conversa(), respostas, pedido)


_HANDLERS = {
    Estado.INICIO: _inicio,
    Estado.CATEGORIAS: _categorias,
    Estado.ITENS: _itens,
    Estado.QUANTIDADE: _quantidade,
    Estado.CARRINHO: _carrinho,
    Estado.REMOVER: _remover,
    Estado.TIPO: _tipo,
    Estado.ENDERECO: _endereco,
    Estado.PAGAMENTO: _pagamento,
    Estado.TROCO: _troco,
    Estado.CONFIRMACAO: _confirmacao,
}
