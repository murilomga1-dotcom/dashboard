"""Fase 2 contra o SIG falso, com navegador de verdade (Playwright + Chromium)."""

import glob
from datetime import date

import pytest

from leilao_sig import registro as reg
from leilao_sig.preparar import preparar
from leilao_sig.sig import cadastro
from leilao_sig.sig.navegador import NavegadorSIG, SessaoExpirada
from tests import fabrica
from tests.sig_falso.servidor import SIGFalso

pytest.importorskip("playwright")
CHROMIUM = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))), None)
pytestmark = pytest.mark.skipif(not CHROMIUM, reason="Chromium do ambiente não encontrado")


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    """As esperas de 3 s da skill valem no SIG real; no SIG falso só deixam o teste lento."""
    monkeypatch.setattr(cadastro.time, "sleep", lambda s: None)


@pytest.fixture
def prep(tmp_path):
    ed = fabrica.edital(tmp_path / "edital.docx")
    pl = fabrica.planilha(tmp_path / "bens.xlsx")
    p = preparar(ed, pl, extrator=lambda e, b, s: (fabrica.extracao(), {}), hoje=date(2026, 11, 6))
    assert not p.bloqueado
    return p


def _nav(sig, tmp_path):
    return NavegadorSIG(base_url=sig.url, perfil=tmp_path / "perfil", headless=True, executavel=CHROMIUM,
                        pasta_prints=tmp_path / "prints")


def _login(nav):
    nav.page.goto(nav.base_url + "/login")
    nav.page.fill("[name=usuario]", "teste")
    nav.page.fill("[name=senha]", "x")
    nav.page.click("button[type=submit]")
    nav.page.wait_for_url("**/montagem/leilao-formulario")


def test_sessao_expirada_para_e_pede_login(tmp_path, prep):
    with SIGFalso() as sig, _nav(sig, tmp_path) as nav:
        with pytest.raises(SessaoExpirada):
            nav.ir("/montagem/leilao-formulario")


def test_cabecalho_e_ciclos_no_sig(tmp_path, prep):
    registro = reg.Registro(tmp_path / "registro.sqlite")
    with SIGFalso() as sig:
        with _nav(sig, tmp_path) as nav:
            _login(nav)
            res = cadastro.gravar_cabecalho_e_datas(nav, prep, registro)
        # o login ficou salvo no perfil do app: nova abertura do Chrome não pede de novo
        with _nav(sig, tmp_path) as nav:
            nav.ir("/montagem/leilao-formulario")

        assert res.sig_id == "501" and list(sig.leiloes) == ["501"]
        l = sig.leiloes["501"]
        cab = prep.cabecalho
        assert l["nm"] == cab.titulo
        assert (l["leiloeiro_id"], l["filial_id"], l["fuso_horario"]) == ("11", "99", "-1")
        assert (l["dt"], l["dt_hora"], l["dt_segundoleilao_data"], l["dt_segundoleilao_hora"]) == (cab.dt1, cab.h1, cab.dt2, cab.h2)
        assert l["dt_contabil"] == cab.dt1 and l["statusvendadireta"] == "99" and l["statusfechamentosucesso_id"] == "4"
        # interruptores corrigidos pelo clique no lado direito
        assert l["bn_segundoleilao"] == "1" and l["bn_destaque"] == "0" and l["bn_fechamentoautomatico"] == "1"
        assert sorted(l["categorias"]) == ["1", "2", "3", "4"]
        assert "VENDA DIRETA" in l["nm_descricao"] and "text-align: justify" in l["nm_descricao"]
        # ciclos: 1º e 2º juntos em 04/01/2027, depois 18/01 e 02/02, às 16:00
        assert sig.ciclos["501"] == [("04/01/2027", "16:00"), ("18/01/2027", "16:00"), ("02/02/2027", "16:00")]
        assert registro.leilao(res.chave).status == reg.CONFIRMADO
        assert set(registro.ciclos(res.chave).values()) == {reg.CONFIRMADO}


