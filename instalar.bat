@echo off
rem Instala o app (rodar uma vez, e de novo depois de baixar uma versao nova)
cd /d "%~dp0"
where py >nul 2>nul && (py -3 -m venv .venv) || (python -m venv .venv)
if not exist .venv\Scripts\python.exe (
  echo.
  echo Python nao encontrado. Instale o Python 3.12 em python.org marcando "Add python.exe to PATH".
  pause
  exit /b 1
)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[windows]"
echo.
echo Instalacao concluida. Para abrir o app, de dois cliques em abrir.bat
pause
