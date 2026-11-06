"""Chrome próprio (perfil salvo) controlado pelo Playwright, só nas telas permitidas do SIG.

Mesma restrição da skill cadastrar-leilao-sig-completo: só o formulário de leilão, a edição do
leilão criado nesta execução e o loteamento dele. Mudança de tela só pela URL.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from leilao_sig import config

log = logging.getLogger(__name__)

TELAS_PERMITIDAS = (
    re.compile(r"^/montagem/leilao-formulario/?$"),
    re.compile(r"^/montagem/(edita-leilao|atualiza-leilao)/id/\d+/?$"),
    re.compile(r"^/montagem/loteamento/id/\d+/leilao_id/\d+/?$"),
)


class SessaoExpirada(Exception):
    """O SIG pediu login: o usuário precisa entrar no Chrome do app e mandar continuar."""


class ForaDasTelas(Exception):
    """A página saiu das telas permitidas (ou do domínio do SIG)."""


class ErroScript(Exception):
    """Um script do SIG devolveu ERRO/FORA/DIVERGE ou falhou."""


def caminho_script(nome: str) -> Path:
    return config.PASTA_SCRIPTS_SIG / f"{nome}.js"


class NavegadorSIG:
    def __init__(self, base_url: str | None = None, perfil: Path | None = None, headless: bool = False,
                 executavel: str | None = None, pasta_prints: Path | None = None):
        self.base_url = (base_url or config.app()["sig_url"]).rstrip("/")
        self.host = urlparse(self.base_url).netloc
        self.perfil = perfil or (config.pasta_dados() / "chrome-perfil")
        self.headless = headless
        self.executavel = executavel
        self.pasta_prints = pasta_prints
        self._pw = self._ctx = self.page = None

    # ---- ciclo de vida ----
    def abrir(self) -> "NavegadorSIG":
        from playwright.sync_api import sync_playwright

        self.perfil.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        opcoes = dict(user_data_dir=str(self.perfil), headless=self.headless, viewport={"width": 1366, "height": 850})
        if self.executavel:
            opcoes["executable_path"] = self.executavel
        else:
            opcoes["channel"] = config.app().get("chrome_canal", "chrome")  # Chrome instalado na máquina
        self._ctx = self._pw.chromium.launch_persistent_context(**opcoes)
        self._ctx.set_default_timeout(20000)
        self.page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        # alert/confirm do SIG: aceitar (os scripts da skill também fazem isso dentro da página)
        self.page.on("dialog", lambda d: d.accept())
        return self

    def fechar(self) -> None:
        try:
            if self._ctx:
                self._ctx.close()
        finally:
            if self._pw:
                self._pw.stop()
            self._ctx = self._pw = self.page = None

    def __enter__(self) -> "NavegadorSIG":
        return self.abrir()

    def __exit__(self, *exc) -> None:
        self.fechar()

    # ---- navegação ----
    def ir(self, caminho: str) -> None:
        if not any(p.match(caminho) for p in TELAS_PERMITIDAS):
            raise ForaDasTelas(f"Tela não permitida: {caminho}")
        self.page.goto(self.base_url + caminho, wait_until="domcontentloaded")
        self.page.wait_for_load_state("load")
        self.conferir_tela()

    def caminho_atual(self) -> str:
        return urlparse(self.page.url).path

    def na_tela_de_login(self) -> bool:
        u = urlparse(self.page.url)
        if re.search(r"login|entrar|auth", u.path, re.I):
            return True
        return self.page.locator("input[type=password]:visible").count() > 0

    def conferir_tela(self) -> None:
        if self.na_tela_de_login():
            raise SessaoExpirada("A sessão do SIG caiu. Faça login no Chrome do app e clique em Continuar.")
        u = urlparse(self.page.url)
        if u.netloc != self.host or not any(p.match(u.path) for p in TELAS_PERMITIDAS):
            raise ForaDasTelas(f"A página saiu das telas permitidas: {self.page.url}")

    def esperar_login(self, timeout_ms: int = 300000) -> None:
        """Abre o formulário e espera o usuário fazer login (primeira vez ou sessão caída)."""
        self.page.goto(self.base_url + "/montagem/leilao-formulario", wait_until="domcontentloaded")
        self.page.wait_for_function(
            "() => !document.querySelector('input[type=password]') && /leilao-formulario/.test(location.pathname)",
            timeout=timeout_ms,
        )

    # ---- scripts da skill ----
    def script(self, nome: str, cfg: dict | None = None) -> str:
        """Roda sig_scripts/<nome>.js com `var $ = window.jQuery; var CFG = {...};` antes, como a skill."""
        self.conferir_tela()
        fonte = caminho_script(nome).read_text(encoding="utf-8")
        resultado = self.page.evaluate(
            "([fonte, cfg]) => { var $ = window.jQuery; var CFG = cfg; return String(eval(fonte)); }",
            [fonte, cfg or {}],
        )
        log.info("script %s %s -> %s", nome, json.dumps(cfg or {}, ensure_ascii=False)[:200], resultado[:400])
        if resultado.startswith("FORA"):
            raise ForaDasTelas(f"{nome}: {resultado}")
        return resultado

    def marcar_documento(self) -> None:
        """Marca a página atual; esperar_novo_documento() só volta quando outra página carregar."""
        self.page.evaluate("() => { window.__leilaoSigMarca = true; }")

    def esperar_novo_documento(self, timeout_ms: int = 20000) -> None:
        self.page.wait_for_function("() => !window.__leilaoSigMarca && document.readyState === 'complete'",
                                    timeout=timeout_ms)

    def esperar_url(self, padrao: str, timeout_ms: int = 20000) -> re.Match:
        rx = re.compile(padrao)
        self.page.wait_for_url(lambda url: bool(rx.search(urlparse(url).path)), timeout=timeout_ms)
        self.page.wait_for_load_state("load")
        return rx.search(self.caminho_atual())

    def print(self, nome: str) -> Path | None:
        if not (self.page and self.pasta_prints):
            return None
        self.pasta_prints.mkdir(parents=True, exist_ok=True)
        caminho = self.pasta_prints / f"{nome}.png"
        try:
            self.page.screenshot(path=str(caminho), full_page=True)
            return caminho
        except Exception:  # print é ajuda de diagnóstico; nunca derruba o fluxo
            log.exception("Falha ao tirar print")
            return None

    def ligar_interruptor(self, nome: str, ligar: bool) -> None:
        """iButton do SIG: clicar no lado DIREITO do controle alterna; confere pelo checkbox."""
        chk = self.page.locator(f'input[type=checkbox][name="{nome}"]').first
        if chk.is_checked() == ligar:
            return
        cont = chk.locator("xpath=ancestor::*[contains(@class,'ibutton-container')][1]")
        if cont.count():
            caixa = cont.bounding_box()
            if caixa:
                self.page.mouse.click(caixa["x"] + caixa["width"] * 0.85, caixa["y"] + caixa["height"] / 2)
        if chk.is_checked() != ligar:  # sem iButton visível: muda pelo próprio checkbox
            self.page.evaluate(
                "([n, v]) => { var $ = window.jQuery; $('input[type=checkbox][name=\"' + n + '\"]').first().prop('checked', v).trigger('change'); }",
                [nome, ligar],
            )
        if chk.is_checked() != ligar:
            raise ErroScript(f"Não consegui {'ligar' if ligar else 'desligar'} {nome}.")
