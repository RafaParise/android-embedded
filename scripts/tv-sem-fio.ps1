# TV sem fio (Miracast, Win+K) com a melhor imagem e o menor atraso possiveis. Pedido do Rafael (05/11/2026).
# Analogia: o PC tem UMA antena e duas conversas: o roteador em 5/6 GHz e a TV em 2,4 GHz (a TV so fala essa faixa).
# Alternar entre as duas e como um interprete correndo entre duas salas: cada corrida e atraso e engasgo. No "modo TV"
# o PC entra no Wi-Fi de 2,4 GHz e as duas conversas ficam na mesma sala (mesmo canal): menos atraso, internet do PC
# mais lenta enquanto durar. A imagem vai na resolucao nativa da TV (1920x1080 a 60 Hz) em vez de 1024x768 esticado.
# Uso:  pwsh -File tv-sem-fio.ps1 status
#       pwsh -File tv-sem-fio.ps1 imagem [-Largura 1920 -Altura 1080]  so a resolucao da TV (TV ja conectada pelo Win+K)
#       pwsh -File tv-sem-fio.ps1 ligar     modo TV: o PC passa para a rede de 2,4 GHz do roteador (mesmo nome sem 5G)
#       pwsh -File tv-sem-fio.ps1 desligar  volta o PC para a rede de 5 GHz (internet rapida de novo)
# O melhor de verdade e o cabo HDMI: imagem sem compressao e atraso quase zero. Precisa de administrador para a placa.
param([ValidateSet('status', 'imagem', 'ligar', 'desligar')][string]$Acao = 'status', [int]$Largura = 1920, [int]$Altura = 1080,
      [int]$Hz = 60, [string]$Placa = 'Wi-Fi')
$ErrorActionPreference = 'Stop'
Add-Type @'
using System; using System.Runtime.InteropServices;
public class Tv {
  [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Ansi)]
  public struct DEVMODE {
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst=32)] public string dmDeviceName;
    public short dmSpecVersion, dmDriverVersion, dmSize, dmDriverExtra; public int dmFields;
    public int dmPositionX, dmPositionY, dmDisplayOrientation, dmDisplayFixedOutput;
    public short dmColor, dmDuplex, dmYResolution, dmTTOption, dmCollate;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst=32)] public string dmFormName;
    public short dmLogPixels; public int dmBitsPerPel, dmPelsWidth, dmPelsHeight, dmDisplayFlags, dmDisplayFrequency;
    public int dmICMMethod, dmICMIntent, dmMediaType, dmDitherType, dmReserved1, dmReserved2, dmPanningWidth, dmPanningHeight;
  }
  [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Ansi)]
  public struct DISPLAY_DEVICE { public int cb; [MarshalAs(UnmanagedType.ByValTStr, SizeConst=32)] public string DeviceName;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst=128)] public string DeviceString; public int StateFlags;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst=128)] public string DeviceID; [MarshalAs(UnmanagedType.ByValTStr, SizeConst=128)] public string DeviceKey; }
  [DllImport("user32.dll", CharSet=CharSet.Ansi)] public static extern bool EnumDisplaySettings(string dev, int mode, ref DEVMODE dm);
  [DllImport("user32.dll", CharSet=CharSet.Ansi)] public static extern int ChangeDisplaySettingsEx(string dev, ref DEVMODE dm, IntPtr h, int flags, IntPtr p);
  [DllImport("user32.dll", CharSet=CharSet.Ansi)] public static extern bool EnumDisplayDevices(string dev, int i, ref DISPLAY_DEVICE dd, int flags);
  // A saida ligada a um monitor "DEFAULT_MONITOR" (o Windows da esse id a tela sem fio do Miracast); nunca o monitor
  // de verdade nem o virtual do celular (MTT1337).
  public static string SaidaTv() {
    for (int i = 0; ; i++) {
      DISPLAY_DEVICE a = new DISPLAY_DEVICE(); a.cb = Marshal.SizeOf(a);
      if (!EnumDisplayDevices(null, i, ref a, 0)) return null;
      if ((a.StateFlags & 1) == 0) continue;  // nao esta na area de trabalho
      DISPLAY_DEVICE m = new DISPLAY_DEVICE(); m.cb = Marshal.SizeOf(m);
      for (int j = 0; EnumDisplayDevices(a.DeviceName, j, ref m, 0); j++) { if ((m.DeviceID ?? "").ToUpper().Contains("DEFAULT_MONITOR")) return a.DeviceName; }
    }
  }
}
'@

