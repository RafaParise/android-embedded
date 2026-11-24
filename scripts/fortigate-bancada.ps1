# fortigate-bancada.ps1 - aplica (ou desfaz) no FortiGate 60D a "porta 2 de bancada": o aparelho ligado no switch da
# porta 2 (internal2, LAN2 10.0.30.0/24) ganha internet e o PC consegue acessa-lo e configura-lo.
# Quem roda e o Rafael (duplo clique em fortigate-bancada.cmd). A SENHA e digitada por ele na janela, direto no plink;
# este script nunca a ve, nunca a grava e nunca a passa por argumento. (Pedido de 20/11/2026.)
#
# O que muda (e so isso):
#  1. BANCADA_INTERNET: internal2 -> wan1, toda a faixa do DHCP (10.0.30.10-150), para qualquer destino MENOS a rede
#     de casa (192.168.1.0/24, dstaddr-negate), com NAT. (20/11: as reservas .10/.11 dos controles do ARENA estao
#     VAZIAS no .env do univo-sync, entao .10 e .11 sao faixa comum: o notebook pegou o .10 e ficou sem internet.)
#  2. PC_GERENCIA_BANCADA: internal -> internal2, so do PC (PC_RYZEN) para a LAN2: ping, SSH, Termux SSH (8022), RDP,
#     WinRM (5985-5986), adb (5555) e paginas de configuracao (HTTP/HTTPS). A LAN2 continua sem entrar na rede do PC.
#  3. O DNS do FortiGate na internal2 passa a usar o filtro BLOQUEIA_TELEMETRIA (o mesmo da DMZ).
#
# Uso:  fortigate-bancada.cmd            aplica
#       fortigate-bancada.cmd -Desfazer  remove tudo o que este script criou
#       fortigate-bancada.cmd -Conferir  so mostra (nao muda nada)
#       fortigate-bancada.cmd -Simular   nao conecta: so mostra os comandos que mandaria
param([switch]$Desfazer, [switch]$Conferir, [switch]$Simular, [string]$Usuario = '')
$ErrorActionPreference = 'Stop'

$plink = 'C:\Program Files\PuTTY\plink.exe'
$fortigate = '10.0.20.1'
# a mesma chave conferida em 19/11 (fortigate-wol.ps1): se mudar, o plink recusa (protege de impostor)
$chaveFortigate = 'SHA256:9PVngalCAzkLJizSAK6etikhRb/08co/L6lkfOvf5y8'
$polInternet = 'BANCADA_INTERNET'
$polGerencia = 'PC_GERENCIA_BANCADA'
$pasta = Join-Path $PSScriptRoot '..\diagnostico'
$log = Join-Path $pasta ('fortigate-bancada-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')

if (-not $Simular -and -not (Test-Path $plink)) { throw 'PuTTY/plink nao encontrado em C:\Program Files\PuTTY.' }

# FortiOS 5.4 nao aceita "set name" na politica: o nome vai em "comments" e a politica e achada por ele (sem duplicar)
function Ids-Da-Politica([string]$saida) {
    @([regex]::Matches($saida, '(?m)^\s*edit (\d+)\s*$') | ForEach-Object { $_.Groups[1].Value } | Where-Object { $_ -ne '0' } | Select-Object -Unique)
}
$cmdAcharInternet = "show firewall policy | grep -f $polInternet"
$cmdAcharGerencia = "show firewall policy | grep -f $polGerencia"

$cmdAplicarModelo = @"
config firewall address
edit "REDE_OPERADORA"
set subnet 192.168.1.0 255.255.255.0
set comment "Rede do roteador da operadora"
next
edit "LAN2_BANCADA"
set subnet 10.0.30.0 255.255.255.0
set comment "Porta 2 inteira (switch da bancada)"
next
edit "LAN2_VISITANTES"
set type iprange
set start-ip 10.0.30.10
set end-ip 10.0.30.150
set comment "Faixa do DHCP da porta 2"
next
end
config firewall service custom
edit "GERENCIA_WINRM"
set protocol TCP/UDP/SCTP
set tcp-portrange 5985-5986
next
end
config firewall service group
edit "GERENCIA_BANCADA"
set member "PING" "SSH" "TERMUX_SSH" "RDP" "GERENCIA_WINRM" "ADB_5555" "HTTP" "HTTPS"
next
end
config firewall policy
edit IDINTERNET
set comments "$polInternet"
set srcintf "internal2"
set dstintf "wan1"
set srcaddr "LAN2_VISITANTES"
set dstaddr "REDE_OPERADORA"
set dstaddr-negate enable
set action accept
set schedule "always"
set service "ALL"
set nat enable
set logtraffic disable
next
edit IDGERENCIA
set comments "$polGerencia"
set srcintf "internal"
set dstintf "internal2"
set srcaddr "PC_RYZEN"
set dstaddr "LAN2_BANCADA"
set action accept
set schedule "always"
set service "GERENCIA_BANCADA"
set logtraffic all
next
end
config system dns-server
edit "internal2"
set mode recursive
set dnsfilter-profile "BLOQUEIA_TELEMETRIA"
next
end
show firewall policy | grep -f BANCADA
show system dns-server internal2
"@

