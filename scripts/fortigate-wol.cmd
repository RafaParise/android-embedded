@echo off
rem Duplo clique: aplica no FortiGate a regra do celular acordar o PC. Digite usuario e senha quando pedir.
rem Para desfazer: fortigate-wol.cmd -Desfazer   |   so olhar: fortigate-wol.cmd -Conferir
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0fortigate-wol.ps1" %*
echo.
pause
