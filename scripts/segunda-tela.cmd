@echo off
rem Segunda tela entre o PC e o celular (menu). Cabo, Wi-Fi ou dados moveis (pela Tailscale).
cd /d "%~dp0.."
python scripts\segunda-tela.py %*
if "%~1"=="" pause
