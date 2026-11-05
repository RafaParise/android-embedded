#!/usr/bin/env python3
"""Cruza pacotes com a lista UAD-ng e com o estado do aparelho (ultima sonda em diagnostico/).
Uso: python scripts/cruzar-uad.py [arquivo_com_pacotes] [--recomendados]
Baixa diagnostico/uad_lists.json se faltar. Somente leitura."""
import argparse
import importlib.util
import json
import pathlib
import re
import sys
import urllib.request
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = pathlib.Path(__file__).resolve().parent.parent
DIAG = RAIZ / "diagnostico"
UAD = DIAG / "uad_lists.json"
URL = ("https://raw.githubusercontent.com/Universal-Debloater-Alliance/"
       "universal-android-debloater-next-generation/main/resources/assets/uad_lists.json")
PROTEGIDOS = {
    "com.android.vending", "com.google.android.gms", "com.google.android.webview", "com.sec.android.app.camera",
    "com.samsung.android.app.contacts", "com.sec.android.app.popupcalculator", "com.sec.android.app.clockpackage",
    "com.samsung.android.app.notes", "com.sec.android.app.fm", "com.samsung.android.dialer",
    "com.samsung.android.incallui", "com.osp.app.signin", "com.sec.android.gallery3d", "com.sec.android.app.myfiles",
    "com.android.bips", "com.google.android.inputmethod.latin", "com.samsung.android.honeyboard",
    "com.samsung.android.fmm", "com.google.android.apps.turbo",
}



def _padroes_protegidos():
    """Os regex PROTEGIDOS de lote-pacotes.py (com.android., knox, telecom, messag, appsedge...): a regra 'nunca desativar' do projeto."""
    arq = RAIZ / "scripts" / "lote-pacotes.py"
    if not arq.exists():
        return []
    spec = importlib.util.spec_from_file_location("lote_pacotes", arq)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return [re.compile(x, re.I) for x in mod.PROTEGIDOS]


PADROES = _padroes_protegidos()


def protegido(pkg):
    return pkg in PROTEGIDOS or any(r.search(pkg) for r in PADROES)


ap = argparse.ArgumentParser()
ap.add_argument("arquivo", nargs="?")
ap.add_argument("--recomendados", action="store_true")
a = ap.parse_args()

DIAG.mkdir(exist_ok=True)
if not UAD.exists():
    urllib.request.urlretrieve(URL, UAD)
uad = json.loads(UAD.read_text(encoding="utf-8"))
sondas = sorted(DIAG.glob("2*/pacotes_todos.txt"))
if not sondas:
    sys.exit("Rode antes: python scripts/sonda-a12.py")
pasta = sondas[-1].parent
todos = set((pasta / "pacotes_todos.txt").read_text(encoding="utf-8").split())
desat = set((pasta / "pacotes_desativados.txt").read_text(encoding="utf-8").split())
print(f"sonda: {pasta.name} | UAD: {len(uad)} entradas")


def info(pkg):
    d = uad.get(pkg)
    if not d:
        return ("fora-da-lista", "", "")
    return (d.get("removal", "?"), d.get("list", "?"), (d.get("description") or "").replace("\n", " ")[:80])


if a.arquivo:
    texto = pathlib.Path(a.arquivo).read_text(encoding="utf-8", errors="replace")
    achados = re.finditer(r"\b(?:com|org|net|app|br|io)\.[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*", texto)
    pacotes = sorted({m.group(0).rstrip(".") for m in achados})
    ordem = {"Recommended": 0, "Advanced": 1, "Expert": 2, "Unsafe": 3}
    linhas, ausentes = [], []
    for p in pacotes:
        if p not in todos:
            ausentes.append(p)
            continue
        rem, lista, desc = info(p)
        estado = "DESATIVADO" if p in desat else "ativo"
        linhas.append((ordem.get(rem, 4), p, estado, rem, lista, "PROTEGIDO" if protegido(p) else "", desc))
    print(f"\n{len(pacotes)} nomes no texto | {len(linhas)} no aparelho | {len(ausentes)} ausentes")
    for _, p, est, rem, lista, marca, desc in sorted(linhas):
        print(f"{p} | {est} | {rem} | {lista} | {marca} | {desc}")
    print("\nAUSENTES:", ", ".join(ausentes) or "(nenhum)")

if a.recomendados:
    grupos = defaultdict(list)
    for p in sorted(todos - desat):
        grupos[info(p)[0]].append(p)
    print("\ninstalados e ativos por classificacao UAD:", {k: len(v) for k, v in grupos.items()})
    print("\nRECOMMENDED (sem os protegidos):", ", ".join(p for p in grupos["Recommended"] if not protegido(p)))
