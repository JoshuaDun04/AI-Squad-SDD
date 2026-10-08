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
OBSERVACAO_MAX = 140  # RN-11

MSG_QTD_INVALIDA = "Envie um número de 1 a 20."
MSG_OPCAO_INVALIDA = "Opção inválida."
MSG_ENDERECO = "Envie o endereço completo para entrega (rua, número, bairro e uma referência)."
MSG_EXPIROU = "Seu carrinho expirou depois de 30 minutos sem resposta. Vamos começar de novo."
MSG_CARRINHO_VAZIO = "Seu carrinho está vazio."
MSG_CANCELADO = "Pedido cancelado. Quando quiser, é só mandar uma mensagem."
MSG_OBSERVACAO = (
    "Escreva a observação para a cozinha, em até 140 caracteres (ex.: tambaqui sem cebola). "
    "Envie 0 para ficar sem observação."
)
MSG_OBSERVACAO_LONGA = "A observação pode ter no máximo 140 caracteres."
MSG_MENU_MUDOU = "O cardápio mudou desde a última mensagem. Confira as opções de novo."
MSG_CARRINHO_MUDOU = "O carrinho mudou desde a última mensagem. Confira de novo."
MSG_PRECO_MUDOU = "Os preços mudaram desde o resumo. Confira o pedido atualizado antes de confirmar."

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
    OBSERVACAO = "OBSERVACAO"


# Estados em que o cliente já está fechando o pedido; se o carrinho muda
# (item ficou indisponível), voltamos ao carrinho para ele revisar.
_ESTADOS_FECHAMENTO = {
    Estado.TIPO,
    Estado.ENDERECO,
    Estado.PAGAMENTO,
    Estado.TROCO,
    Estado.CONFIRMACAO,
    Estado.OBSERVACAO,
}


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
    observacao: str | None = None


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
    if d.get("observacao"):
        linhas.append(f"Observação: {d['observacao']}")
    linhas.append("")
    acao_obs = "Alterar observação" if d.get("observacao") else "Adicionar observação"
    linhas.append(f"1 - Confirmar pedido, 2 - Voltar ao carrinho, 3 - {acao_obs}, 0 - Cancelar")
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
    conversa.dados["menu"] = [c.id for c in ctx.categorias]  # REV-05: número → id exibido
    respostas.append(texto_categorias(ctx, conversa))
    return Resultado(conversa, respostas)


def _escolha(conversa: Conversa, op: int | None, ids_atuais: list[str]) -> str | None:
    """Converte o número digitado no id que estava na tela quando o cliente leu o menu.

    Se o menu salvo não existir (conversa antiga), usa a ordem atual.
    """
    menu = conversa.dados.get("menu") or ids_atuais
    if op is None or not 1 <= op <= len(menu):
        return None
    return menu[op - 1]


def _mostrar_itens(conversa: Conversa, cat: CategoriaVista, respostas: list[str]) -> Resultado:
    conversa.estado = Estado.ITENS
    conversa.dados["categoria_id"] = cat.id
    conversa.dados["menu"] = [it.id for it in cat.itens]
    respostas.append(texto_itens(cat))
    return Resultado(conversa, respostas)


