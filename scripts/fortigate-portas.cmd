@echo off
rem Duplo clique: todas as entradas do FortiGate (portas 1 e 3-7, porta 2 e DMZ) dao internet a qualquer aparelho e o PC alcanca o que estiver ligado. Digite usuario e senha quando pedir (2 vezes).
rem Desfazer: fortigate-portas.cmd -Desfazer   |   so olhar: -Conferir   |   so ver os comandos: -Simular
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0fortigate-portas.ps1" %*
echo.
pause
