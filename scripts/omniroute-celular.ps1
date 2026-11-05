# omniroute-celular.ps1 - ativa a RESERVA do OmniRoute do celular com as chaves de provedor que o Rafael copia (memoria/OMNIROUTE-CELULAR.md).
#   pwsh -NoProfile -File scripts\omniroute-celular.ps1 -Ativar [-Minutos 20] [-Provedores nvidia,gemini,openrouter] [-ManterLigado]
#   pwsh -NoProfile -File scripts\omniroute-celular.ps1 -Status | -Desligar | -Tirar nvidia
# -Ativar: instala o omni-local no Termux (cabo USB), liga o OmniRoute do celular e fica olhando a AREA DE TRANSFERENCIA do PC. Quando ela traz uma chave
# com o formato de um provedor que ainda falta (nvapi-..., AIza..., sk-or-...), manda a chave ao celular pela ENTRADA PADRAO do ssh (nunca na linha de
# comando), mostra o teste do OmniRoute e LIMPA a area de transferencia. Chave nenhuma e impressa, gravada em arquivo ou vai ao git. Depois cria os combos
# codigo/auditoria/rapido so com os modelos dos provedores recebidos, testa e, SO se o combo codigo responder, cria ~/.omniroute/pronto (o que liga a
# reserva no ia). Desliga o OmniRoute do celular no fim (-ManterLigado deixa ligado). Autorizado pelo Rafael em 01/11/2026 (chaves de provedor so as do celular).
param([switch]$Ativar, [switch]$Status, [switch]$Desligar, [string]$Tirar = '', [int]$Minutos = 20,
      [string[]]$Provedores = @('nvidia', 'gemini', 'openrouter'), [switch]$ManterLigado)
# 'Continue' de proposito: no Windows PowerShell 5.1, com 'Stop', qualquer linha de stderr de programa nativo vira excecao (licao de 31/10). Falha real aqui e 'throw'.
$ErrorActionPreference = 'Continue'

