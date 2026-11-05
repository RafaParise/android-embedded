# Liga a vigia de arquivos (guarda.py) a cada login, sem janela e com prioridade baixa. Nao mexe em Defender, firewall, VPN ou DNS.
# -Instalar | -Desinstalar | -Status (padrao). Tudo fica fora do git em %LOCALAPPDATA%\Guarda. Regras: memoria/ANTIVIRUS.md.
param([switch]$Instalar, [switch]$Desinstalar, [switch]$Status)
$ErrorActionPreference = 'Stop'
$tarefa = 'Guarda'
$script = Join-Path $PSScriptRoot 'guarda.py'
$python = (Get-Command python).Source
$sem = Join-Path (Split-Path $python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $sem)) { throw 'pythonw.exe nao encontrado ao lado do python.' }

if ($Desinstalar) {
    Stop-ScheduledTask -TaskName $tarefa -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $tarefa -Confirm:$false -ErrorAction SilentlyContinue
    & $python -B $script status
    return
}
if ($Instalar) {
    $acao = New-ScheduledTaskAction -Execute $sem -Argument "-B `"$script`" vigiar"
    $gatilho = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $regras = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -Priority 7 -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $tarefa -Action $acao -Trigger $gatilho -Settings $regras -Description 'Vigia de arquivos com ClamAV (projeto Android Embeeded)' -Force | Out-Null
    Start-ScheduledTask -TaskName $tarefa
    Start-Sleep -Seconds 3
}
& $python -B $script status
