from datetime import date

from leilao_sig.execucao import Execucao
from leilao_sig.preparar import preparar
from tests import fabrica

HOJE = date(2026, 11, 6)


def _rodar(tmp_path, ext, texto_edital=None):
    ed = fabrica.edital(tmp_path / "edital.docx", *( [texto_edital] if texto_edital else []))
    pl = fabrica.planilha(tmp_path / "bens.xlsx")
    chamadas = []

    def falso(texto, bens, suspeitas):
        chamadas.append((texto, bens, suspeitas))
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
    assert "Edital" in (ex.pasta / "execucao.log").read_text(encoding="utf-8")


def test_joyce_sem_venda_direta(tmp_path):
    prep, _, _ = _rodar(tmp_path, fabrica.extracao(leiloeiro_nome="Joyce Ribeiro", leiloeiro_site="www.jrleiloes.com.br"))
    assert not prep.bloqueado
    assert prep.cabecalho.ciclos == [] and "VENDA DIRETA" not in prep.cabecalho.html
    assert any("regra do leiloeiro" in p.mensagem for p in prep.problemas)


def test_leiloeiro_desconhecido_bloqueia(tmp_path):
    prep, _, _ = _rodar(tmp_path, fabrica.extracao(leiloeiro_nome="Fulano", leiloeiro_site="www.fulano.com.br"))
    assert prep.bloqueado and prep.cabecalho is None
    assert "Leiloeiro desconhecido" in prep.problemas[-1].mensagem


def test_edital_fora_do_padrao_pela_ia(tmp_path):
    prep, _, _ = _rodar(tmp_path, fabrica.extracao(tipo_edital="caixa", motivo_tipo_edital="Venda de imóveis da Caixa"))
    assert prep.bloqueado and "fora do padrão" in prep.problemas[-1].mensagem


def test_senad_bloqueia_sem_chamar_ia(tmp_path):
    prep, chamadas, _ = _rodar(tmp_path, fabrica.extracao(), texto_edital="EDITAL SENAD\nleilão")
    assert prep.bloqueado and chamadas == []


def test_data_passada_bloqueia(tmp_path):
    from leilao_sig.modelos import Pregao
    ext = fabrica.extracao(leilao_1=Pregao(data_inicio=None, hora_inicio=None, data_encerramento="01/10/2026",
                                           hora_encerramento="14:00", duracao_minutos=None, trecho_edital="x"))
    prep, _, _ = _rodar(tmp_path, ext)
    assert prep.bloqueado and "já passou" in prep.problemas[-1].mensagem


def test_encerramento_por_duracao(tmp_path):
    from leilao_sig.modelos import Pregao
    ext = fabrica.extracao(leilao_1=Pregao(data_inicio="20/11/2026", hora_inicio="13h", data_encerramento=None,
                                           hora_encerramento=None, duracao_minutos=60, trecho_edital="x"))
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