# Gemini tem dois formatos: o antigo "AIza..." (39 caracteres) e o novo "AQ.xxxx" (53 caracteres, visto em 01/11/2026 no Google AI Studio).
$FORMATOS = [ordered]@{ nvidia = '^nvapi-[A-Za-z0-9_\-]{20,}$'; gemini = '^(AIza[0-9A-Za-z_\-]{30,}|AQ\.[A-Za-z0-9_\-]{20,})$'; openrouter = '^sk-or-[A-Za-z0-9_\-]{20,}$' }
$ssh = 'C:\Program Files\Git\usr\bin\ssh.exe'
$chaveSsh = Join-Path $env:USERPROFILE '.ssh\a12_termux'
$script:alvo = ''
$script:opts = @('-i', $chaveSsh, '-p', '8022', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=10')
$script:cod = 0
$script:tentouLigar = $false   # ja mandei ligar o OmniRoute do celular (o finally desliga se algo der errado ou o Ctrl+C vier)
$script:esperouChaves = $false # a area de transferencia pode ter chave (o finally limpa)

function Preparar {
    foreach ($f in $ssh, $chaveSsh) { if (-not (Test-Path -LiteralPath $f)) { throw "nao encontrei: $f" } }
    if ((& adb devices 2>&1 | Out-String) -notmatch '\tdevice') { throw 'o A12 nao esta no ADB (cabo e depuracao USB).' }
    if ((& adb shell 'getprop ro.product.model' 2>&1 | Out-String) -notmatch 'SM-A125') { throw 'aparelho inesperado (nao e o SM-A125M).' }
    $uid = ((& adb shell 'dumpsys package com.termux' 2>&1 | Out-String) -split "`n" | Where-Object { $_ -match '^\s*userId=(\d+)' } | Select-Object -First 1)
    if ($uid -notmatch 'userId=(\d+)') { throw 'nao consegui ler o uid do Termux.' }
    $script:alvo = 'u0_a' + ([int]$Matches[1] - 10000) + '@127.0.0.1'
    & cmd.exe /c 'adb forward tcp:8022 tcp:8022 >nul 2>&1'
}
function Celular { # executa no Termux; $Entrada (opcional) vai pela ENTRADA PADRAO do ssh. Devolve a saida (as mensagens do omni-local nunca trazem chave)
    param([string]$Comando, [string]$Entrada = '')
    $opcoes = $script:opts
    $destino = $script:alvo
    if ($Entrada) { $o = $Entrada | & $ssh @opcoes $destino $Comando 2>&1 } else { $o = & $ssh @opcoes $destino $Comando 2>&1 }
    $script:cod = $LASTEXITCODE
    return (($o | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" } }) -join "`n").Trim()
}
function Instalar-Ajudante {
    $dir = Join-Path $PSScriptRoot 'omniroute-celular'
    foreach ($nome in 'omni-local.sh', 'omni-local.combos.json') {
        & pwsh -NoProfile -File (Join-Path $PSScriptRoot 'termux.ps1') -Copiar (Join-Path $dir $nome) -Para '~/bin/' | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "nao consegui copiar $nome para o Termux." }
    }
    $r = Celular 'cd ~/bin && mv -f omni-local.sh omni-local && chmod 700 omni-local && bash -n omni-local && echo ajudante-ok'
    if ($r -notmatch 'ajudante-ok') { throw "o ajudante nao ficou certo no celular: $r" }
}
function Limpa-AreaDeTransferencia {
    try { Set-Clipboard -Value $null } catch { try { Set-Clipboard -Value ' ' } catch { } }
}

function Limpa-SeTiverChave { # limpa a area so se o que esta nela ainda tem cara de chave de provedor (nao apaga outra coisa que o Rafael copiou)
    try { $atual = Get-Clipboard -Raw -ErrorAction Stop } catch { return }
    if ($atual -and $atual.Trim() -match '^(nvapi-|sk-or-|AIza|AQ\.)') { Limpa-AreaDeTransferencia }
}

try {
    Preparar
    if ($Status) { Write-Host (Celular 'bash ~/bin/omni-local status'); exit 0 }
    if ($Desligar) { Write-Host (Celular 'bash ~/bin/omni-local desligar'); exit $script:cod }
    if ($Tirar) {
        if (-not $FORMATOS.Contains($Tirar)) { throw "provedor desconhecido: $Tirar (use nvidia, gemini ou openrouter)" }
        Write-Host (Celular ('bash ~/bin/omni-local tirar ' + $Tirar)); exit $script:cod
    }
    if (-not $Ativar) { Write-Host 'Use -Ativar, -Status, -Desligar ou -Tirar <provedor>. Veja o cabecalho do script.'; exit 0 }

    foreach ($p in $Provedores) { if (-not $FORMATOS.Contains($p)) { throw "provedor desconhecido: $p (use nvidia, gemini ou openrouter)" } }
    Instalar-Ajudante
    Write-Host 'Ligando o OmniRoute do celular (leva de 1 a 2 minutos)...'
    $script:tentouLigar = $true
    $r = Celular 'bash ~/bin/omni-local ligar'
    Write-Host $r
    if ($script:cod -ne 0) { throw 'o OmniRoute do celular nao ligou.' }

    $faltam = New-Object System.Collections.ArrayList
    foreach ($p in $Provedores) { [void]$faltam.Add($p) }
    $recebidos = New-Object System.Collections.ArrayList
    $ultimo = ''
    $falhaEm = $null
    $falhas = 0
    $chaveDaFalha = $null
    $script:esperouChaves = $true
    if (Get-Process -Name 'kdeconnectd' -ErrorAction SilentlyContinue) {
        Write-Host 'AVISO: o KDE Connect esta ligado e pode espelhar a area de transferencia do PC no celular (plugin "Area de transferencia"): a chave iria tambem para a area de transferencia do A12. Se nao quiser isso, desligue esse plugin do A12 no KDE Connect antes de copiar.' -ForegroundColor Yellow
    }
    $fim = (Get-Date).AddMinutes($Minutos)
    Write-Host ('Esperando as chaves ate ' + $fim.ToString('HH:mm') + ' (faltam: ' + ($faltam -join ', ') + '). Crie e COPIE (Ctrl+C) uma chave por vez; eu detecto sozinho.')
    while ($faltam.Count -gt 0 -and (Get-Date) -lt $fim) {
        # depois de uma falha, a MESMA chave ainda copiada e tentada de novo (ate 3 falhas da mesma chave, a cada 25 s): erro de rede passa; chave errada para por aqui
        if ($falhaEm -and $falhas -lt 3 -and ((Get-Date) - $falhaEm).TotalSeconds -gt 25) { $ultimo = ''; $falhaEm = $null }
        $texto = $null
        try { $texto = Get-Clipboard -Raw -ErrorAction Stop } catch { $texto = $null }
        if ($texto -and $texto.Length -le 300) {
            $t = $texto.Trim()
            if ($t -ne $ultimo) {
                $ultimo = $t
                $reconhecida = $false
                foreach ($p in @($faltam)) {
                    if ($t -match $FORMATOS[$p]) {
                        $reconhecida = $true
                        if ($t -ne $chaveDaFalha) { $falhas = 0 }   # chave diferente da que falhou: comeca a contar de novo
                        Write-Host "[$p] chave detectada na area de transferencia; enviando ao celular..."
                        $r = Celular ('bash ~/bin/omni-local provedor ' + $p) $t
                        Write-Host $r
                        if ($script:cod -eq 0) { [void]$faltam.Remove($p); [void]$recebidos.Add($p); Limpa-AreaDeTransferencia; $ultimo = ''; $falhas = 0; $chaveDaFalha = $null }
                        else {
                            $falhas++; $falhaEm = Get-Date; $chaveDaFalha = $t
                            if ($falhas -lt 3) { Write-Host "[$p] falhou (falha $falhas de 3): tento de novo em 25 s se a chave continuar copiada; se ela estiver errada, crie e copie outra." }
                            else { Write-Host "[$p] falhou pela 3a vez: desisti desta chave; crie e copie outra." }
                        }
                        break
                    }
                }
                if (-not $reconhecida) {
                    $jaTem = @($recebidos | Where-Object { $t -match $FORMATOS[$_] })
                    if ($jaTem.Count -gt 0) { Write-Host ('[' + $jaTem[0] + '] ja recebi uma chave deste provedor nesta rodada; ignorei esta (para trocar, rode de novo com -Ativar -Provedores ' + $jaTem[0] + ').') }
                    elseif ($t -match '^(nvapi-|sk-or-|AIza|AQ\.)') { Write-Host ('Copiou so um PEDACO de chave (' + $t.Length + ' caracteres; a completa tem uns 70 na NVIDIA e na OpenRouter): use o botao COPIAR do site logo depois de criar a chave, sem selecionar o texto com o mouse; ignorei.') }
                    elseif ($t -match '^[A-Za-z0-9._\-]{20,200}$') { Write-Host ('Copiou um texto de ' + $t.Length + ' caracteres com cara de chave, mas sem o formato de nenhum provedor que falta (nvapi-, AIza ou AQ., sk-or-); ignorei.') }
                }
            }
        }
        $t = $null; $texto = $null
        Start-Sleep -Milliseconds 700
    }
    $ultimo = $null; $chaveDaFalha = $null
    Limpa-SeTiverChave   # chave que falhou ou foi ignorada nao pode ficar copiada depois do fim
    if ($faltam.Count -gt 0) { Write-Host ('Sem chave de: ' + ($faltam -join ', ') + '.') }
    if ($recebidos.Count -eq 0) {
        Write-Host 'Nenhuma chave foi aceita; nada foi mudado na reserva (se ela ja estava pronta, continua como estava).'
        if (-not $ManterLigado) { Write-Host (Celular 'bash ~/bin/omni-local desligar'); $script:tentouLigar = $false }
        exit 1
    }
    Write-Host (Celular 'bash ~/bin/omni-local combos')
    Write-Host (Celular 'bash ~/bin/omni-local testar')
    $r = Celular 'bash ~/bin/omni-local pronto'
    Write-Host $r
    $pronto = ($script:cod -eq 0)
    if (-not $ManterLigado) { Write-Host (Celular 'bash ~/bin/omni-local desligar'); $script:tentouLigar = $false }
    if ($pronto) { Write-Host 'RESERVA PRONTA: com o PC fora do ar, o ia passa a ligar o OmniRoute do celular sozinho.' }
    else { Write-Host 'Reserva NAO ficou pronta: o combo codigo nao respondeu (veja as linhas acima); o arquivo pronto antigo, se havia, foi apagado.' }
    exit $(if ($pronto) { 0 } else { 1 })
}
catch {
    Write-Host ('ABORTADO: ' + $_.Exception.Message) -ForegroundColor Red
    exit 2
}
finally {
    # erro, Ctrl+C ou saida antecipada: nao deixa o node ligado no A12 (a menos que -ManterLigado) nem a chave copiada no PC
    if ($script:esperouChaves) { Limpa-SeTiverChave }
    if ($script:tentouLigar -and -not $ManterLigado) {
        try { [void](Celular 'bash ~/bin/omni-local desligar') } catch { }
    }
}
