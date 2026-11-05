#!/usr/bin/env python3
"""Auditoria do Galaxy A12 pelo ADB (somente leitura; --fumaca abre apps). Confere o que foi feito e o que costuma quebrar:
armazenamento e cartao (principal = memoria interna; cartao adotado ocioso ou portatil), lotes de bloatware, apps essenciais,
papeis e teclado, rede (DNS e portal cativo), ajustes do script, apps de codigo aberto (volume, versao, permissao de arquivos),
alarme, depuracao. Grava o relatorio em diagnostico/<data>/auditoria.md.

  python scripts/auditoria.py            relatorio completo
  python scripts/auditoria.py --fumaca   alem disso roda teste-fumaca.py --rapido
Saida: [OK] [FALHA] [AVISO] [INFO]; codigo de saida 1 se houver FALHA.
"""
import argparse
import datetime
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

RAIZ = pathlib.Path(__file__).resolve().parent.parent
# Apps que o Android precisa ja no boot ou que guardam estado que nao pode corromper: ficam na memoria interna
# (no cartao adotado so existem depois que o vold monta o volume; teclado e navegador padrao voltaram ao Google/Chrome no reboot).
INTERNOS = ["helium314.keyboard", "org.fossify.messages", "org.fossify.clock", "org.mozilla.fennec_fdroid",
            "org.videolan.vlc", "com.junkfood.seal", "com.termux"]
ESSENCIAIS = ["com.google.android.gms", "com.android.vending", "com.google.android.webview", "com.android.settings",
              "com.android.systemui", "com.android.phone", "com.android.server.telecom", "com.sec.android.app.launcher",
              "com.samsung.android.incallui", "com.samsung.android.app.telephonyui", "com.android.bips", "com.google.android.documentsui",
              "com.google.android.captiveportallogin", "com.google.android.networkstack", "com.samsung.android.providers.contacts",
              "com.android.providers.telephony", "com.android.mms.service", "com.android.externalstorage"]
USUARIO = ["br.gov.meugovbr", "br.gov.sp.educacao.sed.android", "br.gov.sp.educacao.saladofuturo.professores",
           "com.whatsapp.w4b", "com.microsoft.teams", "com.microsoft.office.outlook", "io.github.rafaparise.arena",
           "com.termux", "com.tailscale.ipn"]
FOSS = ["helium314.keyboard", "org.fossify.messages", "org.fossify.clock", "org.fossify.calendar", "org.fossify.notes",
        "org.fossify.gallery", "org.fossify.filemanager", "org.fossify.math", "org.mozilla.fennec_fdroid",
        "net.thunderbird.android", "org.schabi.newpipe", "org.videolan.vlc", "com.junkfood.seal", "app.organicmaps",
        "net.sourceforge.opencamera", "com.gitlab.mudlej.MjPdfReader", "com.google.android.diskusage", "org.fdroid.fdroid",
        "org.kde.kdeconnect_tp", "com.freerdp.afreerdp", "com.termux", "info.dvkr.screenstream", "com.mattgmg.miracastwidget",
        "org.fossify.contacts", "org.fossify.phone", "org.documentfoundation.libreoffice"]  # FeedTV: o Rafael desinstalou em 30/10
PAPEIS = {"android.app.role.SMS": "org.fossify.messages", "android.app.role.BROWSER": "org.mozilla.fennec_fdroid",
          "android.app.role.HOME": "com.sec.android.app.launcher", "android.app.role.DIALER": "org.fossify.phone"}
IME = "helium314.keyboard/.latin.LatinIME"
# Desativados antes do projeto (script antigo do Rafael) ou por troca manual; conhecidos e aceitos
ESPERADOS_FORA = {"com.samsung.android.messaging": "trocado pelo Fossify Mensagens",
                  "com.samsung.android.dialer": "trocado pelo Fossify Telefone (lote FOSS-telefone, Rafael 05/11; a emergencia fica no telephonyui)",
                  "com.sec.android.emergencylauncher": "modo de emergencia Samsung, desativado antes do projeto"}
