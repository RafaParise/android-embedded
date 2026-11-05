# Monitor virtual do PC (Virtual Display Driver) para usar o celular como 2o monitor pelo Moonlight.
# Analogia: e uma tomada extra escondida atras do movel: so fica ligada enquanto o celular esta "plugado" pelo Moonlight.
# O Sunshine (servico do Windows, roda como SYSTEM) chama este script ao comecar e ao terminar a transmissao (apps.json).
# Uso:  pwsh -NoProfile -File monitor-virtual.ps1 ligar [-Largura 1600 -Altura 720]   liga o monitor e acerta a resolucao
#       pwsh -NoProfile -File monitor-virtual.ps1 desligar                            desliga (nenhum monitor fantasma)
#       pwsh -NoProfile -File monitor-virtual.ps1 status
# Precisa de administrador (o Sunshine ja e). Desfazer tudo: desligar + devcon remove Root\MttVDD (pasta do winget).
param([ValidateSet('ligar', 'desligar', 'status')][string]$Acao = 'status', [int]$Largura = 1600, [int]$Altura = 720)
$ErrorActionPreference = 'Stop'
$id = 'ROOT\DISPLAY\0000'
$dev = Get-PnpDevice -FriendlyName 'Virtual Display Driver' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($dev) { $id = $dev.InstanceId }

Add-Type @'
using System; using System.Runtime.InteropServices;
public class Tela {
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
  [DllImport("user32.dll", CharSet=CharSet.Ansi)] public static extern bool EnumDisplaySettings(string dev, int mode, ref DEVMODE dm);
  [DllImport("user32.dll", CharSet=CharSet.Ansi)] public static extern int ChangeDisplaySettingsEx(string dev, ref DEVMODE dm, IntPtr h, int flags, IntPtr p);
  [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Ansi)]
  public struct DISPLAY_DEVICE { public int cb; [MarshalAs(UnmanagedType.ByValTStr, SizeConst=32)] public string DeviceName;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst=128)] public string DeviceString; public int StateFlags;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst=128)] public string DeviceID; [MarshalAs(UnmanagedType.ByValTStr, SizeConst=128)] public string DeviceKey; }
  [DllImport("user32.dll", CharSet=CharSet.Ansi)] public static extern bool EnumDisplayDevices(string dev, int i, ref DISPLAY_DEVICE dd, int flags);
  // A saida (\\.\DISPLAYn) cujo monitor e o do Virtual Display Driver (id MTT1337); nunca a TV nem o monitor de verdade.
  public static string SaidaVirtual() {
    for (int i = 0; ; i++) {
      DISPLAY_DEVICE a = new DISPLAY_DEVICE(); a.cb = Marshal.SizeOf(a);
      if (!EnumDisplayDevices(null, i, ref a, 0)) return null;
      DISPLAY_DEVICE m = new DISPLAY_DEVICE(); m.cb = Marshal.SizeOf(m);
      for (int j = 0; EnumDisplayDevices(a.DeviceName, j, ref m, 0); j++) { if ((m.DeviceID ?? "").ToUpper().Contains("MTT1337")) return a.DeviceName; }
    }
  }
}
'@

function Telas { Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::AllScreens }
function Virtual { $n = [Tela]::SaidaVirtual(); if ($n) { Telas | Where-Object { $_.DeviceName -eq $n } | Select-Object -First 1 } }

switch ($Acao) {
    'status' {
        "monitor virtual: " + $(if ($dev) { $dev.Status } else { 'driver nao instalado' })
        $vn = [Tela]::SaidaVirtual()
        Telas | ForEach-Object { "  $($_.DeviceName) $($_.Bounds.Width)x$($_.Bounds.Height)$(if ($_.Primary) { ' (principal)' })$(if ($_.DeviceName -eq $vn) { ' (monitor virtual, para o celular)' })" }
    }
    'desligar' { pnputil /disable-device $id | Out-Null; "monitor virtual desligado" }
    'ligar' {
        pnputil /enable-device $id | Out-Null
        Start-Sleep -Seconds 3
        $v = Virtual
        if (-not $v) { throw 'o Windows nao mostrou o monitor virtual' }
        $dm = New-Object Tela+DEVMODE; $dm.dmSize = [Runtime.InteropServices.Marshal]::SizeOf($dm)
        [void][Tela]::EnumDisplaySettings($v.DeviceName, -1, [ref]$dm)
        $dm.dmPelsWidth = $Largura; $dm.dmPelsHeight = $Altura; $dm.dmFields = 0x80000 -bor 0x100000
        $r = [Tela]::ChangeDisplaySettingsEx($v.DeviceName, [ref]$dm, [IntPtr]::Zero, 1, [IntPtr]::Zero)  # 1 = guardar no registro
        $v = Virtual
        "monitor virtual ligado: $($v.DeviceName) $($v.Bounds.Width)x$($v.Bounds.Height) (codigo $r)"
    }
}
