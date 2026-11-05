# Segunda opiniao de antivirus no PC: ClamAV (codigo aberto), sem modo residente. Nao substitui o Microsoft Defender, que segue ligado em tempo real.
# Fica em %LOCALAPPDATA%\Programs\ClamAV. Decisao, fontes e limites: memoria/ANTIVIRUS.md.
# Uso:  pwsh -NoProfile -File scripts\antivirus-pc.ps1 -Status
#       pwsh -NoProfile -File scripts\antivirus-pc.ps1 -Atualizar          (baixa as assinaturas)
#       pwsh -NoProfile -File scripts\antivirus-pc.ps1 -Varrer <pasta>     (so le, nao apaga nem move nada)
#       pwsh -NoProfile -File scripts\antivirus-pc.ps1 -Provar             (prova que o motor aponta e que o banco oficial carrega, sem alarme do Defender)
# Saida: 0 = limpo ou ok; 1 = achou algo ou a prova falhou; 2 = nao deu para rodar.
#       pwsh -NoProfile -File scripts\antivirus-pc.ps1 -Agendar            (atualiza todo dia; varre Downloads todo dia e documentos e projetos no domingo, so com o PC parado)
#       pwsh -NoProfile -File scripts\antivirus-pc.ps1 -Celular            (cabo: varre com o mesmo motor os apps instalados e a pasta Download do celular)
param([switch]$Status, [switch]$Atualizar, [switch]$Provar, [string]$Varrer = '', [switch]$Agendar, [switch]$Rotina, [string]$Alvo = 'Downloads', [switch]$Celular)
$ErrorActionPreference = 'Continue'
$pasta = Join-Path $env:LOCALAPPDATA 'Programs\ClamAV'
$clam = Join-Path $pasta 'clamscan.exe'
$fresh = Join-Path $pasta 'freshclam.exe'
$conf = Join-Path $pasta 'freshclam.conf'
$banco = Join-Path $pasta 'database'
if (-not (Test-Path -LiteralPath $clam)) { Write-Host "ClamAV nao encontrado em $pasta"; exit 2 }