AJUSTES = [("global", "window_animation_scale", "0.0"), ("global", "transition_animation_scale", "0.0"),
           ("global", "animator_duration_scale", "0.0"), ("system", "show_touches", "1"), ("global", "mobile_data_always_on", "0"),
           ("global", "wifi_scan_always_enabled", "0"), ("global", "ble_scan_always_enabled", "0"),
           ("global", "force_resizable_activities", "1"), ("global", "enable_freeform_support", "1"), ("secure", "upload_apk_enable", "0"),
           ("global", "send_action_app_error", "0"), ("global", "upload_apk_enable", "0"),
           ("global", "location_background_throttle_interval_ms", "3600000"), ("global", "wifi_suspend_optimizations_enabled", "0"),
           ("global", "sem_enhanced_cpu_responsiveness", "1"), ("global", "cached_apps_freezer", "enabled"),
           ("global", "assisted_gps_enabled", "1")]  # A-GPS: fix do GPS mais rapido (a Precisao de Local do Google fica desligada)

# UUID do cartao quando era PORTATIL exFAT: Dashcam e NewPipe gravavam em /storage/5E6F-7A8B (por SAF). Se o cartao for formatado de novo
# o UUID pode mudar: o codigo usa o do volume montado e deixa esta constante so para as mensagens.
UUID_PORTATIL = "5E6F-7A8B"

R: list[tuple[str, str, str, str]] = []


def sh(cmd, timeout=60):
    r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).replace("\r", "").strip()


def reg(sec, nivel, item, det=""):
    R.append((sec, nivel, item, det))


def pacotes(flag=""):
    return {l.split(":", 1)[1].strip() for l in sh(f"pm list packages {flag}").splitlines() if l.startswith("package:")}


def caminhos():
    d = {}
    for l in sh("pm list packages -f", 120).splitlines():
        m = re.match(r"package:(.+?)=([\w.]+)$", l.strip())
        if m:
            d[m.group(2)] = m.group(1)
    return d


def carrega(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, RAIZ / "scripts" / arquivo)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def aparelho():
    s = "Aparelho"
    modelo = sh("getprop ro.product.model")
    reg(s, "OK" if modelo == "SM-A125M" else "FALHA", "modelo", modelo or "sem resposta do ADB")
    reg(s, "OK" if sh("getprop sys.boot_completed") == "1" else "FALHA", "boot completo")
    b = sh("dumpsys battery")
    n = re.search(r"level:\s*(\d+)", b)
    carga = "USB powered: true" in b or "AC powered: true" in b
    nivel = int(n.group(1)) if n else -1
    reg(s, "AVISO" if nivel < 5 else "INFO", "bateria", f"{nivel}% carregando={carga}")
    reg(s, "INFO", "uptime", sh("uptime | sed 's/,  load.*//'"))


def volumes():
    """sm list-volumes all -> [(id, estado, uuid)]. private:* = cartao ADOTADO, public:* = cartao PORTATIL, emulated;0 = memoria interna."""
    linhas = [l.split() for l in sh("sm list-volumes all").splitlines()]
    return [(p[0], p[1], p[2] if len(p) > 2 else "") for p in linhas if len(p) >= 2]


def dados_do_app(pacote):
    """Tamanho dos dados privados do app em MB (dumpsys diskstats; a saida crua nunca e impressa). None se nao achar."""
    txt = sh("dumpsys diskstats")

    def lista(nome):
        m = re.search(nome + r":\s*(\[.*?\])\s*$", txt, re.M)
        return json.loads(m.group(1)) if m else []

    nomes, dados = lista("Package Names"), lista("App Data Sizes")
    return round(dados[nomes.index(pacote)] / 1048576) if pacote in nomes and len(dados) == len(nomes) else None


