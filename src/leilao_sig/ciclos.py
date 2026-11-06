"""Ciclos da venda direta, recesso, horário dos ciclos e fuso.

Regras de references/datas-horarios.md da skill cadastrar-leilao-sig-completo, em código:
- nº de ciclos = prazo total ÷ duração;
- 1º ciclo nominal = data do 2º leilão + duração; cada seguinte = nominal anterior + duração
  (os ajustes não empurram os próximos);
- sábado, domingo ou feriado -> próximo dia útil;
- data já ajustada caindo no recesso -> data da tabela oficial (com frase de aviso);
- dois ciclos no mesmo dia -> uma linha só ("1º E 2º CICLO").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from leilao_sig import config
from leilao_sig.util import fmt_data

FUSO_POR_UF = {"MS": "-1", "MT": "-1", "RO": "-1", "AM": "-1", "RR": "-1", "AC": "-2"}


class CalendarioDesatualizado(Exception):
    """Algum ciclo cai depois do período coberto pelo calendário de feriados/recesso."""


@dataclass
class Ciclo:
    numeros: list[int]  # [1] ou [1, 2] quando dois ciclos caem no mesmo dia
    data: date
    hora: str
    nominal: date
    prorrogado_de: date | None = None  # data da tabela de recesso que foi substituída
    ajustes: list[str] = field(default_factory=list)

    @property
    def rotulo(self) -> str:
        return " E ".join(f"{n}º" for n in self.numeros) + " CICLO"


def fuso(uf: str, municipio: str = "") -> str:
    if (municipio or "").strip().lower() == "fernando de noronha":
        return "+1"
    return FUSO_POR_UF.get((uf or "").strip().upper(), "0")


def dia_util(d: date, feriados: frozenset) -> bool:
    return d.weekday() < 5 and d not in feriados


def proximo_dia_util(d: date, feriados: frozenset) -> date:
    while not dia_util(d, feriados):
        d += timedelta(days=1)
    return d


def calcular_ciclos(data_2o_leilao: date, prazo_dias: int, duracao_dias: int, hora: str) -> list[Ciclo]:
    if duracao_dias <= 0 or prazo_dias <= 0:
        return []
    if prazo_dias % duracao_dias:
        raise ValueError(f"Prazo da venda direta ({prazo_dias}) não é múltiplo da duração ({duracao_dias}).")
    cal = config.calendario()
    n = prazo_dias // duracao_dias
    ciclos: list[Ciclo] = []
    for i in range(1, n + 1):
        nominal = data_2o_leilao + timedelta(days=duracao_dias * i)
        ajustes = []
        d = proximo_dia_util(nominal, cal.feriados)
        if d != nominal:
            ajustes.append(f"{fmt_data(nominal)} não é dia útil → {fmt_data(d)}")
        prorrogado_de = None
        if d in cal.recesso:
            prorrogado_de, d = d, cal.recesso[d]
            ajustes.append(f"recesso: {fmt_data(prorrogado_de)} → {fmt_data(d)}")
        if d > cal.cobertura_ate:
            raise CalendarioDesatualizado(
                f"O {i}º ciclo cai em {fmt_data(d)}, depois do calendário configurado "
                f"(até {fmt_data(cal.cobertura_ate)}). Atualize config/calendario.json (feriados e recesso)."
            )
        if ciclos and ciclos[-1].data == d:
            ciclos[-1].numeros.append(i)
            ciclos[-1].ajustes.extend(ajustes)
            continue
        ciclos.append(Ciclo([i], d, hora, nominal, prorrogado_de, ajustes))
    return ciclos


def linhas_venda_direta(ciclos: list[Ciclo]) -> list[str]:
    """Linhas do bloco VENDA DIRETA do cabeçalho, com as frases de recesso logo depois."""
    linhas = [f"{c.rotulo} DIA {fmt_data(c.data)} C/ ENCERRAMENTO ÀS {c.hora} HORAS" for c in ciclos]
    for c in ciclos:
        if c.prorrogado_de:
            linhas.append(
                f"ATENÇÃO! POR CONTA DO RECESSO, O CICLO DESIGNADO PARA O DIA {fmt_data(c.prorrogado_de)} "
                f"FOI PRORROGADO PARA ENCERRAR NO DIA {fmt_data(c.data)}."
            )
    return linhas
