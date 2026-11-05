@echo off
title Copia local do celular
cd /d "%~dp0.."
echo Ligue o celular no cabo, com a depuracao USB ligada.
python -B scripts\copia-a12.py copiar --aplicar
echo.
pause