def armazenamento(todos, caminho):
    s = "Armazenamento"
    vols = volumes()
    no_cartao = sorted(p for p, c in caminho.items() if c.startswith("/mnt/expand/"))
    for vid, estado, _ in vols:
        if vid == "emulated;0":
            reg(s, "OK" if estado == "mounted" else "FALHA", "memoria interna emulada", estado)
    # REGRA PERMANENTE (28/10/2026): o principal e a memoria INTERNA (sm get-primary-storage-uuid = null). Com o cartao ADOTADO como
    # principal (o "cartao unificado", via pm move-primary-storage), 1.412 de 5.006 arquivos ficaram diferentes do backup no md5 e, no
    # teste de gravacao (64 MB aleatorios, cache descartado antes de reconferir), o adotado devolveu arquivo diferente e a interna igual.
    # Causa nao provada (cartao com defeito ou limite do adotado da Samsung neste A12). "Success", du e contagem de arquivos nao provam
    # integridade, e conferir o md5 logo depois de gravar engana (vem do cache de paginas): so scripts/teste-gravacao.py.
    primario = sh("sm get-primary-storage-uuid").strip()
    if primario in ("null", "", "primary_physical"):
        reg(s, "OK", "armazenamento principal na memoria interna", f"{primario or 'vazio'} (null = interna)")
    elif len(primario.split()) != 1:  # nao e UUID: o sm nao respondeu (ADB caiu?)
        reg(s, "AVISO", "armazenamento principal", f"sem resposta valida do sm: {primario[:60]}")
    else:
        reg(s, "FALHA", "armazenamento principal FORA da memoria interna",
            f"{primario} (esperado null). Em 28/10 o cartao como principal devolveu arquivos corrompidos. NAO use pm move-primary-storage; "
            "rode scripts/teste-gravacao.py (alvo padrao = o principal) e deixe a decisao com o Rafael antes de mexer")
    cartao = False
    for vid, estado, uuid in vols:
        if vid.startswith("private:"):  # cartao ADOTADO
            cartao = True
            if estado != "mounted":  # parado e sem apps nao atrapalha (AVISO); com apps eles ficam fora do ar (FALHA)
                reg(s, "FALHA" if no_cartao else "AVISO", f"cartao adotado {vid}", f"{estado} (reiniciar o aparelho; nao tirar o cartao)")
            elif no_cartao:
                reg(s, "FALHA", f"cartao adotado {vid} com apps",
                    f"{len(no_cartao)} em /mnt/expand: {', '.join(no_cartao[:4])}. Apps ficam na memoria interna (pm uninstall --user 0 + adb install -r); "
                    "NUNCA pm move-package nem pm move-primary-storage")
            else:
                reg(s, "AVISO", f"cartao adotado {vid} montado e ocioso",
                    "0 apps em /mnt/expand; estado decidido em 28/10 (principal = interna, cartao ocioso). Decisao do Rafael: manter assim ou "
                    "voltar a portatil exFAT, que apaga o cartao e so com o sim dele. Nao mover nada entre volumes")
        elif vid.startswith("public:"):  # cartao PORTATIL
            cartao = True
            if estado == "mounted":
                reg(s, "OK", f"cartao PORTATIL {vid} montado", f"/storage/{uuid}")
                reg(s, "INFO", "teste de gravacao do cartao portatil",
                    f"python scripts/teste-gravacao.py --alvo /storage/{uuid} (conferir o md5 logo depois de gravar nao prova nada; saida 1 = o cartao corrompe)")
            else:
                reg(s, "AVISO", f"cartao PORTATIL {vid}", f"{estado} (nao montado; reiniciar o aparelho; formatar so com o sim do Rafael)")
    if not cartao:
        reg(s, "AVISO", "cartao ausente", "nenhum volume private:/public: em sm list-volumes (sem cartao ou nao reconhecido)")
    df = sh("df -h /data | tail -1").split()
    uso = int(df[4].rstrip("%")) if len(df) >= 5 and df[4].endswith("%") else -1
    if uso < 0:
        reg(s, "AVISO", "/data", "nao consegui ler o df (sem resposta ou formato inesperado)")
    else:
        reg(s, "AVISO" if uso >= 90 else "OK", "/data", f"{uso}% usado, livre {df[3] if len(df) > 3 else '?'}")
    reg(s, "INFO", "apps no cartao", f"{len(no_cartao)} de {len(caminho)}")
    for p in sorted(set(INTERNOS) | set(FOSS)):
        if p not in todos:
            reg(s, "AVISO", f"{p} fora do aparelho", "nao instalado")
        else:
            c = caminho.get(p, "")
            reg(s, "OK" if c.startswith("/data/app/") else "FALHA", f"{p} na memoria interna", "cartao: perde papel/estado no reboot" if "/mnt/expand/" in c else "")
    reg(s, "INFO", "local de instalacao padrao", sh("settings get global default_install_location") + " (1 = interna)")


