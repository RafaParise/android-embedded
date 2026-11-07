#!/usr/bin/env python3
"""Ajustes de configuracao do script original (Otimizacao Samsung A12.txt) que ainda faltavam, com registro para desfazer.
Cada valor anterior fica em diagnostico/<data>/ajustes_antes.json; --restaurar volta ao ultimo registro.

  python scripts/ajustes-script.py                 simulacao: mostra antes -> depois
  python scripts/ajustes-script.py --aplicar       aplica e grava o registro
  python scripts/ajustes-script.py --restaurar     desfaz o ultimo registro
  python scripts/ajustes-script.py --dns automatico   so troca o DNS privado (automatico | adguard; adguard so em casa)
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DNS = "dns.adguard-dns.com"
SETTINGS = [  # (espaco, chave, valor)
    ("global", "send_action_app_error", "0"),
    ("global", "upload_apk_enable", "0"),
    ("global", "location_background_throttle_interval_ms", "3600000"),
    ("global", "wifi_suspend_optimizations_enabled", "0"),
    ("global", "sem_enhanced_cpu_responsiveness", "1"),
    ("global", "cached_apps_freezer", "enabled"),  # vale depois do reinicio
    ("global", "private_dns_mode", "opportunistic"),  # Automatico: o estrito (AdGuard) derrubou a pagina de login do Wi-Fi da escola
    ("global", "captive_portal_mode", "1"),  # 0 desligava a pagina de login das redes SEDUC (estava assim antes do projeto)
    ("global", "captive_portal_detection_enabled", "1"),
    ("global", "default_install_location", "1"),
    ("secure", "upload_apk_enable", "0"),  # o script usa o espaco secure; o Play Protect reescreve a chave global (volta a 1), por isso as duas
    ("global", "force_resizable_activities", "1"),  # Dashcam: tela dividida em qualquer app; vale depois de reiniciar
    ("global", "enable_freeform_support", "1"),
    # itens do script que voltaram ao padrao (27/10 ~23:15: animacoes 1.0, show_touches 0, varredura Wi-Fi e dados moveis ligados)
    ("global", "window_animation_scale", "0.0"),
    ("global", "transition_animation_scale", "0.0"),
    ("global", "animator_duration_scale", "0.0"),
    ("system", "show_touches", "1"),
    ("global", "mobile_data_always_on", "0"),
    ("global", "wifi_scan_always_enabled", "0"),
    ("global", "ble_scan_always_enabled", "0"),  # apps novos na memoria interna: no cartao adotado perdem papel/estado no reboot
    ("global", "assisted_gps_enabled", "1"),  # A-GPS (SUPL): fix mais rapido para o Organic Maps; reapareceu em 0 em 28/10 depois de mexer na Precisao de Local
]
APPOPS = [  # (pacote, operacao, modo)
    ("com.android.vending", "RUN_IN_BACKGROUND", "ignore"),
    ("com.microsoft.teams", "RUN_IN_BACKGROUND", "ignore"),
    ("com.termux", "RUN_IN_BACKGROUND", "ignore"),  # script, Fase 2 Termux: zero consumo ocioso em segundo plano (medido em 02/11: nao impede o guarda `saida` nem o Termux:Boot; ver memoria/CHECKLIST-SCRIPT.md)
    ("net.sourceforge.opencamera", "PICTURE_IN_PICTURE", "allow"),  # Dashcam (ja e o padrao; fica explicito)
    ("app.organicmaps", "PLAY_AUDIO", "allow"),
    # nota do script: repetir a regra em apps sociais e de compras (sem alarme nem estado critico; Instagram nao esta instalado); notificacoes continuam por push
    ("com.shopee.br", "RUN_IN_BACKGROUND", "ignore"),
    ("com.valvesoftware.android.steam.community", "RUN_IN_BACKGROUND", "ignore"),
    ("br.com.vivo", "RUN_IN_BACKGROUND", "ignore"),  # Meu Vivo: surto de 94% de CPU por ~90 s em segundo plano (27/10); push continua
    ("org.fossify.filemanager", "MANAGE_EXTERNAL_STORAGE", "allow"),  # o gerenciador de arquivos (no lugar de Meus Arquivos) precisa ver todos os arquivos
]
GRANTS = [("org.fossify.gallery", "android.permission.READ_EXTERNAL_STORAGE")]  # Galeria no lugar da Samsung: so le midias (sem localizacao das fotos)
BUCKETS = [("com.whatsapp.w4b", "30")]  # 30 = FREQUENT
WHITELIST = ["net.sourceforge.opencamera", "app.organicmaps", "org.fossify.calendar"]  # lista de Doze (script, Dashcam; agenda por pesquisa)
DEVCFG = [("activity_manager", "max_phantom_processes", "2147483647"),  # Termux sobrevive em segundo plano (limite do Android 12)
          # Doze profundo ~40 min mais cedo com o celular parado, sem cabo e de tela apagada (tecnica do Naptime/ForceDoze, sem root;
          # 06/11: padrao 30+30 min; quem esta na lista do Doze, como Termux, Tailscale, SED e Relogio, nao e afetado)
          ("device_idle", "inactive_to", "600000"),
          ("device_idle", "idle_after_inactive_to", "600000")]


def sh(cmd, timeout=60, estrito=False):
    r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    if estrito and getattr(r, "returncode", 0) != 0:
        # leitura do estado ANTERIOR: texto de erro do adb ("error: closed") nao pode virar "valor anterior" no registro de desfazer
        sys.exit(f"ABORTADO: a leitura '{cmd}' falhou (adb saiu com {r.returncode}: {(r.stdout + r.stderr).strip()[:80]}); nada foi alterado")
    return (r.stdout + r.stderr).strip()


def ler_antes():
    antes: dict = {"settings": {}, "appops": {}, "buckets": {}, "device_config": {}, "whitelist": {}, "grants": {}}
    for ns, k, _ in SETTINGS:
        v = sh(f"settings get {ns} {k}", estrito=True)
        antes["settings"][f"{ns}/{k}"] = None if v in ("null", "") else v
    for pkg, op, _ in APPOPS:
        m = re.search(rf"{op}: (\w+)", sh(f"cmd appops get {pkg} {op}", estrito=True))
        antes["appops"][f"{pkg}/{op}"] = m.group(1) if m else None
    for pkg, perm in GRANTS:
        antes["grants"][f"{pkg}/{perm}"] = f"{perm}: granted=true" in sh(f"dumpsys package {pkg}", estrito=True)
    for pkg, _ in BUCKETS:
        antes["buckets"][pkg] = sh(f"am get-standby-bucket {pkg}", estrito=True).strip()
    idle = sh("dumpsys deviceidle whitelist", estrito=True)
    for pkg in WHITELIST:
        antes["whitelist"][pkg] = f",{pkg}," in idle
    for ns, k, _ in DEVCFG:
        v = sh(f"device_config get {ns} {k}", estrito=True)
        antes["device_config"][f"{ns}/{k}"] = None if v in ("null", "") else v
    antes["sync_desligado"] = "persistent" if sh("device_config is_sync_disabled_for_tests", estrito=True).strip() == "true" else "none"
    return antes


def aplicar():
    for ns, k, v in SETTINGS:
        sh(f"settings put {ns} {k} {v}")
    for pkg, op, modo in APPOPS:
        sh(f"cmd appops set {pkg} {op} {modo}")
    for pkg, perm in GRANTS:
        sh(f"pm grant {pkg} {perm}")
    for pkg, b in BUCKETS:
        sh(f"am set-standby-bucket {pkg} {b}")
    for pkg in WHITELIST:
        sh(f"dumpsys deviceidle whitelist +{pkg}")
    sh("device_config set_sync_disabled_for_tests persistent")
    for ns, k, v in DEVCFG:
        sh(f"device_config put {ns} {k} {v}")


def restaurar(antes):
    for chave, v in antes["settings"].items():
        ns, k = chave.split("/", 1)
        sh(f"settings delete {ns} {k}" if v is None else f"settings put {ns} {k} {v}")
    for chave, v in antes["appops"].items():
        pkg, op = chave.split("/", 1)
        sh(f"cmd appops set {pkg} {op} {v or 'default'}")
    for chave, estava in antes.get("grants", {}).items():
        pkg, perm = chave.split("/", 1)
        if not estava:
            sh(f"pm revoke {pkg} {perm}")
    for pkg, b in antes["buckets"].items():
        if b.isdigit():
            sh(f"am set-standby-bucket {pkg} {b}")
    for pkg, estava in antes.get("whitelist", {}).items():
        if not estava:
            sh(f"dumpsys deviceidle whitelist -{pkg}")
    for chave, v in antes["device_config"].items():
        ns, k = chave.split("/", 1)
        sh(f"device_config delete {ns} {k}" if v is None else f"device_config put {ns} {k} {v}")
    sh(f"device_config set_sync_disabled_for_tests {antes.get('sync_desligado', 'none')}")


def ultimo_registro():
    achados = sorted((RAIZ / "diagnostico").glob("*/ajustes_antes.json"))
    return achados[-1] if achados else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--restaurar", action="store_true")
    ap.add_argument("--dns", choices=["automatico", "adguard"])
    a = ap.parse_args()

    if "SM-A125" not in sh("getprop ro.product.model"):
        sys.exit("ABORTADO: aparelho nao encontrado ou inesperado")

    if a.dns:
        modo, host = ("opportunistic", None) if a.dns == "automatico" else ("hostname", DNS)
        sh(f"settings put global private_dns_mode {modo}")
        if host:
            sh(f"settings put global private_dns_specifier {host}")
        print(f"DNS privado: {sh('settings get global private_dns_mode')} {sh('settings get global private_dns_specifier')}")
        return

    if a.restaurar:
        reg = ultimo_registro()
        if not reg:
            sys.exit("nenhum registro de ajustes em diagnostico/")
        restaurar(json.loads(reg.read_text(encoding="utf-8")))
        print(f"restaurado a partir de {reg}")
        return

    antes = ler_antes()
    for chave, v in antes["settings"].items():
        alvo = next(val for ns, k, val in SETTINGS if f"{ns}/{k}" == chave)
        print(f"  {chave:<52} {str(v):<14} -> {alvo}")
    for chave, v in antes["appops"].items():
        alvo = next(modo for pkg, op, modo in APPOPS if f"{pkg}/{op}" == chave)
        print(f"  appops {chave:<45} {str(v):<14} -> {alvo}")
    for chave, estava in antes["grants"].items():
        print(f"  grant  {chave:<45} {'concedida' if estava else 'negada':<14} -> concedida")
    for pkg, estava in antes["whitelist"].items():
        print(f"  doze   {pkg:<45} {'na lista' if estava else 'fora':<14} -> na lista")
    for pkg, v in antes["buckets"].items():
        print(f"  bucket {pkg:<45} {v:<14} -> 30")
    for chave, v in antes["device_config"].items():
        print(f"  device_config {chave:<38} {str(v):<14} -> 2147483647 (sync de flags {antes['sync_desligado']} -> persistent)")
    if not a.aplicar:
        print("SIMULACAO: nada foi alterado (use --aplicar).")
        return

    pasta = RAIZ / "diagnostico" / time.strftime("%Y%m%d-%H%M%S")
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "ajustes_antes.json").write_text(json.dumps(antes, indent=1, ensure_ascii=False), encoding="utf-8")
    aplicar()
    print(f"aplicado; registro para desfazer: {pasta / 'ajustes_antes.json'}")
    print("conferencia:")
    for ns, k, _ in SETTINGS:
        print(f"  {ns}/{k} = {sh(f'settings get {ns} {k}')}")
    for pkg, op, _ in APPOPS:
        print(f"  {sh(f'cmd appops get {pkg} {op}')}  [{pkg}]")
    print(f"  bucket w4b = {sh('am get-standby-bucket com.whatsapp.w4b')}")
    print(f"  doze: {sh('dumpsys deviceidle whitelist | grep -c user,')} apps na lista")
    print(f"  max_phantom_processes = {sh('device_config get activity_manager max_phantom_processes')}")


if __name__ == "__main__":
    main()
