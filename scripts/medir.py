#!/usr/bin/env python3
"""Mede o desempenho do Galaxy A12 pelo ADB de forma repetivel, para comparar ANTES x DEPOIS de uma mudanca.
Mede: memoria e zram, pressao (PSI), CPU em repouso e quem a consome, abertura a frio de apps (mediana de 3),
fluidez ao rolar as Configuracoes (quadros lentos) e disco. Abre apps e rola a tela; nao altera ajustes (so liga a tela
enquanto o USB esta ligado, e restaura). A carga media (load average) NAO serve neste aparelho: 15 threads do kernel
ficam em estado D (tz_worker, ccci) e somam ~20 sempre.

  python scripts/medir.py --rotulo agora                  grava diagnostico/<data>/medicao-agora.json e mostra o resumo
  python scripts/medir.py --comparar A.json B.json        tabela antes x depois
"""
import argparse
import datetime
import json
import pathlib
import re
import statistics
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

RAIZ = pathlib.Path(__file__).resolve().parent.parent
# (rotulo, pacote): abertura a frio. Apps que nao existirem ou estiverem desativados sao ignorados.
# NUNCA incluir com.termux: o force-stop mata o guarda da saida, o sshd e o laco do Termux:Boot (ninguem os religa).
APPS = [("Configuracoes", "com.android.settings"), ("ARENA", "io.github.rafaparise.arena"),
        ("Navegador Fennec", "org.mozilla.fennec_fdroid"), ("Chrome", "com.android.chrome"),
        ("Mensagens Fossify", "org.fossify.messages"), ("Galeria Fossify", "org.fossify.gallery"),
        ("Organic Maps", "app.organicmaps"), ("Gov.br", "br.gov.meugovbr"), ("SED", "br.gov.sp.educacao.sed.android"),
        ("Telefone Samsung", "com.samsung.android.dialer"), ("Telefone Fossify", "org.fossify.phone"),
        ("Contatos Samsung", "com.samsung.android.app.contacts"), ("Contatos Fossify", "org.fossify.contacts"),
        ("Relogio Samsung", "com.sec.android.app.clockpackage"), ("Relogio Fossify", "org.fossify.clock"),
        ("VLC", "org.videolan.vlc"), ("WhatsApp Business", "com.whatsapp.w4b")]
# metrica -> (menor_e_melhor, unidade)
SENTIDO = {"mem.disponivel_mb": (False, "MB"), "mem.livre_mb": (False, "MB"), "mem.swap_usado_mb": (True, "MB"),
           "mem.zram_dados_mb": (True, "MB"), "mem.zram_comprimido_mb": (True, "MB"),
           "proc.total": (True, ""), "proc.apps": (True, ""), "proc.servicos": (True, ""),
           "psi.cpu_some_avg60": (True, "%"), "psi.mem_some_avg60": (True, "%"), "psi.io_some_avg60": (True, "%"),
           "cpu.ocupada_pct": (True, "%"), "jank.janky_pct": (True, "%"), "jank.p90_ms": (True, "ms"),
           "jank.p95_ms": (True, "ms"), "jank.p99_ms": (True, "ms"), "disco.usado_pct": (True, "%"),
           "disco.livre_gb": (False, "GB"), "contagem.ativos": (True, ""), "contagem.wakelocks": (True, "")}


def sh(cmd, timeout=90):
    r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    return (r.stdout + r.stderr).replace("\r", "").strip()


def num(texto, padrao=0.0):
    m = re.search(r"-?[\d.,]+", texto or "")
    return float(m.group(0).replace(",", "")) if m else padrao


def desperta():
    sh("settings put global stay_on_while_plugged_in 3")
    sh("input keyevent KEYCODE_WAKEUP")
    sh("wm dismiss-keyguard")
    time.sleep(1.5)
    foco = sh("dumpsys window | grep -m1 mCurrentFocus")
    if any(x in foco for x in ("NotificationShade", "Keyguard", "StatusBar")):
        sys.exit("ABORTADO: celular travado; desbloqueie a tela e rode de novo")
    sh("input keyevent KEYCODE_HOME")
    time.sleep(1)


