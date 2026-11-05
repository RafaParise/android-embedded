@echo off
rem Duplo clique: fecha de novo a porta do Ollama (11434) na tailnet (o estado normal).
chcp 65001 >nul
title IA do PC - fechar o Ollama para o celular
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0ia-do-pc.ps1" -FecharOllama
echo.
pause
