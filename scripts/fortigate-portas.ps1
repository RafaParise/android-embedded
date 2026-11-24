# fortigate-portas.ps1 - deixa TODAS as entradas do FortiGate 60D versateis (pedido do Rafael, 20/11/2026): qualquer
# aparelho ligado nelas, antigo ou novo (celular, computador, TV, console...), pega endereco pelo DHCP e ganha
# internet; o PC alcanca e configura o que estiver ligado; os projetos (apps de teste e ARENA) continuam alcancaveis.
# Quem roda e o Rafael (duplo clique em fortigate-portas.cmd). A SENHA e digitada por ele na janela, direto no plink;
# este script nunca a ve, nunca a grava e nunca a passa por argumento. Duas conexoes: uma para ler as regras, uma para
# aplicar (duas senhas).
#
# O que fica (inclui o que o fortigate-bancada.ps1 fez; os mesmos nomes, entao nada duplica):
#   Internet (ALL, NAT, sem registro e sem inspecao = aceleracao do processador de rede; nunca para a rede de casa
#   192.168.1.0/24, por dstaddr-negate):
#     LAN1_INTERNET     portas 1 e 3-7 (internal)  faixa do DHCP 10.0.20.50-150
#     DMZ_INTERNET      DMZ (hub do A12)           faixa do DHCP 10.0.10.50-60
#     BANCADA_INTERNET  porta 2 (internal2)        faixa do DHCP 10.0.30.10-150
#   Gerencia pelo PC (ping, SSH, 8022, RDP, WinRM, adb, HTTP/HTTPS):
#     PC_GERENCIA_BANCADA  PC -> porta 2 inteira
#     PC_GERENCIA_DMZ      PC -> faixa da DMZ (antes so o A12)
#     (a LAN1 nao precisa: o PC esta no mesmo switch)
#   Projetos: DMZ_PARA_APPS_PC = aparelhos da DMZ -> apps de teste do PC (8000-8099), controle do ARENA (8780), ping
#     (a porta 2 ja tem as regras 4 e 12 do univo-sync; a LAN1 fala direto com o PC)
#   DNS do FortiGate com o filtro BLOQUEIA_TELEMETRIA na LAN1, na porta 2 e na DMZ (a DMZ ja tinha).
# As regras antigas do univo-sync (1 a 13) e a do Wake-on-LAN nao sao tocadas.
#
# Uso:  fortigate-portas.cmd            aplica (rodar de novo e seguro: edita as mesmas regras)
#       fortigate-portas.cmd -Desfazer  remove o que este script criou (as regras da porta 2 inclusive)
#       fortigate-portas.cmd -Conferir  so mostra (nao muda nada)
#       fortigate-portas.cmd -Simular   nao conecta: so mostra os comandos que mandaria
param([switch]$Desfazer, [switch]$Conferir, [switch]$Simular, [string]$Usuario = '')
$ErrorActionPreference = 'Stop'

