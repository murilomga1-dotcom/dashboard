@echo off
rem Abre o app. A janela preta mostra erros, se houver: deixe aberta enquanto usa.
cd /d "%~dp0"
.venv\Scripts\python -m leilao_sig
if errorlevel 1 pause
