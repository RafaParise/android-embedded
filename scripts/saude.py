#!/usr/bin/env python3
"""Saude do A12 AGORA, em uma tela: bateria, termica, memoria e pressao, o que mais pesa, espaco livre, mortes de apps,
quem acorda a CPU e o Wi-Fi; com --online, tambem se ha firmware ou app FOSS mais novo.
SO LEITURA: so getprop, dumpsys, cat de /proc e /sys, df, date, logcat -d, cmd wifi status e pm list; nada e alterado no aparelho.

  python scripts/saude.py                  leitura pelo adb (uns 20 s)
  python scripts/saude.py --online         alem disso consulta o servidor FOTA da Samsung e a API do F-Droid (so GET, sem dado pessoal)
  python scripts/saude.py --sem-historico  nao grava a linha em diagnostico/saude-historico.jsonl

Cada linha traz OK, ATENCAO ou ALERTA. Saida 0 = sem ALERTA, 1 = ha ALERTA, 2 = sem aparelho ou nao e o A12.
Os limites (todos em constantes LIM_*) sao palpites razoaveis para 3,8 GB de RAM, nao norma; so o Thermal Status e o estado da
bateria vem do proprio Android. Ver memoria/RADAR-DESEMPENHO.md.

Por que existe (01/11/2026): dois `npm install omniroute` do Qwen do celular chegaram a 1,1 GB de RAM (de 3,8 GB), o Android matou
apps em segundo plano (o Open Camera inclusive) e o espaco livre caiu 6 GB em um dia, e nenhum outro script olhava o que PESA agora
(auditoria.py confere configuracao, medir.py mede abertura de app). O historico local pega a queda de espaco na proxima leitura.
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

RAIZ = Path(__file__).resolve().parent.parent
PROJETO_MAH = 5000            # capacidade de projeto do A12 (batterystats: "Capacity: 5000")
MIN_NIVEL_CAPACIDADE = 15     # abaixo disso o charge counter dividido pelo nivel oscila demais
LIM_BAT_TEMP_AT, LIM_BAT_TEMP_AL = 40.0, 45.0            # graus C
LIM_BAT_CAP_AT, LIM_BAT_CAP_AL = 80.0, 60.0              # % do projeto
LIM_DISP_AT_KB, LIM_DISP_AL_KB = 500 * 1024, 300 * 1024  # MemAvailable
LIM_SWAP_PCT = 85.0
LIM_PSI_MEM_FULL_AT, LIM_PSI_MEM_FULL_AL = 2.0, 10.0     # % em 60 s
LIM_PSI_MEM_SOME_AT = 15.0
LIM_PSI_CPU_SOME_AT = 40.0
LIM_PSI_IO_FULL_AT = 10.0
LIM_PSS_AT_KB, LIM_PSS_AL_KB = 450 * 1024, 700 * 1024
LIM_LIVRE_AT_PCT, LIM_LIVRE_AL_PCT = 15.0, 10.0
LIM_QUEDA_KB = 2 * 1024 * 1024                           # queda de espaco desde a leitura anterior
ADJ_EM_USO, ADJ_CACHEADO = 250, 900                      # <=250: visivel ou audivel; >=900: app em cache (morte normal)
MINUTOS_MORTES = 60
LIM_MORTES_MEM_AT = 30                                   # mortes por memoria em 1 h; 36 na hora dos dois npm de 01/11 [Palpite]
RE_MOTIVO_MEMORIA = re.compile(r"chimera|ml_kill|lmkd|low ?mem|pressure", re.I)

OK, AT, AL = "OK", "ATENCAO", "ALERTA"
ORDEM = {OK: 0, AT: 1, AL: 2}
ESTADO_BAT = {1: "estado ?", 2: "carregando", 3: "descarregando", 4: "sem carga", 5: "cheia"}
NOMES_TERMICA = {0: "nenhuma", 1: "leve", 2: "moderada", 3: "grave", 4: "critica", 5: "emergencia", 6: "desligando"}
FOSS = ("org.fossify.phone", "org.fossify.messages", "org.fossify.contacts", "org.fossify.gallery", "org.fossify.clock",
        "org.fossify.calendar", "org.fossify.notes", "org.fossify.filemanager", "org.mozilla.fennec_fdroid", "app.organicmaps",
        "net.sourceforge.opencamera", "org.schabi.newpipe", "org.videolan.vlc", "com.junkfood.seal", "com.termux",
        "org.kde.kdeconnect_tp", "net.thunderbird.android", "com.tailscale.ipn", "helium314.keyboard")
URL_FOTA = "https://fota-cloud-dn.ospserver.net/firmware/{csc}/{modelo}/version.xml"
URL_FDROID = "https://f-droid.org/api/v1/packages/{pacote}"

# Todos os comandos que o script manda ao aparelho (o teste confere que sao so de leitura).
CMD = {
    "modelo": "getprop ro.product.model",
    "build": "getprop ro.build.display.id",
    "csc": "getprop ro.csc.sales_code",
    "hora": "date '+%Y-%m-%d %H:%M:%S'",
    "bateria": "dumpsys battery",
    "termica": "dumpsys thermalservice",
    "meminfo": "cat /proc/meminfo",
    "zram": "cat /sys/block/zram0/mm_stat",
    "psi_memory": "cat /proc/pressure/memory",
    "psi_cpu": "cat /proc/pressure/cpu",
    "psi_io": "cat /proc/pressure/io",
    "pss": "dumpsys meminfo",
    "df": "df -k /data",
    "mortes": "logcat -b events -d | grep am_kill",
    "alarmes": "dumpsys alarm | grep wakeups",
    "wakelocks": "dumpsys power | grep 'Wake Locks: size='",
    "wifi": "cmd wifi status",
    "versoes": "pm list packages --show-versioncode",
}


def sh(cmd, timeout=90):
    try:
        r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return ""
    return (r.stdout + r.stderr).replace("\r", "").strip()


def pior(a, b):
    return a if ORDEM[a] >= ORDEM[b] else b


# ---------------------------------------------------------------- leitura do texto que o Android devolve
def parse_bateria(texto):
    d = {}
    for rotulo, chave in (("level", "nivel"), ("status", "estado"), ("health", "saude"), ("temperature", "temp_dec"),
                          ("voltage", "mv"), ("Charge counter", "carga_uah")):
        m = re.search(rf"^\s*{rotulo}: (-?\d+)\s*$", texto, re.M | re.I)
        if m:
            d[chave] = int(m.group(1))
    return d


def capacidade_estimada_mah(b):
    """Carga restante (charge counter, uAh) dividida pelo nivel: estima a capacidade total. None se o nivel for baixo demais."""
    nivel, carga = b.get("nivel"), b.get("carga_uah")
    if not nivel or nivel < MIN_NIVEL_CAPACIDADE or not carga or carga <= 0:
        return None
    return carga / 1000.0 / (nivel / 100.0)


def parse_termica(texto):
    st = re.search(r"Thermal Status: (\d+)", texto)
    temps = {}
    for m in re.finditer(r"Temperature\{mValue=(-?[\d.]+), mType=\d+, mName=(\w+), mStatus=\d+\}", texto):
        v = float(m.group(1))
        temps[m.group(2)] = max(v, temps.get(m.group(2), v))
    return {"status": int(st.group(1)) if st else None, "temps": temps}


def parse_meminfo(texto):
    d = {}
    for chave in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
        m = re.search(rf"^{chave}:\s+(\d+) kB", texto, re.M)
        if m:
            d[chave] = int(m.group(1))
    return d


def parse_mm_stat(texto):
    """zram: orig_data_size, compr_data_size, mem_used_total (bytes)."""
    p = texto.split()
    if len(p) < 3 or not all(x.isdigit() for x in p[:3]):
        return None
    orig, compr, usada = int(p[0]), int(p[1]), int(p[2])
    return {"orig": orig, "compr": compr, "usada": usada, "razao": (orig / compr) if compr else None}


def parse_psi(texto):
    out = {}
    for linha in texto.splitlines():
        m = re.match(r"(some|full) avg10=([\d.]+) avg60=([\d.]+) avg300=([\d.]+)", linha.strip())
        if m:
            out[m.group(1)] = {"avg10": float(m.group(2)), "avg60": float(m.group(3)), "avg300": float(m.group(4))}
    return out


RE_PSS = re.compile(r"^\s*([\d.,]+)K: (.+?) \(pid (\d+)(?: / [^)]*)?\)\s*$")


def parse_pss(texto):
    """[(kb, nome, pid)] do bloco 'Total PSS by process' do dumpsys meminfo, do maior para o menor (os outros blocos repetem os processos)."""
    lista, dentro = [], False
    for linha in texto.splitlines():
        if linha.startswith("Total PSS by process"):
            dentro = True
            continue
        if dentro and linha.startswith("Total PSS by "):
            break
        if dentro:
            m = RE_PSS.match(linha)
            if m:
                lista.append((int(m.group(1).replace(",", "").replace(".", "")), m.group(2), int(m.group(3))))
    return sorted(lista, reverse=True)


def parse_df(texto):
    """{'total_kb', 'usado_kb', 'livre_kb'} da ultima linha do `df -k` (toybox: Filesystem 1K-blocks Used Available Use% Mounted)."""
    for linha in reversed(texto.splitlines()):
        p = linha.split()
        if len(p) >= 4 and all(x.isdigit() for x in p[1:4]):
            return {"total_kb": int(p[1]), "usado_kb": int(p[2]), "livre_kb": int(p[3])}
    return None


RE_MORTE = re.compile(r"(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)\.\d+\s+\d+\s+\d+ I am_kill\s*: \[(\d+),(\d+),([^,]+),(-?\d+),(.*)\]\s*$")


def parse_mortes(texto, agora, minutos=MINUTOS_MORTES):
    """[(quando, nome, adj, motivo)] dos ultimos `minutos` (hora local do aparelho em `agora`). O logcat nao traz o ano."""
    out = []
    for linha in texto.splitlines():
        m = RE_MORTE.search(linha.strip())
        if not m:
            continue
        mes, dia, h, mi, s = (int(m.group(i)) for i in range(1, 6))
        try:
            quando = datetime.datetime(agora.year, mes, dia, h, mi, s)
        except ValueError:
            continue
        if quando > agora + datetime.timedelta(days=1):
            quando = quando.replace(year=agora.year - 1)
        if 0 <= (agora - quando).total_seconds() <= minutos * 60:
            out.append((quando, m.group(8), int(m.group(9)), m.group(10)))
    return out


def parse_alarmes(texto):
    """[(wakeups, pacote)] do maior para o menor. O dumpsys repete o pacote em secoes diferentes: vale o maior valor visto (nunca a soma)."""
    por = {}
    for m in re.finditer(r"(\d+) wakeups, \d+ alarms: (\S+)", texto):
        pacote = m.group(2).split(":", 1)[-1]
        por[pacote] = max(por.get(pacote, 0), int(m.group(1)))
    return sorted(((w, p) for p, w in por.items()), reverse=True)


def parse_wakelocks(texto):
    m = re.search(r"Wake Locks: size=(\d+)", texto)
    return int(m.group(1)) if m else None


def parse_wifi(texto):
    m = re.search(r"RSSI: (-?\d+), Link speed: (\d+)Mbps", texto)
    f = re.search(r"Frequency: (\d+)MHz", texto)
    return {"conectado": "Wifi is connected" in texto and m is not None, "rssi": int(m.group(1)) if m else None,
            "mbps": int(m.group(2)) if m else None, "mhz": int(f.group(1)) if f else None}


def parse_versoes(texto):
    """{pacote: versionCode} de `pm list packages --show-versioncode`."""
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"package:(\S+) versionCode:(\d+)", texto)}


def fota_ultima(xml):
    m = re.search(r"<latest[^>]*>([^<]+)</latest>", xml or "")
    return m.group(1).split("/")[0].strip() if m else None


def build_instalado(display_id):
    """SP1A.210812.016.A125MUBS6CXJ1 -> A125MUBS6CXJ1"""
    return (display_id or "").strip().rsplit(".", 1)[-1]


def fdroid_desatualizado(codigo_instalado, api):
    """True = ha versao mais nova no F-Droid; False = em dia; None = nao deu para saber. Variantes de ABI (codigos diferentes, mesmo nome) contam como em dia."""
    sug = (api or {}).get("suggestedVersionCode")
    if not isinstance(sug, int) or not isinstance(codigo_instalado, int):
        return None
    if codigo_instalado >= sug:
        return False
    nomes = {p.get("versionCode"): p.get("versionName") for p in (api.get("packages") or []) if isinstance(p, dict)}
    if nomes.get(sug) is not None and nomes.get(codigo_instalado) == nomes.get(sug):
        return False
    return True


# ---------------------------------------------------------------- avaliacao: cada funcao devolve (nivel, texto)
def av_bateria(b):
    if "nivel" not in b:
        return AT, "Bateria: nao consegui ler o dumpsys battery"
    temp = b.get("temp_dec", 0) / 10.0
    nivel = OK
    partes = [f"{b['nivel']}% {ESTADO_BAT.get(b.get('estado'), 'estado ?')}", f"{temp:.1f} C"]
    cap = capacidade_estimada_mah(b)
    if cap is None:
        if b["nivel"] < MIN_NIVEL_CAPACIDADE:
            partes.append(f"capacidade nao estimada (nivel abaixo de {MIN_NIVEL_CAPACIDADE}%)")
        else:
            partes.append("capacidade nao estimada (sem charge counter no dumpsys battery)")
    else:
        pct = cap / PROJETO_MAH * 100
        partes.append(f"capacidade estimada ~{cap:.0f} mAh ({pct:.0f}% do projeto de {PROJETO_MAH})")
        if pct < LIM_BAT_CAP_AL:
            nivel = pior(nivel, AL)
        elif pct < LIM_BAT_CAP_AT:
            nivel = pior(nivel, AT)
    if temp >= LIM_BAT_TEMP_AL:
        nivel = pior(nivel, AL)
    elif temp >= LIM_BAT_TEMP_AT:
        nivel = pior(nivel, AT)
    if b.get("saude") not in (None, 2):
        nivel = pior(nivel, AT)
        partes.append(f"saude segundo o Android = codigo {b['saude']} (2 = boa)")
    return nivel, "Bateria: " + ", ".join(partes)


def av_termica(t):
    st = t.get("status")
    if st is None:
        return AT, "Termica: o thermalservice nao informou o status"
    nivel = OK if st <= 1 else (AT if st == 2 else AL)
    temps = ", ".join(f"{n} {v:.1f} C" for n, v in sorted(t.get("temps", {}).items()) if n in ("AP", "BAT", "PA") and v > 0)
    return nivel, f"Termica: status {st} ({NOMES_TERMICA.get(st, '?')})" + (f"; {temps}" if temps else "")


def av_memoria(mi, zram):
    total, disp = mi.get("MemTotal"), mi.get("MemAvailable")
    if not total or disp is None:
        return AT, "Memoria: nao consegui ler /proc/meminfo"
    nivel = OK
    partes = [f"disponivel {disp / 1024:.0f} MB de {total / 1024:.0f} MB"]
    if disp < LIM_DISP_AL_KB:
        nivel = AL
    elif disp < LIM_DISP_AT_KB:
        nivel = AT
    swap_total, swap_livre = mi.get("SwapTotal"), mi.get("SwapFree")
    if swap_total:
        usado = swap_total - (swap_livre or 0)
        pct = usado / swap_total * 100
        partes.append(f"swap {usado / 1024:.0f} MB usados ({pct:.0f}%)")
        if pct > LIM_SWAP_PCT:
            nivel = pior(nivel, AT)
    if zram and zram.get("razao"):
        partes.append(f"zram {zram['orig'] / 2**20:.0f} MB guardados em {zram['usada'] / 2**20:.0f} MB de RAM ({zram['razao']:.1f}:1)")
    return nivel, "Memoria: " + ", ".join(partes)


def av_pressao(psi):
    """psi = {'memory': {...}, 'cpu': {...}, 'io': {...}}, cada um {'some': {avg60...}, 'full': {...}}."""
    def v(recurso, tipo):
        return psi.get(recurso, {}).get(tipo, {}).get("avg60")
    mem_some, mem_full, cpu_some, io_full = v("memory", "some"), v("memory", "full"), v("cpu", "some"), v("io", "full")
    if mem_some is None and mem_full is None and cpu_some is None:
        return AT, "Pressao: o kernel nao deu /proc/pressure"
    nivel = OK
    if mem_full is not None:
        if mem_full >= LIM_PSI_MEM_FULL_AL:
            nivel = AL
        elif mem_full >= LIM_PSI_MEM_FULL_AT:
            nivel = AT
    if (mem_some or 0) >= LIM_PSI_MEM_SOME_AT or (cpu_some or 0) >= LIM_PSI_CPU_SOME_AT or (io_full or 0) >= LIM_PSI_IO_FULL_AT:
        nivel = pior(nivel, AT)
    def f(x):
        return "?" if x is None else f"{x:.1f}%"
    return nivel, (f"Pressao (media de 60 s): memoria espera {f(mem_some)} e trava {f(mem_full)}; CPU espera {f(cpu_some)}; "
                   f"disco trava {f(io_full)}")


def av_pesados(pss):
    if not pss:
        return AT, "Pesados: sem a lista de processos do dumpsys meminfo"
    topo = ", ".join(f"{nome} {kb / 1024:.0f} MB" for kb, nome, _ in pss[:4])
    acima = [(kb, nome) for kb, nome, _ in pss if kb >= LIM_PSS_AT_KB]
    if not acima:
        return OK, f"Pesados (PSS): {topo}"
    nivel = AL if any(kb >= LIM_PSS_AL_KB for kb, _ in acima) else AT
    lista = "; ".join(f"{nome} {kb / 1024:.0f} MB" for kb, nome in acima)
    return nivel, f"Pesados (PSS): {topo}. ACIMA DE {LIM_PSS_AT_KB // 1024} MB: {lista}"


def av_espaco(df, anterior=None):
    if not df:
        return AT, "Espaco: nao consegui ler o df de /data"
    pct = df["livre_kb"] / df["total_kb"] * 100
    nivel = AL if pct < LIM_LIVRE_AL_PCT else (AT if pct < LIM_LIVRE_AT_PCT else OK)
    txt = f"livre {df['livre_kb'] / 2**20:.1f} GB de {df['total_kb'] / 2**20:.1f} GB ({pct:.0f}%)"
    if anterior and anterior.get("livre_kb") is not None:
        queda = anterior["livre_kb"] - df["livre_kb"]
        quando = anterior.get("ts", "")[:16].replace("T", " ")
        if queda >= LIM_QUEDA_KB:
            txt += f"; CAIU {queda / 2**20:.1f} GB desde {quando}"
            nivel = pior(nivel, AT)
        elif queda <= -LIM_QUEDA_KB:
            txt += f"; subiu {-queda / 2**20:.1f} GB desde {quando}"
    return nivel, "Espaco: " + txt


def av_mortes(mortes):
    """So conta como falta de memoria o que o gerenciador da Samsung (Chimera, ML_Kill) ou o lmkd matou. 'isolated not needed',
    'stop <pacote>' (force-stop de alguem), 'empty #N' e 'remove task' sao faxina normal: o app Vivo, por exemplo, cria e recolhe
    um processo isolado por minuto (30 mortes 'isolated not needed' entre 10:21 e 10:50 de 01/11, adj 0) e nao e falta de RAM."""
    n = len(mortes)
    mem = [m for m in mortes if RE_MOTIVO_MEMORIA.search(m[3])]
    em_uso = sorted({nome for _, nome, adj, _ in mem if adj <= ADJ_EM_USO})
    meio = sorted({nome for _, nome, adj, _ in mem if ADJ_EM_USO < adj < ADJ_CACHEADO})
    base = f"Mortes de apps na ultima hora: {n} no total, {len(mem)} por falta de memoria (Chimera/lmkd)"
    if em_uso:
        return AL, f"{base}; MATOU APP EM USO OU VISIVEL: {', '.join(em_uso)}"
    if meio:
        return AT, f"{base}; incluiu servico ou ultimo app usado: {', '.join(meio)}"
    if len(mem) >= LIM_MORTES_MEM_AT:
        return AT, f"{base}: reciclagem alta de apps em cache, a RAM esta no limite"
    return OK, base


def av_acorda(alarmes, wakelocks):
    topo = ", ".join(f"{p} {w}" for w, p in alarmes[:3]) or "sem dados"
    wl = "?" if wakelocks is None else str(wakelocks)
    return OK, f"Acordam a CPU (alarmes com wakeup, no minimo): {topo}; wake locks segurados agora: {wl}"


def av_wifi(w):
    if not w.get("conectado"):
        return OK, "Wi-Fi: desconectado"
    nivel = AT if w["rssi"] < -75 else OK
    banda = "2,4 GHz" if (w.get("mhz") or 0) < 3000 else "5 GHz"
    return nivel, f"Wi-Fi: sinal {w['rssi']} dBm, {w['mbps']} Mbps, {banda}"


def av_firmware(instalado, ultimo):
    if not ultimo:
        return AT, "Firmware: nao consegui consultar o servidor FOTA da Samsung"
    if ultimo == instalado:
        return OK, f"Firmware: {instalado} e a ultima que a Samsung publica para este modelo e CSC"
    return AT, f"Firmware: a Samsung publica {ultimo}; instalado {instalado}"


def av_apps(estados):
    """estados = {pacote: True (desatualizado) | False (em dia) | None (sem resposta)}"""
    if not estados:
        return AT, "Apps FOSS: nenhuma consulta ao F-Droid deu certo"
    velhos = sorted(p for p, e in estados.items() if e)
    sem = sum(1 for e in estados.values() if e is None)
    txt = f"{len(estados) - len(velhos) - sem} em dia de {len(estados)} consultados"
    if sem:
        txt += f"; {sem} sem resposta"
    if velhos:
        return AT, f"Apps FOSS: {txt}; MAIS NOVOS NO F-DROID: {', '.join(velhos)}"
    return OK, f"Apps FOSS: {txt}"


# ---------------------------------------------------------------- historico local (o espaco livre cai sem ninguem ver)
def arquivo_historico():
    return RAIZ / "diagnostico" / "saude-historico.jsonl"


def ler_anterior(caminho):
    try:
        linhas = [x for x in caminho.read_text(encoding="utf-8").splitlines() if x.strip()]
        return json.loads(linhas[-1]) if linhas else None
    except (OSError, ValueError):
        return None


def gravar_registro(caminho, registro):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=True) + "\n")


# ---------------------------------------------------------------- rede (so com --online)
def baixa(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "Kies2.0"})  # a Samsung responde 403 sem este User-Agent
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - URL fixa, so GET
        return r.read().decode("utf-8", "replace")


def consulta_online(csc, modelo, versoes):
    """Devolve (ultimo_firmware_ou_None, {pacote: bool|None}). Erro de rede vira None, nunca derruba o painel."""
    try:
        ultimo = fota_ultima(baixa(URL_FOTA.format(csc=csc, modelo=modelo)))
    except Exception:  # noqa: BLE001
        ultimo = None
    estados = {}
    for pacote in FOSS:
        if pacote not in versoes:
            continue
        try:
            estados[pacote] = fdroid_desatualizado(versoes[pacote], json.loads(baixa(URL_FDROID.format(pacote=pacote))))
        except Exception:  # noqa: BLE001
            estados[pacote] = None
    return ultimo, estados


# ---------------------------------------------------------------- principal
def main(argv=None):
    ap = argparse.ArgumentParser(description="Painel de saude do Galaxy A12 (so leitura).")
    ap.add_argument("--online", action="store_true", help="consulta o servidor FOTA da Samsung e o F-Droid")
    ap.add_argument("--sem-historico", action="store_true", help="nao grava diagnostico/saude-historico.jsonl")
    args = ap.parse_args(argv)
    try:
        modelo = sh(CMD["modelo"])
    except FileNotFoundError:
        print("ABORTADO: o adb nao esta no PATH.")
        return 2
    if "A125" not in modelo:
        print(f"ABORTADO: nao achei o Galaxy A12 pelo adb (modelo lido: '{modelo or 'nenhum'}').")
        return 2

    hora = sh(CMD["hora"])
    try:
        agora = datetime.datetime.strptime(hora, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        agora = datetime.datetime.now()
    bat = parse_bateria(sh(CMD["bateria"]))
    termica = parse_termica(sh(CMD["termica"]))
    meminfo = parse_meminfo(sh(CMD["meminfo"]))
    zram = parse_mm_stat(sh(CMD["zram"]))
    psi = {"memory": parse_psi(sh(CMD["psi_memory"])), "cpu": parse_psi(sh(CMD["psi_cpu"])), "io": parse_psi(sh(CMD["psi_io"]))}
    pss = parse_pss(sh(CMD["pss"], timeout=120))
    df = parse_df(sh(CMD["df"]))
    mortes = parse_mortes(sh(CMD["mortes"]), agora)
    alarmes = parse_alarmes(sh(CMD["alarmes"]))
    wakelocks = parse_wakelocks(sh(CMD["wakelocks"]))
    wifi = parse_wifi(sh(CMD["wifi"]))

    caminho = arquivo_historico()
    anterior = ler_anterior(caminho)
    linhas = [av_bateria(bat), av_termica(termica), av_memoria(meminfo, zram), av_pressao(psi), av_pesados(pss),
              av_espaco(df, anterior), av_mortes(mortes), av_acorda(alarmes, wakelocks), av_wifi(wifi)]
    if args.online:
        build = build_instalado(sh(CMD["build"]))
        ultimo, estados = consulta_online(sh(CMD["csc"]), modelo, parse_versoes(sh(CMD["versoes"], timeout=120)))
        linhas += [av_firmware(build, ultimo), av_apps(estados)]

    print(f"SAUDE DO A12 em {agora:%d/%m/%Y %H:%M} (hora do aparelho)")
    for nivel, texto in linhas:
        print(f"[{nivel:<7}] {texto}")
    n_al = sum(1 for n, _ in linhas if n == AL)
    n_at = sum(1 for n, _ in linhas if n == AT)
    veredito = "ALERTA" if n_al else ("ATENCAO" if n_at else "SAUDAVEL")
    print(f"VEREDITO: {veredito} ({n_al} alertas, {n_at} atencoes)")

    if not args.sem_historico and df:
        gravar_registro(caminho, {"ts": agora.isoformat(timespec="seconds"), "livre_kb": df["livre_kb"], "total_kb": df["total_kb"],
                                  "mem_disp_kb": meminfo.get("MemAvailable"), "termica": termica.get("status"), "bateria": bat.get("nivel")})
    return 1 if n_al else 0


if __name__ == "__main__":
    sys.exit(main())
