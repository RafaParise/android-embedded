# fortigate-recuperar-senha.ps1 - recupera a senha do "admin" do FortiGate 60D pela conta de manutencao.
# Quem roda e o Rafael (fortigate-recuperar-senha.cmd), com o CABO DE CONSOLE ligado do FortiGate ao PC.
#
# Como funciona (procedimento oficial da Fortinet, "maintainer"): logo depois de o FortiGate ligar, por cerca de
# 1 minuto, o console aceita o usuario "maintainer" com a senha "bcpb" + NUMERO DE SERIE (maiusculas). O script fica
# ouvindo o console, entra na hora certa e troca a senha do admin pela que o Rafael escolher.
# A senha nova e digitada pelo Rafael nesta janela; nunca vai para arquivo, registro, argumento nem para o Claude.
# Se a conta de manutencao estiver desativada no aparelho, so resta o reset de fabrica (o script avisa; nao faz).
#
# Uso:  fortigate-recuperar-senha.cmd            (pergunta a porta COM se houver mais de uma)
#       fortigate-recuperar-senha.cmd -Simular   testa a logica com um console de mentira (nao abre porta nenhuma)
param([switch]$Simular, [string]$Porta = '', [int]$Velocidade = 9600, [string]$Serie = '-')
$ErrorActionPreference = 'Stop'

