# Mostra o que sobrou na pasta TEMP do Windows e, so depois de o Rafael digitar APAGAR, apaga. Quem roda e ele: nenhuma IA apaga por este script.
# Fica de fora: a pasta 'claude' (sessoes em uso) e tudo que foi mexido nos ultimos 2 dias. Arquivo em uso e pulado.
# Uso: limpar-temp.cmd (dois cliques). -Simular so mostra. -Pasta troca o alvo (para os testes).
param([switch]$Simular, [string]$Pasta = $env:TEMP, [int]$Dias = 2)
$ErrorActionPreference = 'Continue'

function Tamanho($item) {
    if (-not $item.PSIsContainer) { return $item.Length }
    $s = (Get-ChildItem -LiteralPath $item.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    if ($s) { return $s } else { return 0 }
}

function Recente($item, $limite) {
    if ($item.LastWriteTime -ge $limite) { return $true }
    if (-not $item.PSIsContainer) { return $false }
    return [bool](Get-ChildItem -LiteralPath $item.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $limite } | Select-Object -First 1)
}

$limite = (Get-Date).AddDays(-$Dias)
if (-not (Test-Path -LiteralPath $Pasta)) { Write-Host "Pasta nao existe: $Pasta"; exit 2 }
Write-Host "Olhando $Pasta (pode levar alguns minutos)..."
$fila = @()
$mantidos = 0
foreach ($i in Get-ChildItem -LiteralPath $Pasta -Force -ErrorAction SilentlyContinue) {
    if ($i.Name -eq 'claude' -or (Recente $i $limite)) { $mantidos++; continue }
    $fila += [pscustomobject]@{ Item = $i; Bytes = (Tamanho $i) }
}
$total = ($fila | Measure-Object Bytes -Sum).Sum
if (-not $total) { $total = 0 }
Write-Host ''
Write-Host "Saem $($fila.Count) itens, $([math]::Round($total / 1GB, 1)) GB pelo tamanho aparente. Ficam $mantidos (em uso, recentes ou da pasta claude)."
Write-Host 'Os maiores:'
$fila | Sort-Object Bytes -Descending | Select-Object -First 12 | ForEach-Object { Write-Host ("  {0,7:N2} GB  {1}" -f ($_.Bytes / 1GB), $_.Item.Name) }
Write-Host ''
if ($Simular) { Write-Host 'Simulacao: nada foi apagado.'; exit 0 }
if ($fila.Count -eq 0) { Write-Host 'Nada para apagar.'; exit 0 }
Write-Host 'Isto apaga de vez, sem passar pela lixeira.'
Write-Host 'Para confirmar, digite APAGAR e aperte Enter (qualquer outra coisa cancela):'
if ([Console]::In.ReadLine() -cne 'APAGAR') { Write-Host 'Cancelado: nada foi apagado.'; exit 0 }
$letra = (Split-Path -Qualifier $Pasta).TrimEnd(':')
$antes = (Get-Volume -DriveLetter $letra).SizeRemaining
$ok = 0
$pulados = 0
foreach ($f in $fila) {
    try {
        if ($f.Item.PSIsContainer) { [IO.Directory]::Delete($f.Item.FullName, $true) } else { [IO.File]::Delete($f.Item.FullName) }
        $ok++
    } catch { $pulados++ }
}
$depois = (Get-Volume -DriveLetter $letra).SizeRemaining
Write-Host "Apagados: $ok. Pulados por estarem em uso: $pulados. Espaco ganho em ${letra}: $([math]::Round(($depois - $antes) / 1GB, 1)) GB."
exit 0
