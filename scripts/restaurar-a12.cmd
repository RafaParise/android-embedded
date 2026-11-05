@echo off
title Restaurar o celular a partir da copia
cd /d "%~dp0.."
echo Ligue o celular no cabo, com a depuracao USB ligada e a conta Google ja entrada.
echo Primeiro mostro o plano. Nada muda sem a sua confirmacao.
echo.
python -B scripts\copia-a12.py restaurar
echo.
set /p OK=Para aplicar, digite RESTAURAR e aperte Enter:
if /i not "%OK%"=="RESTAURAR" (
  echo Nada foi alterado.
  pause
  exit /b 0
)
python -B scripts\copia-a12.py restaurar --aplicar
echo.
echo Passos seguintes: memoria\COPIA-E-RESTAURAR.md, parte 3.
pause
