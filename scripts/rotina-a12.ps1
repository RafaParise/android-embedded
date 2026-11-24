#Requires -Version 7
<#
.SYNOPSIS
Rotina do Galaxy A12: estado, ajustes do projeto, auditoria e metricas, num comando so.
Versao ADAPTADA (20/11/2026) do "Orquestrador_Mestre_A12.ps1" gerado pelo Gemini (original na raiz como .NAO-EXECUTAR;
decisao em memoria/DECISOES.md). Usa so as ferramentas do projeto, sempre no aparelho certo (serial), e mostra o resumo.

  pwsh -NoProfile -File scripts\rotina-a12.ps1                simulacao dos ajustes + auditoria + metricas
  pwsh -NoProfile -File scripts\rotina-a12.ps1 -Aplicar       aplica os ajustes SO se algo mudou (registro para desfazer)
  pwsh -NoProfile -File scripts\rotina-a12.ps1 -Serial 10.0.10.50:5555 -SemMedir
Motor nativo (scripts\a12m, Rust, so le): a rotina confere o binario no aparelho pelo SHA-256, mostra a foto de uma
chamada, deixa o vigia de episodios de pressao rodando (~2 MB, sem acordar o aparelho) e mostra o custo dele e os
episodios. -SemMotor / -SemVigia desligam essas partes.

O que o original fazia e esta rotina NAO faz (de proposito):
  - fases 1..5, VPN, backup e "Bypass DPI Fortinet" da SEDUC: nao existem aqui ou nao se fazem (filtro da rede da escola);
  - reescrever memoria/ESTADO.md com texto fixo e enviar ao GitHub: o ESTADO e o sync sao do Claude, com o que aconteceu;
  - desligar as Opcoes do desenvolvedor (F8): ja estao em 0 por settings desde 05/11 e o adb segue; o F8 e do Rafael;
  - DNS privado, bucket 45 em massa, compile -m speed (medido PIOR em 06/11), input text as cegas, motor Rust no celular.
Desfazer os ajustes: python scripts\ajustes-script.py --restaurar (usa o ultimo registro; esta rotina so grava registro
novo quando algo muda, entao o ultimo registro e sempre o estado de antes da ultima mudanca de verdade).
#>
param(
    [string]$Serial = "",
    [switch]$Aplicar,
    [switch]$SemMedir,
    [switch]$SemMotor,   # nao usa o motor nativo a12m
    [switch]$SemVigia    # usa o a12m so para a foto, sem deixar o vigia de episodios rodando
)

# Continue: as falhas dos programas sao tratadas pelo codigo de saida de cada um (stderr de python nao derruba a rotina)
$ErrorActionPreference = "Continue"
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz
$env:PYTHONIOENCODING = "utf-8"
$avisos = 0

function Falhou([string]$nome, [string]$arq) {
    Write-Warning "$nome falhou (saida $LASTEXITCODE); ultimas linhas:"
    Get-Content $arq -Tail 3 | ForEach-Object { "    " + $_.Substring(0, [Math]::Min(160, $_.Length)) }
    $script:avisos++
}

# 1. Aparelho: um serial so (o A12 costuma aparecer duas vezes: DMZ e Wi-Fi de casa); a DMZ tem preferencia
if (-not $Serial) {
    $linhas = @((adb devices) -split "`n" | Where-Object { $_ -match "^\S+\s+device\s*$" } | ForEach-Object { ($_ -split "\s+")[0] })
    $Serial = (@($linhas | Where-Object { $_ -like "10.0.10.*" }) + $linhas) | Select-Object -First 1
}
if (-not $Serial) { Write-Error "Nenhum aparelho no adb. Ligue a depuracao (cabo ou Wi-Fi) e rode de novo."; exit 1 }
$env:ANDROID_SERIAL = $Serial

$modelo = "$(adb -s $Serial shell getprop ro.product.model)".Trim()
if ($modelo -notlike "SM-A125*") { Write-Error "Aparelho inesperado em ${Serial}: '$modelo' (esta rotina e do A12)."; exit 1 }
$batLinha = adb -s $Serial shell dumpsys battery | Select-String "level:" | Select-Object -First 1
$bat = [int]("$batLinha" -replace "\D", "")
if ($bat -lt 15) { Write-Error "Bateria em $bat%. Ligue o carregador (>= 15%)."; exit 1 }
Write-Host "A12 em $Serial | bateria $bat%" -ForegroundColor Cyan

