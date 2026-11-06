"""Leitura dos arquivos de configuração (pasta config/)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from leilao_sig.util import parse_data, sem_acento

PACOTE = Path(__file__).resolve().parent
PASTA_CONFIG = PACOTE / "config"
PASTA_PROMPTS = PACOTE / "prompts"
PASTA_SCRIPTS_SIG = PACOTE / "sig_scripts"


def _ler(nome: str) -> dict:
    # Permite sobrescrever a config sem recompilar o .exe: <pasta_dados>/config/<nome>
    externo = pasta_dados() / "config" / nome
    caminho = externo if externo.exists() else PASTA_CONFIG / nome
    return json.loads(caminho.read_text(encoding="utf-8"))


@lru_cache
def app() -> dict:
    return json.loads((PASTA_CONFIG / "app.json").read_text(encoding="utf-8"))


def pasta_dados() -> Path:
    bruto = json.loads((PASTA_CONFIG / "app.json").read_text(encoding="utf-8"))["pasta_dados"]
    if "%LOCALAPPDATA%" in bruto:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
        bruto = bruto.replace("%LOCALAPPDATA%", base)
    return Path(bruto)


@dataclass(frozen=True)
class Leiloeiro:
    nome: str
    apelidos: tuple[str, ...]
    site: str
    telefone_0800: str
    horario_ciclos: str
    venda_direta: bool


@lru_cache
def leiloeiros() -> tuple[Leiloeiro, ...]:
    dados = _ler("leiloeiros.json")["leiloeiros"]
    return tuple(
        Leiloeiro(
            nome=d["nome"],
            apelidos=tuple(d.get("apelidos", [])),
            site=d.get("site", ""),
            telefone_0800=d.get("telefone_0800", ""),
            horario_ciclos=d.get("horario_ciclos", "16:00"),
            venda_direta=bool(d.get("venda_direta", True)),
        )
        for d in dados
    )


def achar_leiloeiro(nome: str, site: str = "") -> Leiloeiro | None:
    """Procura pelo nome (ou apelido) e, se não achar, pelo site. Sem acento/maiúsculas."""
    alvo = sem_acento(nome).strip()
    site_alvo = sem_acento(site).replace("www.", "").split(".")[0].strip()
    if alvo:
        # Ganha o nome/apelido mais longo contido no texto ("Aparecida Maria Fixer" não pode
        # cair em "Maria Fixer", que é apelido de outra leiloeira).
        melhor, tam = None, 0
        for l in leiloeiros():
            for n in (sem_acento(x) for x in (l.nome, *l.apelidos)):
                if n and n in alvo and len(n) > tam:
                    melhor, tam = l, len(n)
        if melhor:
            return melhor
    if site_alvo:
        for l in leiloeiros():
            if l.site and sem_acento(l.site) == site_alvo:
                return l
    return None


@dataclass(frozen=True)
class Calendario:
    feriados: frozenset
    recesso: dict
    cobertura_ate: object


@lru_cache
def calendario() -> Calendario:
    d = _ler("calendario.json")
    return Calendario(
        feriados=frozenset(parse_data(x) for x in d["feriados"]),
        recesso={parse_data(k): parse_data(v) for k, v in d["recesso"].items()},
        cobertura_ate=parse_data(d["cobertura_ate"]),
    )


@lru_cache
def triagem() -> dict:
    return _ler("triagem.json")
