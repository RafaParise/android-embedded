# fortigate-wol.ps1 - aplica (ou desfaz) no FortiGate 60D a regra que deixa o celular acordar o PC (Wake-on-LAN).
# Quem roda e o Rafael (duplo clique em fortigate-wol.cmd). A SENHA e digitada por ele na janela, direto no plink;
# este script nunca a ve, nunca a grava e nunca a passa por argumento.
#
# O que a regra faz: o pacote magico que o celular manda (ligar-pc no Termux) para a wan1 do FortiGate (UDP 9) e
# repassado ao PC (10.0.20.100) na rede do cabo; uma entrada fixa de ARP faz o FortiGate entregar mesmo com o PC
# desligado (desligado, o PC nao responde ARP). So a rede de casa (192.168.1.0/24) pode mandar.
#
# Uso:  fortigate-wol.cmd            aplica
#       fortigate-wol.cmd -Desfazer  remove tudo o que este script criou
#       fortigate-wol.cmd -Conferir  so mostra (nao muda nada)
#       fortigate-wol.cmd -Simular   nao conecta: so mostra os comandos que mandaria
param([switch]$Desfazer, [switch]$Conferir, [switch]$Simular, [string]$Usuario = '')
$ErrorActionPreference = 'Stop'

$plink = 'C:\Program Files\PuTTY\plink.exe'
$fortigate = '10.0.20.1'
$wan1 = '192.168.1.40'
$pcIp = '10.0.20.100'
# chave do SSH do FortiGate vista em 19/11/2026 (ssh-keyscan + ssh-keygen -l): se mudar, o plink recusa (protege de impostor)
$chaveFortigate = 'SHA256:9PVngalCAzkLJizSAK6etikhRb/08co/L6lkfOvf5y8'
# Convive com o univo-sync (13/11, scripts/provisionar_rede.py): ele ja cria o ARP fixo do PC (entrada 1), o servico
# WOL_UDP9 e a regra 11 (A12 na DMZ acorda o PC). Aqui os dois primeiros vao com os MESMOS valores e entra so o caminho
# da rede da operadora (VIP na wan1 + regra). O desfazer nao apaga o que e do univo-sync.
$arpId = 1
$nomePolitica = 'WOL_CELULAR_PARA_PC'
$pasta = Join-Path $PSScriptRoot '..\diagnostico'
$log = Join-Path $pasta ('fortigate-wol-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')

if (-not (Test-Path $plink)) { throw 'PuTTY/plink nao encontrado em C:\Program Files\PuTTY.' }
$mac = (Get-NetAdapter -Name 'Cabo FortiGate 60D' -ErrorAction SilentlyContinue).MacAddress
if (-not $mac) { throw 'Nao achei a placa "Cabo FortiGate 60D" neste PC.' }
$mac = $mac.Replace('-', ':').ToLower()

# FortiOS 5.4 (este 60D) nao aceita "set name" na politica (19/11: "node_check_object fail"): vai em "comments", e a
# politica e achada pelo destino VIP_WOL_PC, para rodar de novo sem duplicar.
$cmdAchar = 'show firewall policy | grep -f VIP_WOL_PC'
function Ids-Da-Politica([string]$saida) {
    @([regex]::Matches($saida, '(?m)^\s*edit (\d+)\s*$') | ForEach-Object { $_.Groups[1].Value } | Where-Object { $_ -ne '0' } | Select-Object -Unique)
}
$cmdAplicarModelo = @"
config system arp-table
edit $arpId
set interface "internal"
set ip $pcIp
set mac $mac
next
end
config firewall address
edit "REDE_OPERADORA"
set subnet 192.168.1.0 255.255.255.0
set comment "Rede do roteador da operadora"
next
end
config firewall service custom
edit "WOL_UDP9"
set protocol TCP/UDP/SCTP
set udp-portrange 9
next
end
config firewall vip
edit "VIP_WOL_PC"
set extintf "wan1"
set extip $wan1
set portforward enable
set protocol udp
set extport 9
set mappedport 9
set mappedip "$pcIp"
set comment "Celular acorda o PC (ligar-pc)"
next
end
config firewall policy
edit IDPOLITICA
set comments "$nomePolitica"
set srcintf "wan1"
set dstintf "internal"
set srcaddr "REDE_OPERADORA"
set dstaddr "VIP_WOL_PC"
set action accept
set schedule "always"
set service "WOL_UDP9"
set logtraffic all
next
end
show system arp-table
show firewall vip VIP_WOL_PC
show firewall policy | grep -f VIP_WOL_PC
"@

