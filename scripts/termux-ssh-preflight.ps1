# Confere no PC, numa rodada so, o que falta para o SSH Termux->Tailscale (memoria\nuvem\termux-ssh-tailscale.md)
# funcionar: se o sshd esta instalado, se o usuario e administrador (decide onde vai a chave publica),
# o sshd_config atual e a saida de 'tailscale serve --help'/'tailscale status'. NAO MUDA NADA no PC
# (so leitura); o objetivo e o Claude local ler so o resumo em vez de digitar cada comando a mao.
#
# ATENCAO: escrito na nuvem, sem PowerShell real para testar (NUVEM.md: pwsh nao existe na VM da
# nuvem). Revisado linha a linha, mas rode uma vez e confira a saida antes de confiar.
#
# Uso: pwsh -NoProfile -File scripts\termux-ssh-preflight.ps1 [-Usuario passo]
param([string]$Usuario = 'passo')
$ErrorActionPreference = 'Continue'

function Linha($t) { Write-Host $t }
# 'cmd 2>&1': no Windows PowerShell 5.1 e no 7 a linha do stderr chega como ErrorRecord; so a mensagem interessa (sem o "At line:...")
function TextoNativo($r) { if ($r -is [System.Management.Automation.ErrorRecord]) { $r.Exception.Message } else { "$r" } }

Linha "=== 1/5 OpenSSH Server (sshd) ==="
$svc = Get-Service -Name sshd -ErrorAction SilentlyContinue
if ($svc) {
    Linha "  instalado: SIM | status: $($svc.Status) | inicio: $($svc.StartType)"
    if ($svc.Status -ne 'Running') { Linha "  AVISO: nao esta rodando agora. Para iniciar: Start-Service sshd" }
    if ($svc.StartType -ne 'Automatic') { Linha "  AVISO: nao inicia sozinho no boot. Para corrigir: Set-Service -Name sshd -StartupType Automatic" }
} else {
    Linha "  instalado: NAO"
    Linha "  Para instalar: Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0"
    Linha "  Depois: Start-Service sshd ; Set-Service -Name sshd -StartupType Automatic"
}

Linha "`n=== 2/5 Usuario '$Usuario' e administrador? (decide onde colar a chave publica do celular) ==="
try {
    $grupoAdmin = Get-LocalGroup -SID 'S-1-5-32-544' -ErrorAction Stop   # SID fixo do BUILTIN\Administrators, independe do idioma do Windows
    $membros = @(Get-LocalGroupMember -Group $grupoAdmin -ErrorAction Stop)
    $ehAdmin = @($membros | Where-Object { $_.Name -like "*\$Usuario" }).Count -gt 0
    Linha "  (automatico) $Usuario no grupo de administradores: $(if ($ehAdmin) { 'SIM' } else { 'NAO' })"
} catch {
    $ehAdmin = $null
    Linha "  (automatico) nao consegui checar: $($_.Exception.Message)"
    Linha "  confira a mao: net user $Usuario   (veja a linha 'Local Group Memberships')"
}
if ($ehAdmin -eq $true) {
    Linha "  => chave publica do celular vai em: C:\ProgramData\ssh\administrators_authorized_keys"
    Linha "     (o Windows OpenSSH IGNORA .ssh\authorized_keys da pasta do usuario para administradores)"
} elseif ($ehAdmin -eq $false) {
    Linha "  => chave publica do celular vai em: $env:SystemDrive\Users\$Usuario\.ssh\authorized_keys"
} else {
    Linha "  => confirme a mao (acima) antes de decidir onde colar a chave"
}

Linha "`n=== 3/5 sshd_config atual (so as 3 chaves que o hardening do A2 pede) ==="
$cfg = 'C:\ProgramData\ssh\sshd_config'
if (Test-Path -LiteralPath $cfg) {
    $linhas = @(Get-Content -LiteralPath $cfg -ErrorAction SilentlyContinue |
        Where-Object { $_ -match '^\s*(PasswordAuthentication|PubkeyAuthentication|ListenAddress)\b' })
    if ($linhas.Count -gt 0) { $linhas | ForEach-Object { Linha "  $_" } }
    else { Linha "  nenhuma das 3 definida ainda (valores padrao do OpenSSH valem ate voce adicionar)" }
} else {
    Linha "  arquivo nao encontrado em $cfg"
}

Linha "`n=== 4/5 Tailscale: status e 'serve --help' (resolve a lacuna do A2) ==="
$tsPath = Get-Command tailscale -ErrorAction SilentlyContinue
if (-not $tsPath) {
    Linha "  'tailscale' nao esta no PATH deste PowerShell. Rode de novo num terminal onde 'tailscale status' funcione."
} else {
    Linha "  tailscale status (resumo):"
    & tailscale status 2>&1 | Select-Object -First 6 | ForEach-Object { Linha ("    " + (TextoNativo $_)) }
    Linha "  tailscale serve --help:"
    & tailscale serve --help 2>&1 | ForEach-Object { Linha ("    " + (TextoNativo $_)) }
}

Linha "`n=== 5/5 Regra do Firewall 'OpenSSH SSH Server' (RDP e KDE Connect ja usam LocalSubnet+100.64.0.0/10 neste PC) ==="
try {
    $regras = @(Get-NetFirewallRule -DisplayName 'OpenSSH SSH Server*' -ErrorAction Stop)
    if ($regras.Count -eq 0) {
        Linha "  nenhuma regra 'OpenSSH SSH Server' encontrada (normal se o sshd nunca foi instalado)"
    } else {
        foreach ($r in $regras) {
            $end = $r | Get-NetFirewallAddressFilter -ErrorAction SilentlyContinue
            Linha "  $($r.Name) | perfil: $($r.Profile) | habilitada: $($r.Enabled) | endereco remoto: $($end.RemoteAddress -join ', ')"
        }
        Linha "  Se for seguir o caminho do Firewall por CIDR (em vez de 'tailscale serve'): troque o endereco remoto para LocalSubnet,100.64.0.0/10"
        Linha "  (mesmo padrao do RDP e do KDE Connect neste PC, DECISOES.md 27/10 e 28/10):"
        Linha "    Get-NetFirewallRule -DisplayName 'OpenSSH SSH Server*' | Set-NetFirewallRule -RemoteAddress LocalSubnet,100.64.0.0/10"
    }
} catch {
    Linha "  nao consegui ler a regra: $($_.Exception.Message)"
}

Linha "`nResumo acima; decida com memoria\nuvem\termux-ssh-tailscale.md do lado. Nada foi alterado no PC."