if ($Atualizar) {
    & $fresh "--config-file=$conf" 2>&1 | Select-Object -Last 5 | ForEach-Object { "$_" }
    exit $(if ($LASTEXITCODE -eq 0) { 0 } else { 2 })
}
$temBanco = @(Get-ChildItem -LiteralPath $banco -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in '.cvd', '.cld' }).Count -gt 0
if ($Status -or -not ($Provar -or $Varrer -or $Agendar -or $Rotina -or $Celular -or $MyInvocation.BoundParameters.Count)) {
    $m = Get-MpComputerStatus -ErrorAction SilentlyContinue
    if ($m) { "Defender: ativo=$($m.AntivirusEnabled), tempo real=$($m.RealTimeProtectionEnabled), assinatura de $($m.AntivirusSignatureLastUpdated.ToString('dd/MM/yyyy'))" }
    "ClamAV: " + ((& $clam --version 2>&1) | Select-Object -First 1)
    "Assinaturas do ClamAV: " + $(if ($temBanco) { 'presentes, atualizadas em ' + (Get-ChildItem -LiteralPath $banco -File | Sort-Object LastWriteTime | Select-Object -Last 1).LastWriteTime.ToString('dd/MM/yyyy') } else { 'faltam (rode -Atualizar)' })
    exit 0
}
if (-not $temBanco) { Write-Host 'Faltam as assinaturas: rode -Atualizar.'; exit 2 }
if ($Provar) {
    # No Windows o clamscan nao le da entrada padrao, e um arquivo EICAR em disco dispararia alarme do Defender na tela.
    # Prova em duas partes: (1) o banco oficial carrega, com a contagem real de assinaturas; (2) o motor aponta um arquivo inofensivo marcado por uma assinatura so nossa.
    $t = Join-Path ([IO.Path]::GetTempPath()) ('clam-prova-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    [void][IO.Directory]::CreateDirectory($t)
    try {
        $alvo = Join-Path $t 'alvo.txt'
        [IO.File]::WriteAllText($alvo, 'arquivo inofensivo de prova do projeto')
        $md5 = (Get-FileHash -Algorithm MD5 -LiteralPath $alvo).Hash.ToLowerInvariant()
        $n = (Get-Item -LiteralPath $alvo).Length
        $sig = Join-Path $t 'prova.hdb'
        [IO.File]::WriteAllText($sig, "${md5}:${n}:Prova.Do.Projeto`n")
        $s1 = (& $clam "--database=$sig" --no-summary $alvo 2>&1 | Out-String).Trim()
        $c1 = $LASTEXITCODE
        Write-Host $s1.Replace($t, '<temp>')
        $limpo = Join-Path $t 'limpo.txt'
        [IO.File]::WriteAllText($limpo, 'outro arquivo')
        $s2 = (& $clam "--database=$banco" $limpo 2>&1 | Out-String)
        $c2 = $LASTEXITCODE
        $conta = if ($s2 -match 'Known viruses:\s*(\d+)') { [int64]$Matches[1] } else { 0 }
        Write-Host "Banco oficial: $conta assinaturas carregadas; arquivo comum: codigo $c2"
        if ($c1 -eq 1 -and $s1 -match 'Prova\.Do\.Projeto.*FOUND' -and $conta -gt 1000000 -and $c2 -eq 0) { Write-Host 'Prova ok: o motor aponta o marcado, nao aponta o comum e o banco oficial carregou.'; exit 0 }
        Write-Host 'A prova falhou.'; exit 1
    } finally { [IO.Directory]::Delete($t, $true) }
}
if ($Agendar) {
    # Tudo em prioridade baixa e so com o PC parado ha 10 minutos: nao disputa com jogo nem gravacao. ClamAV carregado usa cerca de 1,3 GB de RAM.
    $eu = $PSCommandPath
    $ajuste = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfIdle -IdleDuration 00:10:00 -IdleWaitTimeout 12:00:00 -Priority 8 -ExecutionTimeLimit 06:00:00 -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $tarefas = @(
        @{ N = 'ClamAV-Atualizar'; A = '-Atualizar'; G = (New-ScheduledTaskTrigger -Daily -At 12:00) },
        @{ N = 'ClamAV-Downloads'; A = '-Rotina -Alvo Downloads'; G = (New-ScheduledTaskTrigger -Daily -At 13:00) },
        @{ N = 'ClamAV-Semanal'; A = '-Rotina -Alvo Semanal'; G = (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 14:00) }
    )
    foreach ($t in $tarefas) {
        $acao = New-ScheduledTaskAction -Execute 'pwsh.exe' -Argument "-NoProfile -WindowStyle Hidden -File `"$eu`" $($t.A)"
        [void](Register-ScheduledTask -TaskName $t.N -Action $acao -Trigger $t.G -Settings $ajuste -Force)
        "Tarefa pronta: $($t.N)"
    }
    exit 0
}
if ($Rotina) {
    $casa = $env:USERPROFILE
    $alvos = if ($Alvo -eq 'Semanal') { @("$casa\Downloads", "$casa\OneDrive\Desktop", "$casa\OneDrive\Documents", "$casa\Documents", "C:\Projetos") } else { @("$casa\Downloads") }
    $dir = Join-Path (Split-Path -Parent $PSScriptRoot) 'diagnostico\antivirus'
    [void][IO.Directory]::CreateDirectory($dir)
    $log = Join-Path $dir ("$Alvo-" + (Get-Date -Format 'yyyyMMdd-HHmm') + '.log')
    $ex = @('--exclude-dir=[\\/]jogos[\\/]?$', '--exclude-dir=[\\/]\.git[\\/]?$', '--exclude-dir=[\\/]node_modules[\\/]?$')
    # @(...) obrigatorio: com um caminho so, @vivos separava letra por letra, e o "\" fazia varrer o disco C: inteiro (visto em 04/11, 1h30 em vez de 8 arquivos)
    $vivos = @($alvos | Where-Object { Test-Path -LiteralPath $_ })
    if ($vivos.Count -eq 0) { Write-Host 'Nenhuma pasta para varrer.'; exit 2 } # sem caminho, o clamscan varreria a pasta atual
    & $clam "--database=$banco" --recursive --infected --max-filesize=200M --max-scansize=400M @ex @vivos 2>&1 | ForEach-Object { "$_" } | Set-Content -LiteralPath $log -Encoding utf8
    $c = $LASTEXITCODE
    if ($c -eq 1) { & msg.exe $env:USERNAME "ClamAV apontou arquivo suspeito. Nada foi apagado. Veja: $log" }
    exit $c
}
if ($Celular) {
    # Um so motor para PC e celular: copia os apps instalados e a pasta Download ao PC, varre e apaga a copia. Nada e apagado no celular.
    if (@(adb devices | Select-String "`tdevice$").Count -eq 0) { Write-Host 'Celular nao conectado.'; exit 2 }
    $t = Join-Path ([IO.Path]::GetTempPath()) ('clam-cel-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    [void][IO.Directory]::CreateDirectory($t)
    try {
        $n = 0
        foreach ($l in (adb shell 'pm list packages -3 -f' 2>$null)) {
            if ("$l" -match '^package:(.+\.apk)=(.+?)\s*$') { adb pull $Matches[1] (Join-Path $t ($Matches[2] + '.apk')) 2>&1 | Out-Null; $n++ }
        }
        adb pull /sdcard/Download (Join-Path $t 'Download') 2>&1 | Out-Null
        $tam = (Get-ChildItem -LiteralPath $t -Recurse -File | Measure-Object Length -Sum).Sum / 1GB
        "Copiados $n apps e a pasta Download ({0:N1} GB). Varrendo..." -f $tam
        & $clam "--database=$banco" --recursive --infected --max-filesize=300M --max-scansize=600M $t 2>&1 | ForEach-Object { "$_".Replace($t, 'celular') }
        $c = $LASTEXITCODE
        if ($c -eq 0) { 'Nada encontrado nos apps e na pasta Download.' } elseif ($c -eq 1) { 'ATENCAO: confira os itens acima. Nada foi apagado.' }
        exit $c
    } finally {
        Get-ChildItem -LiteralPath $t -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object { $_.IsReadOnly = $false }
        [IO.Directory]::Delete($t, $true)
    }
}
if (-not (Test-Path -LiteralPath $Varrer)) { Write-Host "Nao existe: $Varrer"; exit 2 }
& $clam "--database=$banco" --recursive --infected --max-filesize=200M --max-scansize=400M $Varrer 2>&1 | ForEach-Object { "$_" }
$c = $LASTEXITCODE
if ($c -eq 0) { 'Nada encontrado.'; exit 0 }
if ($c -eq 1) { 'ATENCAO: o ClamAV apontou arquivos acima. Nada foi apagado. O ClamAV tem falso positivo: confira antes de agir.'; exit 1 }
exit 2
