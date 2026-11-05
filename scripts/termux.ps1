# Fala com o Termux do A12 pelo cabo: abre a ponte do SSH (adb forward 8022 = SSH do Termux, so em 127.0.0.1) e
# roda UM comando no Termux, ou copia arquivos/pastas para la. Sem senha: chave dedicada ~/.ssh/a12_termux; o sshd do Termux so escuta em 127.0.0.1.
# As pontes que EXPOEM o PC ao celular (adb reverse 11435 = Ollama do PC, 20128 = OmniRoute) ESCUTAM EM TODAS AS INTERFACES do celular (inclusive o Wi-Fi):
# so abrem com -Pontes (e -OmniRoute, so com o "sim" do Rafael no dia) e fecham com -FecharPontes. Comando e copia NAO as abrem (ate 31/10 abriam a 11435 em toda chamada).
# Sem cabo, o celular alcanca o PC pela Tailscale: veja o comando `ia` e scripts\ia-do-pc.cmd.
# Uso:  pwsh -NoProfile -File scripts\termux.ps1 -Comando "ls ~/projetos"
#       pwsh -NoProfile -File scripts\termux.ps1 -Copiar C:\pasta\ou\arquivo -Para "~/kit/"      (pasta vira ~/kit/<nome da pasta>)
#       pwsh -NoProfile -File scripts\termux.ps1 -Pontes                                           (abre a 11435 e mostra o estado)
#       pwsh -NoProfile -File scripts\termux.ps1 -Pontes -OmniRoute                                (alem da 11435, abre adb reverse 20128: OmniRoute do PC no celular; so com o "sim" do Rafael no dia)
#       pwsh -NoProfile -File scripts\termux.ps1 -FecharPontes                                     (fecha a 11435 e a 20128)
#       ... | pwsh -NoProfile -File scripts\termux.ps1 -Comando "bash" -LerEntrada               (o texto recebido pela ENTRADA PADRAO deste script vai a entrada padrao do ssh: use para segredo, que nunca deve ir como argumento)
# Saida 0 = ok; 1 = o comando falhou; 2 = nao deu para conectar (cabo, depuracao USB, sshd do Termux: abra o Termux e rode "sshd").
param([string]$Comando = '', [string]$Copiar = '', [string]$Para = '~/', [switch]$Pontes, [switch]$OmniRoute, [switch]$FecharPontes, [string]$Usuario = '', [switch]$LerEntrada)
# 'Continue' de proposito: no Windows PowerShell 5.1, com 'Stop', QUALQUER linha que um programa nativo escreva em stderr (com 2>&1) vira excecao
# (medido em 31/10: `-Comando 'echo ok; echo aviso 1>&2'` dava "ABORTADO: aviso", saida 2; o pwsh 7 nao faz isso). Toda falha real daqui e 'throw', que termina mesmo em 'Continue'.
$ErrorActionPreference = 'Continue'
try {
    $ssh = 'C:\Program Files\Git\usr\bin\ssh.exe'
    $tar = 'C:\Program Files\Git\usr\bin\tar.exe'
    $chave = Join-Path $env:USERPROFILE '.ssh\a12_termux'
    foreach ($f in $ssh, $tar, $chave) { if (-not (Test-Path -LiteralPath $f)) { throw "nao encontrei: $f" } }
    # a revisao de 31/10 achou que -OmniRoute sozinho ja abria a 20128 (escuta em todas as interfaces do celular): as pontes so abrem com -Pontes
    if ($OmniRoute -and -not $Pontes) { throw '-OmniRoute so vale junto com -Pontes (abre a 11435 e a 20128 no celular, em todas as interfaces dele; so com o "sim" do Rafael no dia).' }
    $lista = (& adb devices 2>&1 | Out-String)
    if ($lista -notmatch '\tdevice') { throw 'o A12 nao esta no ADB (cabo e depuracao USB).' }
    if ((& adb shell 'getprop ro.product.model' 2>&1 | Out-String) -notmatch 'SM-A125') { throw 'aparelho inesperado (nao e o SM-A125M).' }
    if (-not $Usuario) {
        $uid = ((& adb shell 'dumpsys package com.termux' 2>&1 | Out-String) -split "`n" | Where-Object { $_ -match '^\s*userId=(\d+)' } | Select-Object -First 1)
        if ($uid -notmatch 'userId=(\d+)') { throw 'nao consegui ler o uid do Termux.' }
        $Usuario = 'u0_a' + ([int]$Matches[1] - 10000)
    }
    # "adb forward/reverse" repetido reclama de porta em uso (o "reverse --list" nao mostra a ponte antiga): o cmd engole o aviso, a conferencia real e o teste abaixo
    & cmd.exe /c 'adb forward tcp:8022 tcp:8022 >nul 2>&1'
    if ($FecharPontes) {
        & cmd.exe /c 'adb reverse --remove tcp:11435 >nul 2>&1'
        & cmd.exe /c 'adb reverse --remove tcp:20128 >nul 2>&1'
        $resta = (((& adb reverse --list 2>&1 | ForEach-Object { "$_" }) -join "`n").Trim())
        # a lista pode nao mostrar a ponte antiga (linha 31), mas se ela citar uma das portas a ponte NAO esta fechada: nao diz "fechadas" nem sai com 0
        if ($resta -match 'tcp:(11435|20128)') {
            Write-Host ('ATENCAO: a remocao NAO fechou a ponte; ainda na lista: [' + $resta + ']. Tente de novo; se persistir, reinicie o adb (adb kill-server) ou desligue a depuracao USB.') -ForegroundColor Red
            exit 1
        }
        Write-Host ('pontes fechadas. Restam (deve estar vazio): [' + $resta + ']')
        exit 0
    }
    if ($Pontes) { & cmd.exe /c 'adb reverse tcp:11435 tcp:11434 >nul 2>&1' }
    if ($OmniRoute) { & cmd.exe /c 'adb reverse tcp:20128 tcp:20128 >nul 2>&1' }   # o OmniRoute do PC exige chave de cliente: a ponte sozinha nao da acesso
    $opts = @('-i', $chave, '-p', '8022', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=10')
    $alvo = "$Usuario@127.0.0.1"
    if ($Pontes) {
        Write-Host "pontes abertas: adb forward 8022 (SSH do Termux) e adb reverse 11435 (celular) -> 11434 (Ollama do PC)$(if ($OmniRoute) { ' e 20128 (OmniRoute do PC)' }); usuario do Termux: $Usuario. Elas escutam em todas as interfaces do celular: feche com -FecharPontes quando terminar."
        # sem aspas duplas (o 5.1 as perde) e sem pipeline: num pipe o status seria o do ultimo comando e o "ollama-sem-resposta" nunca sairia
        $o = ((& $ssh @opts $alvo 'echo sshd-ok; r=$(curl -s -m 4 http://127.0.0.1:11435/api/tags); case $r in *llama3.2-32k*) echo modelo-no-pc:1;; ?*) echo modelo-no-pc:0;; *) echo ollama-sem-resposta;; esac' 2>&1 | ForEach-Object { "$_" }) -join "`n")
        $codP = $LASTEXITCODE
        Write-Host $o.Trim()
        if ($codP -eq 255 -or $o -notmatch 'sshd-ok') { throw 'nao deu para conectar ao sshd do Termux (abra o Termux e rode "sshd").' }
        if ($o -match 'ollama-sem-resposta|modelo-no-pc:0') { Write-Host 'AVISO: a ponte 11435 abriu no celular, mas o Ollama do PC nao respondeu ou nao tem o modelo llama3.2-32k.' -ForegroundColor Yellow; exit 1 }
        exit 0
    }
    if ($Copiar) {
        if (-not (Test-Path -LiteralPath $Copiar)) { throw "nao existe: $Copiar" }
        $item = Get-Item -LiteralPath $Copiar
        $pai = if ($item.PSIsContainer) { $item.Parent.FullName } else { $item.DirectoryName }
        $nome = $item.Name
        # tar passa pelo cmd (o pipe do cmd e binario; o do PowerShell corromperia). Aspas simples no destino nao sao aceitas.
        if ($Para -match '\s') { throw 'o destino (-Para) nao pode ter espaco: o mkdir -p do Termux o partiria em dois (o NOME do arquivo ou da pasta pode ter).' }
        if ("$Para$nome" -match "['""`$``]") { throw 'o destino nao pode ter aspas, $ nem crase.' }
        # lista de PERMITIDOS no destino: ; & | < > ( ) e afins chegariam ao shell do Termux
        if ($Para -notmatch '^[~A-Za-z0-9_./-]+$') { throw 'o destino (-Para) so aceita letras, numeros, ~ . / _ e - (sem ; & | < > parenteses nem espaco).' }
        # tar primeiro para um arquivo temporario: num "tar | ssh" o codigo de saida e o do ULTIMO programa, e uma falha do tar (arquivo travado, sem permissao)
        # passaria como "copiado" com arquivo faltando. O cmd le o .tar com "<" (binario; o pipe do PowerShell corromperia).
        $tmpTar = Join-Path ([IO.Path]::GetTempPath()) ('termux-copia-' + [guid]::NewGuid().ToString('N').Substring(0, 8) + '.tar')
        try {
            $cmdTar = "`"$tar`" -C `"$pai`" --force-local -cf `"$tmpTar`" `"$nome`""
            & cmd.exe /c $cmdTar
            $codTar = $LASTEXITCODE
            if ($codTar -ne 0) { throw "o tar do PC falhou (codigo $codTar): a copia foi cancelada, nada foi enviado." }
            $cmd = "`"$ssh`" -i `"$chave`" -p 8022 -o BatchMode=yes -o StrictHostKeyChecking=accept-new $alvo `"mkdir -p $Para && tar -C $Para -xf -`" < `"$tmpTar`""
            & cmd.exe /c $cmd
            if ($LASTEXITCODE -ne 0) { throw "a copia falhou (codigo $LASTEXITCODE)." }
        } finally {
            if (Test-Path -LiteralPath $tmpTar) { Remove-Item -LiteralPath $tmpTar -Force -ErrorAction SilentlyContinue }
        }
        Write-Host "copiado: $Copiar -> $Para"
        exit 0
    }
    if (-not $Comando) { throw 'diga -Comando "..." ou -Copiar <caminho> ou -Pontes.' }
    # O Windows PowerShell 5.1 passa argumentos a programas nativos sem escapar aspas duplas (medido em 31/10: cat "a b" chegou ao Termux como cat a b); o pwsh 7 escapa certo.
    if ($PSVersionTable.PSVersion.Major -lt 7 -and $Comando.Contains('"')) { throw 'no Windows PowerShell 5.1 as aspas duplas do -Comando se perdem a caminho do ssh: use o pwsh (7) ou troque por aspas simples.' }
    if ($LerEntrada) {
        # $input, nao [Console]::In: com "pwsh -File" a entrada ja foi consumida pelo host e o Console chega vazio (visto no aparelho em 03/11)
        $txtEntrada = @($input | ForEach-Object { "$_" }) -join "`n"
        if (-not $txtEntrada) { throw 'pediu -LerEntrada, mas a entrada padrao veio vazia: nada foi enviado.' }
        # o PowerShell termina a entrada com CRLF: sem tirar o CR, o bash do Termux responde "$'\r': command not found" (visto no aparelho em 03/11)
        $saida = $txtEntrada | & $ssh @opts $alvo ("tr -d '\r' | " + $Comando) 2>&1
    } else {
        $saida = & $ssh @opts $alvo $Comando 2>&1
    }
    $cod = $LASTEXITCODE
    ($saida | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" } }) | Write-Host
    if ($cod -eq 255) { exit 2 }
    exit $(if ($cod -eq 0) { 0 } else { 1 })
}
catch {
    Write-Host ('ABORTADO: ' + $_.Exception.Message) -ForegroundColor Red
    exit 2
}
