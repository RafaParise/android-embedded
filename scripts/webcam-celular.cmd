@echo off
rem Dois cliques: celular como webcam do PC (scrcpy + camera virtual do OBS). Veja webcam-celular.py.
python "%~dp0webcam-celular.py" ligar %*
echo.
pause
