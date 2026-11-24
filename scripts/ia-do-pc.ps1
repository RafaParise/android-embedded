# Confere (e liga, se estiver desligado, menos a Tailscale: essa o Rafael conecta pelo icone dela) o que o celular usa no PC: Tailscale, OmniRoute, a ponte do projeto (ponte-pc) e as portas da tailnet.
# Uso: duplo clique em scripts\ia-do-pc.cmd   ou   pwsh -NoProfile -File scripts\ia-do-pc.ps1 [-SoVerificar]
#   -SoVerificar   nao liga nem muda nada: so mostra
# O Ollama foi removido em 13/11/2026: a porta 11434 dele sai da tailnet (o script fecha se ainda estiver aberta).
# As portas do OmniRoute (20128) e da ponte do projeto (20130) sao abertas SO para a tailnet (PC e celular). Nada fica exposto na internet nem na rede da escola.
# Desfazer a do OmniRoute:  tailscale serve --tcp=20128 off      a da ponte:  tailscale serve --tcp=20130 off      Desfazer tudo:  tailscale serve reset
param([switch]$SoVerificar, [switch]$AbrirOllama, [switch]$FecharOllama)
$ErrorActionPreference = 'Continue'
$IpEsperado = '100.64.0.1'   # o mesmo IP do comando `ia` no celular (variavel IA_PC_IP)

function Ok($t)    { Write-Host ('  [ok]  ' + $t) -ForegroundColor Green }
function Aviso($t) { Write-Host ('  [!!]  ' + $t) -ForegroundColor Yellow }
$script:nFalhas = 0
function Falha($t) { $script:nFalhas++; Write-Host ('  [--]  ' + $t) -ForegroundColor Red }
function CodigoHttp($url) {
    try { return [int](Invoke-WebRequest -Uri $url -TimeoutSec 5 -UseBasicParsing).StatusCode }
    catch { if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode } else { return 0 } }
}
function OmniNoAr { (CodigoHttp 'http://127.0.0.1:20128/v1/models') -in 200, 401 }

Write-Host ''
Write-Host '== IA do PC para o celular ==' -ForegroundColor Cyan

# 1) Tailscale
$ts = (Get-Command tailscale -ErrorAction SilentlyContinue).Source
if (-not $ts) { Falha 'Tailscale nao encontrada neste PC.'; exit 1 }
$ip = "$(& $ts ip -4 2>&1 | Select-Object -First 1)".Trim()
if ($ip -eq $IpEsperado) { Ok "Tailscale do PC conectada ($ip)" }
elseif ($ip -match '^100\.') { Aviso "O IP do PC na Tailscale e $ip (o comando ia espera $IpEsperado). No celular: IA_PC_IP=$ip ia ..." }
else { Falha 'Tailscale do PC desconectada: abra o icone dela perto do relogio e conecte.' }
$linhaCel = (& $ts status 2>&1 | Out-String) -split "`r?`n" | Where-Object { $_ -match 'samsung-a12' } | Select-Object -First 1
if ($linhaCel -match 'offline') { Aviso 'O celular aparece OFFLINE na Tailscale: abra o app Tailscale no celular e ligue a chave.' }
elseif ($linhaCel) { Ok 'Celular conectado na Tailscale' }
else { Aviso 'O celular nao aparece na lista da Tailscale.' }

# 2) OmniRoute (nuvem gratis): responde 401 sem chave, e isso e o esperado
if (OmniNoAr) { Ok 'OmniRoute no ar (porta 20128; so neste PC e na tailnet)' }
elseif ($SoVerificar) { Falha 'OmniRoute parado.' }
else {
    Aviso 'OmniRoute parado: ligando (tarefa OmniRoute)...'
    schtasks /run /tn OmniRoute | Out-Null
    for ($i = 0; $i -lt 30 -and -not (OmniNoAr); $i++) { Start-Sleep -Seconds 2 }
    if (OmniNoAr) { Ok 'OmniRoute ligou' } else { Falha 'OmniRoute nao ligou em 60 s (veja C:\Projetos\kit-ia-professor).' }
}

