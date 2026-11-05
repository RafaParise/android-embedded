#!/usr/bin/env python3
"""Revisao dos apps e servicos NATIVOS (de sistema) ainda ativos: quem usa rede, CPU, alarmes, jobs, servicos e wakelocks.
Somente leitura. Cruza dados reais do aparelho com o inventario (internet, permissoes sensiveis, classe UAD-ng e descricao).
Serve para decidir, com evidencia, o que ainda rouba dado ou desempenho. Tambem confere se algum pacote de lote voltou a ficar ativo.

  python scripts/auditoria-nativos.py            tabela dos 28 mais pesados e a lista de "desativados que voltaram"
  python scripts/auditoria-nativos.py --todos    todos os nativos ativos que tem rede ou algum consumo
"""
import argparse
import collections
import csv
import json
import pathlib
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

RAIZ = pathlib.Path(__file__).resolve().parent.parent
# infraestrutura que fica por decisao (ver DECISOES.md); aparece na tabela como [base]
BASE = re.compile(r"^(android$|com\.android\.|com\.google\.android\.(gms|gsf|webview|vending|ext\.|networkstack|captiveportallogin|"
                  r"documentsui|permissioncontroller|providers|configupdater|tts|packageinstaller|overlay|cellbroadcast)|"
                  r"com\.samsung\.android\.(dialer|incallui|providers|app\.telephonyui)|com\.sec\.android\.app\.launcher|com\.sec\.phone|"
                  r"com\.sec\.imsservice|com\.sec\.epdg|com\.samsung\.ims|com\.mediatek|com\.qualcomm|vendor\.)")


def sh(cmd, timeout=180):
    r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).replace("\r", "")


def uid_de_rotulo(t):  # u0a97 -> 10097 ; 1000 -> 1000
    m = re.match(r"u\d+a(\d+)$", t)
    return 10000 + int(m.group(1)) if m else (int(t) if t.isdigit() else None)


def mapa_uid():
    d = collections.defaultdict(list)
    for l in sh("pm list packages -U -s -e").splitlines():
        m = re.match(r"package:(\S+)\s+uid:(\d+)", l.strip())
        if m:
            d[int(m.group(2))].append(m.group(1))
    return d


def rede_por_uid():
    tot = collections.Counter()
    uid, ok = None, False
    for l in sh("dumpsys netstats --full --uid", 240).splitlines():
        m = re.search(r"\buid=(\d+) set=(\w+) tag=(0x[0-9a-f]+)", l)
        if m:
            uid, ok = int(m.group(1)), (m.group(3) == "0x0" and m.group(2) in ("DEFAULT", "ALL", "FOREGROUND"))
            continue
        m = re.search(r"\brb=(\d+) rp=\d+ tb=(\d+)", l)
        if m and uid is not None and ok:
            tot[uid] += int(m.group(1)) + int(m.group(2))
    return tot


def cpu_por_uid():
    """Tempo de CPU acumulado pelos processos vivos (desde que cada um nasceu; os persistentes, desde o boot)."""
    tot = collections.Counter()
    for l in sh("ps -A -o UID,TIME,NAME").splitlines()[1:]:
        p = l.split(None, 2)
        if len(p) < 3 or not p[1].count(":") == 2:
            continue
        h, m, s = p[1].split(":")
        seg = int(h) * 3600 + int(m) * 60 + int(s)
        u = p[0]
        mm = re.match(r"u\d+_a(\d+)$", u)
        uid = int(u) if u.isdigit() else (10000 + int(mm.group(1)) if mm else {"system": 1000, "root": 0, "radio": 1001, "shell": 2000}.get(u))
        if uid is not None:
            tot[uid] += seg
    return tot


def maiores_cpu(n=14):
    """Processos que mais gastaram CPU desde que nasceram, com a media de uso (CPU/idade). Pega laco em segundo plano."""
    linhas = []
    for l in sh("ps -A -o UID,TIME,ETIME,NAME").splitlines()[1:]:
        p = l.split(None, 3)
        if len(p) < 4:
            continue

        def seg(s):
            d = 0
            if "-" in s:
                d, s = s.split("-", 1)
            x = [int(v) for v in s.split(":")]
            while len(x) < 3:
                x.insert(0, 0)
            return int(d) * 86400 + x[0] * 3600 + x[1] * 60 + x[2]

        try:
            cpu, vida = seg(p[1]), seg(p[2])
        except ValueError:
            continue
        if p[3].startswith("["):
            continue
        linhas.append((cpu, vida, p[3].strip()))
    linhas.sort(reverse=True)
    print()
    print(f"{'maiores consumidores de CPU (processos vivos)':56s} {'CPU min':>8s} {'idade min':>9s} {'media':>7s}")
    for cpu, vida, nome in linhas[:n]:
        print(f"{nome[:56]:56s} {cpu / 60:8.1f} {vida / 60:9.0f} {100 * cpu / max(vida, 1):6.1f}%")