def lotes(todos, desativados):
    s = "Lotes"
    dados = json.loads((RAIZ / "scripts" / "lotes-bloatware.json").read_text(encoding="utf-8"))
    protegidos = [re.compile(x, re.I) for x in carrega("lote_pacotes", "lote-pacotes.py").PROTEGIDOS]
    dos_lotes: set[str] = set()
    for nome, lote in dados.items():
        pk = lote.get("pacotes", [])
        dos_lotes.update(pk)
        if not lote.get("aplicavel"):
            continue
        ativos = [p for p in pk if p in todos and p not in desativados]
        ok = len(pk) - len(ativos)
        reg(s, "OK" if not ativos else "FALHA", f"lote {nome}", f"{ok}/{len(pk)} desativados ou ausentes" + (f"; ativos: {', '.join(ativos[:4])}" if ativos else ""))
        for velho, novo in (lote.get("substitutos") or {}).items():
            if velho in desativados or velho not in todos:
                reg(s, "OK" if novo in todos and novo not in desativados else "FALHA", f"substituto {novo}", f"no lugar de {velho}")
    fora = sorted(desativados - dos_lotes)
    prot = [p for p in fora if any(r.search(p) for r in protegidos) and p not in ESPERADOS_FORA]
    reg(s, "INFO", "desativados fora dos lotes", f"{len(fora)}: {', '.join(fora)}")
    if prot:
        reg(s, "AVISO", "protegidos desativados fora dos lotes", ", ".join(prot))
    brasil = [p for p in fora if p.startswith("br.")]
    if brasil:
        reg(s, "AVISO", "apps do Brasil desativados antes do projeto (reativar se usa: pm enable)", ", ".join(brasil))
    reg(s, "INFO", "total desativados", str(len(desativados)))


def essenciais(todos, desativados):
    s = "Essenciais"
    falta = [p for p in ESSENCIAIS if p not in todos or p in desativados]
    reg(s, "OK" if not falta else "FALHA", f"sistema ({len(ESSENCIAIS)})", "todos ativos" if not falta else "inativos: " + ", ".join(falta))
    falta = [p for p in USUARIO if p not in todos or p in desativados]
    reg(s, "OK" if not falta else "AVISO", f"apps do dia a dia ({len(USUARIO)})", "todos ativos" if not falta else "ausentes/inativos: " + ", ".join(falta))


def papeis():
    s = "Papeis e teclado"
    for papel, esperado in PAPEIS.items():
        atual = sh(f"cmd role get-role-holders {papel}")
        det = atual or "SEM DONO"
        if atual != esperado:
            det += f" (esperado {esperado})"
        reg(s, "OK" if atual == esperado else "FALHA", papel.rsplit(".", 1)[1], det)
    ime = sh("settings get secure default_input_method")
    reg(s, "OK" if ime == IME else "FALHA", "teclado padrao", ime)
    ativos = sh("ime list -s")
    reg(s, "OK" if re.search(r"helium314|honeyboard|inputmethod\.latin", ativos) else "FALHA", "teclado de verdade ativo", ativos.replace("\n", " ")[:90])


def rede():
    s = "Rede"
    g = lambda k: sh(f"settings get global {k}")  # noqa: E731
    dns = g("private_dns_mode")
    reg(s, "OK" if dns in ("opportunistic", "off", "null") else "AVISO", "DNS privado", dns + ("" if dns != "hostname" else " (estrito: derruba rede de escola/portal)"))
    for k in ("captive_portal_mode", "captive_portal_detection_enabled"):
        v = g(k)
        reg(s, "OK" if v in ("1", "null") else "FALHA", k, f"{v} (0 desliga a pagina de login de Wi-Fi)")
    for nome in ("google.com", "packages-cf.termux.dev", "www.youtube.com"):
        r = ""
        for _ in range(7):  # logo depois do boot o DNS leva alguns minutos para responder
            r = sh(f"ping -c1 -W4 {nome} 2>&1 | head -1")
            if r.startswith("PING"):
                break
            time.sleep(10)
        reg(s, "OK" if r.startswith("PING") else "FALHA", f"resolve {nome}", "" if r.startswith("PING") else r[:60])
    wifi = sh("cmd wifi status | head -3").replace("\n", " | ")
    reg(s, "INFO", "Wi-Fi", wifi[:140])
    seduc = [l.split(None, 1)[1].strip() for l in sh("cmd wifi list-networks").splitlines() if "SEDUC" in l]
    reg(s, "INFO", "redes SEDUC salvas", ", ".join(sorted(set(seduc))) or "nenhuma (usar SEDUC-ALUNOS e PROFESSORES, login na pagina; 172.30.0.1 se nao abrir)")