# 4) Portas da tailnet (tailscale serve): so a tailnet enxerga
function ServeAtivo($porta) { ((& $ts serve status 2>&1 | Out-String) -match (':' + $porta + '\b')) }
function Serve($argumentos) {
    $saida = & $ts serve @argumentos 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { Falha ('tailscale serve falhou: ' + (($saida -split "`r?`n")[0]) + ' (tente: botao direito no ia-do-pc.cmd > Executar como administrador)'); return $false }
    return $true
}
if (ServeAtivo 20128) { Ok 'Porta 20128 (OmniRoute) aberta so para a tailnet' }
elseif ($SoVerificar) { Falha 'Porta 20128 NAO esta aberta na tailnet: o celular nao alcanca a nuvem sem o cabo.' }
elseif (Serve @('--bg', '--tcp=20128', 'tcp://127.0.0.1:20128')) { Ok 'Porta 20128 (OmniRoute) aberta so para a tailnet' }

# Ollama removido em 13/11/2026: a porta 11434 nao deve ficar aberta na tailnet (algo novo nela ficaria exposto)
if (ServeAtivo 11434) {
    if ($SoVerificar) { Aviso 'Porta 11434 (Ollama, removido em 13/11) ainda aberta na tailnet: rode ia-do-pc.cmd para fechar.' }
    elseif (Serve @('--tcp=11434', 'off')) { Ok 'Porta 11434 (Ollama, removido em 13/11) fechada na tailnet' }
}
if ($AbrirOllama -or $FecharOllama) { Aviso 'O Ollama foi removido em 13/11: -AbrirOllama e -FecharOllama nao fazem mais nada.' }

# 5) Ponte do projeto (ponte-pc, porta 20130): projeto ao vivo, skills e caixa de recados para o Qwen do celular (MCP). So tailnet.
function PonteNoAr { (CodigoHttp 'http://127.0.0.1:20130/saude') -eq 200 }
if (PonteNoAr) { Ok 'Ponte do projeto no ar (porta 20130; so neste PC e na tailnet)' }
elseif ($SoVerificar) { Falha 'Ponte do projeto parada: rode scripts\ponte-pc.ps1 -Iniciar.' }
elseif (Get-ScheduledTask -TaskName 'PontePC' -ErrorAction SilentlyContinue) {
    Aviso 'Ponte do projeto parada: ligando (tarefa PontePC)...'
    Start-ScheduledTask -TaskName 'PontePC'
    for ($i = 0; $i -lt 15 -and -not (PonteNoAr); $i++) { Start-Sleep -Seconds 1 }
    if (PonteNoAr) { Ok 'Ponte do projeto ligou' } else { Falha 'A ponte nao ligou em 15 s (veja C:\Projetos\qwen-celular\ponte.log).' }
} else { Aviso 'A ponte do projeto ainda nao foi instalada neste PC: rode scripts\ponte-pc.ps1 -Instalar.' }
if (ServeAtivo 20130) { Ok 'Porta 20130 (ponte do projeto) aberta so para a tailnet' }
elseif ($SoVerificar) { Falha 'Porta 20130 NAO esta aberta na tailnet: o Qwen do celular nao le o projeto sem o cabo.' }
elseif ((PonteNoAr) -and (Serve @('--bg', '--tcp=20130', 'tcp://127.0.0.1:20130'))) { Ok 'Porta 20130 (ponte do projeto) aberta so para a tailnet' }

Write-Host ''
if ($script:nFalhas -gt 0) {
    Write-Host ('NAO esta pronto: ' + $script:nFalhas + ' item(ns) essencial(is) com [--] acima. Resolva e rode de novo; o comando ia no celular pode nao funcionar sem eles.') -ForegroundColor Red
    exit 1
}
Write-Host 'Pronto. No celular, abra o Termux e digite:  ia' -ForegroundColor Cyan
