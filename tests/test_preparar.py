from datetime import date

from leilao_sig.execucao import Execucao
from leilao_sig.preparar import preparar
from tests import fabrica

HOJE = date(2026, 11, 6)


def _rodar(tmp_path, ext, texto_edital=None, n_editais=1):
    eds = [fabrica.edital(tmp_path / ("edital.docx" if i == 0 else f"edital{i + 1}.docx"), *([texto_edital] if texto_edital else []))
           for i in range(n_editais)]
    ed = eds if n_editais > 1 else eds[0]
    pl = fabrica.planilha(tmp_path / "bens.xlsx")
    chamadas = []

    def falso(editais, bens, suspeitas):
        chamadas.append((editais, bens, suspeitas))
        return ext, {"entrada": 0, "saida": 0}

    with Execucao(tmp_path / "exec") as ex:
        prep = preparar(ed, pl, extrator=falso, hoje=HOJE, execucao=ex)
    return prep, chamadas, ex


def test_fluxo_completo(tmp_path):
    prep, chamadas, ex = _rodar(tmp_path, fabrica.extracao())
    assert not prep.bloqueado, prep.problemas
    c = prep.cabecalho
    assert (c.site, c.fuso, c.dt1, c.h1, c.dt2, c.h2) == ("alvaroleiloes", "-1", "20/11/2026", "14:00", "04/12/2026", "14:00")
    assert "VENDA DIRETA:<br>1º E 2º CICLO DIA 04/01/2027" in c.html
    assert "0800 500 9913" in c.html and "{0800}" not in c.html
    # imóvel primeiro, depois veículos do mesmo processo do maior para o menor
    assert [(l.ordem, l.numero_no_edital, l.vistoria) for l in prep.lotes] == [(1, "3", "33600"), (2, "1", "33578"), (3, "2", "33579")]
    assert all(l.pode_gravar for l in prep.lotes)
    assert prep.lotes[0].v2 == "150.000,00"
    assert (ex.pasta / "resposta_ia.json").exists() and (ex.pasta / "preparacao.json").exists()
    assert "1 edital(is)" in (ex.pasta / "execucao.log").read_text(encoding="utf-8")


def test_joyce_sem_venda_direta(tmp_path):
    ext = fabrica.extracao(leiloeiro_nome="Joyce Ribeiro", leiloeiro_site="www.jrleiloes.com.br",
                           editais=[fabrica.info_edital(leiloeiro_nome="Joyce Ribeiro")])
    prep, _, _ = _rodar(tmp_path, ext)
    assert not prep.bloqueado
    assert prep.cabecalho.ciclos == [] and "VENDA DIRETA" not in prep.cabecalho.html
    assert any("regra do leiloeiro" in p.mensagem for p in prep.problemas)


def test_leiloeiro_desconhecido_bloqueia(tmp_path):
    prep, _, _ = _rodar(tmp_path, fabrica.extracao(leiloeiro_nome="Fulano", leiloeiro_site="www.fulano.com.br"))
    assert prep.bloqueado and prep.cabecalho is None
    assert "Leiloeiro desconhecido" in prep.problemas[-1].mensagem


def test_edital_fora_do_padrao_pela_ia(tmp_path):
    ext = fabrica.extracao(editais=[fabrica.info_edital(tipo_edital="caixa", motivo_tipo_edital="Venda de imóveis da Caixa")])
    prep, _, _ = _rodar(tmp_path, ext)
    assert prep.bloqueado and "fora do padrão" in prep.problemas[-1].mensagem


def test_senad_bloqueia_sem_chamar_ia(tmp_path):
    prep, chamadas, _ = _rodar(tmp_path, fabrica.extracao(), texto_edital="EDITAL SENAD\nleilão")
    assert prep.bloqueado and chamadas == []


def test_data_passada_bloqueia(tmp_path):
    from leilao_sig.modelos import Pregao
    ext = fabrica.extracao(leilao_1=fabrica.pregao("01/10/2026"),
                           editais=[fabrica.info_edital(leilao_1=fabrica.pregao("01/10/2026"))])
    prep, _, _ = _rodar(tmp_path, ext)
    assert prep.bloqueado and "já passou" in prep.problemas[-1].mensagem


