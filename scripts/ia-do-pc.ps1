# Confere (e liga, se estiver desligado, menos a Tailscale: essa o Rafael conecta pelo icone dela) o que o celular usa no PC: Tailscale, OmniRoute, Ollama, a ponte do projeto (ponte-pc) e as portas da tailnet.
# Uso: duplo clique em scripts\ia-do-pc.cmd   ou   pwsh -NoProfile -File scripts\ia-do-pc.ps1 [-SoVerificar] [-AbrirOllama | -FecharOllama]
#   -SoVerificar   nao liga nem muda nada: so mostra
#   -AbrirOllama   reabre a porta do Ollama (11434) SO para a tailnet (desde 05/11 ela ja abre por padrao)
#   -FecharOllama  fecha e mantem fechada ate um -AbrirOllama
# As portas do OmniRoute (20128) e da ponte do projeto (20130) sao abertas SO para a tailnet (PC e celular). Nada fica exposto na internet nem na rede da escola.
# Desfazer a do OmniRoute:  tailscale serve --tcp=20128 off      a da ponte:  tailscale serve --tcp=20130 off      Desfazer tudo:  tailscale serve reset
param([switch]$SoVerificar, [switch]$AbrirOllama, [switch]$FecharOllama)
$ErrorActionPreference = 'Continue'
$IpEsperado = '100.64.0.1'   # o mesmo IP do comando `ia` no celular (variavel IA_PC_IP)

function Ok($t)    { Write-Host ('  [ok]  ' + $t) -ForegroundColor Green }
function Aviso($t) { Write-Host ('  [!!]  ' + $t) -ForegroundColor Yellow }
$script:nFalhas = 0
function Falha($t) { $script:nFalhas++; Write-Host ('  [--]  ' + $t) -ForegroundColor Red }
function FalhaLeve($t) { Write-Host ('  [--]  ' + $t) -ForegroundColor Red }   # nao conta para a mensagem final: o Ollama so serve ao `ia pc`
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

# 3) Ollama (modelo local do PC)
function Tags { try { return Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5 } catch { return $null } }
$tags = Tags
if (-not $tags -and -not $SoVerificar) {
    $ol = (Get-Command ollama -ErrorAction SilentlyContinue).Source
    if ($ol) {
        Aviso 'Ollama parado: ligando...'
        Start-Process -FilePath $ol -ArgumentList 'serve' -WindowStyle Hidden
        for ($i = 0; $i -lt 15 -and -not $tags; $i++) { Start-Sleep -Seconds 2; $tags = Tags }
    }
}
if ($tags) {
    if (@($tags.models | Where-Object { $_.name -like 'llama3.2-32k*' }).Count -gt 0) { Ok 'Ollama no ar com o modelo llama3.2-32k (usado por `ia pc`)' }
    else { Aviso 'Ollama no ar, mas sem o modelo llama3.2-32k (o `ia pc` precisa dele).' }
} else { FalhaLeve 'Ollama parado (o `ia pc` nao funciona; a nuvem nao precisa dele).' }

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

# Ollama: ABERTO por padrao so para a tailnet desde 05/11 (pedido do Rafael: "nao deve depender de cabo para acessar ollama,
# omniroute e afins"); a tailnet tem so os aparelhos dele. -FecharOllama fecha e deixa a marca diagnostico\ollama-fechado,
# que mantem fechado ate um -AbrirOllama.
$marcaOllama = Join-Path (Split-Path $PSScriptRoot -Parent) 'diagnostico\ollama-fechado'
if ($FecharOllama -and -not $SoVerificar) {
    if (Serve @('--tcp=11434', 'off')) { [IO.File]::WriteAllText($marcaOllama, 'fechado pelo -FecharOllama'); Ok 'Porta do Ollama (11434) fechada (fica fechada ate -AbrirOllama)' }
} elseif (-not $SoVerificar -and ($AbrirOllama -or -not (Test-Path $marcaOllama)) -and -not (ServeAtivo 11434)) {
    if (Serve @('--bg', '--tcp=11434', 'tcp://127.0.0.1:11434')) { Ok 'Porta do Ollama (11434) aberta so para a tailnet' }
}
if ($AbrirOllama -and -not $SoVerificar -and (Test-Path $marcaOllama)) { [IO.File]::Delete($marcaOllama) }
if (ServeAtivo 11434) { Ok 'Porta do Ollama (11434) aberta so para a tailnet (o Matrix usa sem cabo, com Wi-Fi ou dados moveis)' }
elseif (Test-Path $marcaOllama) { Aviso 'Porta do Ollama fechada por escolha (-FecharOllama). Para abrir: ia-do-pc.cmd -AbrirOllama' }
else { FalhaLeve 'Porta do Ollama fechada: o Matrix nao alcanca o modelo do PC (rode ia-do-pc.cmd).' }

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
