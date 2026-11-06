"""Dados de teste: planilha .xlsx, edital .docx e uma resposta de IA falsa."""

from pathlib import Path

import docx
import openpyxl

from leilao_sig.modelos import Bloco, ExtracaoEdital, LoteIA, Pregao, VendaDireta

PROC_A = "0001234-56.2023.8.12.0001"
PROC_B = "7002054-21.2020.8.22.0003"


def planilha(caminho: Path, linhas=None) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Bens do Leilão"])
    ws.append([])
    ws.append(["Processo", "Tipo do Bem", "Nº Vistoria", "ID Vistoria", "Avaliação", "Lance Mínimo", "Descrição"])
    for l in linhas if linhas is not None else [
        [PROC_A, "Veículo", 33578, 9001, 40000, 20000, "Fiat Uno 2010 placa ABC-1234"],
        [PROC_A, "Veículo", 33579.0, 9002, "R$ 25.000,00", "12.500,00", "Honda CG 160 placa XYZ-9876"],
        ["70020542120208220003", "Imóvel", "33600", 9003, 300000, 150000, "Lote rural 50,0287ha"],
        [PROC_B, "Imóvel", None, None, 1, 1, "Sem vistoria: deve ser ignorado"],
    ]:
        ws.append(l)
    wb.save(caminho)
    return caminho


def edital(caminho: Path, texto: str = "EDITAL DE LEILÃO\nJuízo da 1ª Vara Cível de Campo Grande/MS\nLeiloeiro Álvaro Sérgio Fuzo") -> Path:
    d = docx.Document()
    for linha in texto.splitlines():
        d.add_paragraph(linha)
    d.save(caminho)
    return caminho


def _lote(**kw) -> LoteIA:
    base = dict(
        numero_no_edital="1", processo=PROC_A, vistoria_planilha="33578", tipo_bem="veiculo",
        titulo="Fiat/Uno Mille - 10/10 - Campo Grande/MS",
        resumo="Fiat/Uno Mille, ano 2010/2010, cor branca, placa ABC-1234",
        parcelamento=None, obs=None, frases=[], localizacao="Rua A, 100, Campo Grande/MS",
        partes_df=[], incra=None, cri=None, chave_vistoria="ABC-1234", cidade_uf_bem="Campo Grande/MS",
        avaliacao_edital="40.000,00", lance_2o_leilao_edital="20.000,00", percentual_2o_leilao="50%",
        trecho_edital="LOTE 1: Fiat Uno",
    )
    base.update(kw)
    return LoteIA(**base)


def extracao(**kw) -> ExtracaoEdital:
    base = dict(
        tipo_edital="judicial_comum", motivo_tipo_edital="Edital judicial comum",
        titulo_leilao="JUSTIÇA ESTADUAL DE CAMPO GRANDE/MS - 1ª VARA CÍVEL",
        comarca_cidade="Campo Grande", uf="MS", distrito_federal=False,
        leiloeiro_nome="Álvaro Sérgio Fuzo", leiloeiro_site="www.alvaroleiloes.com.br", telefone_0800_edital=None,
        leilao_1=Pregao(data_inicio=None, hora_inicio=None, data_encerramento="20/11/2026", hora_encerramento="14:00", duracao_minutos=None, trecho_edital="1º leilão 20/11/2026"),
        leilao_2=Pregao(data_inicio=None, hora_inicio=None, data_encerramento="04/12/2026", hora_encerramento="14:00", duracao_minutos=None, trecho_edital="2º leilão 04/12/2026"),
        venda_direta=VendaDireta(prazo_dias=60, duracao_ciclo_dias=15, horario_fixado_no_edital=None, trecho_edital="venda direta 60 dias"),
        blocos_cabecalho=[
            Bloco(tipo="repasse", texto="OS BENS NÃO ARREMATADOS, SERÃO DISPONIBILIZADOS NOVAMENTE EM REPASSE."),
            Bloco(tipo="participacao", texto="PARA PARTICIPAÇÃO ... NO SITE www.alvaroleiloes.com.br. ORIENTAMOS ..."),
            Bloco(tipo="tipo_bem", texto="RURAL: LIGUE {0800}"),
        ],
        lotes=[
            _lote(),
            _lote(numero_no_edital="2", vistoria_planilha="33579", titulo="Honda/CG 160 - 20/20 - Campo Grande/MS",
                  resumo="Honda CG 160, placa XYZ-9876", chave_vistoria="XYZ-9876",
                  avaliacao_edital="25.000,00", lance_2o_leilao_edital="12.500,00"),
            _lote(numero_no_edital="3", processo=PROC_B, vistoria_planilha=None, tipo_bem="imovel",
                  titulo="Lote rural 50,0287ha - Gov. Jorge Teixeira/RO",
                  resumo="Lote rural nº 95, com área de 50,0287ha, Imóvel com Incra n.º 950.173.986.798-5 e CRI n.º 24.350, Jaru/RO (Proc. 7002054-21.2020.8.22.0003)",
                  localizacao=None, incra="950.173.986.798-5", cri="24.350", chave_vistoria="",
                  avaliacao_edital="300.000,00", lance_2o_leilao_edital="150.000,00"),
        ],
        alertas=[],
    )
    base.update(kw)
    return ExtracaoEdital(**base)