def test_encerramento_por_duracao(tmp_path):
    from leilao_sig.modelos import Pregao
    p1 = Pregao(data_inicio="20/11/2026", hora_inicio="13h", data_encerramento=None,
                hora_encerramento=None, duracao_minutos=60, trecho_edital="x")
    ext = fabrica.extracao(leilao_1=p1, editais=[fabrica.info_edital(leilao_1=p1)])
    prep, _, _ = _rodar(tmp_path, ext)
    assert not prep.bloqueado
    assert prep.cabecalho.h1 == "14:00"
    assert "1º LEILÃO (INÍCIO): 20/11/2026 A PARTIR DAS 13:00 HORAS | 1º ENCERRAMENTO: 20/11/2026 ÀS 14:00 HORAS" in prep.cabecalho.html


def test_erro_num_lote_nao_bloqueia_os_outros(tmp_path):
    ext = fabrica.extracao()
    ext.lotes[1].vistoria_planilha = "99999"
    prep, _, _ = _rodar(tmp_path, ext)
    assert not prep.bloqueado
    ruins = [l for l in prep.lotes if not l.pode_gravar]
    assert [l.numero_no_edital for l in ruins] == ["2"]
    assert any("33579" in p.mensagem for p in prep.problemas)  # vistoria da planilha que sobrou


def test_sessao_com_dois_editais(tmp_path):
    ext = fabrica.extracao(editais=[fabrica.info_edital("edital.docx", processos=[fabrica.PROC_A]),
                                    fabrica.info_edital("edital2.docx", vara="2ª Vara", processos=[fabrica.PROC_B])])
    ext.lotes[2].arquivo_edital = "edital2.docx"
    prep, chamadas, _ = _rodar(tmp_path, ext, n_editais=2)
    assert not prep.bloqueado, prep.problemas
    assert [n for n, _ in chamadas[0][0]] == ["edital.docx", "edital2.docx"]  # uma chamada com os dois
    assert len(prep.editais) == 2 and prep.lotes[0].arquivo_edital == "edital2.docx"
    # varas diferentes: todas no título, sem repetir
    assert prep.cabecalho.titulo == "JUSTIÇA ESTADUAL DE CAMPO GRANDE/MS - 1ª VARA CÍVEL / 2ª VARA"
    assert prep.cabecalho.html.startswith("<p><strong>JUSTIÇA ESTADUAL DE CAMPO GRANDE/MS - 1ª VARA CÍVEL / 2ª VARA</strong>")


def test_titulo_mesma_vara_nao_repete():
    from leilao_sig.preparar import titulo_leilao
    ext = fabrica.extracao(editais=[fabrica.info_edital("a.pdf", vara="1ª Vara Cível"), fabrica.info_edital("b.pdf", vara="1ª VARA CIVEL")])
    assert titulo_leilao(ext) == "JUSTIÇA ESTADUAL DE CAMPO GRANDE/MS - 1ª VARA CÍVEL"


def test_sessao_com_datas_diferentes_bloqueia(tmp_path):
    ext = fabrica.extracao(editais=[fabrica.info_edital("edital.docx"),
                                    fabrica.info_edital("edital2.docx", leilao_2=fabrica.pregao("05/12/2026"))])
    prep, _, _ = _rodar(tmp_path, ext, n_editais=2)
    assert prep.bloqueado and "edital2.docx: encerramentos" in prep.problemas[-1].mensagem


def test_sessao_com_venda_direta_diferente_bloqueia(tmp_path):
    ext = fabrica.extracao(editais=[fabrica.info_edital("edital.docx"), fabrica.info_edital("edital2.docx", venda_direta=None)])
    prep, _, _ = _rodar(tmp_path, ext, n_editais=2)
    assert prep.bloqueado and "venda direta" in prep.problemas[-1].mensagem


def test_ia_esqueceu_um_edital_bloqueia(tmp_path):
    prep, _, _ = _rodar(tmp_path, fabrica.extracao(), n_editais=2)
    assert prep.bloqueado and "edital2.docx" in prep.problemas[-1].mensagem
