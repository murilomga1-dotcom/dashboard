"""Pasta e log de cada execução: <pasta_dados>/execucoes/AAAA-MM-DD_HHMMSS/."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from leilao_sig import config


class Execucao:
    def __init__(self, base: Path | None = None):
        base = base or (config.pasta_dados() / "execucoes")
        self.pasta = base / datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.pasta.mkdir(parents=True, exist_ok=True)
        self._handler = logging.FileHandler(self.pasta / "execucao.log", encoding="utf-8")
        self._handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        raiz = logging.getLogger("leilao_sig")
        raiz.setLevel(logging.INFO)
        raiz.addHandler(self._handler)
        self.log = logging.getLogger("leilao_sig.execucao")

    def salvar_json(self, nome: str, obj: object) -> Path:
        caminho = self.pasta / nome
        caminho.write_text(json.dumps(obj, default=_serializar, ensure_ascii=False, indent=2), encoding="utf-8")
        return caminho

    def fechar(self) -> None:
        logging.getLogger("leilao_sig").removeHandler(self._handler)
        self._handler.close()

    def __enter__(self) -> "Execucao":
        return self

    def __exit__(self, *exc) -> None:
        if exc[0]:
            self.log.exception("Execução interrompida")
        self.fechar()


def _serializar(o: object):
    if isinstance(o, BaseModel):
        return o.model_dump()
    if is_dataclass(o):
        return asdict(o)  # type: ignore[arg-type]
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if isinstance(o, (Decimal, Path)):
        return str(o)
    raise TypeError(type(o).__name__)
