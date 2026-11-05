# adguard-pc.ps1 - instala e cuida do AdGuard Home no PC (bloqueador de anuncios por DNS para o celular, so pela Tailscale).
# Uso (terminal de administrador; o instalador pode repetir sem estragar):
#   pwsh -NoProfile -File scripts\adguard-pc.ps1 -Instalar      baixa a versao fixa, confere o SHA-256, cria o servico e o firewall, configura
#   pwsh -NoProfile -File scripts\adguard-pc.ps1 -Status        servico, porta e teste de DNS (o dia a dia e pelo adguard-pc.py)
#   pwsh -NoProfile -File scripts\adguard-pc.ps1 -Reiniciar     reinicia o servico (depois de a Tailscale voltar, se o DNS nao responder)
#   pwsh -NoProfile -File scripts\adguard-pc.ps1 -Desinstalar   apaga servico e firewall; dados e regras ficam (ProgramData) para voce apagar a mao
#                                                               ANTES: tire o nameserver do PC do painel da Tailscale (login.tailscale.com/admin/dns), senao o celular fica sem DNS
# Decisoes (memoria/ADGUARD-PC.md): DNS SO no IP da tailnet (a porta 53 de 0.0.0.0 e do ICS do Windows); painel SO em 127.0.0.1:3000; servico em LOCAL SERVICE, nao SYSTEM,
# com o programa em Program Files (usuario comum nao troca o .exe) e os dados em ProgramData; firewall so para a faixa da Tailscale.
param([switch]$Instalar, [switch]$Status, [switch]$Reiniciar, [switch]$Desinstalar, [string]$IpDns = '100.64.0.1')
$ErrorActionPreference = 'Continue'   # programa nativo escrevendo em stderr nao pode virar excecao no Windows PowerShell 5.1; toda falha real aqui e 'throw'
$Versao = 'v0.107.79'
$Zip = 'AdGuardHome_windows_amd64.zip'
$Url = "https://github.com/AdguardTeam/AdGuardHome/releases/download/$Versao"
$Pasta = Join-Path $env:ProgramFiles 'AdGuardHome'
$Dados = Join-Path $env:ProgramData 'AdGuardHome'
$Exe = Join-Path $Pasta 'AdGuardHome.exe'
$Yaml = Join-Path $Dados 'AdGuardHome.yaml'
$Servico = 'AdGuardHome'
$Regra = 'AdGuard Home DNS (somente tailnet)'
$Py = Join-Path $PSScriptRoot 'adguard-pc.py'

function Ok([string]$m) { Write-Host "  ok  $m" -ForegroundColor Green }
function Aviso([string]$m) { Write-Host "  !!  $m" -ForegroundColor Yellow }
function EhAdmin { ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) }
function AchaPy { $c = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1; if (-not $c) { throw 'python nao encontrado' }; $c.Source }
function ServicoObj { Get-Service -Name $Servico -ErrorAction SilentlyContinue }