def memoria():
    mi = {k: int(v) for k, v in re.findall(r"(\w+):\s+(\d+) kB", sh("cat /proc/meminfo"))}
    z = sh("cat /sys/block/zram0/mm_stat").split()
    d = {"disponivel_mb": mi["MemAvailable"] // 1024, "livre_mb": mi["MemFree"] // 1024,
         "em_cache_mb": mi["Cached"] // 1024, "swap_usado_mb": (mi["SwapTotal"] - mi["SwapFree"]) // 1024}
    if len(z) >= 3:
        d["zram_dados_mb"] = int(z[0]) // 1048576
        d["zram_comprimido_mb"] = int(z[1]) // 1048576
    for chave, rot in (("Free RAM", "ram_livre_dumpsys_mb"), ("Used RAM", "ram_usada_dumpsys_mb")):
        m = re.search(chave + r":\s*([\d,]+)K", sh("dumpsys meminfo | grep -m1 '" + chave + ":'"))
        if m:
            d[rot] = int(m.group(1).replace(",", "")) // 1024
    return d


def processos():
    return {"total": int(num(sh("ps -A | wc -l"))), "apps": int(num(sh("ps -A -o USER | grep -c '^u0_a'"))),
            "servicos": int(num(sh("dumpsys activity services | grep -c 'ServiceRecord{'")))}


def pressao():
    d = {}
    for nome, arq in (("cpu", "cpu"), ("mem", "memory"), ("io", "io")):
        for tipo, linha in re.findall(r"(some|full) (.*)", sh(f"cat /proc/pressure/{arq}")):
            for k, v in re.findall(r"(avg10|avg60|avg300)=([\d.]+)", linha):
                d[f"{nome}_{tipo}_{k}"] = float(v)
    return d


def cpu_repouso(janela=15):
    """CPU total ocupada e os maiores consumidores numa janela em que o celular fica parado na tela inicial."""
    saida = sh(f"head -n1 /proc/stat; top -b -n 2 -d {janela} -m 8; head -n1 /proc/stat", timeout=janela + 60)
    cpus = [l for l in saida.splitlines() if l.startswith("cpu ")]
    ocupada = None
    if len(cpus) >= 2:
        a, b = ([int(x) for x in l.split()[1:9]] for l in (cpus[0], cpus[-1]))
        tot = sum(b) - sum(a)
        ocioso = (b[3] + b[4]) - (a[3] + a[4])
        ocupada = round(100.0 * (1 - ocioso / tot), 1) if tot else None
    linhas = saida.splitlines()
    ini = max((i for i, l in enumerate(linhas) if l.startswith("Tasks:")), default=0)
    top = []
    for l in linhas[ini:]:
        p = l.split(None, 11)
        if len(p) == 12 and p[0].isdigit() and re.match(r"^[\d.]+$", p[8]):
            top.append({"pid": int(p[0]), "cpu_pct": float(p[8]), "nome": p[11][:60]})
    return {"ocupada_pct": ocupada, "janela_s": janela, "maiores": top[:5]}


def componente(pkg):
    s = sh(f"cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.LAUNCHER {pkg}")
    achados = [l.strip() for l in s.splitlines() if "/" in l and " " not in l.strip()]
    return achados[-1] if achados else None


def abertura_fria(pkg, n=3):
    comp = componente(pkg)
    if not comp:
        return None
    ts = []
    for _ in range(n):
        sh(f"am force-stop {pkg}")
        time.sleep(1.5)
        m = re.search(r"TotalTime:\s*(\d+)", sh(f"am start -W -n {comp}"))
        if m:
            ts.append(int(m.group(1)))
        sh("input keyevent KEYCODE_HOME")
        time.sleep(0.8)
    return int(statistics.median(ts)) if ts else None


def fluidez(rolagens=8):
    pkg = "com.android.settings"
    comp = componente(pkg)
    if not comp:
        return {}
    sh(f"am force-stop {pkg}")
    sh(f"am start -W -n {comp}")
    time.sleep(2)
    sh(f"dumpsys gfxinfo {pkg} reset")
    for sentido in (("1250", "450"), ("450", "1250")):
        for _ in range(rolagens):
            sh(f"input swipe 360 {sentido[0]} 360 {sentido[1]} 220")
            time.sleep(0.4)
    g = sh(f"dumpsys gfxinfo {pkg}")
    sh("input keyevent KEYCODE_HOME")
    d = {}
    m = re.search(r"Total frames rendered:\s*(\d+)", g)
    d["quadros"] = int(m.group(1)) if m else 0
    m = re.search(r"Janky frames:\s*(\d+) \(([\d.]+)%\)", g)
    if m:
        d["janky"], d["janky_pct"] = int(m.group(1)), float(m.group(2))
    for p in (50, 90, 95, 99):
        m = re.search(rf"{p}th percentile:\s*(\d+)ms", g)
        if m:
            d[f"p{p}_ms"] = int(m.group(1))
    return d


def disco():
    f = sh("df -k /data | tail -n 1").split()
    if len(f) < 5:
        return {}
    return {"total_gb": round(int(f[1]) / 1048576, 1), "usado_pct": int(f[4].rstrip("%")),
            "livre_gb": round(int(f[3]) / 1048576, 2)}


def contagens():
    return {"ativos": int(num(sh("pm list packages -e | wc -l"))), "desativados": int(num(sh("pm list packages -d | wc -l"))),
            "sistema_ativos": int(num(sh("pm list packages -s -e | wc -l"))),
            "usuario": int(num(sh("pm list packages -3 | wc -l"))),
            "wakelocks": int(num(sh("dumpsys power | grep -c 'PARTIAL_WAKE_LOCK'"))),
            "jobs": int(num(sh("dumpsys jobscheduler | grep -c 'JOB #'")))}


def medir(rotulo, so_rapido=False):
    if "SM-A125" not in sh("getprop ro.product.model"):
        sys.exit("ABORTADO: aparelho nao encontrado ou inesperado")
    anterior = sh("settings get global stay_on_while_plugged_in")
    r = {"rotulo": rotulo, "quando": datetime.datetime.now().isoformat(timespec="seconds"),
         "uptime": sh("uptime | sed 's/,.*//'"), "bateria": sh("dumpsys battery | grep -E 'level|temperature' | tr -s ' ' | tr '\\n' ' '")}
    try:
        desperta()
        sh("am kill-all")
        print("  preparando: processos em cache encerrados; aguardando 25 s para estabilizar...")
        time.sleep(25)
        r["mem"], r["proc"], r["psi"], r["disco"], r["contagem"] = memoria(), processos(), pressao(), disco(), contagens()
        print("  CPU em repouso (15 s, tela inicial parada)...")
        r["cpu"] = cpu_repouso(15)
        if not so_rapido:
            print("  abertura a frio (mediana de 3)...")
            r["frio_ms"] = {}
            for rot, pkg in APPS:
                t = abertura_fria(pkg)
                if t is not None:
                    r["frio_ms"][rot] = t
                    print(f"    {rot:20s} {t} ms")
            print("  fluidez ao rolar as Configuracoes...")
            r["jank"] = fluidez()
    finally:
        sh(f"settings put global stay_on_while_plugged_in {anterior if anterior.isdigit() else 0}")
        sh("input keyevent KEYCODE_HOME")
    return r


def achata(d, pre=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(achata(v, f"{pre}{k}."))
        elif isinstance(v, (int, float)):
            out[f"{pre}{k}"] = v
    return out


def resumo(r):
    m, p, ps, c = r["mem"], r["proc"], r["psi"], r["cpu"]
    print(f"\n== {r['rotulo']} ({r['quando']}, {r['uptime'].strip()}) bateria: {r['bateria']}")
    print(f"memoria: disponivel {m['disponivel_mb']} MB | livre {m['livre_mb']} MB | swap usado {m['swap_usado_mb']} MB | "
          f"zram {m.get('zram_dados_mb')} MB -> {m.get('zram_comprimido_mb')} MB")
    print(f"processos: {p['total']} total, {p['apps']} de apps, {p['servicos']} servicos ativos")
    print(f"pressao (media 60 s): cpu {ps.get('cpu_some_avg60')}% | memoria {ps.get('mem_some_avg60')}% | disco {ps.get('io_some_avg60')}%")
    print(f"CPU ocupada em repouso: {c['ocupada_pct']}%  maiores: " + "; ".join(f"{x['nome']} {x['cpu_pct']}%" for x in c["maiores"][:4]))
    if "jank" in r and r["jank"]:
        j = r["jank"]
        print(f"fluidez (Configuracoes): {j.get('quadros')} quadros, {j.get('janky_pct')}% lentos, p90 {j.get('p90_ms')} ms, p99 {j.get('p99_ms')} ms")
    print(f"disco /data: {r['disco'].get('usado_pct')}% usado, {r['disco'].get('livre_gb')} GB livres | pacotes ativos {r['contagem']['ativos']}")


def comparar(a, b):
    ra, rb = json.loads(pathlib.Path(a).read_text(encoding="utf-8")), json.loads(pathlib.Path(b).read_text(encoding="utf-8"))
    fa, fb = achata(ra), achata(rb)
    print(f"\nANTES  = {ra['rotulo']} ({ra['quando']})\nDEPOIS = {rb['rotulo']} ({rb['quando']})\n")
    print(f"{'metrica':36s} {'antes':>9s} {'depois':>9s} {'variacao':>10s}  resultado")
    linhas = [(k, SENTIDO[k]) for k in SENTIDO if k in fa and k in fb]
    frios = sorted(k for k in fa if k.startswith("frio_ms.") and k in fb)
    for k in [x for x, _ in linhas] + frios:
        menor = SENTIDO[k][0] if k in SENTIDO else True
        x, y = fa[k], fb[k]
        var = (y - x) / x * 100 if x else 0.0
        bom = (y < x) if menor else (y > x)
        # base zero: nao ha variacao relativa; vale a diferenca absoluta (menos de 1 unidade e ruido)
        pequeno = abs(y - x) < 1 if not x else abs(var) < 3
        r = "igual" if pequeno else ("MELHOR" if bom else "PIOR")
        nome = k.replace("frio_ms.", "abrir ") + (" (ms)" if k.startswith("frio_ms.") else f" ({SENTIDO[k][1]})" if SENTIDO[k][1] else "")
        print(f"{nome:36s} {x:9.1f} {y:9.1f} {var:+9.0f}%  {r}")
    print("\nmaiores consumidores de CPU em repouso:")
    for rot, rr in (("antes ", ra), ("depois", rb)):
        print(f"  {rot}: " + "; ".join(f"{x['nome']} {x['cpu_pct']}%" for x in rr["cpu"]["maiores"][:4]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rotulo", default="medicao")
    ap.add_argument("--rapido", action="store_true", help="sem abertura a frio nem fluidez (so memoria, pressao e CPU)")
    ap.add_argument("--comparar", nargs=2, metavar=("ANTES.json", "DEPOIS.json"))
    a = ap.parse_args()
    if a.comparar:
        comparar(*a.comparar)
        return
    r = medir(a.rotulo, a.rapido)
    pasta = RAIZ / "diagnostico" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"medicao-{a.rotulo}.json"
    arq.write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
    resumo(r)
    print(f"\ngravado em {arq}")


if __name__ == "__main__":
    main()