def test_rodar_de_novo_nao_duplica(tmp_path, prep):
    registro = reg.Registro(tmp_path / "registro.sqlite")
    with SIGFalso(exigir_login=False) as sig, _nav(sig, tmp_path) as nav:
        cadastro.gravar_cabecalho_e_datas(nav, prep, registro)
        res = cadastro.gravar_cabecalho_e_datas(nav, prep, registro)  # "tentar de novo"
        assert list(sig.leiloes) == ["501"] and len(sig.ciclos["501"]) == 3
        assert res.passos[0].startswith("Cabeçalho já gravado (ID 501)")
        with pytest.raises(cadastro.JaCadastrado):
            cadastro.cadastrar_cabecalho(nav, prep, registro)


def test_continua_ciclos_que_faltaram(tmp_path, prep):
    registro = reg.Registro(tmp_path / "registro.sqlite")
    with SIGFalso(exigir_login=False) as sig, _nav(sig, tmp_path) as nav:
        res = cadastro.cadastrar_cabecalho(nav, prep, registro)  # simula: caiu antes das datas
        assert sig.ciclos.get("501") is None
        cadastro.gravar_cabecalho_e_datas(nav, prep, registro)
        assert list(sig.leiloes) == ["501"] and len(sig.ciclos["501"]) == 3


def test_falha_ao_salvar_para_tudo_e_exige_verificacao(tmp_path, prep):
    registro = reg.Registro(tmp_path / "registro.sqlite")
    with SIGFalso(exigir_login=False, falhar_salvar_leilao=True) as sig, _nav(sig, tmp_path) as nav:
        with pytest.raises(cadastro.ParadaTotal):
            cadastro.gravar_cabecalho_e_datas(nav, prep, registro)
        assert (tmp_path / "prints" / "erro_cabecalho.png").exists()
        # ficou "gravando": a próxima tentativa não regrava às cegas
        with pytest.raises(cadastro.VerificarNoSIG):
            cadastro.gravar_cabecalho_e_datas(nav, prep, registro)
        # depois que o usuário confere no SIG e descarta, pode tentar de novo
        registro.descartar_leilao(cadastro.chave_de(prep.cabecalho))
        sig.falhar_salvar_leilao = False
        res = cadastro.gravar_cabecalho_e_datas(nav, prep, registro)
        assert res.sig_id and len(sig.ciclos[res.sig_id]) == 3


def test_tela_nao_permitida(tmp_path):
    from leilao_sig.sig.navegador import ForaDasTelas
    with SIGFalso(exigir_login=False) as sig, _nav(sig, tmp_path) as nav:
        with pytest.raises(ForaDasTelas):
            nav.ir("/montagem/excluir-leilao/id/501")


def test_botao_gravar_espera_login_e_grava(tmp_path, prep, monkeypatch):
    """O que o botão "Gravar no SIG" faz: abre o Chrome, espera o login, grava e informa."""
    from leilao_sig import gui
    from leilao_sig.sig import navegador

    with SIGFalso() as sig:
        original = navegador.NavegadorSIG

        class NavTeste(original):
            def __init__(self, **kw):
                super().__init__(base_url=sig.url, perfil=tmp_path / "perfil", headless=True, executavel=CHROMIUM, **kw)

            def abrir(self):
                super().abrir()
                # "usuário" digita o login na janela do Chrome meio segundo depois de a página abrir
                self._ctx.add_init_script("""
                  if (location.pathname === '/login') setTimeout(function () {
                    document.querySelector('[name=senha]').value = 'x';
                    document.querySelector('form').submit();
                  }, 500);""")
                return self

        monkeypatch.setattr(navegador, "NavegadorSIG", NavTeste)
        trab = gui._TrabalhoSIG(prep)
        avisos, fim = [], []
        trab.aviso.connect(avisos.append)
        trab.terminou.connect(lambda *a: fim.append(a))
        trab.rodar()
        assert fim[0][0] == "ok", fim
        assert "ID 501" in fim[0][1] and any("Faça login" in a for a in avisos)
        assert len(sig.ciclos["501"]) == 3
        # segunda vez: não duplica, só confirma
        trab.rodar()
        assert fim[1][0] == "ok" and list(sig.leiloes) == ["501"]