def ajustes():
    s = "Ajustes do script"
    for ns, k, esperado in AJUSTES:
        v = sh(f"settings get {ns} {k}")
        reg(s, "OK" if v == esperado else "AVISO", f"{k}", f"{v} (esperado {esperado})")
    v = sh("device_config get activity_manager max_phantom_processes")
    reg(s, "OK" if v == "2147483647" else "AVISO", "max_phantom_processes", v)
    for pkg in ("com.android.vending", "com.microsoft.teams"):
        m = re.search(r"RUN_IN_BACKGROUND: (\w+)", sh(f"cmd appops get {pkg} RUN_IN_BACKGROUND"))
        reg(s, "INFO", f"{pkg} em segundo plano", m.group(1) if m else "padrao")
    m = sh("grep -E 'MemAvailable|SwapFree' /proc/meminfo").replace("\n", " ").replace("  ", " ")
    reg(s, "INFO", "memoria", m)


def foss(todos, desativados, caminho):
    s = "Apps de codigo aberto"
    for p in FOSS:
        if p not in todos:
            reg(s, "AVISO", p, "nao instalado")
            continue
        vol = "cartao" if "/mnt/expand/" in caminho.get(p, "") else "interna"
        ver = re.search(r"versionName=(\S+)", sh(f"dumpsys package {p} | grep -m1 versionName"))
        reg(s, "FALHA" if p in desativados else "OK", p, f"{ver.group(1) if ver else '?'} | {vol}")
    for p in ("org.videolan.vlc", "com.junkfood.seal"):
        m = re.search(r"MANAGE_EXTERNAL_STORAGE: (\w+)", sh(f"cmd appops get {p} MANAGE_EXTERNAL_STORAGE"))
        reg(s, "OK" if m and m.group(1) == "allow" else "FALHA", f"{p} acesso a todos os arquivos", m.group(1) if m else "?")
    reg(s, "INFO", "alarme (Fossify Relogio)", f"{sh('dumpsys alarm | grep -c org.fossify.clock')} entradas no AlarmManager")


def dashcam(todos):
    s = "Dashcam (Open Camera + Organic Maps)"
    for p in ("net.sourceforge.opencamera", "app.organicmaps"):
        reg(s, "OK" if p in todos else "FALHA", f"{p} instalado")
    idle = sh("dumpsys deviceidle whitelist")
    for p in ("net.sourceforge.opencamera", "app.organicmaps"):
        reg(s, "OK" if f",{p}," in idle else "AVISO", f"{p} na lista de Doze")
    for ns, k in (("global", "force_resizable_activities"), ("global", "enable_freeform_support")):
        v = sh(f"settings get {ns} {k}")
        reg(s, "OK" if v == "1" else "AVISO", k, v + " (so vale depois de reiniciar)")
    perm = sh("dumpsys package net.sourceforge.opencamera | grep -E 'android.permission.(CAMERA|RECORD_AUDIO):'")
    reg(s, "OK" if perm.count("granted=true") == 2 else "FALHA", "Open Camera: camera e microfone concedidos", perm.replace(chr(10), " ")[:90])
    # O Dashcam grava no cartao PORTATIL (Open Camera por SAF). A pasta so existe com esse cartao montado: com o cartao adotado (ocioso)
    # ou sem cartao (estado de 28/10) ela nao existe e isso e AVISO, nao FALHA. /storage/emulated/0/Dashcam NAO e exigida.
    vols = volumes()
    portatil = next((u for vid, est, u in vols if vid.startswith("public:") and est == "mounted" and u not in ("", "null")), "")
    if portatil:
        pasta = sh(f"ls -d /storage/{portatil}/Dashcam 2>&1")
        reg(s, "OK" if pasta.endswith("Dashcam") else "AVISO", "pasta de gravacao no cartao (Dashcam)", pasta[:70])
    else:
        if any(v[0].startswith("private:") for v in vols):
            quadro = "cartao ADOTADO, nao portatil"
        elif any(v[0].startswith("public:") for v in vols):
            quadro = "cartao PORTATIL nao montado"
        else:
            quadro = "sem cartao"
        reg(s, "AVISO", "pasta de gravacao no cartao (Dashcam)",
            f"{quadro}: a pasta Dashcam (era /storage/{UUID_PORTATIL}/Dashcam) so existe com o cartao PORTATIL montado; Dashcam e NewPipe dependiam dele. "
            "Decisao do Rafael (voltar a portatil apaga o cartao); /storage/emulated/0/Dashcam nao e exigida")
    om = dados_do_app("app.organicmaps")  # os mapas offline ficam nos dados privados do app, nao em Android/data
    reg(s, "INFO" if om is None or om >= 100 else "AVISO", "mapas do Organic Maps",
        "dumpsys diskstats sem resposta" if om is None else f"dados do app = {om} MB (abaixo de 100 MB = sem mapa offline: baixar de novo no app)")
    if portatil:  # os mapas ficam na interna: no SD o Organic Maps pode nao conseguir gravar (memoria/PESQUISA-APPS.md)
        omc = sh(f"du -sm /storage/{portatil}/Android/data/app.organicmaps/files 2>/dev/null | cut -f1")
        reg(s, "OK" if (omc or "0").isdigit() and int(omc or 0) < 20 else "AVISO", "mapas do Organic Maps fora do cartao",
            f"{omc or 0} MB no cartao (devem ficar no armazenamento interno)")
    cod = sh("grep -c 'c2.mtk.avc.encoder' /vendor/etc/media_codecs_c2.xml")
    reg(s, "INFO", "encoder H.264 por hardware", f"{cod} entrada(s); HEVC nao existe neste chip (use H.264)")