$plink = 'C:\Program Files\PuTTY\plink.exe'
$fortigate = '10.0.20.1'
# a mesma chave conferida em 19/11 (fortigate-wol.ps1): se mudar, o plink recusa (protege de impostor)
$chaveFortigate = 'SHA256:9PVngalCAzkLJizSAK6etikhRb/08co/L6lkfOvf5y8'
$pasta = Join-Path $PSScriptRoot '..\diagnostico'
$log = Join-Path $pasta ('fortigate-portas-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
if (-not $Simular -and -not (Test-Path $plink)) { throw 'PuTTY/plink nao encontrado em C:\Program Files\PuTTY.' }

# --- as regras: nome (vai em "comments", o FortiOS 5.4 nao aceita "set name"), origem, destino, enderecos, servico
$regras = @(
    @{ n = 'LAN1_INTERNET';       src = 'internal';  dst = 'wan1';      sa = 'LAN1_DHCP';        da = 'REDE_OPERADORA'; neg = $true;  svc = '"ALL"';              nat = $true;  log = 'disable' },
    @{ n = 'DMZ_INTERNET';        src = 'dmz';       dst = 'wan1';      sa = 'DMZ_DHCP';         da = 'REDE_OPERADORA'; neg = $true;  svc = '"ALL"';              nat = $true;  log = 'disable' },
    @{ n = 'BANCADA_INTERNET';    src = 'internal2'; dst = 'wan1';      sa = 'LAN2_VISITANTES';  da = 'REDE_OPERADORA'; neg = $true;  svc = '"ALL"';              nat = $true;  log = 'disable' },
    @{ n = 'PC_GERENCIA_BANCADA'; src = 'internal';  dst = 'internal2'; sa = 'PC_RYZEN';         da = 'LAN2_BANCADA';   neg = $false; svc = '"GERENCIA_BANCADA"'; nat = $false; log = 'all' },
    @{ n = 'PC_GERENCIA_DMZ';     src = 'internal';  dst = 'dmz';       sa = 'PC_RYZEN';         da = 'DMZ_DHCP';       neg = $false; svc = '"GERENCIA_BANCADA"'; nat = $false; log = 'all' },
    @{ n = 'DMZ_PARA_APPS_PC';    src = 'dmz';       dst = 'internal';  sa = 'DMZ_DHCP';         da = 'PC_RYZEN';       neg = $false; svc = '"APPS_TESTE_PC" "ARENA_WEBSOCKET" "PING"'; nat = $false; log = 'disable' }
)

# sem paginacao: o "--More--" do FortiOS engolia os comandos seguintes (20/11)
$semPaginas = "config system console`nset output standard`nend"

$objetos = @"
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
edit "LAN1_DHCP"
set type iprange
set start-ip 10.0.20.50
set end-ip 10.0.20.150
set comment "Faixa do DHCP das portas 1 e 3-7"
next
edit "DMZ_DHCP"
set type iprange
set start-ip 10.0.10.50
set end-ip 10.0.10.60
set comment "Faixa do DHCP da DMZ"
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
"@

function Texto-Regras([hashtable]$ids) {
    $l = @('config firewall policy')
    foreach ($r in $regras) {
        $id = if ($ids.ContainsKey($r.n)) { $ids[$r.n] } else { '0' }
        $l += "edit $id", "set comments `"$($r.n)`"", "set srcintf `"$($r.src)`"", "set dstintf `"$($r.dst)`"",
              "set srcaddr `"$($r.sa)`"", "set dstaddr `"$($r.da)`""
        $l += $(if ($r.neg) { 'set dstaddr-negate enable' } else { 'set dstaddr-negate disable' })
        $l += 'set action accept', 'set schedule "always"', "set service $($r.svc)"
        $l += $(if ($r.nat) { 'set nat enable' } else { 'set nat disable' })
        $l += "set logtraffic $($r.log)", 'next'
    }
    $l += 'end'
    $l += 'config system dns-server'
    foreach ($i in 'internal', 'internal2', 'dmz') { $l += "edit `"$i`"", 'set mode recursive', 'set dnsfilter-profile "BLOQUEIA_TELEMETRIA"', 'next' }
    # anuncios bloqueados para tudo que usa o DNS do FortiGate (AdGuard DNS publico, gratis e sem conta; 20/11)
    $l += 'end', 'config system dns', 'set primary 94.140.14.14', 'set secondary 94.140.15.15', 'end'
    $l += 'show firewall policy', 'show system dns-server', 'show system dns'
    return ($l -join "`n")
}

# acha as regras ja criadas pelos comentarios, numa conexao so
function Ids-Por-Nome([string]$saida) {
    $ids = @{}
    foreach ($m in [regex]::Matches($saida, '(?ms)^\s*edit (\d+)\s*$(.*?)^\s*next\s*$')) {
        $c = [regex]::Match($m.Groups[2].Value, 'set comments "([^"]+)"')
        if ($c.Success -and -not $ids.ContainsKey($c.Groups[1].Value)) { $ids[$c.Groups[1].Value] = $m.Groups[1].Value }
    }
    return $ids
}

function Rodar([string]$comandos, [string]$titulo) {
    $arq = Join-Path $env:TEMP ('fgt-' + [guid]::NewGuid().ToString('N') + '.txt')
    [IO.File]::WriteAllText($arq, ($comandos -replace "`r`n", "`n"))
    try {
        Write-Host ''
        Write-Host "== $titulo ==" -ForegroundColor Cyan
        if ($Simular) { Write-Host ('[simulacao] mandaria ao FortiGate ' + $fortigate + ' como ' + $script:usuario + ':'); $comandos | Out-File -FilePath $log -Append -Encoding utf8; $comandos | Out-Host; return '' }
        Write-Host 'Digite a senha do FortiGate quando ele pedir (nada aparece enquanto digita).' -ForegroundColor Yellow
        $saida = & $plink -ssh -P 22 -hostkey $chaveFortigate -l $script:usuario -m $arq $fortigate
        $saida | Out-File -FilePath $log -Append -Encoding utf8
        return (@($saida) -join "`n")
    } finally { Remove-Item $arq -Force -ErrorAction SilentlyContinue }
}

New-Item -ItemType Directory -Force -Path $pasta | Out-Null
$script:usuario = if ($Usuario) { $Usuario } elseif ($Simular) { 'admin' } else { Read-Host 'Usuario do FortiGate (Enter = admin)' }
if ([string]::IsNullOrWhiteSpace($script:usuario)) { $script:usuario = 'admin' }
if ($script:usuario -notmatch '^[A-Za-z0-9._-]{1,32}$') { throw 'Usuario fora do formato.' }
$nomes = @($regras | ForEach-Object { $_.n })

if ($Conferir) {
    $ids = Ids-Por-Nome (Rodar ($semPaginas + "`nshow firewall policy`nshow system dns-server`nshow system dns") 'Conferindo (nao muda nada)')
    foreach ($n in $nomes) { Write-Host ("  {0,-20} {1}" -f $n, $(if ($ids.ContainsKey($n)) { "regra $($ids[$n])" } else { 'FALTA' })) }
} elseif ($Desfazer) {
    $ids = Ids-Por-Nome (Rodar ($semPaginas + "`nshow firewall policy") 'Achando as regras para remover')
    $del = @($nomes | Where-Object { $ids.ContainsKey($_) } | ForEach-Object { "delete $($ids[$_])" })
    $remover = "config firewall policy`n" + ($del -join "`n") + "`nend`n" +
        "config system dns-server`nedit `"internal`"`nunset dnsfilter-profile`nnext`nedit `"internal2`"`nunset dnsfilter-profile`nnext`nend`n" +
        "config firewall service group`ndelete `"GERENCIA_BANCADA`"`nend`nconfig firewall service custom`ndelete `"GERENCIA_WINRM`"`nend`n" +
        "config firewall address`ndelete `"LAN1_DHCP`"`ndelete `"DMZ_DHCP`"`ndelete `"LAN2_VISITANTES`"`ndelete `"LAN2_BANCADA`"`nend`n"
    Write-Host ("Regras a remover: " + $(if ($del) { ($del -replace 'delete ', '') -join ', ' } else { 'nenhuma' }))
    Rodar $remover 'Removendo (o DNS da DMZ continua com o filtro, que ja era do univo-sync)' | Out-Null
} else {
    $ids = @{}
    if (-not $Simular) { $ids = Ids-Por-Nome (Rodar ($semPaginas + "`nshow firewall policy") 'Lendo as regras (as que ja existem sao editadas, nada duplica)') }
    Write-Host ('Ja existem: ' + $(if ($ids.Count) { ($ids.GetEnumerator() | Where-Object { $nomes -contains $_.Key } | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ', ' } else { 'nenhuma' }))
    # 20/11: sem a quebra de linha o "end" grudava no "config firewall policy" e as regras caiam dentro do grupo
    $texto = Rodar ($semPaginas + "`n" + $objetos + "`n" + (Texto-Regras $ids)) 'Aplicando e conferindo as tres entradas'
    $faltam = @($nomes | Where-Object { $texto -notmatch "set comments `"$_`"" })
    Write-Host ''
    if ($Simular) {
        Write-Host 'SIMULACAO: nada foi mandado ao FortiGate.' -ForegroundColor Yellow
    } elseif (-not $faltam -and $texto -notmatch 'Command fail|node_check_object|parse error|entry not found') {
        Write-Host 'PRONTO: as tres entradas dao internet a qualquer aparelho e o PC alcanca o que estiver ligado.' -ForegroundColor Green
    } else {
        Write-Host ('Algo nao ficou gravado' + $(if ($faltam) { ' (faltam: ' + ($faltam -join ', ') + ')' } else { '' }) + '. Mande ao Claude o arquivo de registro (nao tem senha):') -ForegroundColor Red
    }
}
Write-Host "Registro (sem senha): $log"
