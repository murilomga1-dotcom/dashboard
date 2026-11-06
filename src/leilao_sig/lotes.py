"""Cruzamento lote do edital ↔ planilha, valores e ordem dos lotes (references/lotes.md)."""

from __future__ import annotations

from decimal import Decimal

from leilao_sig.modelos import LoteIA, Problema
from leilao_sig.planilha import Grupo, normalizar_processo, normalizar_vistoria
from leilao_sig.util import fmt_valor, parse_valor

LIMITE_TITULO = 56
ORDEM_TIPO = {"imovel": 0, "veiculo": 1}


def cruzar(lotes: list[LoteIA], grupos: list[Grupo]) -> tuple[list[tuple[LoteIA, Grupo | None, list[Problema]]], list[Problema]]:
    """Casa cada lote do edital com uma vistoria (grupo de linhas) da planilha.

    A IA indica a vistoria (pela descrição); aqui o código confere que ela existe, é do mesmo
    processo e não foi usada por outro lote. Se a IA não indicou e o processo tem uma vistoria
    só na planilha, usa essa.
    """
    por_processo: dict[str, list[Grupo]] = {}
    for g in grupos:
        por_processo.setdefault(g.processo_digitos, []).append(g)
    usados: dict[tuple, str] = {}
    saida = []
    for lote in lotes:
        probs: list[Problema] = []
        proc = normalizar_processo(lote.processo)
        candidatos = por_processo.get(proc, [])
        escolhido: Grupo | None = None

        def erro(msg: str) -> None:
            probs.append(Problema("erro", msg, lote.processo, lote.numero_no_edital, lote.trecho_edital))

        if not candidatos:
            erro(f"Processo {lote.processo} não está na planilha (ou está sem vistoria).")
        else:
            vist = normalizar_vistoria(lote.vistoria_planilha)
            if vist:
                escolhido = next((b for b in candidatos if b.vistoria == vist), None)
                if not escolhido:
                    erro(f"A vistoria {vist} indicada não pertence ao processo {lote.processo} na planilha.")
            elif len(candidatos) == 1:
                escolhido = candidatos[0]
            else:
                erro(
                    f"Processo {lote.processo} tem {len(candidatos)} vistorias na planilha "
                    f"({', '.join(g.vistoria for g in candidatos)}) e não foi possível saber qual é este lote."
                )
        if escolhido:
            if escolhido.chave in usados:
                erro(f"A vistoria {escolhido.vistoria} já foi usada no lote {usados[escolhido.chave]}.")
                escolhido = None
            else:
                usados[escolhido.chave] = lote.numero_no_edital
        saida.append((lote, escolhido, probs))

    gerais = [
        Problema("alerta", f"Vistoria {g.vistoria} (linha {g.linhas}) não corresponde a nenhum lote do edital.", g.processo)
        for g in grupos
        if g.chave not in usados
    ]
    return saida, gerais


def valores(lote: LoteIA, bem: Grupo, fonte: str = "planilha") -> tuple[dict[str, str], list[Problema]]:
    """v1 = aval = avaliação; v2 = lance mínimo do 2º leilão (somas da vistoria).
    Divergência planilha × edital vira alerta."""
    probs: list[Problema] = []

    def aviso(nivel: str, msg: str) -> None:
        probs.append(Problema(nivel, msg, lote.processo, lote.numero_no_edital, lote.trecho_edital))  # type: ignore[arg-type]

    aval_ed, min_ed = parse_valor(lote.avaliacao_edital), parse_valor(lote.lance_2o_leilao_edital)
    aval, minimo = bem.avaliacao, bem.lance_minimo
    if fonte == "edital":
        aval, minimo = aval_ed or aval, min_ed or minimo
    if aval_ed is not None and bem.avaliacao is not None and aval_ed != bem.avaliacao:
        aviso("alerta", f"Avaliação diverge: planilha {fmt_valor(bem.avaliacao)} × edital {fmt_valor(aval_ed)} (usando {fonte}).")
    if min_ed is not None and bem.lance_minimo is not None and min_ed != bem.lance_minimo:
        aviso("alerta", f"Lance mínimo diverge: planilha {fmt_valor(bem.lance_minimo)} × edital {fmt_valor(min_ed)} (usando {fonte}).")
    pct = parse_valor((lote.percentual_2o_leilao or "").replace("%", ""))
    if bem.tipo != "outro" and lote.tipo_bem != bem.tipo:
        aviso("alerta", f"Tipo do bem: planilha diz {bem.tipo}, IA leu {lote.tipo_bem} (vale a planilha).")
    if pct and aval is not None and minimo is not None:
        esperado = (aval * pct / Decimal(100)).quantize(Decimal("0.01"))
        if abs(esperado - minimo) > Decimal("0.05"):
            aviso("alerta", f"Lance mínimo {fmt_valor(minimo)} ≠ {pct}% da avaliação ({fmt_valor(esperado)}).")
    if aval is None or minimo is None:
        aviso("erro", "Sem avaliação ou lance mínimo.")
        return {}, probs
    if minimo > aval:
        aviso("erro", f"Lance mínimo ({fmt_valor(minimo)}) maior que a avaliação ({fmt_valor(aval)}).")
    return {"v1": fmt_valor(aval), "aval": fmt_valor(aval), "v2": fmt_valor(minimo)}, probs


def ordenar(itens: list[tuple[LoteIA, str, Decimal]]) -> list[LoteIA]:
    """Imóveis → veículos → demais; dentro do tipo, avaliação maior → menor, com bens do mesmo
    processo juntos na posição do maior deles."""
    grupos: dict[tuple[int, str], list[tuple[LoteIA, Decimal]]] = {}
    for lote, tipo_bem, aval in itens:
        tipo = ORDEM_TIPO.get(tipo_bem, 2)
        grupos.setdefault((tipo, normalizar_processo(lote.processo)), []).append((lote, aval))
    for g in grupos.values():
        g.sort(key=lambda x: x[1], reverse=True)
    chaves = sorted(grupos, key=lambda k: (k[0], -grupos[k][0][1]))
    return [lote for k in chaves for lote, _ in grupos[k]]


def problemas_do_lote(lote: LoteIA, tipo_bem: str | None = None) -> list[Problema]:
    tipo_bem = tipo_bem or lote.tipo_bem
    probs = []

    def p(nivel: str, msg: str) -> None:
        probs.append(Problema(nivel, msg, lote.processo, lote.numero_no_edital, lote.trecho_edital))  # type: ignore[arg-type]

    if len(lote.titulo) > LIMITE_TITULO:
        p("erro", f"Título com {len(lote.titulo)} caracteres (máx. {LIMITE_TITULO}): “{lote.titulo}”.")
    if tipo_bem == "imovel":
        faltam = [n for n, v in (("Incra", lote.incra), ("CRI/matrícula", lote.cri)) if not v]
        if faltam:
            p("alerta", f"Imóvel sem {' e '.join(faltam)} no edital (cadastrado sem esse número).")
    elif not lote.localizacao:
        p("alerta", "Edital sem endereço ou depositário do bem: localização omitida.")
    return probs
