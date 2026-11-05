# Ajustes do PC para o MENOR atraso de imagem e som ao projetar na TV (Miracast) ou no celular (Moonlight).
# Pedido do Rafael (05/11/2026): "otimizar ao maximo as configuracoes do pc para diminuir ao maximo o atraso".
# Analogia: a placa Wi-Fi e um carteiro. Por padrao ele junta cartas para viajar menos (economia); aqui ele passa
# a entregar na hora, sem cochilar entre entregas e sem sair procurando outra rua no meio do caminho.
# Uso:  pwsh -File pc-baixa-latencia.ps1             mostra o que mudaria (nada muda)
#       pwsh -File pc-baixa-latencia.ps1 -Aplicar    aplica e guarda os valores antigos em diagnostico\pc-baixa-latencia.json
#       pwsh -File pc-baixa-latencia.ps1 -Desfazer   volta os valores guardados
# Precisa de administrador. O agendamento de GPU por hardware so vale depois de reiniciar o PC.
param([switch]$Aplicar, [switch]$Desfazer, [string]$Placa = 'Wi-Fi')
$ErrorActionPreference = 'Stop'
$raiz = Split-Path $PSScriptRoot -Parent
$guarda = Join-Path $raiz 'diagnostico\pc-baixa-latencia.json'

# (nome na placa Intel AX210 em portugues, valor de baixa latencia, por que)
$wifi = @(
    @('União de pacote', 'Desabilitado', 'junta pacotes para economizar e entrega atrasado'),
    @('MIMO - Modo de Economia de Energia', 'Sem SMPS', 'antenas sem cochilo entre pacotes'),
    @('Agressividade de roaming', '1. Mais baixo', 'menos buscas por outro ponto de acesso no meio da transmissao'),
    @('Suporte para U-APSD', 'Desabilitado', 'sem modo de economia de energia por pacote')
)
$reg = @(
    @('HKCU:\Software\Microsoft\GameBar', 'AutoGameModeEnabled', 1, 'Modo de Jogo ligado (prioriza o que esta na tela)'),
    @('HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers', 'HwSchMode', 2, 'agendamento de GPU por hardware (vale depois de reiniciar)')
)

if ($Desfazer) {
    if (-not (Test-Path $guarda)) { throw "Nada guardado em $guarda" }
    $v = Get-Content $guarda -Raw | ConvertFrom-Json
    foreach ($p in $v.wifi) { Set-NetAdapterAdvancedProperty -Name $Placa -DisplayName $p.nome -DisplayValue $p.valor -NoRestart; "voltou: $($p.nome) = $($p.valor)" }
    foreach ($r in $v.reg) {
        if ($null -eq $r.valor) { Remove-ItemProperty -Path $r.caminho -Name $r.nome -ErrorAction SilentlyContinue; "voltou: $($r.nome) = (padrao)" }
        else { Set-ItemProperty -Path $r.caminho -Name $r.nome -Value $r.valor; "voltou: $($r.nome) = $($r.valor)" }
    }
    Restart-NetAdapter -Name $Placa
    'Desfeito. (Wi-Fi reiniciado; o agendamento de GPU volta depois de reiniciar o PC.)'
    exit 0
}

$antes = @{ wifi = @(); reg = @() }
foreach ($w in $wifi) {
    $atual = (Get-NetAdapterAdvancedProperty -Name $Placa -DisplayName $w[0]).DisplayValue
    $antes.wifi += @{ nome = $w[0]; valor = $atual }
    "{0,-38} {1,-22} -> {2,-16} ({3})" -f $w[0], $atual, $w[1], $w[2]
}
foreach ($r in $reg) {
    $atual = (Get-ItemProperty -Path $r[0] -Name $r[1] -ErrorAction SilentlyContinue).($r[1])
    $antes.reg += @{ caminho = $r[0]; nome = $r[1]; valor = $atual }
    "{0,-38} {1,-22} -> {2,-16} ({3})" -f $r[1], $(if ($null -eq $atual) { '(padrao)' } else { $atual }), $r[2], $r[3]
}
if (-not $Aplicar) { 'Simulacao. Para aplicar: -Aplicar (o Wi-Fi reinicia por uns segundos).'; exit 0 }

if (-not (Test-Path $guarda)) { $antes | ConvertTo-Json -Depth 4 | Set-Content $guarda -Encoding utf8 }  # guarda so o ORIGINAL
foreach ($w in $wifi) { Set-NetAdapterAdvancedProperty -Name $Placa -DisplayName $w[0] -DisplayValue $w[1] -NoRestart }
foreach ($r in $reg) { if (-not (Test-Path $r[0])) { New-Item -Path $r[0] -Force | Out-Null }; Set-ItemProperty -Path $r[0] -Name $r[1] -Value $r[2] -Type DWord }
Restart-NetAdapter -Name $Placa
Start-Sleep -Seconds 8
foreach ($w in $wifi) { $v = (Get-NetAdapterAdvancedProperty -Name $Placa -DisplayName $w[0]).DisplayValue; "{0,-38} {1}" -f $w[0], $(if ($v -eq $w[1]) { "ok ($v)" } else { "FALHOU ($v)" }) }
"Valores antigos em $guarda. Desfazer: -Desfazer"
