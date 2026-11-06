@echo off
rem Celular no OBS do PC: camera da aula, gravar camera ou tela, live. Perto ou longe (cabo, Wi-Fi ou dados moveis pela Tailscale).
rem Feito para o acesso remoto (aFreeRDP): cada opcao liga em segundo plano e volta ao menu. Detalhes: webcam-celular.py e obs-controle.py.
:menu
cls
echo  ===== Celular no OBS do PC =====
echo.
echo   1  Camera do celular para a aula (OBS Virtual Camera)
echo   2  Camera FRONTAL para a aula
echo   3  Gravar a camera do celular
echo   4  Gravar a TELA do celular (com o som dele)
echo   5  Parar a gravacao (salva o arquivo)
echo   6  Comecar a live (destino e chave configurados no OBS)
echo   7  Parar a live
echo   8  Ver o que esta ligado
echo   9  Desligar tudo
echo   0  Sair
echo.
choice /c 1234567890 /n /m "Escolha: "
set op=%errorlevel%
if %op%==10 exit /b 0
if %op%==1 python "%~dp0webcam-celular.py" iniciar
if %op%==2 python "%~dp0webcam-celular.py" iniciar --frontal
if %op%==3 python "%~dp0webcam-celular.py" gravar
if %op%==4 python "%~dp0webcam-celular.py" iniciar --tela --som --gravar
if %op%==5 python "%~dp0webcam-celular.py" parar-gravacao
if %op%==6 python "%~dp0webcam-celular.py" live
if %op%==7 python "%~dp0webcam-celular.py" parar-live
if %op%==8 python "%~dp0webcam-celular.py" status
if %op%==9 python "%~dp0webcam-celular.py" parar
echo.
pause
goto menu
