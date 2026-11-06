from datetime import date
from decimal import Decimal

import pytest

from leilao_sig import ciclos, config, documento, lotes, montagem
from leilao_sig.planilha import agrupar, ler_planilha
from leilao_sig.util import fmt_valor, parse_valor
from tests import fabrica


@pytest.mark.parametrize("entrada,esperado", [
    ("68.000,00", "68000.00"), ("R$ 1.234.567,89", "1234567.89"), (68000, "68000.00"),
    (68000.5, "68000.50"), ("68.000", "68000.00"), ("1500.50", "1500.50"), ("", None), (None, None),
])
def test_parse_valor(entrada, esperado):
    v = parse_valor(entrada)
    assert (str(v) if v is not None else None) == esperado


def test_fmt_valor():
    assert fmt_valor(Decimal("68000")) == "68.000,00"
    assert fmt_valor(Decimal("1234567.8")) == "1.234.567,80"
    assert fmt_valor(Decimal("5")) == "5,00"


def test_fuso():
    assert ciclos.fuso("MS") == "-1"
    assert ciclos.fuso("ac") == "-2"
    assert ciclos.fuso("SP") == "0"
    assert ciclos.fuso("PE", "Fernando de Noronha") == "+1"


def test_ciclos_recesso_e_ciclos_juntados():
    # 2º leilão 04/12/2026, 60 dias, ciclos de 15:
    # 19/12 (sáb) -> 21/12 -> recesso 04/01/2027; 03/01 (dom) -> 04/01 => "1º E 2º CICLO"
    cs = ciclos.calcular_ciclos(date(2026, 12, 4), 60, 15, "16:00")
    assert [(c.numeros, c.data) for c in cs] == [
        ([1, 2], date(2027, 1, 4)), ([3], date(2027, 1, 18)), ([4], date(2027, 2, 2)),
    ]
    assert cs[0].prorrogado_de == date(2026, 12, 21)
    linhas = ciclos.linhas_venda_direta(cs)
    assert linhas[0] == "1º E 2º CICLO DIA 04/01/2027 C/ ENCERRAMENTO ÀS 16:00 HORAS"
    assert linhas[-1].startswith("ATENÇÃO! POR CONTA DO RECESSO, O CICLO DESIGNADO PARA O DIA 21/12/2026")


def test_ciclos_ajuste_nao_empurra_os_proximos():
    # 2º leilão 10/11/2026, ciclos de 5: 15/11 (dom, feriado) -> 16/11; seguinte = 20/11 nominal (feriado) -> 23/11
    cs = ciclos.calcular_ciclos(date(2026, 11, 10), 10, 5, "16:00")
    assert [c.data for c in cs] == [date(2026, 11, 16), date(2026, 11, 23)]
    assert [c.nominal for c in cs] == [date(2026, 11, 15), date(2026, 11, 20)]


def test_ciclos_fora_do_calendario():
    with pytest.raises(ciclos.CalendarioDesatualizado):
        ciclos.calcular_ciclos(date(2027, 12, 1), 60, 15, "16:00")


def test_ciclos_prazo_nao_multiplo():
    with pytest.raises(ValueError):
        ciclos.calcular_ciclos(date(2026, 11, 10), 50, 15, "16:00")


@pytest.mark.parametrize("nome,site,esperado", [
    ("Aparecida Maria Fixer", "", "Aparecida Maria Fixer"),
    ("CONCEIÇÃO MARIA FIXER", "", "Conceição Maria Fixer"),
    ("Leiloeira Oficial Joyce Ribeiro, JUCEPAR nº 1", "", "Joyce Ribeiro"),
    ("", "www.jrleiloes.com.br", "Joyce Ribeiro"),
    ("Fulano de Tal", "www.fulano.com.br", None),
])
def test_achar_leiloeiro(nome, site, esperado):
    l = config.achar_leiloeiro(nome, site)
    assert (l.nome if l else None) == esperado


def test_regra_joyce_bruno_sem_venda_direta():
    assert not config.achar_leiloeiro("Joyce Ribeiro").venda_direta
    assert not config.achar_leiloeiro("Bruno Meireles").venda_direta


