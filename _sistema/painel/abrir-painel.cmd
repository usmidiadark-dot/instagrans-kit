@echo off
rem Abre o Painel de Producao (http://127.0.0.1:8765). Se o servidor ja estiver no ar, so abre o navegador.
cd /d "%~dp0..\.."
start "" pythonw "_sistema\painel\painel.py"
