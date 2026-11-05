@echo off
title Limpar a pasta TEMP
pwsh -NoProfile -File "%~dp0limpar-temp.ps1" %*
echo.
pause
