"""Registro local do que já foi gravado no SIG (anti-duplicidade).

Toda gravação é feita em duas fases:
  1. `gravando`  — marcado ANTES de clicar em Salvar;
  2. `confirmado` — depois de conferir no SIG que salvou (com o ID).
Se o app cair no meio, sobra um `gravando`: o app não regrava às cegas, pede para verificar
no SIG (o usuário confirma ou descarta pela tela).
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from leilao_sig import config

GRAVANDO, CONFIRMADO = "gravando", "confirmado"

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS leiloes (
    chave TEXT PRIMARY KEY, titulo TEXT, site TEXT, dt1 TEXT, dt2 TEXT, editais TEXT,
    sig_id TEXT, status TEXT NOT NULL, atualizado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ciclos (
    chave_leilao TEXT NOT NULL, data TEXT NOT NULL, hora TEXT, status TEXT NOT NULL, atualizado TEXT NOT NULL,
    PRIMARY KEY (chave_leilao, data)
);
CREATE TABLE IF NOT EXISTS lotes (
    chave_leilao TEXT NOT NULL, processo TEXT NOT NULL, vistoria TEXT NOT NULL, titulo TEXT,
    sig_lote TEXT, status TEXT NOT NULL, atualizado TEXT NOT NULL,
    PRIMARY KEY (chave_leilao, processo, vistoria)
);
"""


def chave_leilao(site: str, titulo: str, dt1: str, h1: str, dt2: str, h2: str) -> str:
    base = "|".join(x.strip().upper() for x in (site, titulo, dt1, h1, dt2, h2))
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:20]


@dataclass
class LeilaoRegistrado:
    chave: str
    titulo: str
    sig_id: str | None
    status: str
    atualizado: str


class Registro:
    def __init__(self, caminho: Path | None = None):
        self.caminho = caminho or (config.pasta_dados() / "registro.sqlite")
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._con()) as con:
            con.executescript(_ESQUEMA)

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.caminho, timeout=10)
        con.row_factory = sqlite3.Row
        return con

    def _exec(self, sql: str, params: tuple) -> None:
        with closing(self._con()) as con, con:
            con.execute(sql, params)

    @staticmethod
    def _agora() -> str:
        return datetime.now().isoformat(timespec="seconds")

    # ---- leilão (cabeçalho) ----
    def leilao(self, chave: str) -> LeilaoRegistrado | None:
        with closing(self._con()) as con:
            r = con.execute("SELECT chave, titulo, sig_id, status, atualizado FROM leiloes WHERE chave=?", (chave,)).fetchone()
        return LeilaoRegistrado(**dict(r)) if r else None

    def leilao_gravando(self, chave: str, titulo: str, site: str, dt1: str, dt2: str, editais: list[str]) -> None:
        self._exec(
            "INSERT INTO leiloes (chave, titulo, site, dt1, dt2, editais, sig_id, status, atualizado) "
            "VALUES (?,?,?,?,?,?,NULL,?,?) ON CONFLICT(chave) DO UPDATE SET status=excluded.status, atualizado=excluded.atualizado",
            (chave, titulo, site, dt1, dt2, "; ".join(editais), GRAVANDO, self._agora()),
        )

    def leilao_confirmado(self, chave: str, sig_id: str) -> None:
        self._exec("UPDATE leiloes SET sig_id=?, status=?, atualizado=? WHERE chave=?", (sig_id, CONFIRMADO, self._agora(), chave))

    def descartar_leilao(self, chave: str) -> None:
        """Usado quando o usuário verificou no SIG que um `gravando` não chegou a ser salvo."""
        with closing(self._con()) as con, con:
            for tabela, coluna in (("lotes", "chave_leilao"), ("ciclos", "chave_leilao"), ("leiloes", "chave")):
                con.execute(f"DELETE FROM {tabela} WHERE {coluna}=?", (chave,))

    # ---- ciclos (aba Datas) ----
    def ciclos(self, chave: str) -> dict[str, str]:
        with closing(self._con()) as con:
            return {r["data"]: r["status"] for r in con.execute("SELECT data, status FROM ciclos WHERE chave_leilao=?", (chave,))}

    def ciclo(self, chave: str, data: str, hora: str, status: str) -> None:
        self._exec(
            "INSERT INTO ciclos (chave_leilao, data, hora, status, atualizado) VALUES (?,?,?,?,?) "
            "ON CONFLICT(chave_leilao, data) DO UPDATE SET status=excluded.status, hora=excluded.hora, atualizado=excluded.atualizado",
            (chave, data, hora, status, self._agora()),
        )

    # ---- lotes (Fase 3) ----
    def lotes(self, chave: str) -> dict[tuple[str, str], str]:
        with closing(self._con()) as con:
            return {(r["processo"], r["vistoria"]): r["status"]
                    for r in con.execute("SELECT processo, vistoria, status FROM lotes WHERE chave_leilao=?", (chave,))}

    def lote(self, chave: str, processo: str, vistoria: str, titulo: str, status: str, sig_lote: str | None = None) -> None:
        self._exec(
            "INSERT INTO lotes (chave_leilao, processo, vistoria, titulo, sig_lote, status, atualizado) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(chave_leilao, processo, vistoria) DO UPDATE SET status=excluded.status, "
            "sig_lote=COALESCE(excluded.sig_lote, lotes.sig_lote), atualizado=excluded.atualizado",
            (chave, processo, vistoria, titulo, sig_lote, status, self._agora()),
        )