def depuracao():
    s = "Depuracao e privacidade"
    adb = sh("settings get global adb_enabled")
    dev = sh("settings get global development_settings_enabled")
    reg(s, "AVISO" if adb == "1" else "OK", "depuracao USB", f"adb_enabled={adb} opcoes_do_desenvolvedor={dev} (opcoes em 0 por settings desde 05/11: o gov.br abre e o adb segue; F8 = desligar a depuracao USB ao terminar)")
    if dev == "1":
        reg(s, "AVISO", "opcoes do desenvolvedor visiveis", "o gov.br bloqueia com 1: settings put global development_settings_enabled 0 (o adb segue vivo)")
    reg(s, "INFO", "verificador de instalacao por adb", sh("settings get global verifier_verify_adb_installs"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fumaca", action="store_true")
    a = ap.parse_args()
    if "device" not in subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout.split("List of devices")[-1]:
        sys.exit("aparelho offline (adb devices vazio)")
    todos, desativados, caminho = pacotes(), pacotes("-d"), caminhos()
    aparelho()
    armazenamento(todos, caminho)
    lotes(todos, desativados)
    essenciais(todos, desativados)
    papeis()
    rede()
    ajustes()
    foss(todos, desativados, caminho)
    dashcam(todos)
    depuracao()
    if a.fumaca:
        r = subprocess.run([sys.executable, "-I", str(RAIZ / "scripts" / "teste-fumaca.py"), "--rapido"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
        linhas = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
        reg("Fumaca", "OK" if r.returncode == 0 and not any("FALHOU" in l or "caiu" in l.lower() for l in linhas) else "FALHA", "teste-fumaca --rapido", " | ".join(linhas[-6:])[:300])

    conta = {n: sum(1 for x in R if x[1] == n) for n in ("OK", "FALHA", "AVISO", "INFO")}
    secao = ""
    linhas_md = [f"# Auditoria do A12 - {datetime.datetime.now():%d/%m/%Y %H:%M}", ""]
    for sec, nivel, item, det in R:
        if sec != secao:
            secao = sec
            print(f"\n== {sec}")
            linhas_md += ["", f"## {sec}"]
        if nivel != "OK" or sec in ("Lotes", "Papeis e teclado", "Rede"):
            print(f"  [{nivel}] {item}" + (f": {det}" if det else ""))
        linhas_md.append(f"- [{nivel}] {item}" + (f": {det}" if det else ""))
    resumo = f"OK={conta['OK']} FALHA={conta['FALHA']} AVISO={conta['AVISO']} INFO={conta['INFO']}"
    print(f"\n== Resumo: {resumo}")
    pasta = RAIZ / "diagnostico" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "auditoria.md").write_text("\n".join(linhas_md + ["", f"**{resumo}**"]) + "\n", encoding="utf-8")
    print(f"relatorio: {pasta / 'auditoria.md'}")
    sys.exit(1 if conta["FALHA"] else 0)


if __name__ == "__main__":
    main()