$cmdConferir = @"
show system arp-table
show firewall vip VIP_WOL_PC
show firewall policy | grep -f VIP_WOL_PC
"@

function Rodar([string]$comandos, [string]$titulo) {
    $arq = Join-Path $env:TEMP ('fgt-' + [guid]::NewGuid().ToString('N') + '.txt')
    [IO.File]::WriteAllText($arq, ($comandos -replace "`r`n", "`n"))
    try {
        Write-Host ''
        Write-Host "== $titulo ==" -ForegroundColor Cyan
        if ($Simular) { Write-Host ('[simulacao] mandaria ao FortiGate ' + $fortigate + ' como ' + $script:usuario + ':'); $comandos | Tee-Object -FilePath $log -Append | Out-Host; return '' }
        Write-Host 'Digite a senha do FortiGate quando ele pedir (nada aparece enquanto digita; de fabrica e vazia: so Enter).' -ForegroundColor Yellow
        # sem 2>&1: o pedido de senha do plink vai direto para a janela (pelo pipe ele so apareceria depois)
        $saida = & $plink -ssh -P 22 -hostkey $chaveFortigate -l $script:usuario -m $arq $fortigate | Tee-Object -FilePath $log -Append
        $saida | Out-Host
        return (@($saida) -join "`n")
    } finally { Remove-Item $arq -Force -ErrorAction SilentlyContinue }
}

New-Item -ItemType Directory -Force -Path $pasta | Out-Null
$script:usuario = if ($Usuario) { $Usuario } else { Read-Host 'Usuario do FortiGate (Enter = admin)' }
if ([string]::IsNullOrWhiteSpace($script:usuario)) { $script:usuario = 'admin' }
if ($script:usuario -notmatch '^[A-Za-z0-9._-]{1,32}$') { throw 'Usuario fora do formato.' }

if ($Conferir) {
    Rodar $cmdConferir 'Conferindo (nao muda nada)' | Out-Null
} elseif ($Desfazer) {
    $ids = @(Ids-Da-Politica (Rodar $cmdAchar 'Achando a regra para remover'))
    $remover = "config firewall policy`n" + (($ids | ForEach-Object { "delete $_" }) -join "`n") + "`nend`nconfig firewall vip`ndelete `"VIP_WOL_PC`"`nend`nconfig firewall address`ndelete `"REDE_OPERADORA`"`nend`n"
    Write-Host ("Politicas a remover: " + ($(if ($ids) { $ids -join ', ' } else { 'nenhuma' })))
    Rodar $remover 'Removendo' | Out-Null
} else {
    $existentes = @(Ids-Da-Politica (Rodar $cmdAchar 'Procurando a regra (se ja existe, e editada; nao duplica)'))
    $id = if ($existentes) { $existentes[0] } else { '0' }
    $cmdAplicar = $cmdAplicarModelo.Replace('edit IDPOLITICA', "edit $id")
    if ($existentes.Count -gt 1) {   # regra repetida de uma tentativa antiga: fica so a primeira
        $cmdAplicar = "config firewall policy`n" + (($existentes | Select-Object -Skip 1 | ForEach-Object { "delete $_" }) -join "`n") + "`nend`n" + $cmdAplicar
    }
    Write-Host ("Regra: " + $(if ($id -eq '0') { 'nova' } else { "editando a $id" }))
    $texto = Rodar $cmdAplicar 'Aplicando e conferindo a regra do Wake-on-LAN'
    $ok = ($texto -match 'set dstaddr "VIP_WOL_PC"') -and ($texto -match [regex]::Escape($mac)) -and ($texto -notmatch 'Command fail')
    Write-Host ''
    if ($Simular) {
        Write-Host 'SIMULACAO: nada foi mandado ao FortiGate.' -ForegroundColor Yellow
    } elseif ($ok) {
        Write-Host 'PRONTO: a regra esta no FortiGate. Teste: desligue o PC e rode "ligar-pc" no Termux do celular.' -ForegroundColor Green
    } else {
        Write-Host 'Algo nao ficou gravado. Mande ao Claude o arquivo de registro:' -ForegroundColor Red
    }
    if (-not $Simular -and $texto -match 'Command fail|Unknown action|entry not found|parse error|Access denied') {
        Write-Host 'O FortiGate respondeu com erro em algum comando (veja o registro).' -ForegroundColor Red
    }
}
Write-Host "Registro (sem senha): $log"
