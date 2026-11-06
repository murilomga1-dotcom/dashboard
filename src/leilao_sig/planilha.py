"""Leitura da planilha "Bens do Leilão"."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from leilao_sig.util import parse_valor, sem_acento, so_digitos

# nome interno -> grafias aceitas no cabeçalho (comparadas sem acento/maiúsculas)
COLUNAS = {
    "processo": ["processo", "n processo", "nº processo", "numero do processo"],
    "tipo": ["tipo do bem", "tipo"],
    "vistoria": ["nº vistoria", "n vistoria", "numero vistoria", "no vistoria", "vistoria"],
    "id_vistoria": ["id vistoria", "id da vistoria"],
    "avaliacao": ["avaliacao", "valor da avaliacao", "avaliacao r$"],
    "lance_minimo": ["lance minimo", "lance minimo r$", "valor minimo"],
    "descricao": ["descricao", "descricao do bem"],
}
OBRIGATORIAS = ("processo", "vistoria", "avaliacao", "lance_minimo", "descricao")


class PlanilhaInvalida(Exception):
    pass


@dataclass(frozen=True)
class Bem:
    linha: int  # linha na planilha (para o relatório)
    processo: str  # como veio
    processo_digitos: str
    tipo: str
    vistoria: str
    id_vistoria: str
    avaliacao: Decimal | None
    lance_minimo: Decimal | None
    descricao: str

    @property
    def chave(self) -> tuple[str, str]:
        return (self.processo_digitos, self.vistoria)


def normalizar_processo(p: object) -> str:
    """Só os dígitos: '0001234-56.2023.8.12.0001' e '00012345620238120001' viram iguais."""
    return so_digitos(p)


def normalizar_vistoria(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def ler_planilha(caminho: str | Path) -> tuple[list[Bem], list[str]]:
    """Devolve (bens com vistoria preenchida, avisos)."""
    caminho = Path(caminho)
    linhas = _linhas(caminho)
    idx_cab, mapa = _achar_cabecalho(linhas)
    avisos: list[str] = []
    bens: list[Bem] = []
    for n, linha in enumerate(linhas[idx_cab + 1:], start=idx_cab + 2):
        def col(nome: str):
            i = mapa.get(nome)
            return linha[i] if i is not None and i < len(linha) else None

        if not any(c not in (None, "") for c in linha):
            continue
        vistoria = normalizar_vistoria(col("vistoria"))
        if not vistoria:
            continue  # regra: só entram as linhas com vistoria preenchida
        processo = str(col("processo") or "").strip()
        if not processo:
            avisos.append(f"Linha {n}: vistoria {vistoria} sem número de processo — ignorada.")
            continue
        aval, minimo = parse_valor(col("avaliacao")), parse_valor(col("lance_minimo"))
        if aval is None:
            avisos.append(f"Linha {n}: vistoria {vistoria} sem avaliação.")
        if minimo is None:
            avisos.append(f"Linha {n}: vistoria {vistoria} sem lance mínimo.")
        bens.append(Bem(
            linha=n,
            processo=processo,
            processo_digitos=normalizar_processo(processo),
            tipo=str(col("tipo") or "").strip(),
            vistoria=vistoria,
            id_vistoria=normalizar_vistoria(col("id_vistoria")),
            avaliacao=aval,
            lance_minimo=minimo,
            descricao=str(col("descricao") or "").strip(),
        ))
    vistos: dict[tuple, int] = {}
    for b in bens:
        if b.chave in vistos:
            avisos.append(
                f"Linha {b.linha}: processo {b.processo} + vistoria {b.vistoria} repetidos (já na linha {vistos[b.chave]})."
            )
        vistos.setdefault(b.chave, b.linha)
    if not bens:
        avisos.append("Nenhuma linha com Nº Vistoria preenchido.")
    return bens, avisos


def _linhas(caminho: Path) -> list[list]:
    ext = caminho.suffix.lower()
    if ext in (".xlsx", ".xlsm"):
        import openpyxl

        wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
        try:
            ws = wb.active
            return [list(r) for r in ws.iter_rows(values_only=True)]
        finally:
            wb.close()
    if ext == ".csv":
        texto = caminho.read_text(encoding="utf-8-sig")
        dialeto = csv.Sniffer().sniff(texto[:2000], delimiters=";,\t")
        return [list(r) for r in csv.reader(texto.splitlines(), dialeto)]
    raise PlanilhaInvalida(f"Formato de planilha não suportado: {ext} (use .xlsx ou .csv)")


def _achar_cabecalho(linhas: list[list]) -> tuple[int, dict[str, int]]:
    for i, linha in enumerate(linhas[:20]):
        nomes = [sem_acento(str(c or "")).replace(".", "").strip() for c in linha]
        mapa: dict[str, int] = {}
        # "id vistoria" precisa ser resolvido antes de "vistoria" para não ser confundido
        for chave in ("id_vistoria", *[k for k in COLUNAS if k != "id_vistoria"]):
            aceitas = [sem_acento(a).replace(".", "") for a in COLUNAS[chave]]
            for j, n in enumerate(nomes):
                if j not in mapa.values() and n in aceitas:
                    mapa[chave] = j
                    break
        if all(k in mapa for k in OBRIGATORIAS):
            return i, mapa
    raise PlanilhaInvalida(
        "Cabeçalho da planilha não encontrado. Colunas esperadas: Processo, Tipo do Bem, "
        "Nº Vistoria, ID Vistoria, Avaliação, Lance Mínimo, Descrição."
    )
