@echo off
title Proteger a bateria do celular
rem Quem roda e o Rafael. Limita a carga a 85%%: desgasta menos a bateria com o celular sempre no cabo. Nao esfria o processador. Em troca, a carga para em 85%%.
rem Ligar: dois cliques. Desligar: proteger-bateria.cmd 0
set VALOR=%1
if "%VALOR%"=="" set VALOR=1
adb shell settings put global protect_battery %VALOR%
echo.
echo Valor agora no celular (1 = limita a 85%%, 0 = carga completa):
adb shell settings get global protect_battery
echo.
echo Confira depois se a carga para em 85%%. O aparelho pode ignorar este ajuste, porque o Device Care foi removido.
pause
