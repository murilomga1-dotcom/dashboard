"""Montagem do HTML do cabeçalho e da descrição dos lotes (formatação fixa da skill)."""

from __future__ import annotations

import re
from html import escape

from leilao_sig.modelos import ORDEM_BLOCOS, Bloco, LoteIA

VERMELHO = "color: rgb(219, 42, 22);"
AZUL = "color: rgb(11, 16, 198);"
SEP = "<p><br></p>"
FRASE_FINAL = (
    "CASO HAJA ALGUMA DIVERGÊNCIA ENTRE A FOTO E O BEM PENHORADO, FICA VALENDO O BEM CONSTANTE "
    "NA DESCRIÇÃO DO EDITAL"
)


def _linkar_site(texto_html: str) -> str:
    def troca(m: re.Match) -> str:
        site = m.group(0)
        return f'<a href="https://{site}" target="_blank">{site}</a>'

    return re.sub(r"(?i)\bwww\.[a-z0-9\-]+(?:\.[a-z0-9\-]+)+\b", troca, texto_html)


def _p(conteudo: str) -> str:
    return f"<p>{conteudo}</p>"


def _txt(texto: str) -> str:
    """Texto puro -> HTML seguro, com quebras de linha viradas em <br>."""
    return "<br>".join(escape(l.strip(), quote=False) for l in texto.strip().splitlines() if l.strip())


def bloco_html(b: Bloco) -> str:
    t = _txt(b.texto)
    if b.tipo in ("valor_minimo", "veiculos_parcelados"):
        t = f"<strong>{t}</strong>"
    elif b.tipo == "parcelamento":
        t = f'<span style="{VERMELHO}"><strong>{t}</strong></span>'
    elif b.tipo == "repasse":
        t = f'<span style="{AZUL}"><strong>{t}</strong></span>'
    elif b.tipo == "direito_preferencia":
        t = re.sub(r"^(DIREITO DE PREFER[ÊE]NCIA:)", r"<strong>\1</strong>", t)
    return _p(_linkar_site(t))


def ordenar_blocos(blocos: list[Bloco]) -> list[Bloco]:
    pos = {t: i for i, t in enumerate(ORDEM_BLOCOS)}
    return sorted(blocos, key=lambda b: pos[b.tipo])  # sorted é estável: mantém a ordem da IA no empate


def cabecalho_html(titulo: str, linhas_datas: list[str], linhas_venda_direta: list[str], blocos: list[Bloco]) -> str:
    partes = [_p(f"<strong>{_txt(titulo)}</strong>")]
    partes.append(_p("<br>".join(f"<strong>{escape(l, quote=False)}</strong>" for l in linhas_datas)))
    if linhas_venda_direta:
        partes.append(_p("<br>".join(escape(l, quote=False) for l in ["VENDA DIRETA:", *linhas_venda_direta])))
    partes.extend(bloco_html(b) for b in ordenar_blocos(blocos))
    partes.append(_p(f'<span style="{VERMELHO}">{escape(FRASE_FINAL, quote=False)}</span>'))
    return SEP.join(partes)


def linhas_datas(n: int, inicio: tuple[str, str] | None, encerramento: tuple[str, str]) -> str:
    dt, h = encerramento
    if inicio and inicio[0]:
        di, hi = inicio
        return f"{n}º LEILÃO (INÍCIO): {di} A PARTIR DAS {hi} HORAS | {n}º ENCERRAMENTO: {dt} ÀS {h} HORAS"
    return f"{n}º ENCERRAMENTO DIA {dt} ÀS {h} HORAS"


def resumo_com_registro(lote: LoteIA) -> str:
    """Resumo + (Proc. nº). O registro Incra/CRI do imóvel já vem no resumo pela IA."""
    r = lote.resumo.strip().rstrip(".")
    if lote.processo and lote.processo not in r:
        r = f"{r} (Proc. {lote.processo})"
    return r


def lote_html(lote: LoteIA, distrito_federal: bool) -> str:
    partes = [_p(_txt(resumo_com_registro(lote)))]
    if lote.parcelamento:
        partes.append(_p(f"<strong>{_txt(lote.parcelamento)}</strong>"))
    if lote.obs:
        partes.append(_p(_txt(lote.obs)))
    partes.extend(_p(_txt(f)) for f in lote.frases if f.strip())
    if lote.localizacao and lote.tipo_bem != "imovel":
        loc = lote.localizacao.strip()
        if not loc.lower().startswith("localização do bem"):
            loc = f"Localização do bem: {loc}"
        partes.append(_p(_txt(loc)))
    if distrito_federal and lote.partes_df:
        partes.append(_p("<br>".join(escape(l.strip(), quote=False) for l in lote.partes_df if l.strip())))
    return SEP.join(partes)
