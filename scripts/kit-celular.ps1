# Monta e, com -Enviar, manda ao Termux do A12 (pelo cabo, scripts\termux.ps1) o kit completo do Qwen Code:
#   ~/.agents/skills            8 skills essenciais (as unicas CARREGADAS: cada skill carregada gasta contexto de um modelo pequeno)
#   ~/kit/skills-extras         as outras skills (para ativar uma, copie a pasta dela para ~/.agents/skills)
#   ~/kit/estrategias           CLAUDE.md global do Claude Code, politica de divisao de trabalho, AGENTS.md do Hermes, kit-ia-professor
#   ~/kit/projeto-android-embeeded   CLAUDE.md, memoria/*.md e scripts/ deste projeto (so leitura, para o Qwen consultar)
# Antes de mandar, varre TODO arquivo com padroes-segredo.ps1: texto com cara de segredo, planilha, MAPAO, chave ou binario fica de fora,
# e qualquer achado de segredo ABORTA tudo (nada e enviado). Nunca vao: .credentials.json, ~/.claude.json, settings.json do Claude,
# a pasta synced (skills do claude.ai) nem dado de aluno.
# Uso: pwsh -NoProfile -File scripts\kit-celular.ps1            (so monta numa pasta temporaria e mostra o resumo)
#      pwsh -NoProfile -File scripts\kit-celular.ps1 -Enviar    (monta, varre e manda)
#      pwsh -NoProfile -File scripts\kit-celular.ps1 -Exportar C:\Projetos\qwen-celular\kit   (monta, varre e grava skills\ e estrategias\ NO PC,
#           para a ponte-pc servir ao Qwen do celular de qualquer lugar; a pasta precisa se chamar kit; so substitui skills\ e estrategias\)
# Saida 0 = ok; 2 = abortado (segredo achado, pasta de origem ou CLAUDE.md do projeto ausente, cabo, conferencia final sem resposta).
# Documento solto ausente (ex.: AGENTS.md do Hermes, README do kit-turbo) so AVISA e fica de fora (o Hermes e opcional).
# -Enviar apaga no Termux, antes de cada copia, as pastas que o kit gera (skills-extras, estrategias, projeto-android-embeeded e as 8 skills essenciais);
# uma skill ativada a mao em ~/.agents/skills que NAO seja uma das essenciais fica.
param([switch]$Enviar, [string]$Exportar = '')
$ErrorActionPreference = 'Stop'
function Nativo([scriptblock]$bloco) {
    # Windows PowerShell 5.1: com $ErrorActionPreference = 'Stop', QUALQUER linha que um programa nativo escreva em stderr vira excecao (medido em 31/10; no pwsh 7 nao).
    # Aqui a preferencia fica em 'Continue' so durante a chamada (o resto do script continua em 'Stop': a varredura de segredos nao pode falhar em silencio);
    # devolve as linhas (stdout + stderr) como texto e deixa o $LASTEXITCODE para quem chamou.
    $antes = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { return @(& $bloco 2>&1 | ForEach-Object { "$_" }) } finally { $ErrorActionPreference = $antes }
}
$tmp = ''
try {
    $raiz = Split-Path -Parent $PSScriptRoot
    . (Join-Path $PSScriptRoot 'padroes-segredo.ps1')
    $perfil = $env:USERPROFILE
    $essenciais = @('spec-driven-development', 'planning-and-task-breakdown', 'incremental-implementation', 'test-driven-development',
        'debugging-and-error-recovery', 'code-review-and-quality', 'git-workflow-and-versioning', 'security-and-hardening')
    $agentBase = Join-Path $perfil '.claude\plugins\cache\addy-agent-skills\agent-skills'
    if (-not (Test-Path -LiteralPath $agentBase)) { throw "nao achei as skills do plugin agent-skills em $agentBase" }
    # versao mais nova pelo numero (texto poria 0.6.9 depois de 0.6.13); pasta cujo nome nao e versao e ignorada
    $ver = Get-ChildItem -LiteralPath $agentBase -Directory | Where-Object { $_.Name -match '^\d+(\.\d+){1,3}$' } | Sort-Object { [version]$_.Name } | Select-Object -Last 1
    if (-not $ver) { throw "nao achei pasta de versao (ex.: 0.6.13) em $agentBase" }
    $fonteAgent = Join-Path $ver.FullName 'skills'
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('kit-celular-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    $dEss = Join-Path $tmp 'skills'
    $dExt = Join-Path $tmp 'skills-extras'
    $dEst = Join-Path $tmp 'estrategias'
    $dProj = Join-Path $tmp 'projeto-android-embeeded'
    foreach ($d in $dEss, $dExt, $dEst, $dProj) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $script:suspeitos = New-Object System.Collections.Generic.List[string]
    $script:nArq = 0; $script:bytes = 0; $script:fora = 0

    function Copia-Arquivo($arq, [string]$destino) {
        # so texto de ate 300 KB, sem nome proibido e sem cara de segredo
        if ((Test-NomeProibido $arq.Name) -or $arq.Name -match '^(\.credentials\.json|\.claude\.json|settings\.json)$') { $script:fora++; return }
        if ($arq.Length -gt 300KB) { $script:fora++; return }
        $txt = [IO.File]::ReadAllText($arq.FullName)
        if ($txt.IndexOf([char]0) -ge 0) { $script:fora++; return }
        # a LEITURA do valor do ambiente (process.env.X, os.environ["X"], getenv("X"), $env:X) nao e segredo: e o exemplo "nunca ponha a chave no codigo" dos manuais de seguranca.
        # So essa referencia sai do texto varrido; o resto da linha continua (ate 31/10 a linha INTEIRA saia: um literal ao lado, como getenv("A", "ghp_..."), passava).
        # Quem esta sendo ATRIBUIDO ($env:X = "...", process.env.X = "...") fica, com o nome que da contexto ao padrao. (?>...) impede o recuo do \w+ que burlaria o (?!...).
        # Se o trecho que seria tirado tem cara de segredo (chave colada no lugar do nome: getenv("sk-..."), os.environ["AKIA..."]), ele FICA no texto varrido.
        $tirar = [System.Text.RegularExpressions.MatchEvaluator]{ param($m) if (Find-Segredo $m.Value) { $m.Value } else { '' } }
        $paraVarrer = (($txt -split "`r?`n") | ForEach-Object { [regex]::Replace($_, '(?>(?:process\.env|os\.environ|os\.getenv|getenv)[\w\.\-\[\]\(\)''"]*|\$env:\w+)(?!\s*=[^=])', $tirar) }) -join "`n"
        $padrao = Find-Segredo $paraVarrer
        if ($padrao) { $script:suspeitos.Add($arq.FullName + '  <- padrao ' + $padrao); return }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destino) | Out-Null
        [IO.File]::WriteAllText($destino, $txt, $utf8)
        $script:nArq++; $script:bytes += $arq.Length
    }
    function Copia-Pasta([string]$de, [string]$para) {
        if (-not (Test-Path -LiteralPath $de)) { throw "fonte ausente: $de" }
        $base = (Get-Item -LiteralPath $de).FullName
        foreach ($f in (Get-ChildItem -LiteralPath $base -Recurse -File -Force)) {
            $rel = $f.FullName.Substring($base.Length).TrimStart('\')
            if ($rel -match '(^|\\)(\.git|node_modules|__pycache__|\.pytest_cache)(\\|$)') { continue }
            Copia-Arquivo $f (Join-Path $para $rel)
        }
    }
    function Copia-Um([string]$de, [string]$para, [switch]$Obrigatorio) {
        if (-not (Test-Path -LiteralPath $de)) {
            if ($Obrigatorio) { throw "fonte ausente: $de" }
            Write-Host "AVISO: nao existe, ficou de fora: $de"; return
        }
        Copia-Arquivo (Get-Item -LiteralPath $de) $para
    }

    # 1) skills: essenciais carregadas; o resto em extras
    foreach ($n in $essenciais) { Copia-Pasta (Join-Path $fonteAgent $n) (Join-Path $dEss $n) }
    foreach ($d in (Get-ChildItem -LiteralPath $fonteAgent -Directory | Where-Object { $essenciais -notcontains $_.Name })) { Copia-Pasta $d.FullName (Join-Path $dExt $d.Name) }
    $skillsUsuario = Join-Path $perfil '.claude\skills'
    foreach ($n in 'divisao-trabalho-ia', 'skill-creator') { Copia-Pasta (Join-Path $skillsUsuario $n) (Join-Path $dExt $n) }
    foreach ($kit in 'kit-professor', 'kit-turbo') {
        $sk = Join-Path $skillsUsuario "$kit\skills"
        if (Test-Path -LiteralPath $sk) { foreach ($d in (Get-ChildItem -LiteralPath $sk -Directory)) { Copia-Pasta $d.FullName (Join-Path $dExt $d.Name) } }
    }
    # 2) estrategias
    Copia-Um (Join-Path $perfil '.claude\CLAUDE.md') (Join-Path $dEst 'CLAUDE-global-do-claude-code.md')
    Copia-Um 'C:\Projetos\kit-ia-professor\POLITICA-DIVISAO-TRABALHO.md' (Join-Path $dEst 'POLITICA-DIVISAO-TRABALHO.md')
    Copia-Um 'C:\Projetos\kit-ia-professor\LEIA-ME.md' (Join-Path $dEst 'kit-ia-professor-LEIA-ME.md')
    Copia-Um 'C:\Projetos\hermes-trabalho\android-embeeded\AGENTS.md' (Join-Path $dEst 'hermes-AGENTS.md')
    Copia-Um (Join-Path $skillsUsuario 'kit-turbo\README.md') (Join-Path $dEst 'kit-turbo-README.md')
    # 3) snapshot do projeto (so leitura): CLAUDE.md, memoria/*.md de primeiro nivel e scripts/ de primeiro nivel
    Copia-Um (Join-Path $raiz 'CLAUDE.md') (Join-Path $dProj 'CLAUDE.md') -Obrigatorio
    foreach ($f in (Get-ChildItem -LiteralPath (Join-Path $raiz 'memoria') -File -Filter '*.md')) { Copia-Arquivo $f (Join-Path $dProj ('memoria\' + $f.Name)) }
    foreach ($f in (Get-ChildItem -LiteralPath (Join-Path $raiz 'scripts') -File | Where-Object { $_.Extension -in '.py', '.ps1', '.sh', '.json', '.cmd' })) { Copia-Arquivo $f (Join-Path $dProj ('scripts\' + $f.Name)) }

    if ($script:suspeitos.Count -gt 0) {
        Write-Host ('ABORTADO: {0} arquivo(s) com cara de segredo; NADA foi enviado. Abra cada um e decida:' -f $script:suspeitos.Count) -ForegroundColor Red
        $script:suspeitos | Select-Object -First 15 | ForEach-Object { Write-Host ('  ' + $_) }
        exit 2
    }
    $nEss = @(Get-ChildItem -LiteralPath $dEss -Directory).Count
    $nExt = @(Get-ChildItem -LiteralPath $dExt -Directory).Count
    Write-Host ('montado: {0} arquivos de texto, {1} KB; {2} skills essenciais, {3} extras; {4} arquivo(s) deixados de fora (nome proibido, binario ou maior que 300 KB); varredura de segredos: limpa.' -f $script:nArq, [math]::Round($script:bytes / 1KB), $nEss, $nExt, $script:fora)
    if ($Exportar) {
        # CUIDADO: o PowerShell nao diferencia maiusculas, entao $dest seria o mesmo que $dEst (a pasta de estrategias montada acima)
        $pastaKit = [IO.Path]::GetFullPath($Exportar)
        if ((Split-Path -Leaf $pastaKit) -ne 'kit') { throw "-Exportar precisa terminar em \kit (recebi $pastaKit)" }
        New-Item -ItemType Directory -Force -Path $pastaKit | Out-Null
        foreach ($sub in 'skills', 'estrategias') { $velha = Join-Path $pastaKit $sub; if (Test-Path -LiteralPath $velha) { [IO.Directory]::Delete($velha, $true) } }
        Copy-Item -LiteralPath $dEss -Destination (Join-Path $pastaKit 'skills') -Recurse
        Copy-Item -Path (Join-Path $dExt '*') -Destination (Join-Path $pastaKit 'skills') -Recurse -Force
        Copy-Item -LiteralPath $dEst -Destination (Join-Path $pastaKit 'estrategias') -Recurse
        Write-Host ('exportado para {0}: {1} skills e {2} documentos de estrategia (ja varridos).' -f $pastaKit, @(Get-ChildItem -LiteralPath (Join-Path $pastaKit 'skills') -Directory).Count, @(Get-ChildItem -LiteralPath (Join-Path $pastaKit 'estrategias') -File).Count)
        if (-not $Enviar) { exit 0 }
    }
    if (-not $Enviar) { Write-Host 'Nada foi enviado (use -Enviar).'; exit 0 }

    $termux = Join-Path $PSScriptRoot 'termux.ps1'
    $envios = @(@($dEss, '~/.agents/'), @($dExt, '~/kit/'), @($dEst, '~/kit/'), @($dProj, '~/kit/'))
    foreach ($e in $envios) {
        # destinos que o kit gera: apagados antes da copia, para o que saiu do kit nao ficar no celular (so depois de a varredura passar)
        $velhos = if ($e[0] -eq $dEss) { @(Get-ChildItem -LiteralPath $dEss -Directory | ForEach-Object { $e[1] + 'skills/' + $_.Name }) } else { @($e[1] + (Split-Path -Leaf $e[0])) }
        foreach ($v in $velhos) { if ($v -notmatch '^~/[A-Za-z0-9._/-]+$' -or $v -match '\.\.') { throw "destino com nome estranho, nada apagado: $v" } }
        $lim = (Nativo { & pwsh -NoProfile -File $termux -Comando ('rm -r -f -- ' + ($velhos -join ' ')) }) -join "`n"
        if ($LASTEXITCODE -ne 0) { throw ('nao consegui limpar o destino antigo de ' + (Split-Path -Leaf $e[0]) + ': ' + $lim.Trim()) }
        $saida = (Nativo { & pwsh -NoProfile -File $termux -Copiar $e[0] -Para $e[1] }) -join "`n"
        if ($LASTEXITCODE -ne 0) { throw ('o envio de ' + (Split-Path -Leaf $e[0]) + ' falhou: ' + $saida.Trim()) }
        Write-Host ('enviado: ' + (Split-Path -Leaf $e[0]) + ' -> ' + $e[1])
    }
    $conf = (Nativo { & pwsh -NoProfile -File $termux -Comando 'echo carregadas: $(ls ~/.agents/skills | wc -l); echo extras: $(ls ~/kit/skills-extras | wc -l); du -sk ~/kit/estrategias ~/kit/projeto-android-embeeded | cut -c1-80' }) -join "`n"
    if ($LASTEXITCODE -ne 0) { throw ('as copias terminaram, mas a conferencia final no Termux falhou: ' + $conf.Trim()) }
    Write-Host $conf.Trim()
    exit 0
}
catch {
    Write-Host ('ABORTADO: ' + $_.Exception.Message) -ForegroundColor Red
    exit 2
}
finally {
    # a pasta temporaria so e apagada se estiver mesmo dentro da pasta temporaria do sistema
    if ($tmp -and $tmp.StartsWith([IO.Path]::GetTempPath()) -and (Test-Path -LiteralPath $tmp)) { [IO.Directory]::Delete($tmp, $true) }
}
