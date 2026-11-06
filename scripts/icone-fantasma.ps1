# Tira da tela inicial da Samsung um icone "fantasma": um "instale depois" do OMC ou de operadora para um app que
# NUNCA foi instalado (ex.: "Samsung Itaucard" = com.odete.samsung, 05/11/2026). O menu do icone so oferece
# "Desativar" (apagado), o banco da tela inicial e fechado para o adb e o launcher so apaga esses icones quando o
# pacote e desinstalado. Entao: instala um APK VAZIO com o mesmo nome (sem codigo, sem icone, sem permissao, chave
# descartavel) e desinstala em seguida. O launcher tira o icone; os outros ficam onde estao (a vaga fica vazia).
#
# Uso:  pwsh -File scripts\icone-fantasma.ps1 -Pacote com.odete.samsung            (simulacao: so confere)
#       pwsh -File scripts\icone-fantasma.ps1 -Pacote com.odete.samsung -Aplicar   (faz)
# Achar o pacote: toque no icone e leia o logcat ("Unable to launch ... targetComponent=ComponentInfo{PACOTE/...}").
# Recusa pacote que exista no aparelho (instalado, desativado ou removido com -k): ai nao e fantasma.
param(
    [Parameter(Mandatory)][string]$Pacote,
    [switch]$Aplicar
)
$ErrorActionPreference = 'Stop'
if ($Pacote -notmatch '^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$') { throw "nome de pacote invalido: $Pacote" }

$existe = adb shell "pm list packages -u $Pacote" 2>$null | Where-Object { $_.Trim() -eq "package:$Pacote" }
if ($existe) { Write-Output "RECUSADO: $Pacote existe no aparelho (instalado ou guardado com -k). Nao e icone fantasma."; exit 2 }
$bat = (adb shell "dumpsys battery" 2>$null) -join "`n"
$nivel = [int]([regex]::Match($bat, 'level: (\d+)').Groups[1].Value)
if ($nivel -lt 3) { Write-Output "Bateria em $nivel%: parado (regra dos 3%)."; exit 2 }
if (-not $Aplicar) { Write-Output "SIMULACAO: instalaria um APK vazio chamado $Pacote e o desinstalaria em seguida (bateria $nivel%). Use -Aplicar."; exit 0 }

$dex = 'C:\Projetos\ferramentas\compilar-dex'
$sdk = 'C:\Projetos\ferramentas\android-sdk'
$java = Join-Path $dex 'jdk\bin\java.exe'
$keytool = Join-Path $dex 'jdk\bin\keytool.exe'
$androidJar = Join-Path $sdk 'plat\android-12\android.jar'
$bt = Join-Path $sdk 'bt\android-14'
$aapt2 = Join-Path $bt 'aapt2.exe'
$zipalign = Join-Path $bt 'zipalign.exe'
$apksigner = Join-Path $bt 'lib\apksigner.jar'
foreach ($f in $java, $keytool, $androidJar, $aapt2, $zipalign, $apksigner) { if (-not (Test-Path $f)) { throw "falta $f" } }

$t = Join-Path ([IO.Path]::GetTempPath()) ('fantasma-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
[void][IO.Directory]::CreateDirectory($t)
try {
    $man = Join-Path $t 'AndroidManifest.xml'
    [IO.File]::WriteAllText($man, "<?xml version=`"1.0`" encoding=`"utf-8`"?>`n<manifest xmlns:android=`"http://schemas.android.com/apk/res/android`" package=`"$Pacote`">`n  <application android:hasCode=`"false`" android:label=`"vazio`" />`n</manifest>`n")
    $cru = Join-Path $t 'cru.apk'
    & $aapt2 link -o $cru -I $androidJar --manifest $man --min-sdk-version 26 --target-sdk-version 31 --version-code 1 --version-name 0
    if ($LASTEXITCODE -ne 0) { throw 'aapt2 link falhou' }
    $alinhado = Join-Path $t 'alinhado.apk'
    & $zipalign -f 4 $cru $alinhado
    if ($LASTEXITCODE -ne 0) { throw 'zipalign falhou' }
    $senha = Join-Path $t 'senha'
    [IO.File]::WriteAllText($senha, [guid]::NewGuid().ToString('N'))
    $ks = Join-Path $t 'descartavel.jks'
    & $keytool -genkeypair -keystore $ks -alias v -keyalg RSA -keysize 2048 -validity 2 -storepass:file $senha -keypass:file $senha -dname 'CN=vazio' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'keytool falhou' }
    $apk = Join-Path $t 'vazio.apk'
    & $java -jar $apksigner sign --ks $ks --ks-key-alias v --ks-pass "file:$senha" --out $apk $alinhado
    if ($LASTEXITCODE -ne 0) { throw 'apksigner falhou' }

    $r = (adb install $apk 2>&1) -join ' '
    Write-Output "instalar o vazio: $r"
    if ($r -notmatch 'Success') { exit 1 }
    Start-Sleep 3
    $u = (adb shell "pm uninstall $Pacote" 2>&1) -join ' '
    Write-Output "desinstalar: $u"
    $sobrou = adb shell "pm list packages -u $Pacote" 2>$null | Where-Object { $_.Trim() -eq "package:$Pacote" }
    if ($sobrou) { Write-Output "ATENCAO: o pacote vazio ficou no aparelho; rode: adb uninstall $Pacote"; exit 1 }
    Write-Output "Pronto: o vazio entrou e saiu. Confira a tela inicial (o icone some; os outros ficam no lugar)."
}
finally {
    Get-ChildItem $t -Recurse -File | ForEach-Object { [IO.File]::Delete($_.FullName) }
    [IO.Directory]::Delete($t, $true)
}
