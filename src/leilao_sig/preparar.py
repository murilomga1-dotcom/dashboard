"""Fase 1: editais + planilha -> Preparacao (cabeçalho, ciclos e lotes prontos para revisão).

Nada aqui toca no SIG. Qualquer erro em triagem, leiloeiro, datas ou ciclos bloqueia tudo;
erro num lote marca só aquele lote.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from leilao_sig import ciclos as mod_ciclos
from leilao_sig import config, documento, ia, lotes as mod_lotes, montagem
from leilao_sig.execucao import Execucao
from leilao_sig.modelos import (
    Bloco, CabecalhoPreparado, ExtracaoEdital, LotePreparado, Preparacao, Pregao, Problema,
)
from leilao_sig.planilha import TIPOS, Bem, PlanilhaInvalida, agrupar, ler_planilha
from leilao_sig.util import fmt_data, parse_data, sem_acento

log = logging.getLogger(__name__)

Extrator = Callable[[list[tuple[str, str]], list[Bem], tuple[str, ...]], tuple[ExtracaoEdital, dict]]


class Bloqueio(Exception):
    """Erro que impede o cadastro inteiro (cabeçalho/datas/triagem)."""

    def __init__(self, mensagem: str, trecho: str = ""):
        super().__init__(mensagem)
        self.trecho = trecho


def preparar(
    caminhos_editais: list[str | Path] | str | Path,
    caminho_planilha: str | Path,
    extrator: Extrator | None = None,
    hoje: date | None = None,
    execucao: Execucao | None = None,
) -> Preparacao:
    """Um leilão do SIG: um ou mais editais (um por processo) e a planilha da sessão."""
    if isinstance(caminhos_editais, (str, Path)):
        caminhos_editais = [caminhos_editais]
    caminhos = [Path(c) for c in caminhos_editais]
    extrator = extrator or (lambda e, b, s: ia.extrair(e, b, s))
    hoje = hoje or date.today()
    prep = Preparacao(editais=[str(c) for c in caminhos], planilha=str(caminho_planilha), cabecalho=None, lotes=[], problemas=[])
    try:
        if not caminhos:
            raise Bloqueio("Nenhum edital selecionado.")
        if len({c.name for c in caminhos}) != len(caminhos):
            raise Bloqueio("Há editais com o mesmo nome de arquivo; renomeie para diferenciar.")
        textos: list[tuple[str, str]] = []
        suspeitas: set[str] = set()
        for c in caminhos:
            try:
                edital = documento.ler_edital(c)
            except documento.EditalInvalido as e:
                raise Bloqueio(f"{c.name}: {e}") from e
            tri = documento.triar(edital.texto)
            if tri.bloqueado:
                raise Bloqueio(f"{c.name}: {tri.motivo}")
            suspeitas.update(tri.suspeitas)
            textos.append((c.name, edital.texto))
        try:
            bens, avisos = ler_planilha(caminho_planilha)
        except PlanilhaInvalida as e:
            raise Bloqueio(str(e)) from e
        prep.problemas += [Problema("alerta", a) for a in avisos]
        if not bens:
            raise Bloqueio("A planilha não tem nenhuma linha com vistoria preenchida.")

        log.info("%d edital(is) (%d caracteres), %d bens na planilha",
                 len(textos), sum(len(t) for _, t in textos), len(bens))
        ext, uso = extrator(textos, bens, tuple(sorted(suspeitas)))
        prep.extracao = ext
        if execucao:
            execucao.salvar_json("resposta_ia.json", {"uso": uso, "extracao": ext})
        _montar(prep, ext, bens, textos, hoje)
    except Bloqueio as e:
        prep.problemas.append(Problema("erro", str(e), trecho=e.trecho))
    except (ia.ErroIA, mod_ciclos.CalendarioDesatualizado) as e:
        prep.problemas.append(Problema("erro", str(e)))
    if prep.bloqueado:
        prep.cabecalho = None  # nunca deixar um cabeçalho "meio pronto" ir para o SIG
    if execucao:
        execucao.salvar_json("preparacao.json", {k: v for k, v in prep.__dict__.items() if k != "extracao"})
    return prep


def _montar(prep: Preparacao, ext: ExtracaoEdital, bens: list[Bem], textos: list[tuple[str, str]], hoje: date) -> None:
    texto = "\n\n".join(t for _, t in textos)
    nomes = {n for n, _ in textos}
    lidos = {e.arquivo for e in ext.editais}
    if nomes - lidos:
        raise Bloqueio(f"A IA não devolveu os dados de: {', '.join(sorted(nomes - lidos))}.")
    for e in ext.editais:
        if e.tipo_edital != "judicial_comum":
            raise Bloqueio(f"{e.arquivo}: edital fora do padrão ({e.tipo_edital}): {e.motivo_tipo_edital}")

    leiloeiro = config.achar_leiloeiro(ext.leiloeiro_nome, ext.leiloeiro_site)
    if not leiloeiro:
        raise Bloqueio(
            f"Leiloeiro desconhecido: “{ext.leiloeiro_nome}” ({ext.leiloeiro_site or 'sem site'}). "
            "Cadastre-o em config/leiloeiros.json antes de continuar.",
            documento.trecho(texto, ext.leiloeiro_nome),
        )

    dt1, h1, ini1, a1 = _encerramento(1, ext.leilao_1)
    dt2, h2, ini2, a2 = _encerramento(2, ext.leilao_2)
    for a in a1 + a2:
        prep.problemas.append(Problema("alerta", a))
    d1, d2 = parse_data(dt1), parse_data(dt2)
    _conferir_editais(ext, leiloeiro, (dt1, h1, dt2, h2))
    if d1 < hoje:
        raise Bloqueio(f"O 1º leilão ({dt1}) já passou.", ext.leilao_1.trecho_edital)
    if (d2, h2) <= (d1, h1):
        raise Bloqueio(f"O 2º encerramento ({dt2} {h2}) não é depois do 1º ({dt1} {h1}).", ext.leilao_2.trecho_edital)

    fuso = mod_ciclos.fuso(ext.uf, ext.comarca_cidade)
    if fuso != "0" and "horario de brasilia" in sem_acento(texto):
        prep.problemas.append(Problema("alerta", f"O edital fala em “horário de Brasília”, mas a comarca ({ext.uf}) tem fuso {fuso}."))

    # Venda direta e ciclos
    lista_ciclos: list[mod_ciclos.Ciclo] = []
    vd = ext.venda_direta
    if vd and not leiloeiro.venda_direta:
        prep.problemas.append(Problema("alerta", f"Venda direta não cadastrada (regra do leiloeiro {leiloeiro.nome})."))
    elif vd:
        hora = leiloeiro.horario_ciclos
        if vd.horario_fixado_no_edital and _hora(vd.horario_fixado_no_edital) != hora:
            hora = _hora(vd.horario_fixado_no_edital)
            prep.problemas.append(Problema("alerta", f"Edital fixa os ciclos às {hora} (padrão do leiloeiro: {leiloeiro.horario_ciclos}).", trecho=vd.trecho_edital))
        try:
            lista_ciclos = mod_ciclos.calcular_ciclos(d2, vd.prazo_dias, vd.duracao_ciclo_dias, hora)
        except ValueError as e:
            raise Bloqueio(str(e), vd.trecho_edital) from e
        for c in lista_ciclos:
            for aj in c.ajustes:
                prep.problemas.append(Problema("alerta", f"{c.rotulo}: {aj}."))

    # 0800 nos blocos
    tel = leiloeiro.telefone_0800 or (ext.telefone_0800_edital or "")
    blocos = list(ext.blocos_cabecalho)
    if any("{0800}" in b.texto for b in blocos):
        if not tel:
            tel = "0800-***-***"
            prep.problemas.append(Problema("alerta", "0800 do leiloeiro não encontrado: ficou 0800-***-*** no cabeçalho."))
        blocos = [Bloco(tipo=b.tipo, texto=b.texto.replace("{0800}", tel)) for b in blocos]

    datas = [montagem.linhas_datas(1, ini1, (dt1, h1)), montagem.linhas_datas(2, ini2, (dt2, h2))]
    html = montagem.cabecalho_html(ext.titulo_leilao, datas, mod_ciclos.linhas_venda_direta(lista_ciclos), blocos)
    site = leiloeiro.site or sem_acento(ext.leiloeiro_site).replace("https://", "").replace("http://", "").replace("www.", "").split(".")[0]
    prep.cabecalho = CabecalhoPreparado(
        site=site, titulo=ext.titulo_leilao, fuso=fuso, dt1=dt1, h1=h1, dt2=dt2, h2=h2, html=html,
        ciclos=lista_ciclos, leiloeiro=leiloeiro.nome, venda_direta_cadastrada=bool(lista_ciclos),
    )
    prep.problemas += [Problema("alerta", f"IA: {a}") for a in ext.alertas]

    # Lotes
    grupos, avisos_grupos = agrupar(bens)
    prep.problemas += [Problema("alerta", a) for a in avisos_grupos]
    cruzados, gerais = mod_lotes.cruzar(ext.lotes, grupos)
    prep.problemas += gerais
    fonte = config.app().get("fonte_valores", "planilha")
    preparados: dict[int, LotePreparado] = {}
    para_ordenar = []
    for lote, bem, probs in cruzados:
        tipo = bem.tipo if bem and bem.tipo != "outro" else lote.tipo_bem
        probs += mod_lotes.problemas_do_lote(lote, tipo)
        vals: dict[str, str] = {}
        if bem:
            vals, pv = mod_lotes.valores(lote, bem, fonte)
            probs += pv
        lp = LotePreparado(
            ordem=0, arquivo_edital=lote.arquivo_edital, numero_no_edital=lote.numero_no_edital, processo=lote.processo,
            vistoria=bem.vistoria if bem else "", chave_vistoria=lote.chave_vistoria,
            tipo_bem=tipo, aba_sig=TIPOS.get(tipo, ("", ""))[1], titulo=lote.titulo, html=montagem.lote_html(lote, ext.distrito_federal),
            v1=vals.get("v1", ""), aval=vals.get("aval", ""), v2=vals.get("v2", ""),
            trecho_edital=lote.trecho_edital, problemas=probs,
        )
        preparados[id(lote)] = lp
        para_ordenar.append((lote, tipo, bem.avaliacao if bem and bem.avaliacao is not None else 0))
    for i, lote in enumerate(mod_lotes.ordenar(para_ordenar), start=1):
        preparados[id(lote)].ordem = i
    prep.lotes = sorted(preparados.values(), key=lambda l: l.ordem)


def _conferir_editais(ext: ExtracaoEdital, leiloeiro, datas: tuple[str, str, str, str]) -> None:
    """Todos os editais do leilão precisam ter o mesmo leiloeiro, encerramentos e venda direta,
    porque o SIG tem um cabeçalho e uma aba Datas só para o leilão inteiro."""
    vd = ext.venda_direta
    vd_cab = (vd.prazo_dias, vd.duracao_ciclo_dias) if vd else None
    for e in ext.editais:
        l = config.achar_leiloeiro(e.leiloeiro_nome)
        if l and l.nome != leiloeiro.nome:
            raise Bloqueio(f"{e.arquivo}: leiloeiro {l.nome}, diferente do leilão ({leiloeiro.nome}).")
        try:
            d = (*_encerramento(1, e.leilao_1)[:2], *_encerramento(2, e.leilao_2)[:2])
        except Bloqueio as b:
            raise Bloqueio(f"{e.arquivo}: {b}", b.trecho) from b
        if d != datas:
            raise Bloqueio(
                f"{e.arquivo}: encerramentos {d[0]} {d[1]} / {d[2]} {d[3]} diferentes do leilão "
                f"({datas[0]} {datas[1]} / {datas[2]} {datas[3]}). Editais com datas diferentes não podem ir no mesmo leilão.",
                e.leilao_1.trecho_edital,
            )
        vd_e = (e.venda_direta.prazo_dias, e.venda_direta.duracao_ciclo_dias) if e.venda_direta else None
        if vd_e != vd_cab:
            raise Bloqueio(
                f"{e.arquivo}: venda direta {vd_e or 'ausente'} diferente do leilão ({vd_cab or 'ausente'}) — prazo e duração dos ciclos (dias).",
                e.venda_direta.trecho_edital if e.venda_direta else "",
            )


def _hora(h: str) -> str:
    h = h.strip().lower().replace("h", ":").rstrip(":")
    if ":" not in h:
        h += ":00"
    hh, mm = h.split(":")[:2]
    return f"{int(hh):02d}:{int(mm or 0):02d}"


def _encerramento(n: int, p: Pregao) -> tuple[str, str, tuple[str, str] | None, list[str]]:
    """Devolve (data, hora do encerramento, (data, hora) do início ou None, alertas)."""
    alertas = []
    inicio = (p.data_inicio, _hora(p.hora_inicio)) if p.data_inicio and p.hora_inicio else None
    try:
        if p.data_encerramento and p.hora_encerramento:
            dt, h = p.data_encerramento, _hora(p.hora_encerramento)
            parse_data(dt)
        elif inicio and p.duracao_minutos:
            fim = datetime.strptime(f"{inicio[0]} {inicio[1]}", "%d/%m/%Y %H:%M") + timedelta(minutes=p.duracao_minutos)
            dt, h = fmt_data(fim.date()), fim.strftime("%H:%M")
            alertas.append(f"{n}º encerramento calculado: início {inicio[1]} + {p.duracao_minutos} min = {h}.")
        else:
            raise Bloqueio(f"O edital não informa o encerramento do {n}º leilão.", p.trecho_edital)
    except ValueError as e:
        raise Bloqueio(f"Data/hora inválida no {n}º leilão: {e}", p.trecho_edital) from e
    return dt, h, inicio, alertas