$pasta = Join-Path $Raiz ("diagnostico\" + (Get-Date -Format "yyyyMMdd-HHmmss") + "-rotina")
New-Item -ItemType Directory -Path $pasta -Force | Out-Null

# 2. Sonda (so leitura): guarda inteira, mostra a primeira linha
$arq = Join-Path $pasta "sonda.txt"
python scripts\sonda-a12.py *> $arq
if ($LASTEXITCODE -ne 0) { Falhou "sonda" $arq } else { Get-Content $arq -TotalCount 1 }

# 2b. Motor nativo a12m (Rust, so le; scripts\a12m): binario igual ao do PC, foto numa chamada e o vigia de episodios
if (-not $SemMotor) {
    $binPc = Join-Path $env:LOCALAPPDATA "a12m-target\aarch64-linux-android\release\a12m"
    $binCel = "/data/local/tmp/a12m/a12m"
    if (-not (Test-Path $binPc)) {
        # sem o binario do PC nao ha com o que conferir o do aparelho: nao roda nada sem conferencia
        Write-Warning "motor: binario nao compilado no PC (cargo build --release --target aarch64-linux-android em scripts\a12m); motor pulado"
        $avisos++
    } else {
        $hashPc = (Get-FileHash $binPc -Algorithm SHA256).Hash.ToLower()
        $hashCel = "$(adb -s $Serial shell "sha256sum $binCel 2>/dev/null")".Split(" ")[0].Trim()
        if ($hashPc -ne $hashCel) {
            # o vigia em execucao segue com o binario velho na memoria: para antes, sobe de novo abaixo
            adb -s $Serial shell "[ -x $binCel ] && $binCel parar" | Out-Null
            adb -s $Serial shell "mkdir -p -m 700 /data/local/tmp/a12m && chmod 700 /data/local/tmp/a12m" | Out-Null
            adb -s $Serial push $binPc $binCel | Out-Null
            adb -s $Serial shell "chmod 700 $binCel" | Out-Null
            $hashCel = "$(adb -s $Serial shell "sha256sum $binCel 2>/dev/null")".Split(" ")[0].Trim()
            Write-Host "motor: binario atualizado no aparelho" -ForegroundColor Green
        }
        if ($hashPc -ne $hashCel) {
            Write-Warning "motor: o binario do aparelho nao confere com o do PC; motor pulado"; $avisos++
        } else {
            # UMA foto (texto e JSON saem dela): mesma estrutura do medir.py, o --comparar funciona entre os dois
            $json = "$(adb -s $Serial shell "$binCel status --json --janela 5 --rotulo rotina-a12m 2>/dev/null")".Trim()
            try {
                $f = $json | ConvertFrom-Json
                [IO.File]::WriteAllText((Join-Path $pasta "a12m-status.json"), $json, (New-Object Text.UTF8Encoding $false))
                "  memoria: disponivel $($f.mem.disponivel_mb) MB | swap usado $($f.mem.swap_usado_mb) MB | zram $($f.mem.zram_dados_mb) MB -> $($f.mem.zram_comprimido_mb) MB"
                "  pressao (avg60): cpu $($f.psi.cpu_some_avg60)% | memoria $($f.psi.mem_some_avg60)% | disco $($f.psi.io_some_avg60)%"
                "  CPU ocupada (5 s): $($f.cpu.ocupada_pct)% | processos $($f.proc.total), de apps $($f.proc.apps)"
                "  maiores CPU: " + (($f.cpu.maiores | ForEach-Object { "$($_.nome) $($_.cpu_pct)%" }) -join "; ")
                "  maiores RAM: " + (($f.maiores_ram | ForEach-Object { "$($_.nome) $($_.mb) MB" }) -join "; ")
            } catch {
                Write-Warning "motor: a foto do a12m nao veio em JSON valido"; $avisos++
            }
            if (-not $SemVigia) {
                # setsid + nohup: o vigia sobrevive ao fim desta sessao do adb; a trava (flock) do a12m impede 2 copias
                adb -s $Serial shell "setsid nohup $binCel vigiar >/dev/null 2>&1 < /dev/null &" | Out-Null
                Start-Sleep -Seconds 1
                "  " + "$(adb -s $Serial shell "$binCel custo")".Trim()
                $eps = @(adb -s $Serial shell "$binCel episodios 400" | Where-Object { $_ -match '"evento":"inicio"' })
                "  episodios de pressao gravados: $($eps.Count)" + $(if ($eps.Count) { " (ultimo: " + ($eps[-1] -replace '.*"quando":"([^"]+)".*', '$1') + ")" } else { "" })
            }
        }
    }
}

# 3. Ajustes do projeto: simulacao SEMPRE primeiro; aplica so se algo muda (cada --aplicar grava um registro de desfazer)
$arq = Join-Path $pasta "ajustes-simulacao.txt"
python scripts\ajustes-script.py *> $arq
if ($LASTEXITCODE -ne 0) {
    Falhou "simulacao dos ajustes" $arq
} else {
    # linha "  chave   valor_antigo   -> valor_novo": muda quando o antigo (palavra inteira, no fim) nao e o novo
    $mudam = @(Get-Content $arq | Where-Object { $_ -match "->" } | Where-Object {
        $esq, $dir = $_ -split "->", 2
        $esq.TrimEnd() -notmatch ("(\s|^)" + [regex]::Escape($dir.Trim()) + "$")
    })
    if ($mudam.Count -eq 0) {
        Write-Host "ajustes: tudo no lugar (nada a aplicar)" -ForegroundColor Green
    } elseif (-not $Aplicar) {
        Write-Host "ajustes: $($mudam.Count) item(ns) fora do lugar (use -Aplicar):" -ForegroundColor Yellow
        $mudam | ForEach-Object { "    " + ($_.Trim() -replace "\s{2,}", "  ") }
    } else {
        $arqA = Join-Path $pasta "ajustes-aplicar.txt"
        python scripts\ajustes-script.py --aplicar *> $arqA
        if ($LASTEXITCODE -ne 0) { Falhou "aplicar os ajustes" $arqA }
        else {
            Write-Host "ajustes: $($mudam.Count) item(ns) aplicado(s):" -ForegroundColor Green
            $mudam | ForEach-Object { "    " + ($_.Trim() -replace "\s{2,}", "  ") }
            Get-Content $arqA | Where-Object { $_ -match "registro para desfazer" }
        }
    }
}

# 4. Auditoria (so leitura): mostra FALHA, AVISO e o resumo
$arq = Join-Path $pasta "auditoria.txt"
python scripts\auditoria.py *> $arq
$saidaAud = $LASTEXITCODE
$linhasAud = @(Get-Content $arq | Where-Object { $_ -match "\[FALHA\]|\[AVISO\]|== Resumo" })
if ($linhasAud.Count -eq 0) { Falhou "auditoria" $arq }
else { $linhasAud | ForEach-Object { $_.Substring(0, [Math]::Min(180, $_.Length)) } }
# a auditoria sai com 1 quando ha FALHA (o resumo ja mostra); so e erro se nem o resumo saiu
if ($saidaAud -gt 1) { Falhou "auditoria" $arq }

# 5. Metricas (modo rapido: memoria, pressao, CPU; fecha os apps em cache e restaura a tela) e comparacao com a anterior
if (-not $SemMedir) {
    $anterior = Get-ChildItem (Join-Path $Raiz "diagnostico") -Recurse -Filter "medicao-*.json" | Sort-Object LastWriteTime | Select-Object -Last 1
    $arq = Join-Path $pasta "medir.txt"
    python scripts\medir.py --rapido --rotulo rotina *> $arq
    if ($LASTEXITCODE -ne 0) {
        Falhou "medicao" $arq
    } else {
        Get-Content $arq | Where-Object { $_ -match "^(memoria|processos|pressao|CPU|disco)" }
        # a medicao NOVA e a que o medir.py acabou de gravar (linha "gravado em <arquivo>"), nunca "a mais recente do disco"
        $gravado = (Get-Content $arq | Select-String "gravado em (.+\.json)" | Select-Object -Last 1).Matches.Groups[1].Value
        if ($anterior -and $gravado -and (Test-Path $gravado) -and ($anterior.FullName -ne (Resolve-Path $gravado).Path)) {
            Write-Host "comparacao com $($anterior.Directory.Name)\$($anterior.Name):" -ForegroundColor Cyan
            python scripts\medir.py --comparar $anterior.FullName $gravado | Select-Object -First 25
        }
    }
}
Write-Host "relatorios: $pasta" -ForegroundColor Cyan
if ($avisos -gt 0) { Write-Warning "$avisos etapa(s) com falha: veja os relatorios"; exit 2 }
