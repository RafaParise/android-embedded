@echo off
title Copia local do celular
cd /d "%~dp0.."
echo Cabo, Wi-Fi ou dados moveis (Tailscale): tirar ou ligar o cabo no meio troca sozinho.
python -B scripts\copia-a12.py copiar --aplicar
echo.
pause
