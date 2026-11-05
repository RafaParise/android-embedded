@echo off
rem Duplo clique: abre a porta do Ollama (11434) SO para a tailnet, para o comando `ia pc` do celular funcionar sem cabo.
rem O Ollama nao tem senha: feche depois com ia-do-pc-fechar-ollama.cmd.
chcp 65001 >nul
title IA do PC - abrir o Ollama para o celular
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0ia-do-pc.ps1" -AbrirOllama
echo.
pause
