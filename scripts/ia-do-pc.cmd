@echo off
rem Duplo clique: confere o que o celular usa no PC (Tailscale) e liga o que faltar (OmniRoute, Ollama, ponte). Detalhes em ia-do-pc.ps1.
chcp 65001 >nul
title IA do PC para o celular
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0ia-do-pc.ps1" %*
echo.
pause
