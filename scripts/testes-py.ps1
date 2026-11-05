# Roda os testes Python (scripts\tests, pytest com ADB falso) no WSL (Ubuntu), como a nuvem roda no Linux dela.
# Nenhum teste abre o adb de verdade: o conftest.py troca o subprocess.run, esvazia o PATH e barra qualquer Popen que cite adb.
# Mesmo assim a regra de memoria\NUVEM.md prefere o cabo do A12 desligado: este script AVISA se o celular esta no ADB.
# O pytest e instalado so em diagnostico\pytest-lib (fora do git, nao toca o Python do sistema).
# Uso: pwsh -NoProfile -File scripts\testes-py.ps1 [-Raiz <projeto>] [-Lib <pasta do pytest>] [-Filtro <expressao do pytest -k>]
# Saida 0 = todos passaram; 1 = algum falhou; 2 = nao deu para rodar.
param([string]$Raiz = (Split-Path -Parent $PSScriptRoot), [string]$Lib = '', [string]$Filtro = '')
$ErrorActionPreference = 'Stop'
function Nativo([scriptblock]$bloco) {
    # Windows PowerShell 5.1: com $ErrorActionPreference = 'Stop', QUALQUER linha que um programa nativo escreva em stderr vira excecao (o wsl.exe pode avisar de proxy
    # e de systemd pelo stderr [Provavel: nao reproduzido em 31/10]; o pwsh 7 nao tem esse problema). Aqui a preferencia fica em 'Continue' so durante a chamada; devolve as linhas (stdout + stderr)
    # como texto e deixa o $LASTEXITCODE para quem chamou.
    $antes = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { return @(& $bloco 2>&1 | ForEach-Object { "$_" }) } finally { $ErrorActionPreference = $antes }
}
try {
    if (-not $Lib) { $Lib = Join-Path $Raiz 'diagnostico\pytest-lib' }
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { throw 'wsl.exe nao encontrado.' }
    $distros = ((Nativo { & wsl.exe -l -q }) -join "`n") -replace "`0", ''
    if ($distros -notmatch 'Ubuntu') { throw 'nao ha a distro Ubuntu no WSL (wsl -l -q).' }
    if (-not (Test-Path -LiteralPath (Join-Path $Raiz 'scripts\tests'))) { throw "nao ha scripts\tests em $Raiz" }
    if ($Raiz -notmatch '^[A-Za-z]:\\' -or $Lib -notmatch '^[A-Za-z]:\\') { throw 'use caminhos absolutos com letra de unidade.' }
    if ("$Raiz$Lib" -match "'") { throw "o caminho nao pode ter aspas simples." }

    $adb = Get-Command adb -ErrorAction SilentlyContinue
    if ($adb) {
        $lista = (Nativo { & adb devices }) -join "`n"
        if ($lista -match '\tdevice') { Write-Host 'AVISO: o A12 esta no ADB. Os testes nao abrem o adb (conftest.py), mas a regra do NUVEM.md prefere o cabo desligado.' -ForegroundColor Yellow }
    }

    if (-not (Test-Path -LiteralPath (Join-Path $Lib 'pytest'))) {
        Write-Host "Instalando o pytest em $Lib (so nessa pasta; precisa de internet)..."
        New-Item -ItemType Directory -Force -Path $Lib | Out-Null
        [void](Nativo { & python -I -B -m pip install --target $Lib pytest --no-compile --disable-pip-version-check --quiet })
        if (-not (Test-Path -LiteralPath (Join-Path $Lib 'pytest'))) { throw 'nao consegui instalar o pytest (python/pip do Windows e internet).' }
    }

    function Para-Wsl($p) { '/mnt/' + $p.Substring(0, 1).ToLowerInvariant() + ($p.Substring(2) -replace '\\', '/') }
    $wRaiz = Para-Wsl $Raiz
    $wLib = Para-Wsl $Lib
    $k = if ($Filtro) { " -k '" + ($Filtro -replace "'", '') + "'" } else { '' }
    $cmd = "cd '$wRaiz' && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH='$wLib' python3 -m pytest -p no:cacheprovider scripts/tests -q$k 2>&1"
    $saida = Nativo { & wsl.exe -d Ubuntu -- bash -c $cmd }
    $cod = $LASTEXITCODE
    (($saida -join "`n").Replace("`0", '')).TrimEnd() | Write-Host
    exit $(if ($cod -eq 0) { 0 } elseif ($cod -eq 1) { 1 } else { 2 })
}
catch {
    Write-Host ('ABORTADO: ' + $_.Exception.Message) -ForegroundColor Red
    exit 2
}
