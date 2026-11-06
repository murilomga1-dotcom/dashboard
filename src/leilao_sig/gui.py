"""Tela principal: escolher edital e planilha, preparar com a IA e revisar (Fase 1).

A gravação no SIG (Fase 2/3) entra no botão "Gravar no SIG", hoje desabilitado.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
    QTextBrowser, QVBoxLayout, QWidget,
)

from leilao_sig import __version__, ia
from leilao_sig.execucao import Execucao
from leilao_sig.modelos import Preparacao
from leilao_sig.preparar import preparar
from leilao_sig.util import fmt_data

COR_ERRO = QColor("#fde2e1")
COR_ALERTA = QColor("#fff4d6")


class _Trabalho(QObject):
    terminou = Signal(object, str)  # (Preparacao | None, pasta da execução ou mensagem de erro)

    def __init__(self, edital: str, planilha: str):
        super().__init__()
        self.edital, self.planilha = edital, planilha

    def rodar(self) -> None:
        try:
            with Execucao() as ex:
                prep = preparar(self.edital, self.planilha, execucao=ex)
            self.terminou.emit(prep, str(ex.pasta))
        except Exception as e:  # nunca derrubar a tela
            self.terminou.emit(None, f"{type(e).__name__}: {e}")


def _tabela(colunas: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(colunas))
    t.setHorizontalHeaderLabels(colunas)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    t.setWordWrap(True)
    return t


def _preencher(t: QTableWidget, linhas: list[list[str]], cores: list[QColor | None] | None = None) -> None:
    t.setRowCount(len(linhas))
    for i, linha in enumerate(linhas):
        for j, valor in enumerate(linha):
            item = QTableWidgetItem(str(valor))
            if cores and cores[i]:
                item.setBackground(cores[i])
            t.setItem(i, j, item)
    t.resizeRowsToContents()


class Janela(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Cadastro de Leilões no SIG — v{__version__}")
        self.resize(1200, 800)
        self.prep: Preparacao | None = None
        self.pasta_execucao = ""
        self._thread: QThread | None = None

        self.campo_edital, self.campo_planilha = QLineEdit(), QLineEdit()
        for campo in (self.campo_edital, self.campo_planilha):
            campo.setReadOnly(True)
        form = QFormLayout()
        form.addRow("Edital (PDF/Word):", self._com_botao(self.campo_edital, "Escolher…", self._escolher_edital))
        form.addRow("Planilha Bens do Leilão:", self._com_botao(self.campo_planilha, "Escolher…", self._escolher_planilha))

        self.bt_preparar = QPushButton("Preparar com a IA")
        self.bt_preparar.clicked.connect(self._preparar)
        self.bt_gravar = QPushButton("Gravar no SIG")
        self.bt_gravar.setEnabled(False)
        self.bt_gravar.setToolTip("Disponível na Fase 2 (cadastro automático no SIG).")
        self.bt_log = QPushButton("Abrir pasta do log")
        self.bt_log.setEnabled(False)
        self.bt_log.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.pasta_execucao)))
        self.bt_chave = QPushButton("Chave da API…")
        self.bt_chave.clicked.connect(self._configurar_chave)
        botoes = QHBoxLayout()
        for b in (self.bt_preparar, self.bt_gravar, self.bt_log):
            botoes.addWidget(b)
        botoes.addStretch()
        botoes.addWidget(self.bt_chave)

        self.status = QLabel("Escolha o edital e a planilha.")
        self.status.setWordWrap(True)

        self.abas = QTabWidget()
        self.tab_problemas = _tabela(["Nível", "Processo", "Lote", "O que faltou / conferir", "Trecho do edital"])
        self.abas.addTab(self.tab_problemas, "Relatório")
        cab = QWidget()
        lc = QVBoxLayout(cab)
        self.lbl_cab = QLabel()
        self.lbl_cab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.html_cab = QTextBrowser()
        self.html_cab.setOpenExternalLinks(True)
        self.tab_ciclos = _tabela(["Ciclo", "Data", "Hora", "Data nominal", "Ajustes"])
        sp = QSplitter(Qt.Orientation.Vertical)
        sp.addWidget(self.html_cab)
        sp.addWidget(self.tab_ciclos)
        lc.addWidget(self.lbl_cab)
        lc.addWidget(sp)
        self.abas.addTab(cab, "Cabeçalho e datas")
        lot = QSplitter(Qt.Orientation.Vertical)
        self.tab_lotes = _tabela(["Ordem", "Lote edital", "Processo", "Vistoria", "Tipo", "Título", "Inicial 1º", "Avaliação", "Inicial 2º", "Situação"])
        self.tab_lotes.itemSelectionChanged.connect(self._mostrar_lote)
        self.html_lote = QTextBrowser()
        lot.addWidget(self.tab_lotes)
        lot.addWidget(self.html_lote)
        self.abas.addTab(lot, "Lotes")

        raiz = QWidget()
        lr = QVBoxLayout(raiz)
        lr.addLayout(form)
        lr.addLayout(botoes)
        lr.addWidget(self.status)
        lr.addWidget(self.abas)
        self.setCentralWidget(raiz)

    def _com_botao(self, campo: QLineEdit, texto: str, acao) -> QWidget:
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        b = QPushButton(texto)
        b.clicked.connect(acao)
        l.addWidget(campo)
        l.addWidget(b)
        return w

    def _escolher_edital(self) -> None:
        c, _ = QFileDialog.getOpenFileName(self, "Edital", "", "Editais (*.pdf *.docx *.doc)")
        if c:
            self.campo_edital.setText(c)

    def _escolher_planilha(self) -> None:
        c, _ = QFileDialog.getOpenFileName(self, "Planilha Bens do Leilão", "", "Planilhas (*.xlsx *.xlsm *.csv)")
        if c:
            self.campo_planilha.setText(c)

    def _configurar_chave(self) -> None:
        chave, ok = QInputDialog.getText(self, "Chave da API do Claude", "Cole a chave (fica no cofre do Windows):", QLineEdit.EchoMode.Password)
        if ok and chave.strip():
            try:
                ia.salvar_chave_api(chave.strip())
                QMessageBox.information(self, "Chave", "Chave salva no cofre de credenciais.")
            except Exception as e:
                QMessageBox.warning(self, "Chave", f"Não foi possível salvar a chave: {e}")

    def _preparar(self) -> None:
        edital, planilha = self.campo_edital.text(), self.campo_planilha.text()
        if not (edital and planilha):
            QMessageBox.warning(self, "Faltam arquivos", "Escolha o edital e a planilha.")
            return
        self.bt_preparar.setEnabled(False)
        self.status.setText("Lendo o edital e consultando a IA… (pode levar alguns minutos)")
        self._thread = QThread()
        self._trab = _Trabalho(edital, planilha)
        self._trab.moveToThread(self._thread)
        self._thread.started.connect(self._trab.rodar)
        self._trab.terminou.connect(self._terminou)
        self._trab.terminou.connect(self._thread.quit)
        self._thread.start()

    def _terminou(self, prep: Preparacao | None, info: str) -> None:
        self.bt_preparar.setEnabled(True)
        if prep is None:
            self.status.setText(f"Falha inesperada: {info}")
            return
        self.prep, self.pasta_execucao = prep, info
        self.bt_log.setEnabled(True)
        self.mostrar(prep)

    def mostrar(self, prep: Preparacao) -> None:
        self.prep = prep
        erros = [p for p in prep.problemas if p.nivel == "erro"]
        n_ok = sum(l.pode_gravar for l in prep.lotes)
        if prep.bloqueado:
            self.status.setText("⛔ NÃO SERÁ CADASTRADO: " + " | ".join(p.mensagem for p in erros))
        else:
            self.status.setText(
                f"✅ Pronto para revisão: {n_ok} de {len(prep.lotes)} lote(s) podem ser gravados. "
                "Confira os alertas no Relatório antes de gravar."
            )
        probs = list(prep.problemas) + [p for l in prep.lotes for p in l.problemas]
        probs.sort(key=lambda p: p.nivel != "erro")
        _preencher(self.tab_problemas, [[p.nivel.upper(), p.processo, p.lote, p.mensagem, p.trecho] for p in probs],
                   [COR_ERRO if p.nivel == "erro" else COR_ALERTA for p in probs])

        c = prep.cabecalho
        if c:
            self.lbl_cab.setText(
                f"<b>{c.titulo}</b><br>Leiloeiro: {c.leiloeiro} (site no SIG: {c.site}) · Fuso: {c.fuso}<br>"
                f"1º encerramento: {c.dt1} {c.h1} · 2º encerramento: {c.dt2} {c.h2}"
                + ("" if c.venda_direta_cadastrada else " · <i>sem venda direta</i>")
            )
            self.html_cab.setHtml(c.html)
            _preencher(self.tab_ciclos, [[x.rotulo, fmt_data(x.data), x.hora, fmt_data(x.nominal), "; ".join(x.ajustes)] for x in c.ciclos])
        else:
            self.lbl_cab.setText("Cabeçalho não gerado (ver Relatório).")
            self.html_cab.clear()
            _preencher(self.tab_ciclos, [])
        _preencher(
            self.tab_lotes,
            [[l.ordem, l.numero_no_edital, l.processo, l.vistoria, l.tipo_bem, l.titulo, l.v1, l.aval, l.v2,
              "OK" if l.pode_gravar else "ERRO — será pulado"] for l in prep.lotes],
            [None if l.pode_gravar else COR_ERRO for l in prep.lotes],
        )
        self.html_lote.clear()

    def _mostrar_lote(self) -> None:
        linhas = self.tab_lotes.selectionModel().selectedRows()
        if self.prep and linhas:
            self.html_lote.setHtml(self.prep.lotes[linhas[0].row()].html)


def main() -> None:
    app = QApplication(sys.argv)
    j = Janela()
    j.show()
    if len(sys.argv) >= 3:  # atalho: leilao_sig <edital> <planilha>
        j.campo_edital.setText(str(Path(sys.argv[1]).resolve()))
        j.campo_planilha.setText(str(Path(sys.argv[2]).resolve()))
    sys.exit(app.exec())


if __name__ == "__main__":
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    main()
