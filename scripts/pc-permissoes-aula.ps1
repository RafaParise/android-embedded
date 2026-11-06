# Permissoes do Windows que a aula ao vivo (CMSP Web / Sala do Futuro, Meet, Teams) precisa: CAMERA e CAPTURA DE TELA.
# Em 05/11/2026 estavam em "Negar" (so o microfone em "Permitir"), por uma ferramenta de otimizacao de fora do projeto:
# o site mostrava a camera sem imagem e o compartilhamento de tela ficava desabilitado; o microfone funcionava.
#
#   pwsh -File scripts\pc-permissoes-aula.ps1             mostra o estado (so le)
#   pwsh -File scripts\pc-permissoes-aula.ps1 -Aplicar    libera camera e captura de tela (guarda o estado anterior)
#   pwsh -File scripts\pc-permissoes-aula.ps1 -Desfazer   devolve o estado guardado
# HKLM precisa de administrador. O microfone nao e tocado. Depois de aplicar, feche e abra o navegador.
param([switch]$Aplicar, [switch]$Desfazer)
$ErrorActionPreference = 'Stop'
$base = 'SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore'
$chaves = 'webcam', 'graphicsCaptureProgrammatic', 'graphicsCaptureWithoutBorder'
$guarda = Join-Path $PSScriptRoot '..\diagnostico\pc-permissoes-aula-antes.json'

function Le {
    $r = [ordered]@{}
    foreach ($h in 'HKLM', 'HKCU') {
        foreach ($c in $chaves) {
            $p = "${h}:\$base\$c"
            $r["$h\$c"] = if (Test-Path $p) { (Get-ItemProperty $p -Name Value -ErrorAction SilentlyContinue).Value } else { $null }
        }
    }
    $r
}

function Grava($estado) {
    foreach ($k in $estado.Keys) {
        $h, $c = $k -split '\\', 2
        $p = "${h}:\$base\$c"
        if ($null -eq $estado[$k]) { continue }
        if (-not (Test-Path $p)) { New-Item -Path $p -Force | Out-Null }
        Set-ItemProperty -Path $p -Name Value -Value $estado[$k] -Type String
    }
}

$agora = Le
if ($Aplicar) {
    if (-not (Test-Path $guarda)) { $agora | ConvertTo-Json | Set-Content -Path $guarda -Encoding utf8 }
    $novo = [ordered]@{}
    foreach ($k in $agora.Keys) { $novo[$k] = 'Allow' }
    Grava $novo
    'Liberado: camera e captura de tela. Feche e abra o navegador para valer.'
}
elseif ($Desfazer) {
    if (-not (Test-Path $guarda)) { 'Nada guardado para desfazer.'; exit 1 }
    $antes = Get-Content $guarda -Raw | ConvertFrom-Json -AsHashtable
    Grava $antes
    Move-Item $guarda "$guarda.usado-$(Get-Date -Format yyyyMMdd-HHmmss)"
    'Devolvido ao estado anterior.'
}
$fim = Le
foreach ($k in $fim.Keys) { "{0,-36} {1}" -f $k, $(if ($null -eq $fim[$k]) { '(sem valor = Permitir)' } else { $fim[$k] }) }
$neg = @($fim.Values | Where-Object { $_ -eq 'Deny' }).Count
if ($neg) { "ATENCAO: $neg permissao(oes) em Negar: a aula ao vivo pode ficar sem camera ou sem compartilhar a tela."; exit 3 }
'OK: camera e captura de tela permitidas.'
