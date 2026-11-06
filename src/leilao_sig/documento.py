"""Leitura do edital (PDF, .docx, .doc) e verificações que não precisam de IA."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from leilao_sig import config
from leilao_sig.util import sem_acento


class EditalInvalido(Exception):
    """O edital não pode ser processado (escaneado, formato não suportado, fora do padrão)."""


@dataclass
class Edital:
    caminho: Path
    texto: str
    paginas: int


def ler_edital(caminho: str | Path) -> Edital:
    caminho = Path(caminho)
    ext = caminho.suffix.lower()
    if ext == ".pdf":
        texto, paginas = _ler_pdf(caminho)
    elif ext == ".docx":
        texto, paginas = _ler_docx(caminho), 0
    elif ext == ".doc":
        texto, paginas = _ler_doc(caminho), 0
    else:
        raise EditalInvalido(f"Formato não suportado: {ext} (use PDF, .docx ou .doc)")
    texto = _limpar(texto)
    if paginas and len(texto) / paginas < config.triagem()["min_caracteres_por_pagina"]:
        raise EditalInvalido(
            "O PDF parece escaneado (quase sem texto). Edital escaneado está fora do padrão: "
            "não será cadastrado automaticamente."
        )
    if not texto.strip():
        raise EditalInvalido("Não foi possível extrair texto do edital.")
    return Edital(caminho=caminho, texto=texto, paginas=paginas)


def _limpar(texto: str) -> str:
    texto = texto.replace("\r", "").replace(" ", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def _ler_pdf(caminho: Path) -> tuple[str, int]:
    import pdfplumber

    partes = []
    with pdfplumber.open(caminho) as pdf:
        for i, pagina in enumerate(pdf.pages, start=1):
            partes.append(f"[página {i}]\n{pagina.extract_text() or ''}")
        n = len(pdf.pages)
    return "\n\n".join(partes), n


def _ler_docx(caminho: Path) -> str:
    import docx

    doc = docx.Document(str(caminho))
    linhas = [p.text for p in doc.paragraphs]
    for tabela in doc.tables:
        for linha in tabela.rows:
            linhas.append(" | ".join(c.text.strip() for c in linha.cells))
    return "\n".join(linhas)


def _ler_doc(caminho: Path) -> str:
    """.doc antigo: converte para .docx com o LibreOffice (ou Word, no Windows)."""
    with tempfile.TemporaryDirectory() as tmp:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if soffice:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "docx", "--outdir", tmp, str(caminho)],
                check=True, capture_output=True, timeout=120,
            )
            convertido = Path(tmp) / (caminho.stem + ".docx")
            if convertido.exists():
                return _ler_docx(convertido)
        try:  # Windows com Microsoft Word instalado
            import win32com.client  # type: ignore

            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            try:
                d = word.Documents.Open(str(caminho.resolve()))
                destino = Path(tmp) / (caminho.stem + ".docx")
                d.SaveAs2(str(destino), FileFormat=16)
                d.Close()
            finally:
                word.Quit()
            return _ler_docx(destino)
        except ImportError:
            pass
    raise EditalInvalido("Para ler .doc é preciso ter o Word ou o LibreOffice instalado.")


@dataclass
class ResultadoTriagem:
    bloqueado: bool
    motivo: str = ""
    suspeitas: tuple[str, ...] = ()


def triar(texto: str) -> ResultadoTriagem:
    """Detecta editais fora do padrão sem gastar API. Suspeitas vão para a IA confirmar."""
    cfg = config.triagem()
    t = sem_acento(texto)
    for tipo, termos in cfg["bloqueios"].items():
        for termo in termos:
            if sem_acento(termo) in t:
                return ResultadoTriagem(True, f"Edital fora do padrão ({tipo}): encontrado “{termo}”.")
    # Vários editais num documento só (ex.: Diário Oficial)
    cabecalhos = re.findall(r"(?m)^\s*edital\s+(?:de\s+)?(?:leil[aã]o|hasta|pra[cç]a|intima[cç][aã]o)", t)
    if len(cabecalhos) > cfg["max_editais_no_documento"]:
        return ResultadoTriagem(
            True, f"O documento parece ter {len(cabecalhos)} editais (ex.: Diário Oficial). Separe um edital por arquivo."
        )
    suspeitas = tuple(
        tipo for tipo, termos in cfg.get("suspeitas", {}).items() if any(sem_acento(x) in t for x in termos)
    )
    return ResultadoTriagem(False, suspeitas=suspeitas)


def trecho(texto: str, busca: str, margem: int = 160) -> str:
    """Trecho do edital em volta de `busca` (para o relatório). Vazio se não achar."""
    if not busca:
        return ""
    t, b = sem_acento(texto), sem_acento(busca)
    i = t.find(b)
    if i < 0:
        return ""
    ini, fim = max(0, i - margem), min(len(texto), i + len(busca) + margem)
    return ("…" if ini else "") + texto[ini:fim].replace("\n", " ") + ("…" if fim < len(texto) else "")