$cmdConferir = @"
show firewall address LAN2_VISITANTES
show firewall service group GERENCIA_BANCADA
show firewall policy | grep -f BANCADA
show system dns-server internal2
"@

function Rodar([string]$comandos, [string]$titulo) {
    $arq = Join-Path $env:TEMP ('fgt-' + [guid]::NewGuid().ToString('N') + '.txt')
    [IO.File]::WriteAllText($arq, ($comandos -replace "`r`n", "`n"))
    try {
        Write-Host ''
        Write-Host "== $titulo ==" -ForegroundColor Cyan
        if ($Simular) { Write-Host ('[simulacao] mandaria ao FortiGate ' + $fortigate + ' como ' + $script:usuario + ':'); $comandos | Tee-Object -FilePath $log -Append | Out-Host; return '' }
        Write-Host 'Digite a senha do FortiGate quando ele pedir (nada aparece enquanto digita).' -ForegroundColor Yellow
        # sem 2>&1: o pedido de senha do plink vai direto para a janela
        $saida = & $plink -ssh -P 22 -hostkey $chaveFortigate -l $script:usuario -m $arq $fortigate | Tee-Object -FilePath $log -Append
        $saida | Out-Host
        return (@($saida) -join "`n")
    } finally { Remove-Item $arq -Force -ErrorAction SilentlyContinue }
}

New-Item -ItemType Directory -Force -Path $pasta | Out-Null
$script:usuario = if ($Usuario) { $Usuario } elseif ($Simular) { 'admin' } else { Read-Host 'Usuario do FortiGate (Enter = admin)' }
if ([string]::IsNullOrWhiteSpace($script:usuario)) { $script:usuario = 'admin' }
if ($script:usuario -notmatch '^[A-Za-z0-9._-]{1,32}$') { throw 'Usuario fora do formato.' }

if ($Conferir) {
    Rodar $cmdConferir 'Conferindo (nao muda nada)' | Out-Null
} elseif ($Desfazer) {
    $ids = @(Ids-Da-Politica (Rodar "show firewall policy | grep -f BANCADA" 'Achando as regras para remover'))
    $remover = "config firewall policy`n" + (($ids | ForEach-Object { "delete $_" }) -join "`n") + "`nend`n" +
        "config system dns-server`nedit `"internal2`"`nunset dnsfilter-profile`nnext`nend`n" +
        "config firewall service group`ndelete `"GERENCIA_BANCADA`"`nend`nconfig firewall service custom`ndelete `"GERENCIA_WINRM`"`nend`n" +
        "config firewall address`ndelete `"LAN2_VISITANTES`"`ndelete `"LAN2_BANCADA`"`nend`n"
    Write-Host ("Politicas a remover: " + ($(if ($ids) { $ids -join ', ' } else { 'nenhuma' })))
    Rodar $remover 'Removendo' | Out-Null
} else {
    $idI = '0'; $idG = '0'
    if (-not $Simular) {
        $idI = @(Ids-Da-Politica (Rodar $cmdAcharInternet 'Procurando a regra de internet (se ja existe, e editada)')) | Select-Object -First 1
        $idG = @(Ids-Da-Politica (Rodar $cmdAcharGerencia 'Procurando a regra de gerencia (se ja existe, e editada)')) | Select-Object -First 1
        if (-not $idI) { $idI = '0' }; if (-not $idG) { $idG = '0' }
    }
    $cmdAplicar = $cmdAplicarModelo.Replace('edit IDINTERNET', "edit $idI").Replace('edit IDGERENCIA', "edit $idG")
    $texto = Rodar $cmdAplicar 'Aplicando e conferindo a porta 2 de bancada'
    $ok = ($texto -match $polInternet) -and ($texto -match $polGerencia) -and ($texto -match 'BLOQUEIA_TELEMETRIA') -and ($texto -notmatch 'Command fail')
    Write-Host ''
    if ($Simular) {
        Write-Host 'SIMULACAO: nada foi mandado ao FortiGate.' -ForegroundColor Yellow
    } elseif ($ok) {
        Write-Host 'PRONTO: a porta 2 da internet ao aparelho e o PC o alcanca. Teste no aparelho: abrir um site.' -ForegroundColor Green
    } else {
        Write-Host 'Algo nao ficou gravado. Mande ao Claude o arquivo de registro (nao tem senha):' -ForegroundColor Red
    }
    if (-not $Simular -and $texto -match 'Command fail|Unknown action|entry not found|parse error|Access denied|node_check_object') {
        Write-Host 'O FortiGate respondeu com erro em algum comando (veja o registro).' -ForegroundColor Red
    }
}
Write-Host "Registro (sem senha): $log"
