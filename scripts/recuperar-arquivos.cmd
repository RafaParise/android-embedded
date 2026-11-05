@echo off
rem Dois cliques: abre o PhotoRec (recuperador de arquivos, codigo aberto) como administrador. Guia: memoria\WEBCAM-E-RECUPERACAO.md
rem REGRA DE OURO: pare de usar o disco onde o arquivo estava e salve o que recuperar em OUTRO disco.
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
    exit /b
)
set "T=C:\Projetos\ferramentas\testdisk\testdisk-7.2"
if not exist "%T%\qphotorec_win.exe" (
    echo Nao achei o PhotoRec em %T%.
    pause
    exit /b 2
)
echo REGRA DE OURO: salve o que recuperar em OUTRO disco, nunca no mesmo do arquivo perdido.
echo Primeiro confira a Lixeira, o Backup-PC no Google Drive e o GitHub.
start "" "%T%\qphotorec_win.exe"
