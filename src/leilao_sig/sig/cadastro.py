"""Fase 2: cadastro do cabeçalho do leilão e dos ciclos (aba Datas) no SIG.

Erro no cabeçalho ou nas datas PARA TUDO (regra do projeto). Cada passo grava no registro
local antes e depois de salvar, para nunca duplicar.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from leilao_sig import registro as reg
from leilao_sig.modelos import CabecalhoPreparado, Preparacao
from leilao_sig.sig.navegador import ErroScript, NavegadorSIG
from leilao_sig.util import fmt_data

log = logging.getLogger(__name__)

URL_FORMULARIO = "/montagem/leilao-formulario"
RX_EDITA = r"^/montagem/(?:edita-leilao|atualiza-leilao)/id/(\d+)"


class ParadaTotal(Exception):
    """Erro no cabeçalho ou nas datas: nada mais é feito nesta execução."""


class JaCadastrado(Exception):
    pass


class VerificarNoSIG(Exception):
    """Ficou um `gravando` de uma execução anterior: alguém precisa olhar no SIG."""


@dataclass
class ResultadoCabecalho:
    chave: str
    sig_id: str = ""
    passos: list[str] = field(default_factory=list)
    ciclos_gravados: list[str] = field(default_factory=list)


def chave_de(cab: CabecalhoPreparado) -> str:
    return reg.chave_leilao(cab.site, cab.titulo, cab.dt1, cab.h1, cab.dt2, cab.h2)


def verificar_registro(prep: Preparacao, registro: reg.Registro) -> str:
    """Antes de abrir o navegador: impede duplicar um leilão já gravado."""
    if prep.bloqueado or not prep.cabecalho:
        raise ParadaTotal("A preparação tem erros: corrija antes de gravar.")
    chave = chave_de(prep.cabecalho)
    existente = registro.leilao(chave)
    if existente and existente.status == reg.CONFIRMADO:
        raise JaCadastrado(f"Este leilão já foi cadastrado no SIG (ID {existente.sig_id}, em {existente.atualizado}).")
    if existente and existente.status == reg.GRAVANDO:
        raise VerificarNoSIG(
            f"Uma execução anterior começou a salvar este leilão em {existente.atualizado} e não confirmou. "
            "Verifique no SIG se ele existe: se existir, não grave de novo; se não existir, descarte o registro e tente outra vez."
        )
    return chave


def verificar_registro_ou_continuar(prep: Preparacao, registro: reg.Registro) -> None:
    """Checagem antes de abrir o Chrome: leilão já confirmado segue (vai continuar nas datas);
    pendente (`gravando`) levanta VerificarNoSIG."""
    if prep.cabecalho and not prep.bloqueado:
        existente = registro.leilao(chave_de(prep.cabecalho))
        if existente and existente.status == reg.CONFIRMADO:
            return
    verificar_registro(prep, registro)


def cadastrar_cabecalho(nav: NavegadorSIG, prep: Preparacao, registro: reg.Registro) -> ResultadoCabecalho:
    cab = prep.cabecalho
    chave = verificar_registro(prep, registro)
    res = ResultadoCabecalho(chave=chave)

    def falhar(msg: str) -> ParadaTotal:
        nav.print("erro_cabecalho")
        return ParadaTotal(f"Cabeçalho: {msg}")

    nav.ir(URL_FORMULARIO)
    r = nav.script("leilao", {"site": cab.site, "titulo": cab.titulo, "fuso": cab.fuso, "dt1": cab.dt1, "h1": cab.h1,
                              "dt2": cab.dt2, "h2": cab.h2, "html": cab.html})
    res.passos.append(f"leilao.js: {r}")
    if not r.startswith("OK"):
        raise falhar(r)
    nav.script("ok-modal")

    for tentativa in range(3):
        r = nav.script("conferir-leilao")
        res.passos.append(f"conferir-leilao.js: {r}")
        if r.startswith("OK"):
            break
        _corrigir_divergencias(nav, r)
        nav.script("ok-modal")
    else:
        raise falhar(f"interruptores fora do padrão depois de 3 tentativas: {r}")
    m = re.search(r"comissao=([\d.,]+)", r)
    if m and m.group(1).replace(",", ".") not in ("5", "5.00", "5.0"):
        res.passos.append(f"ALERTA: comissão no SIG = {m.group(1)} (padrão 5%).")

    registro.leilao_gravando(chave, cab.titulo, cab.site, f"{cab.dt1} {cab.h1}", f"{cab.dt2} {cab.h2}", prep.editais)
    r = nav.script("salvar", {"alvo": "leilao"})
    res.passos.append(f"salvar.js: {r}")
    if not r.startswith("SALVANDO"):
        raise falhar(r)
    try:
        m = nav.esperar_url(RX_EDITA, timeout_ms=30000)
    except Exception as e:
        raise falhar("o SIG não abriu a tela do leilão salvo. Verifique no SIG se ele foi criado antes de tentar de novo.") from e
    res.sig_id = m.group(1)
    registro.leilao_confirmado(chave, res.sig_id)
    log.info("Leilão salvo no SIG: ID %s", res.sig_id)
    return res


def _corrigir_divergencias(nav: NavegadorSIG, retorno: str) -> None:
    """Interpreta o DIVERGE do conferir-leilao.js e liga/desliga os interruptores."""
    for item in retorno.split(":", 1)[-1].split(";"):
        item = item.strip()
        if item.startswith("LIGAR "):
            nav.ligar_interruptor(item[6:].strip(), True)
        elif item.startswith("DESLIGAR "):
            nav.ligar_interruptor(item[9:].strip(), False)
        elif item.startswith("CATEGORIAS"):
            cats = nav.page.locator('input[type=checkbox][name="categorialeilao[]"]')
            for i in range(cats.count()):
                c = cats.nth(i)
                if not c.is_checked():
                    cont = c.locator("xpath=ancestor::*[contains(@class,'ibutton-container')][1]")
                    caixa = cont.bounding_box() if cont.count() else None
                    if caixa:
                        nav.page.mouse.click(caixa["x"] + caixa["width"] * 0.85, caixa["y"] + caixa["height"] / 2)
                    if not c.is_checked():
                        c.evaluate("e => { e.checked = true; window.jQuery(e).trigger('change'); }")
        elif item:
            # campos de select (status, tipo...): o próprio script já acerta tipo e status; o resto é parada
            raise ErroScript(f"Divergência que o app não corrige sozinho: {item}")


def cadastrar_ciclos(nav: NavegadorSIG, prep: Preparacao, res: ResultadoCabecalho, registro: reg.Registro) -> None:
    cab = prep.cabecalho
    if not cab.ciclos:
        res.passos.append("Sem ciclos de venda direta para cadastrar.")
        return
    url = f"/montagem/edita-leilao/id/{res.sig_id}"
    ja = registro.ciclos(res.chave)
    anterior = None
    for c in cab.ciclos:
        data = fmt_data(c.data)
        if ja.get(data) == reg.GRAVANDO:
            nav.print("erro_ciclo")
            raise ParadaTotal(f"Ciclo {data}: ficou pendente numa execução anterior. Verifique a aba Datas no SIG.")
        nav.ir(url)
        nav.marcar_documento()
        r = nav.script("ciclo", {"data": data, "hora": c.hora, "anterior": anterior})
        res.passos.append(f"ciclo.js {data}: {r}")
        if r.startswith("JA_EXISTE"):
            registro.ciclo(res.chave, data, c.hora, reg.CONFIRMADO)
        elif r.startswith("SALVANDO"):
            registro.ciclo(res.chave, data, c.hora, reg.GRAVANDO)
            _esperar_salvar(nav)
            nav.ir(url)
            datas = nav.script("ler-datas")
            if f"Ciclo {data}" not in datas:
                nav.print("erro_ciclo")
                raise ParadaTotal(f"Ciclo {data}: o SIG não mostra o ciclo depois de salvar ({datas[:200]}).")
            registro.ciclo(res.chave, data, c.hora, reg.CONFIRMADO)
            res.ciclos_gravados.append(data)
        else:
            nav.print("erro_ciclo")
            raise ParadaTotal(f"Ciclo {data}: {r}")
        anterior = data
    final = nav.script("ler-datas")
    res.passos.append(f"ler-datas.js: {final}")
    faltando = [fmt_data(c.data) for c in cab.ciclos if f"Ciclo {fmt_data(c.data)}" not in final]
    if faltando:
        raise ParadaTotal(f"Ciclos que não aparecem na aba Datas: {', '.join(faltando)}.")


def _esperar_salvar(nav: NavegadorSIG) -> None:
    """O Salvar da aba Datas recarrega a página: espera a página NOVA carregar (senão a próxima
    navegação atropela o envio) e mais 3 s, como na skill."""
    try:
        nav.esperar_novo_documento(timeout_ms=30000)
    except Exception as e:
        nav.print("erro_ciclo")
        raise ParadaTotal("O SIG não recarregou a aba Datas depois de salvar o ciclo.") from e
    time.sleep(3)


def gravar_cabecalho_e_datas(nav: NavegadorSIG, prep: Preparacao, registro: reg.Registro) -> ResultadoCabecalho:
    """Grava cabeçalho e ciclos. Se o cabeçalho já foi confirmado numa execução anterior (ex.: um
    ciclo falhou), continua no MESMO leilão em vez de criar outro."""
    if prep.cabecalho and not prep.bloqueado:
        existente = registro.leilao(chave_de(prep.cabecalho))
        if existente and existente.status == reg.CONFIRMADO and existente.sig_id:
            res = ResultadoCabecalho(chave=existente.chave, sig_id=existente.sig_id,
                                     passos=[f"Cabeçalho já gravado (ID {existente.sig_id}): continuando nas datas."])
            cadastrar_ciclos(nav, prep, res, registro)
            return res
    res = cadastrar_cabecalho(nav, prep, registro)
    cadastrar_ciclos(nav, prep, res, registro)
    return res