function Modo($saida) { $d = New-Object Tv+DEVMODE; $d.dmSize = [Runtime.InteropServices.Marshal]::SizeOf($d); [void][Tv]::EnumDisplaySettings($saida, -1, [ref]$d); $d }
# Nome da rede atual e das salvas: so na memoria, nunca em arquivo (regra do projeto: nome de rede nao vai a arquivo).
function Rede { (Get-NetConnectionProfile -InterfaceAlias $Placa -ErrorAction SilentlyContinue | Select-Object -First 1).Name }
function Perfis { netsh wlan show profiles | Select-String ':\s*(.+)$' | ForEach-Object { $_.Matches[0].Groups[1].Value.Trim() } }
function Faixa { if ((Rede) -match '[_ -]5G$') { '5 GHz' } else { '2,4 GHz (rede sem 5G no nome)' } }

switch ($Acao) {
    'status' {
        $tv = [Tv]::SaidaTv()
        if ($tv) { $m = Modo $tv; "TV conectada: $tv $($m.dmPelsWidth)x$($m.dmPelsHeight) a $($m.dmDisplayFrequency) Hz" } else { 'TV nao conectada (Win+K > TV PHILCO)' }
        "Wi-Fi do PC: $(Faixa); ligacao = $((Get-NetAdapter -Name $Placa).LinkSpeed)"
        $p2p = Get-NetAdapter | Where-Object { $_.InterfaceDescription -match 'Wi-Fi Direct' -and $_.Status -eq 'Up' }
        if ($p2p) { "ligacao com a TV (Wi-Fi Direct): $($p2p.LinkSpeed)" }
    }
    'imagem' {
        $tv = [Tv]::SaidaTv(); if (-not $tv) { throw 'TV nao conectada: Win+K > TV PHILCO, e rode de novo.' }
        $d = Modo $tv; $d.dmPelsWidth = $Largura; $d.dmPelsHeight = $Altura; $d.dmDisplayFrequency = $Hz
        $d.dmFields = 0x80000 -bor 0x100000 -bor 0x400000
        $r = [Tv]::ChangeDisplaySettingsEx($tv, [ref]$d, [IntPtr]::Zero, 1, [IntPtr]::Zero)   # 1 = guardar para as proximas conexoes
        $m = Modo $tv
        "TV: $($m.dmPelsWidth)x$($m.dmPelsHeight) a $($m.dmDisplayFrequency) Hz (codigo $r; 0 = ok)"
    }
    'ligar' {
        $atual = Rede
        if ($atual -notmatch '[_ -]5G$') { "O PC ja esta numa rede sem '5G' no nome (provavel 2,4 GHz). Nada a trocar."; break }
        $alvo = $atual -replace '[_ -]5G$', ''
        if (-not (Perfis | Where-Object { $_ -eq $alvo })) { throw 'Nao achei a rede de 2,4 GHz salva no PC (mesmo nome sem 5G). Conecte uma vez a ela pelo icone do Wi-Fi.' }
        $r = netsh wlan connect name="$alvo" interface="$Placa" 2>&1
        if (($r -join ' ') -match 'permiss|location') {
            'O Windows pede a permissao de LOCALIZACAO para trocar de rede por comando (a otimizacao desligou a localizacao).'
            'Troque a mao: icone do Wi-Fi > a rede SEM "5G" no nome. Depois: Win+K > TV PHILCO.'; break }
        Start-Sleep -Seconds 12
        if ((Rede) -match '[_ -]5G$') { 'A troca nao pegou: o PC continua na rede de 5 GHz. Troque a mao pelo icone do Wi-Fi.'; break }
        "Modo TV ligado: PC na rede de 2,4 GHz (ligacao $((Get-NetAdapter -Name $Placa).LinkSpeed)). Reconecte a TV: Win+K > TV PHILCO."
    }
    'desligar' {
        $atual = Rede
        if ($atual -match '[_ -]5G$') { 'O PC ja esta na rede de 5 GHz.'; break }
        $alvo = Perfis | Where-Object { $_ -match ('^' + [regex]::Escape($atual) + '[_ -]5G$') } | Select-Object -First 1
        if (-not $alvo) { throw 'Nao achei a rede de 5 GHz salva no PC (mesmo nome com 5G).' }
        $r = netsh wlan connect name="$alvo" interface="$Placa" 2>&1
        if (($r -join ' ') -match 'permiss|location') { 'O Windows pede a permissao de LOCALIZACAO. Troque a mao: icone do Wi-Fi > a rede COM "5G" no nome.'; break }
        Start-Sleep -Seconds 12
        "Modo TV desligado: PC de volta na rede de 5 GHz (ligacao $((Get-NetAdapter -Name $Placa).LinkSpeed))."
    }
}
