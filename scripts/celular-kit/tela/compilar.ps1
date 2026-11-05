# Compila Tela.java em tela.dex. Ferramentas portateis em C:\Projetos\ferramentas\compilar-dex (JDK e R8 oficiais, com hash conferido); nada e instalado no Windows.
$ErrorActionPreference = 'Stop'
$base = 'C:\Projetos\ferramentas\compilar-dex'
$java = Join-Path $base 'jdk\bin\java.exe'
$javac = Join-Path $base 'jdk\bin\javac.exe'
$r8 = Join-Path $base 'r8.jar'
foreach ($f in $java, $javac, $r8) { if (-not (Test-Path $f)) { throw "falta $f" } }
$t = Join-Path ([IO.Path]::GetTempPath()) ('tela-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
[void][IO.Directory]::CreateDirectory($t)
try {
    & $javac --release 8 -Xlint:-options -d $t (Join-Path $PSScriptRoot 'Tela.java')
    if ($LASTEXITCODE -ne 0) { throw 'javac falhou' }
    & $java -cp $r8 com.android.tools.r8.D8 --release --min-api 26 --output $t (Get-ChildItem $t -Filter *.class).FullName
    if ($LASTEXITCODE -ne 0) { throw 'd8 falhou' }
    Copy-Item (Join-Path $t 'classes.dex') (Join-Path $PSScriptRoot 'tela.dex') -Force
    $i = Get-Item (Join-Path $PSScriptRoot 'tela.dex')
    "tela.dex: $($i.Length) bytes, SHA-256 $((Get-FileHash $i.FullName).Hash)"
} finally { [IO.Directory]::Delete($t, $true) }
