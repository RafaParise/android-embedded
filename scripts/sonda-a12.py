#!/usr/bin/env python3
"""Sonda SOMENTE LEITURA do Galaxy A12 por ADB.
Grava tudo em diagnostico/<data>/ (fora do GitHub) e imprime um resumo curto.
Uso: python scripts/sonda-a12.py"""
import datetime
import json
import pathlib
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = pathlib.Path(__file__).resolve().parent.parent
ADB = shutil.which("adb") or (str(pathlib.Path.home()) + r"\AppData\Local\Microsoft\WinGet\Packages"
                              r"\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe")
OUT = RAIZ / "diagnostico" / datetime.datetime.now().strftime("%Y%m%d-%H%M")
OUT.mkdir(parents=True, exist_ok=True)
GB = 1 << 30


def sh(cmd, t=180):
    try:
        p = subprocess.run([ADB, "shell", cmd], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=t)
        return (p.stdout or "").strip()
    except Exception as e:  # noqa: BLE001
        return f"[erro] {e}"


def corta(txt, n=12, c=150):
    return "\n".join(l[:c] for l in (txt or "(vazio)").splitlines()[:n])


def secao(titulo, txt, n=12):
    print(f"\n== {titulo} ==\n{corta(txt, n)}")


dev = subprocess.run([ADB, "devices"], capture_output=True, text=True).stdout
if not re.search(r"\tdevice\s*$", dev, re.M):
    sys.exit("Nenhum aparelho autorizado: ligue a Depuracao USB e aceite a chave RSA no celular.")

PROPS = ["ro.product.model", "ro.build.version.release", "ro.build.version.oneui", "ro.build.version.security_patch",
         "ro.build.display.id", "ro.product.cpu.abilist", "ro.zygote", "ro.boot.verifiedbootstate",
         "ro.boot.flash.locked", "ro.boot.warranty_bit"]
SETTINGS = [("global", k) for k in (
    "window_animation_scale", "transition_animation_scale", "animator_duration_scale", "ram_expand_size",
    "ram_expand_size_list", "activity_manager_constants", "sem_enhanced_cpu_responsiveness", "low_power",
    "private_dns_mode", "private_dns_specifier", "wifi_scan_always_enabled", "ble_scan_always_enabled",
    "send_action_app_error", "location_background_throttle_interval_ms", "wifi_suspend_optimizations_enabled",
    "mobile_data_always_on", "assisted_gps_enabled", "force_resizable_activities", "enable_freeform_support",
    "development_settings_enabled", "adb_enabled", "cached_apps_freezer")] + [
    ("system", "show_touches"), ("secure", "default_input_method"), ("secure", "upload_apk_enable")]

R = {"props": {p: sh(f"getprop {p}") for p in PROPS}, "kernel": sh("uname -r")}
R["settings"] = {f"{ns}:{k}": sh(f"settings get {ns} {k}") for ns, k in SETTINGS}
R["am"] = sh("dumpsys activity settings | grep -i -E 'max_cached|max_phantom|use_freezer' | head -6")
R["df"] = sh("df -h | grep -E 'Filesystem|/data$|/storage|/mnt/expand'")
R["volumes"] = sh("sm list-volumes all")
R["meminfo"] = sh("grep -E 'MemTotal|MemAvailable|SwapTotal|SwapFree' /proc/meminfo")
R["bateria"] = sh("dumpsys battery | grep -E 'level|status|powered|Max charging current'")
R["ime"] = sh("ime list -s")
ds = sh("dumpsys diskstats")
mi = sh("dumpsys meminfo | head -60")
(OUT / "diskstats.txt").write_text(ds, encoding="utf-8")
(OUT / "meminfo.txt").write_text(mi, encoding="utf-8")

todos = sh("pm list packages").replace("package:", "").split()
desat = sh("pm list packages -d").replace("package:", "").split()
terc = sh("pm list packages -3").replace("package:", "").split()
for nome, lista in (("pacotes_todos", todos), ("pacotes_desativados", desat), ("pacotes_terceiros", terc)):
    (OUT / f"{nome}.txt").write_text("\n".join(sorted(lista)), encoding="utf-8")
(OUT / "sonda.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- resumo curto ----
P = R["props"]
print(f"== {P['ro.product.model']} | Android {P['ro.build.version.release']} (One UI {P['ro.build.version.oneui']}) "
      f"| patch {P['ro.build.version.security_patch']} | kernel {R['kernel']}")
print(f"   ABIs {P['ro.product.cpu.abilist']} | zygote {P['ro.zygote']} | boot {P['ro.boot.verifiedbootstate']} "
      f"| travado {P['ro.boot.flash.locked']} | Knox {P['ro.boot.warranty_bit']}")
secao("bateria", R["bateria"])
secao("armazenamento", R["df"])
secao("volumes", R["volumes"])


def pega(chave):
    m = re.search(rf"^{chave}: (\d+)", ds, re.M)
    return f"{int(m.group(1)) / GB:.1f}" if m else "?"


print("\n== /data por tipo (GB) ==")
print(" | ".join(f"{k.replace(' Size', '')} {pega(k)}" for k in
                 ("App Size", "App Data Size", "App Cache Size", "Photos Size", "Videos Size", "System Size", "Other Size")))


def lista_ds(chave):
    m = re.search(rf"^{chave}: (\[.*\])", ds, re.M)
    return json.loads(m.group(1)) if m else []


nomes, ap_, da, ca = (lista_ds(c) for c in ("Package Names", "App Sizes", "App Data Sizes", "Cache Sizes"))
n = min(len(nomes), len(ap_), len(da), len(ca))
print("maiores (MB: app / dados / cache):")
for p, a, d, c in sorted(((nomes[i], ap_[i], da[i], ca[i]) for i in range(n)), key=lambda t: -sum(t[1:]))[:10]:
    print(f"  {p[:46]:46} {a / 1048576:6.0f} {d / 1048576:6.0f} {c / 1048576:6.0f}")

secao("memoria", R["meminfo"])
secao("ActivityManager", R["am"])
print("\n== configuracoes (null = nao existe) ==")
itens = [f"{k.split(':', 1)[1]}={v}" for k, v in R["settings"].items()]
for i in range(0, len(itens), 2):
    print("  " + " | ".join(itens[i:i + 2]))
secao("teclados habilitados", R["ime"])
print(f"\n== pacotes == total {len(todos)} | desativados {len(desat)} | terceiros {len(terc)}")
notaveis = re.compile(r"termux|fdroid|opencamera|organicmaps|tailscale|vlc|ppsspp|retroarch|armsx2|arena|claude|shizuku", re.I)
print("notaveis:", ", ".join(p for p in sorted(set(terc)) if notaveis.search(p)) or "(nenhum)")
print("\n== maiores processos (RSS) ==\n" + corta("\n".join(l for l in mi.splitlines() if "K:" in l), 12))
print(f"\nArquivos completos em: {OUT}")
