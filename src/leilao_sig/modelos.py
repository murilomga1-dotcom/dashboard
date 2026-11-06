"""Formato da resposta da IA (saída estruturada, validada pelo SDK) e do resultado preparado.

A IA só extrai fatos e redige textos. Datas de ciclos, fuso, ordem, valores e HTML são
calculados pelo código a partir daqui.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict

TipoEdital = Literal[
    "judicial_comum", "senad", "caixa", "alienacoes_ms", "giordano",
    "diario_oficial_varios_editais", "escaneado_ilegivel", "outro",
]

TipoBloco = Literal[
    "participacao", "direito_preferencia", "valor_minimo", "excecao_lote", "parcelamento",
    "avista_parcelado", "veiculos_parcelados", "lote_unificado", "repasse", "escalonamento",
    "tipo_bem", "atualizacao_avaliacao", "comissao", "cronometro", "tribunal",
]

# Ordem dos blocos no cabeçalho (references/cabecalho-frases.md). Título, datas e venda direta
# são montados pelo código antes destes; a frase "CASO HAJA ALGUMA DIVERGÊNCIA..." vai sempre no fim.
ORDEM_BLOCOS: tuple[str, ...] = get_args(TipoBloco)


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Pregao(_Base):
    data_inicio: str | None  # dd/mm/aaaa
    hora_inicio: str | None  # HH:MM
    data_encerramento: str | None
    hora_encerramento: str | None
    duracao_minutos: int | None  # quando o edital diz "inicia às X, aberto por N minutos"
    trecho_edital: str


class VendaDireta(_Base):
    prazo_dias: int
    duracao_ciclo_dias: int
    horario_fixado_no_edital: str | None  # HH:MM, só se o edital fixar o horário dos ciclos
    trecho_edital: str


class Bloco(_Base):
    tipo: TipoBloco
    texto: str  # MAIÚSCULAS, texto puro; parágrafos internos separados por \n


class LoteIA(_Base):
    numero_no_edital: str
    processo: str
    vistoria_planilha: str | None  # Nº Vistoria da linha da planilha que corresponde a este bem
    tipo_bem: Literal["imovel", "veiculo", "equipamento", "outro"]
    titulo: str
    resumo: str
    parcelamento: str | None
    obs: str | None
    frases: list[str]
    localizacao: str | None
    partes_df: list[str]
    incra: str | None
    cri: str | None
    chave_vistoria: str  # placa ou palavra do bem, para escolher a vistoria no SIG ('' = sem filtro)
    cidade_uf_bem: str | None
    avaliacao_edital: str | None
    lance_2o_leilao_edital: str | None
    percentual_2o_leilao: str | None
    trecho_edital: str


class ExtracaoEdital(_Base):
    tipo_edital: TipoEdital
    motivo_tipo_edital: str
    titulo_leilao: str  # JUSTIÇA ESTADUAL DE CIDADE/UF - VARA
    comarca_cidade: str
    uf: str
    distrito_federal: bool
    leiloeiro_nome: str
    leiloeiro_site: str  # www.exemplo.com.br
    telefone_0800_edital: str | None
    leilao_1: Pregao
    leilao_2: Pregao
    venda_direta: VendaDireta | None
    blocos_cabecalho: list[Bloco]
    lotes: list[LoteIA]
    alertas: list[str]


# ---- Resultado preparado (o que vai para a tela de revisão e, depois, para o SIG) ----


@dataclass
class Problema:
    """Algo que impede (erro) ou merece atenção (alerta)."""

    nivel: Literal["erro", "alerta"]
    mensagem: str
    processo: str = ""
    lote: str = ""
    trecho: str = ""


@dataclass
class LotePreparado:
    ordem: int
    numero_no_edital: str
    processo: str
    vistoria: str
    chave_vistoria: str
    tipo_bem: str
    aba_sig: str  # aba do modal "Selecione a vistoria": Imóveis / Veículos / Equipamentos
    titulo: str
    html: str
    v1: str  # Inicial 1º leilão (= avaliação)
    aval: str  # Mínimo / Avaliação 2º leilão (= avaliação)
    v2: str  # Inicial 2º leilão (= lance mínimo)
    trecho_edital: str
    problemas: list[Problema] = field(default_factory=list)

    @property
    def pode_gravar(self) -> bool:
        return not any(p.nivel == "erro" for p in self.problemas)


@dataclass
class CabecalhoPreparado:
    site: str
    titulo: str
    fuso: str
    dt1: str
    h1: str
    dt2: str
    h2: str
    html: str
    ciclos: list = field(default_factory=list)  # list[ciclos.Ciclo]
    leiloeiro: str = ""
    venda_direta_cadastrada: bool = False


@dataclass
class Preparacao:
    edital: str
    planilha: str
    cabecalho: CabecalhoPreparado | None
    lotes: list[LotePreparado]
    problemas: list[Problema]  # gerais (cabeçalho, datas, leiloeiro, triagem)
    extracao: ExtracaoEdital | None = None

    @property
    def bloqueado(self) -> bool:
        """Erro no cabeçalho/datas/triagem: nada pode ser gravado."""
        return self.cabecalho is None or any(p.nivel == "erro" for p in self.problemas)
