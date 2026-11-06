"""Funções pequenas usadas em vários módulos."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def sem_acento(texto: str) -> str:
    """Minúsculas e sem acentos, para comparar textos sem depender de grafia."""
    nfkd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def so_digitos(texto: object) -> str:
    return re.sub(r"\D", "", str(texto or ""))


def parse_data(texto: str) -> date:
    return datetime.strptime(texto.strip(), "%d/%m/%Y").date()


def fmt_data(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def parse_valor(valor: object) -> Decimal | None:
    """Converte '68.000,00', 'R$ 68.000,00', 68000 ou 68000.0 em Decimal."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor)).quantize(Decimal("0.01"))
    t = re.sub(r"[^\d,.\-]", "", str(valor))
    if not t:
        return None
    if "," in t:  # formato brasileiro: ponto = milhar, vírgula = decimal
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1 or re.search(r"\.\d{3}$", t):  # "68.000" = sessenta e oito mil
        t = t.replace(".", "")
    try:
        return Decimal(t).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def fmt_valor(v: Decimal) -> str:
    """Decimal -> '68.000,00' (formato que o SIG espera)."""
    inteiro, _, cent = f"{v:.2f}".partition(".")
    neg = inteiro.startswith("-")
    inteiro = inteiro.lstrip("-")
    grupos = []
    while inteiro:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    return ("-" if neg else "") + ".".join(grupos or ["0"]) + "," + cent