def test_planilha(tmp_path):
    bens, avisos = ler_planilha(fabrica.planilha(tmp_path / "p.xlsx"))
    assert [b.vistoria for b in bens] == ["33578", "33579", "33600"]  # sem vistoria = ignorada; 33579.0 -> 33579
    assert bens[2].processo_digitos == "70020542120208220003"  # sem máscara bate com a máscara
    assert bens[1].avaliacao == Decimal("25000.00") and bens[1].lance_minimo == Decimal("12500.00")
    assert avisos == []


def test_planilha_sem_cabecalho(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook(); wb.active.append(["x", "y"]); wb.save(tmp_path / "ruim.xlsx")
    from leilao_sig.planilha import PlanilhaInvalida
    with pytest.raises(PlanilhaInvalida):
        ler_planilha(tmp_path / "ruim.xlsx")


def test_triagem():
    assert documento.triar("EDITAL ... SENAD - Secretaria Nacional").bloqueado
    caixa = documento.triar("Depósito judicial na Caixa Econômica Federal")
    assert not caixa.bloqueado and caixa.suspeitas == ("Caixa",)
    dois = documento.triar("EDITAL DE LEILÃO\n...\nEDITAL DE LEILÃO\n...")
    assert dois.bloqueado and "2 editais" in dois.motivo


def test_cruzamento_varias_vistorias_por_processo(tmp_path):
    ext = fabrica.extracao()
    bens, _ = ler_planilha(fabrica.planilha(tmp_path / "p.xlsx"))
    bens, _ = agrupar(bens)
    cruz, gerais = lotes.cruzar(ext.lotes, bens)
    assert [b.vistoria for _, b, _ in cruz] == ["33578", "33579", "33600"]  # 3º sem vistoria: processo tem 1 bem só
    assert gerais == []
    # Sem a IA indicar, processo com 2 bens é ambíguo -> erro só naquele lote
    ambiguo = fabrica._lote(vistoria_planilha=None)
    cruz, _ = lotes.cruzar([ambiguo], bens)
    assert cruz[0][1] is None and "2 vistorias" in cruz[0][2][0].mensagem
    # Mesma vistoria em dois lotes -> o segundo dá erro
    cruz, _ = lotes.cruzar([fabrica._lote(), fabrica._lote(numero_no_edital="9")], bens)
    assert cruz[1][1] is None and "já foi usada" in cruz[1][2][0].mensagem


def test_ordem_dos_lotes():
    a = fabrica._lote(numero_no_edital="A", processo="1", tipo_bem="veiculo")
    b = fabrica._lote(numero_no_edital="B", processo="2", tipo_bem="imovel")
    c = fabrica._lote(numero_no_edital="C", processo="1", tipo_bem="veiculo")
    d = fabrica._lote(numero_no_edital="D", processo="3", tipo_bem="veiculo")
    e = fabrica._lote(numero_no_edital="E", processo="4", tipo_bem="equipamento")
    ordem = lotes.ordenar([(x, x.tipo_bem, v) for x, v in ((a, Decimal(10)), (b, Decimal(1)), (c, Decimal(50)), (d, Decimal(30)), (e, Decimal(999)))])
    # imóvel primeiro; veículos: processo 1 (maior = 50) junto: C, A; depois D; depois demais
    assert [l.numero_no_edital for l in ordem] == ["B", "C", "A", "D", "E"]


def test_valores_e_divergencia(tmp_path):
    bens, _ = agrupar(ler_planilha(fabrica.planilha(tmp_path / "p.xlsx"))[0])
    vals, probs = lotes.valores(fabrica._lote(), bens[0])
    assert vals == {"v1": "40.000,00", "aval": "40.000,00", "v2": "20.000,00"} and probs == []
    vals, probs = lotes.valores(fabrica._lote(avaliacao_edital="41.000,00"), bens[0])
    assert vals["v1"] == "40.000,00" and "diverge" in probs[0].mensagem


def test_titulo_longo_e_imovel_sem_registro():
    probs = lotes.problemas_do_lote(fabrica._lote(titulo="x" * 57))
    assert probs[0].nivel == "erro"
    probs = lotes.problemas_do_lote(fabrica._lote(tipo_bem="imovel", incra=None, cri="1"))
    assert [p.nivel for p in probs] == ["alerta"] and "Incra" in probs[0].mensagem


def test_html_cabecalho_formatacao():
    from leilao_sig.modelos import Bloco
    html = montagem.cabecalho_html(
        "JUSTIÇA ESTADUAL DE X/SP - 1ª VARA", ["1º ENCERRAMENTO DIA 01/12/2026 ÀS 14:00 HORAS"], [],
        [Bloco(tipo="repasse", texto="REPASSE"), Bloco(tipo="parcelamento", texto="PARCELA <5>"),
         Bloco(tipo="participacao", texto="SITE www.alvaroleiloes.com.br.")],
    )
    partes = html.split("<p><br></p>")
    assert partes[0] == "<p><strong>JUSTIÇA ESTADUAL DE X/SP - 1ª VARA</strong></p>"
    assert 'href="https://www.alvaroleiloes.com.br"' in partes[2]  # participação vem antes do parcelamento
    assert "rgb(219, 42, 22)" in partes[3] and "&lt;5&gt;" in partes[3]  # parcelamento vermelho, texto escapado
    assert "rgb(11, 16, 198)" in partes[4]  # repasse azul
    assert "CASO HAJA ALGUMA DIVERGÊNCIA" in partes[-1]


def test_html_lote():
    html = montagem.lote_html(fabrica._lote(parcelamento="(O VEÍCULO PODE SER PARCELADO)", partes_df=["Cartório: X"]), distrito_federal=False)
    assert html.startswith("<p>Fiat/Uno Mille, ano 2010/2010, cor branca, placa ABC-1234 (Proc. 0001234-56.2023.8.12.0001)</p>")
    assert "<strong>(O VEÍCULO PODE SER PARCELADO)</strong>" in html
    assert "Localização do bem: Rua A" in html
    assert "Cartório" not in html  # partes só no DF


def test_vistoria_com_varios_bens_formato_real(tmp_path):
    """Formato da planilha real (sem coluna ID Vistoria): várias linhas com a mesma vistoria
    são um lote só, com valores somados; o mesmo processo pode ter duas vistorias."""
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["BENS DO LEILÃO — JE Salvador/BA"])
    ws.append(["Processo", "Tipo do Bem", "Nº Vistoria", "Avaliação", "Lance Mínimo", "Descrição"])
    ws.append(["0001472-91.2018.8.05.0001", "Veículos", "33731", 30000, 18000, "barco"])
    ws.append(["0001472-91.2018.8.05.0001", "Equipamentos", "13819", 10000, 6000, "mesa 1"])
    ws.append(["0001472-91.2018.8.05.0001", "Equipamentos", "13819", 7770, 4662, "mesa 2"])
    ws.append(["0030527-29.2014.8.05.0001", "Equipamentos", "13820", 1000, 600, "ar 9.000 BTUs quarto"])
    ws.append(["0030527-29.2014.8.05.0001", "Equipamentos", "13820", 1000, 600, "ar 9.000 BTUs quarto"])
    wb.save(tmp_path / "real.xlsx")
    bens, avisos = ler_planilha(tmp_path / "real.xlsx")
    assert len(bens) == 5 and avisos == []
    grupos, avisos = agrupar(bens)
    assert avisos == []
    assert [(g.vistoria, g.tipo, g.aba_sig, str(g.avaliacao), str(g.lance_minimo), len(g.bens)) for g in grupos] == [
        ("33731", "veiculo", "Veículos", "30000.00", "18000.00", 1),
        ("13819", "equipamento", "Equipamentos", "17770.00", "10662.00", 2),
        ("13820", "equipamento", "Equipamentos", "2000.00", "1200.00", 2),
    ]
    # Processo com 2 vistorias: a IA precisa dizer qual é; com a indicação, cruza certo
    l = fabrica._lote(processo="0001472-91.2018.8.05.0001", vistoria_planilha="13819", tipo_bem="equipamento")
    cruz, gerais = lotes.cruzar([l], grupos)
    assert cruz[0][1].vistoria == "13819" and len(gerais) == 2  # as outras duas vistorias ficam como alerta


def test_mesma_vistoria_em_processos_diferentes(tmp_path):
    bens, _ = ler_planilha(fabrica.planilha(tmp_path / "p.xlsx", [
        [fabrica.PROC_A, "Veículo", 7, 1, 10, 5, "a"], [fabrica.PROC_B, "Imóvel", 7, 1, 10, 5, "b"],
    ]))
    _, avisos = agrupar(bens)
    assert "processos diferentes" in avisos[0]
