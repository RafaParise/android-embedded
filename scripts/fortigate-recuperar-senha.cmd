@echo off
rem Recupera a senha do admin do FortiGate pelo cabo de console (conta de manutencao). Siga o que a janela pedir.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0fortigate-recuperar-senha.ps1" %*
echo.
pause
