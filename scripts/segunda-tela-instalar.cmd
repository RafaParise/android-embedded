@echo off
rem Quem roda e o Rafael, UMA vez: botao direito > Executar como administrador.
rem Instala, pelo winget (fontes oficiais), o que faz o CELULAR virar MONITOR EXTRA do PC:
rem   - Sunshine (LizardByte.Sunshine, codigo aberto GPL-3.0): transmite a tela do PC; o Moonlight do celular recebe.
rem   - Virtual Display Driver (VirtualDrivers.Virtual-Display-Driver, codigo aberto): um monitor de mentira no Windows,
rem     para ESTENDER a area de trabalho ate o celular (sem ele, o celular so espelha o monitor de verdade).
rem Depois: o servico do Sunshine fica em INICIO MANUAL (so liga quando voce usa: segunda-tela.cmd > 3).
rem Na 1a vez o Sunshine pede para VOCE criar usuario e senha em https://localhost:47990 (o Claude nao cria senhas).
rem Desfazer: winget uninstall LizardByte.Sunshine  e  winget uninstall VirtualDrivers.Virtual-Display-Driver
net session >nul 2>&1
if errorlevel 1 (
  echo Precisa de administrador: botao direito neste arquivo ^> Executar como administrador.
  pause
  exit /b 1
)
winget install --id LizardByte.Sunshine --exact --source winget --accept-package-agreements --accept-source-agreements
winget install --id VirtualDrivers.Virtual-Display-Driver --exact --source winget --accept-package-agreements --accept-source-agreements
sc config SunshineService start= demand >nul 2>&1
sc stop SunshineService >nul 2>&1
echo.
echo Pronto. Para usar: segunda-tela.cmd e escolha 3.
echo Na 1a vez: abra https://localhost:47990 e crie seu usuario e senha do Sunshine.
pause
