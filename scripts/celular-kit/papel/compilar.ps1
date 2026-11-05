# Compila o papel de parede rolante em papel.apk (sem Android Studio, sem Gradle).
# Ferramentas portateis e oficiais, com hash conferido em 05/11/2026, fora do git:
#   C:\Projetos\ferramentas\compilar-dex (JDK 21 e R8)
#   C:\Projetos\ferramentas\android-sdk  (platform-31_r01 sha1 ca5bcaa5..., build-tools_r34-windows sha1 62cfde1b..., de dl.google.com)
# A chave de assinatura e a senha dela ficam so em C:\Projetos\ferramentas\android-sdk (nunca no git). Sem a chave,
# um APK novo nao atualiza o instalado: o papel-rolante.py desinstala e instala de novo.
$ErrorActionPreference = 'Stop'
$dex = 'C:\Projetos\ferramentas\compilar-dex'
$sdk = 'C:\Projetos\ferramentas\android-sdk'
$java = Join-Path $dex 'jdk\bin\java.exe'
$javac = Join-Path $dex 'jdk\bin\javac.exe'
$keytool = Join-Path $dex 'jdk\bin\keytool.exe'
$r8 = Join-Path $dex 'r8.jar'
$androidJar = Join-Path $sdk 'plat\android-12\android.jar'
$bt = Join-Path $sdk 'bt\android-14'
$aapt2 = Join-Path $bt 'aapt2.exe'
$zipalign = Join-Path $bt 'zipalign.exe'
$apksigner = Join-Path $bt 'lib\apksigner.jar'
foreach ($f in $java, $javac, $keytool, $r8, $androidJar, $aapt2, $zipalign, $apksigner) { if (-not (Test-Path $f)) { throw "falta $f" } }

$chave = Join-Path $sdk 'chave-papel.jks'
$senhaArq = Join-Path $sdk 'chave-papel.senha'
if (-not (Test-Path $chave)) {
    $senha = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
    [IO.File]::WriteAllText($senhaArq, $senha)
    & $keytool -genkeypair -keystore $chave -alias papel -keyalg RSA -keysize 2048 -validity 10000 `
        -storepass:file $senhaArq -keypass:file $senhaArq -dname 'CN=Papel rolante' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'keytool falhou' }
}

$t = Join-Path ([IO.Path]::GetTempPath()) ('papel-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
[void][IO.Directory]::CreateDirectory($t)
try {
    $cls = Join-Path $t 'cls'
    [void][IO.Directory]::CreateDirectory($cls)
    $fontes = (Get-ChildItem (Join-Path $PSScriptRoot 'src') -Recurse -Filter *.java).FullName
    & $javac --release 8 -Xlint:-options -cp $androidJar -d $cls $fontes
    if ($LASTEXITCODE -ne 0) { throw 'javac falhou' }
    $classes = (Get-ChildItem $cls -Recurse -Filter *.class).FullName
    & $java -cp $r8 com.android.tools.r8.D8 --release --min-api 26 --lib $androidJar --output $t $classes
    if ($LASTEXITCODE -ne 0) { throw 'd8 falhou' }

    $res = Join-Path $t 'res.zip'
    & $aapt2 compile --dir (Join-Path $PSScriptRoot 'res') -o $res
    if ($LASTEXITCODE -ne 0) { throw 'aapt2 compile falhou' }
    $cru = Join-Path $t 'cru.apk'
    & $aapt2 link -o $cru -I $androidJar --manifest (Join-Path $PSScriptRoot 'AndroidManifest.xml') `
        --min-sdk-version 26 --target-sdk-version 31 --version-code 1 --version-name 1.0 $res
    if ($LASTEXITCODE -ne 0) { throw 'aapt2 link falhou' }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $z = [IO.Compression.ZipFile]::Open($cru, 'Update')
    try { [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($z, (Join-Path $t 'classes.dex'), 'classes.dex') } finally { $z.Dispose() }

    $alinhado = Join-Path $t 'alinhado.apk'
    & $zipalign -f 4 $cru $alinhado
    if ($LASTEXITCODE -ne 0) { throw 'zipalign falhou' }
    # O APK fica FORA de scripts/ (o sync recusa .apk na memoria): diagnostico/ nao vai ao git.
    $saida = Join-Path $PSScriptRoot '..\..\..\diagnostico\papel.apk'
    & $java -jar $apksigner sign --ks $chave --ks-key-alias papel --ks-pass "file:$senhaArq" --out $saida $alinhado
    if ($LASTEXITCODE -ne 0) { throw 'apksigner falhou' }
    & $java -jar $apksigner verify $saida
    if ($LASTEXITCODE -ne 0) { throw 'assinatura nao confere' }
    $i = Get-Item $saida
    "papel.apk: $($i.Length) bytes, SHA-256 $((Get-FileHash $i.FullName).Hash)"
} finally { [IO.Directory]::Delete($t, $true) }
