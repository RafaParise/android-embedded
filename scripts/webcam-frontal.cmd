@echo off
rem Dois cliques: webcam do celular com a camera FRONTAL, para aula online. Na chamada, escolha "OBS Virtual Camera". Veja webcam-celular.py.
python "%~dp0webcam-celular.py" ligar --frontal %*
echo.
pause