def _mostrar_resumo(conversa: Conversa, ctx: Contexto, respostas: list[str]) -> Resultado:
    """Mostra o resumo e guarda o total exibido: o cliente só confirma o que viu (REV-06)."""
    conversa.estado = Estado.CONFIRMACAO
    conversa.dados["total_resumo"] = _total(conversa, ctx)
    respostas.append(texto_resumo(conversa, ctx))
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
    cid = _escolha(conversa, op, [c.id for c in ctx.categorias])
    if cid is None:
        respostas.append(MSG_OPCAO_INVALIDA)
        return _ir_categorias(conversa, ctx, respostas)
    cat = next((c for c in ctx.categorias if c.id == cid), None)
    if cat is None:  # a categoria escolhida saiu do menu depois que o cliente o leu
        respostas.append(MSG_MENU_MUDOU)
        return _ir_categorias(conversa, ctx, respostas)
    return _mostrar_itens(conversa, cat, respostas)


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
    item_id = _escolha(conversa, op, [it.id for it in cat.itens])
    if item_id is None:
        respostas.append(MSG_OPCAO_INVALIDA)
        return _mostrar_itens(conversa, cat, respostas)
    item = next((it for it in cat.itens if it.id == item_id), None)
    if item is None:  # o item escolhido ficou indisponível depois que o cliente leu o menu
        respostas.append(MSG_MENU_MUDOU)
        return _mostrar_itens(conversa, cat, respostas)
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
        conversa.dados["menu"] = [l["item_id"] for l in conversa.carrinho]
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
    if op == 0:
        return _ir_carrinho(conversa, ctx, respostas)
    item_id = _escolha(conversa, op, [l["item_id"] for l in conversa.carrinho])
    if item_id is None:
        respostas.append(MSG_OPCAO_INVALIDA)
        return _ir_carrinho(conversa, ctx, respostas)
    restantes = [l for l in conversa.carrinho if l["item_id"] != item_id]
    if len(restantes) == len(conversa.carrinho):  # a linha já tinha saído do carrinho
        respostas.append(MSG_CARRINHO_MUDOU)
    conversa.carrinho = restantes
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
    return _mostrar_resumo(conversa, ctx, respostas)


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
    return _mostrar_resumo(conversa, ctx, respostas)


def _confirmacao(conversa: Conversa, texto: str, ctx: Contexto, respostas: list[str]) -> Resultado:
    op = _opcao(texto)
    if op == 2:
        return _ir_carrinho(conversa, ctx, respostas)
    if op == 0:
        respostas.append(MSG_CANCELADO)
        return Resultado(Conversa(), respostas)
    if op == 3:
        conversa.estado = Estado.OBSERVACAO
        return Resultado(conversa, [MSG_OBSERVACAO])
    if op != 1:
        return _mostrar_resumo(conversa, ctx, [MSG_OPCAO_INVALIDA])

    # Carrinho não fica vazio aqui: item indisponível devolve o cliente ao carrinho antes
    linhas = tuple(_linhas(conversa, ctx))
    total = _total(conversa, ctx)
    d = conversa.dados
    troco = d.get("troco_para") if d.get("pagamento") == "dinheiro" else None
    if troco is not None and troco < total:  # preço mudou depois do troco informado
        conversa.estado = Estado.TROCO
        respostas.append(_texto_troco(total))
        return Resultado(conversa, respostas)
    if d.get("total_resumo") != total:  # REV-06: confirma só o total que o cliente viu
        return _mostrar_resumo(conversa, ctx, [MSG_PRECO_MUDOU])
    pedido = PedidoConfirmado(
        linhas=linhas,
        tipo=d["tipo"],
        endereco=d.get("endereco") if d.get("tipo") == "entrega" else None,
        pagamento=d["pagamento"],
        troco_para_centavos=troco,
        total_centavos=total,
        observacao=d.get("observacao"),
    )
    # A mensagem "Pedido #N recebido" é montada pelo serviço, que conhece o número.
    return Resultado(Conversa(), respostas, pedido)


def _observacao(conversa: Conversa, texto: str, ctx: Contexto, respostas: list[str]) -> Resultado:
    """RN-11: observação livre do pedido, opcional, até 140 caracteres."""
    obs = " ".join(texto.split())
    if obs == "0":
        conversa.dados.pop("observacao", None)
    elif not obs:
        return Resultado(conversa, [MSG_OBSERVACAO])
    elif len(obs) > OBSERVACAO_MAX:
        return Resultado(conversa, [MSG_OBSERVACAO_LONGA, MSG_OBSERVACAO])
    else:
        conversa.dados["observacao"] = obs
    return _mostrar_resumo(conversa, ctx, respostas)


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
    Estado.OBSERVACAO: _observacao,
}
