@echo off
rem Duplo clique: a porta 2 do FortiGate (switch da bancada) ganha internet e o PC acessa o aparelho. Digite usuario e senha quando pedir.
rem Para desfazer: fortigate-bancada.cmd -Desfazer   |   so olhar: fortigate-bancada.cmd -Conferir   |   so ver os comandos: -Simular
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0fortigate-bancada.ps1" %*
echo.
pause
