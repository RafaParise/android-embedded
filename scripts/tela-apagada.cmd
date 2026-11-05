@echo off
title Tela do celular
python "%~dp0tela-apagada.py"
echo.
echo Pode fechar esta janela.
timeout /t 12 >nul