$pasta = Join-Path $PSScriptRoot '..\diagnostico'
New-Item -ItemType Directory -Force -Path $pasta | Out-Null
$log = Join-Path $pasta ('fortigate-recuperar-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
$reSerie = '^FGT60D[0-9A-Z]{6,12}$'
# '?' abre a ajuda no CLI do FortiOS, aspas e espacos quebram o comando: so estes caracteres
$reSenha = '^[A-Za-z0-9!@#%*_.+=-]{8,32}$'

function Escrever-Log([string]$t) { Add-Content -Path $log -Value $t -Encoding UTF8 }

# ---------------- entrada e saida (porta serial de verdade ou console simulado) ----------------
if ($Simular) {
    $script:fila = [System.Collections.Generic.Queue[string]]::new()
    @("`r`nFortiGate-60D (14:43-06.17.2015)`r`nVer:04000024`r`nSerial number: FGT60D4615012345`r`n",
      "Reading boot image... Done.`r`n", "System is starting...`r`n",
      "`r`nFGT60D4615012345 login: ") | ForEach-Object { $script:fila.Enqueue($_) }
    $script:enviado = [System.Collections.Generic.List[string]]::new()
    function Ler-Console { if ($script:fila.Count) { return $script:fila.Dequeue() } Start-Sleep -Milliseconds 50; return '' }
    function Mandar([string]$t, [switch]$Secreto) {
        $script:enviado.Add($t)
        if ($t -eq "maintainer`r") { $script:fila.Enqueue("Password: ") }
        elseif ($t -like 'bcpb*') { $script:fila.Enqueue("`r`nFGT60D4615012345 # ") }
        elseif ($t -eq "end`r") { $script:fila.Enqueue("`r`nFGT60D4615012345 # ") }
        else { $script:fila.Enqueue("`r`nFGT60D4615012345 (x) # ") }
    }
    function Fechar-Console { }
} else {
    $portas = [System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object -Unique
    if (-not $portas) { throw 'Nenhuma porta serial (COM) neste PC. Ligue o cabo de console (ou o adaptador USB-serial) e rode de novo.' }
    if (-not $Porta) {
        if ($portas.Count -eq 1) { $Porta = $portas[0] }
        else { $Porta = Read-Host ('Portas encontradas: ' + ($portas -join ', ') + '. Qual e a do cabo do FortiGate?') }
    }
    if ($portas -notcontains $Porta) { throw "A porta $Porta nao existe neste PC." }
    $script:sp = New-Object System.IO.Ports.SerialPort $Porta, $Velocidade, 'None', 8, 'One'
    $script:sp.Handshake = 'None'; $script:sp.ReadTimeout = 200; $script:sp.Open()
    function Ler-Console { try { return $script:sp.ReadExisting() } catch { return '' } }
    function Mandar([string]$t, [switch]$Secreto) { $script:sp.Write($t) }
    function Fechar-Console { if ($script:sp.IsOpen) { $script:sp.Close() } }
}

# espera um texto aparecer no console (mostra tudo na tela e no registro), ate o prazo
$script:buffer = ''
$script:serieLida = ''
function Esperar([string[]]$padroes, [int]$segundos) {
    $fim = (Get-Date).AddSeconds($segundos)
    while ((Get-Date) -lt $fim) {
        $t = Ler-Console
        if ($t) {
            Write-Host -NoNewline $t
            Escrever-Log $t
            $script:buffer += $t
            if (-not $script:serieLida -and $script:buffer -match 'Serial number:\s*(FGT60D[0-9A-Z]+)') { $script:serieLida = $Matches[1] }
            if (-not $script:serieLida -and $script:buffer -match '(FGT60D[0-9A-Z]+) login:') { $script:serieLida = $Matches[1] }
            if ($script:buffer.Length -gt 8000) { $script:buffer = $script:buffer.Substring($script:buffer.Length - 4000) }
            foreach ($p in $padroes) { if ($script:buffer -match $p) { $m = $Matches; $script:buffer = ''; return $m } }
        }
    }
    return $null
}

try {
    Write-Host 'RECUPERAR A SENHA DO FORTIGATE (conta de manutencao)' -ForegroundColor Cyan
    Write-Host 'Antes: o cabo de console azul ligado na porta CONSOLE do FortiGate e no PC.'
    Write-Host 'A internet da casa vai cair por uns 2 minutos (o FortiGate reinicia).'
    Write-Host ''
    $serie = if ($Serie -ne '-') { $Serie } else { Read-Host 'Numero de serie da etiqueta embaixo do FortiGate (comeca com FGT60D; Enter = o script le sozinho)' }
    $serie = "$serie".Trim().ToUpper()
    if ($serie -and $serie -notmatch $reSerie) { throw 'Numero de serie fora do formato (ex.: FGT60D4615012345).' }

    if ($Simular) {
        $nova = 'SenhaTeste123'
    } else {
        $s1 = Read-Host 'Senha NOVA do admin (8 a 32: letras, numeros e ! @ # % * _ . + = -)' -AsSecureString
        $s2 = Read-Host 'Repita a senha nova' -AsSecureString
        $nova = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s1))
        $conf = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s2))
        if ($nova -cne $conf) { throw 'As duas senhas nao batem.' }
        $conf = $null
    }
    if ($nova -notmatch $reSenha) { throw 'Senha fora da regra (8 a 32; sem espaco, aspas nem ?).' }

    Write-Host ''
    Write-Host 'AGORA: tire o FortiGate da tomada, espere 10 segundos e ligue de novo.' -ForegroundColor Yellow
    Write-Host 'O script fica ouvindo o console (ate 5 minutos) e entra sozinho na hora certa.' -ForegroundColor Yellow
    Write-Host ''

    # so o pedido de login importa; o numero de serie e capturado no caminho (Esperar)
    if (-not (Esperar @('login:\s*$') 300)) { throw 'O pedido de login nao apareceu em 5 minutos: confira o cabo, a porta COM e se o FortiGate religou.' }
    if (-not $serie -and $script:serieLida) { $serie = $script:serieLida.ToUpper() }
    if (-not $serie -or $serie -notmatch $reSerie) { throw 'Nao achei o numero de serie: rode de novo digitando o da etiqueta.' }

    Write-Host "`n[script] entrando como maintainer (serie ...$($serie.Substring($serie.Length-4)))" -ForegroundColor Cyan
    Mandar "maintainer`r"
    if (-not (Esperar @('[Pp]assword:\s*$') 15)) { throw 'O console nao pediu a senha.' }
    Mandar ("bcpb$serie`r") -Secreto
    Escrever-Log '[senha do maintainer enviada - nao registrada]'
    $r = Esperar @('#\s*$', 'Login incorrect', 'login:\s*$') 20
    if (-not $r -or $r[0] -notmatch '#') {
        throw ('A conta de manutencao nao entrou. Ou passou o tempo (rode de novo e religue o FortiGate), ou ela esta ' +
               'desativada neste aparelho; nesse caso so o reset de fabrica, que APAGA a configuracao (fale com o Claude antes).')
    }
    Write-Host "`n[script] dentro. Trocando a senha do admin..." -ForegroundColor Cyan
    Mandar "config system admin`r"; [void](Esperar @('#\s*$') 10)
    Mandar "edit admin`r"; [void](Esperar @('#\s*$') 10)
    Mandar ("set password $nova`r") -Secreto
    Escrever-Log '[set password ******** - nao registrada]'
    [void](Esperar @('#\s*$') 10)
    Mandar "end`r"
    $fim = Esperar @('#\s*$', 'Command fail', 'error') 15
    $nova = $null
    if ($fim -and $fim[0] -match '#') {
        Mandar "exit`r"
        Write-Host "`n`nPRONTO: senha do admin trocada. Use a senha nova no atalho 'FortiGate - celular liga o PC'." -ForegroundColor Green
        if ($Simular) { Write-Host ('[simulacao] enviado: ' + (($script:enviado | ForEach-Object { $_.Trim() -replace 'bcpb\S+', 'bcpb<serie>' -replace 'password \S+', 'password <nova>' }) -join ' | ')) }
    } else {
        Write-Host "`n`nO FortiGate nao confirmou a troca. Mande ao Claude o registro (sem senhas): $log" -ForegroundColor Red
    }
} catch {
    Write-Host "`n$($_.Exception.Message)" -ForegroundColor Red
} finally {
    $nova = $null
    Fechar-Console
    Write-Host "Registro do console (sem senhas): $log"
}