def alarmes_por_pacote():
    d = collections.Counter()
    for l in sh("dumpsys alarm | grep -E ' running, [0-9]+ wakeups'").splitlines():
        m = re.search(r"\S+:(\S+)\s+.*running, (\d+) wakeups", l)
        if m:
            d[m.group(1)] += int(m.group(2))
    return d


def jobs_por_uid():
    d = collections.Counter()
    for l in sh("dumpsys jobscheduler | grep -E '^ +JOB #'").splitlines():
        m = re.search(r"JOB #(\S+?)/", l)
        if m:
            u = uid_de_rotulo(m.group(1))
            if u is not None:
                d[u] += 1
    return d


def servicos_por_pacote():
    d = collections.Counter()
    for l in sh("dumpsys activity services | grep -E 'ServiceRecord\\{'").splitlines():
        m = re.search(r"ServiceRecord\{\w+ u\d+ ([\w.]+)/", l)
        if m:
            d[m.group(1)] += 1
    return d


def wakelocks_por_uid():
    d = collections.Counter()
    for l in sh("dumpsys power | grep -E 'PARTIAL_WAKE_LOCK'").splitlines():
        m = re.search(r"uid=(\d+)", l)
        if m:
            d[int(m.group(1))] += 1
    return d


def inventario():
    sh("true")
    r = subprocess.run([sys.executable, "-I", str(RAIZ / "scripts" / "inventario.py"), "--ver", "sistema"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        # sem isto o TSV de OUTRO dia entraria no relatorio como se fosse o estado atual
        sys.exit("ABORTADO: inventario.py falhou (codigo %s); nao uso inventario.tsv antigo: %s" % (r.returncode, (r.stdout + r.stderr).strip()[-150:]))
    achados = sorted((RAIZ / "diagnostico").glob("*/inventario.tsv"))
    if not achados:
        sys.exit("sem inventario.tsv")
    return {r["pacote"]: r for r in csv.DictReader(achados[-1].open(encoding="utf-8"), delimiter="\t")}


def descricoes():
    p = RAIZ / "diagnostico" / "uad_lists.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def voltaram():
    """Pacotes de lotes (lotes-bloatware.json) que estao ativos de novo (atualizacao do sistema ou da loja pode reativar)."""
    lotes = json.loads((RAIZ / "scripts" / "lotes-bloatware.json").read_text(encoding="utf-8"))
    ativos = {l.split(":", 1)[1].strip() for l in sh("pm list packages -e").splitlines() if l.startswith("package:")}
    return sorted((nome, p) for nome, lote in lotes.items() if lote.get("aplicavel", True) for p in lote["pacotes"] if p in ativos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--todos", action="store_true")
    a = ap.parse_args()
    if "SM-A125" not in sh("getprop ro.product.model"):
        sys.exit("ABORTADO: aparelho nao encontrado")
    inv, uad = inventario(), descricoes()
    uids = mapa_uid()
    rede, cpu, jobs, wl = rede_por_uid(), cpu_por_uid(), jobs_por_uid(), wakelocks_por_uid()
    alarmes, servicos = alarmes_por_pacote(), servicos_por_pacote()
    linhas = []
    for uid, pacotes in uids.items():
        for pkg in pacotes:
            r = inv.get(pkg, {})
            if r.get("estado") != "ativo":
                continue
            n = len(pacotes)  # uid compartilhado: divide o consumo
            mb, seg = rede[uid] / 1048576 / n, cpu[uid] / n
            w, j, s, k = alarmes[pkg], jobs[uid] // n, servicos[pkg], wl[uid]
            peso = mb / 5 + seg / 60 + w / 10 + j + s * 2 + k * 3 + (3 if r.get("internet") == "sim" and r.get("sensiveis") else 0)
            linhas.append((peso, pkg, r, mb, seg, w, j, s, k))
    linhas.sort(reverse=True)
    print(f"{'pacote':46s} {'UAD':11s} {'rede MB':>8s} {'CPU min':>7s} {'alarm':>5s} {'jobs':>4s} {'serv':>4s} {'wl':>3s}  flags / descricao")
    mostrados = 0
    for peso, pkg, r, mb, seg, w, j, s, k in linhas:
        if not a.todos and (mostrados >= 28 or peso < 1):
            break
        d = (uad.get(pkg, {}).get("description") or "").split("\n")[0][:62]
        flags = ("[base] " if BASE.search(pkg) else "") + ("NET " if r.get("internet") == "sim" else "") + (r.get("sensiveis") or "")
        print(f"{pkg[:46]:46s} {r.get('uad', '-')[:11]:11s} {mb:8.1f} {seg / 60:7.1f} {w:5d} {j:4d} {s:4d} {k:3d}  {flags[:40]} {d}")
        mostrados += 1
    maiores_cpu()
    ativos = [x for x in voltaram()]
    print(f"\nlotes: {len(ativos)} pacote(s) de lote ATIVO de novo" + (": " + ", ".join(f"{n}:{p}" for n, p in ativos[:12]) if ativos else " (todos continuam desativados)"))


if __name__ == "__main__":
    main()