function BaixaConferido {
    $tmp = Join-Path $env:TEMP ('adguard-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    [void](New-Item -ItemType Directory -Force $tmp)
    $arq = Join-Path $tmp $Zip
    Invoke-WebRequest "$Url/$Zip" -OutFile $arq -UseBasicParsing
    Invoke-WebRequest "$Url/checksums.txt" -OutFile (Join-Path $tmp 'checksums.txt') -UseBasicParsing
    $linha = Get-Content (Join-Path $tmp 'checksums.txt') | Where-Object { $_ -match [regex]::Escape($Zip) } | Select-Object -First 1
    if (-not $linha) { throw "checksums.txt sem a linha de $Zip" }
    $esperado = ($linha -split '\s+')[0]
    $obtido = (Get-FileHash $arq -Algorithm SHA256).Hash
    if ($esperado -ine $obtido) { throw "SHA-256 NAO confere (esperado $esperado, obtido $obtido): nada foi instalado" }
    Ok "SHA-256 conferido ($($obtido.Substring(0, 16))...)"
    Expand-Archive $arq -DestinationPath $tmp -Force
    $novo = Join-Path $tmp 'AdGuardHome\AdGuardHome.exe'
    if (-not (Test-Path -LiteralPath $novo)) { throw 'o zip nao trouxe AdGuardHome\AdGuardHome.exe' }
    return $tmp
}

function CriaFirewall {
    Get-NetFirewallRule -DisplayName $Regra -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    foreach ($proto in 'UDP', 'TCP') {
        [void](New-NetFirewallRule -DisplayName $Regra -Direction Inbound -Action Allow -Protocol $proto -LocalPort 53 -LocalAddress $IpDns -RemoteAddress 100.64.0.0/10 -Program $Exe -Profile Any)
    }
    Ok 'Firewall: porta 53 so da faixa da Tailscale para o IP da tailnet do PC'
}

function DaAcessoAoServico {
    # LOCAL SERVICE so escreve nos dados; o programa fica somente leitura para ele
    [void](New-Item -ItemType Directory -Force $Dados)
    & icacls $Dados /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-19:(OI)(CI)M' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'icacls falhou na pasta de dados' }
}

function ProtegeAcesso {
    $a = 'C:\Projetos\adguard-home\acesso.json'
    if (Test-Path -LiteralPath $a) {
        & icacls $a /inheritance:r /grant:r "${env:USERNAME}:F" | Out-Null
        if ($LASTEXITCODE -eq 0) { Ok "Acesso guardado em $a (so este usuario le; fora do git)" } else { Aviso "nao consegui restringir $a" }
    }
}

function RodaPy([string[]]$a) {
    # a saida do Python vai para a tela; a funcao devolve SO o codigo (sem o Out-Host, o texto entraria no valor de retorno e o -ne 0 daria sempre verdadeiro)
    & (AchaPy) -I -B $Py @a | Out-Host
    return $LASTEXITCODE
}

function EsperaPainel([int]$segundos = 40) {
    for ($i = 0; $i -lt $segundos; $i++) {
        try { [void](Invoke-WebRequest 'http://127.0.0.1:3000/' -UseBasicParsing -TimeoutSec 3 -MaximumRedirection 0 -ErrorAction Stop); return $true }
        catch { if ($_.Exception.Response) { return $true } }
        Start-Sleep -Seconds 1
    }
    return $false
}

try {
    if ($Status) {
        $s = ServicoObj
        if (-not $s) { Aviso 'servico nao instalado (use -Instalar)'; exit 1 }
        Write-Host ("Servico: {0}" -f $s.Status)
        exit (RodaPy @('status'))
    }
    if ($Reiniciar) {
        if (-not (EhAdmin)) { throw 'abra um terminal de administrador' }
        Restart-Service $Servico -Force
        if (EsperaPainel) { Ok 'Servico reiniciado' } else { throw 'o painel nao voltou em 40 s' }
        exit 0
    }
    if ($Desinstalar) {
        if (-not (EhAdmin)) { throw 'abra um terminal de administrador' }
        Aviso 'ANTES de apagar: o nameserver deste PC precisa ja ter saido do painel da Tailscale (login.tailscale.com/admin/dns); se ainda estiver la, o celular fica sem DNS.'
        if (ServicoObj) {
            Stop-Service $Servico -Force -ErrorAction SilentlyContinue
            & sc.exe delete $Servico | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "sc delete falhou (codigo $LASTEXITCODE): o servico $Servico continua registrado." }
            Ok 'Servico apagado'
        }
        Get-NetFirewallRule -DisplayName $Regra -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
        Ok 'Firewall apagado'
        Aviso "Dados e regras continuam em $Dados e o programa em $Pasta : apague a mao se quiser. Tire tambem o nameserver do PC do painel da Tailscale ANTES (login.tailscale.com/admin/dns)."
        exit 0
    }
    if (-not $Instalar) { throw 'diga -Instalar, -Status, -Reiniciar ou -Desinstalar' }

    Write-Host '== AdGuard Home no PC ==' -ForegroundColor Cyan
    if (-not (EhAdmin)) { throw 'abra um terminal de administrador (servico e firewall exigem)' }
    if (-not (Get-NetIPAddress -IPAddress $IpDns -ErrorAction SilentlyContinue)) { throw "o IP $IpDns nao esta neste PC: a Tailscale esta conectada?" }
    if (-not (Test-Path -LiteralPath $Exe)) {
        $tmp = BaixaConferido
        try {
            [void](New-Item -ItemType Directory -Force $Pasta)
            Copy-Item (Join-Path $tmp 'AdGuardHome\*') $Pasta -Recurse -Force
        } finally { [System.IO.Directory]::Delete($tmp, $true) }
        Ok "Programa $Versao em $Pasta"
    } else { Ok "Programa ja estava em $Pasta" }
    DaAcessoAoServico
    $jaExistia = [bool](ServicoObj)
    if (-not $jaExistia) {
        Push-Location $Pasta
        try { & $Exe -s install -c $Yaml -w $Dados --no-check-update -h 127.0.0.1 -p 3000 2>&1 | Out-Null } finally { Pop-Location }
        if (-not (ServicoObj)) { throw 'o servico nao foi criado' }
        Stop-Service $Servico -Force -ErrorAction SilentlyContinue
    } else { Ok 'Servico ja existia' }
    # a conta, o inicio e a recuperacao sao aplicados SEMPRE (idempotente): se um 'sc config' falhou numa execucao anterior, repetir -Instalar conserta
    $contaAntes = "$((Get-CimInstance Win32_Service -Filter "Name='$Servico'" -ErrorAction SilentlyContinue).StartName)"
    & sc.exe config $Servico obj= 'NT AUTHORITY\LocalService' password= '""' start= delayed-auto | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'sc config falhou' }
    & sc.exe failure $Servico reset= 3600 actions= restart/30000/restart/60000/restart/120000 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'sc failure falhou' }
    $conta = "$((Get-CimInstance Win32_Service -Filter "Name='$Servico'" -ErrorAction SilentlyContinue).StartName)"
    if ($conta -notmatch 'LocalService') { throw "o servico ficou na conta '$conta', nao em LOCAL SERVICE." }
    # a conta nova so vale depois de reiniciar
    if ($jaExistia -and $contaAntes -notmatch 'LocalService' -and (ServicoObj).Status -eq 'Running') { Restart-Service $Servico -Force }
    Ok 'Servico em LOCAL SERVICE, inicio automatico atrasado, reinicia se cair'
    CriaFirewall
    if ((ServicoObj).Status -ne 'Running') { Start-Service $Servico }
    if (-not (EsperaPainel)) { throw 'o painel nao subiu em 40 s (veja o log de eventos do Windows)' }
    if ((RodaPy @('configurar', '--ip', $IpDns)) -ne 0) { throw 'a primeira configuracao falhou' }
    ProtegeAcesso
    if (-not (EsperaPainel)) { throw 'o painel nao voltou depois do assistente' }
    Start-Sleep -Seconds 3
    if ((RodaPy @('ajustar')) -ne 0) { throw 'os ajustes falharam' }
    Write-Host 'Pronto. Confira com: python scripts\adguard-pc.py status' -ForegroundColor Cyan
    exit 0
} catch {
    Write-Host ('ABORTADO: ' + $_.Exception.Message) -ForegroundColor Red
    exit 2
}
