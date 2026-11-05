# Padroes de segredo e de arquivo proibido varridos ANTES de enviar (sync-memoria.ps1) ou de integrar (nuvem-integrar.ps1) qualquer coisa. So ASCII.
# Uso: . (Join-Path $PSScriptRoot 'padroes-segredo.ps1')   <- ponto e espaco: carrega $script:PadroesSegredo, Find-Segredo e Test-NomeProibido
# Quem carrega trata a AUSENCIA deste arquivo como erro (sem varredura, nada e enviado nem integrado).
# Um texto de teste com um segredo falso precisa montar o valor em pedacos (a varredura le os proprios scripts: 'gh' + 'p_' + ...).
$script:PadroesSegredo = @(
    'gh[pousr]_[A-Za-z0-9]{20,}', 'github_pat_[A-Za-z0-9_]{20,}', 'sk-ant-[A-Za-z0-9_\-]{20,}', 'sk-[A-Za-z0-9]{32,}',
    'AKIA[0-9A-Z]{16}', 'AIza[0-9A-Za-z_\-]{35}', '-----BEGIN [A-Z ]*PRIVATE KEY-----', '\b\d{15}\b',
    '(?i)(api[_-]?key|secret|passw(or)?d|senha|token)\s*[:=]\s*["'']?[A-Za-z0-9_\-\.]{16,}',
    # 28/10/2026: chave de cliente do OmniRoute (sk- com hifen/sublinhado), JSON "apiKey": "...", Bearer, cookie de sessao, outros provedores
    '(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{30,}',
    '(?i)"[A-Za-z0-9_\-]*(api[_-]?key|secret|passw(or)?d|senha|token|cookie|credential|authorization)[A-Za-z0-9_\-]*"\s*:\s*"[A-Za-z0-9_\-\.%+/=]{20,}"',
    '(?i)\bBearer\s+[A-Za-z0-9_\-\.=]{20,}', '(?i)\b(user_session|_gh_sess)\s*[=:]\s*["'']?[A-Za-z0-9%_\-\.]{20,}',
    'gsk_[A-Za-z0-9]{20,}', 'sk-or-v1-[A-Za-z0-9]{32,}', 'hf_[A-Za-z0-9]{30,}', 'csk-[A-Za-z0-9]{20,}', 'nvapi-[A-Za-z0-9_\-]{20,}',
    # 02/11/2026: chave nova do Google AI Studio (AQ., 53 caracteres; a do celular ja vem assim) e chave da Tailscale
    'AQ\.[A-Za-z0-9_\-]{40,}', 'tskey-[A-Za-z0-9_\-]{20,}',
    'eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}'
)

# Extensoes que nunca entram (dados, planilhas, chaves) e o marcador da planilha do Rafael (MAPAO_*.xlsx: nunca no repositorio)
$script:PadraoArquivoProibido = '\.(xlsx|xls|csv|zip|gz|tar|apk|env|pem|key)$'
$script:PadraoArquivoMapao = 'MAPAO'

function Find-Segredo {
    # Devolve o PADRAO que casou com o texto (nunca o segredo em si) ou $null.
    param([string]$Texto)
    foreach ($re in $script:PadroesSegredo) { if ($Texto -match $re) { return $re } }
    return $null
}

function Test-NomeProibido {
    # $true se o nome (ou caminho) e de um tipo que nunca entra no projeto
    param([string]$Nome)
    return ($Nome -match $script:PadraoArquivoProibido -or $Nome -match $script:PadraoArquivoMapao)
}
