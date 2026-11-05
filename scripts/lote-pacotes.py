#!/usr/bin/env python3
"""Desativa (ou reativa) um lote de pacotes do A12 pelo ADB, com travas. Padrao = simulacao.

  python scripts/lote-pacotes.py A1              simulacao (nao altera nada)
  python scripts/lote-pacotes.py A1 --aplicar    pm disable-user --user 0 (reversivel, pm enable desfaz)
  python scripts/lote-pacotes.py A1 --remover    pm uninstall -k --user 0 (so pacote JA desativado, de lote com substituto
                                                  declarado ou com "remocao_autorizada" no manifesto -- decisao
                                                  do Rafael, 30/10: aceitar menos reversivel que o padrao do
                                                  projeto. O -k MANTEM os dados do app; nao e permanente de
                                                  verdade: sem root, "cmd package install-existing" ainda traz
                                                  de volta, e reset de fabrica sempre traria)
  python scripts/lote-pacotes.py A1 --restaurar  desfaz --aplicar (pm enable) e --remover (install-existing)

Lotes e pacotes: scripts/lotes-bloatware.json.
"""
import argparse
import datetime
import json
import pathlib
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

RAIZ = pathlib.Path(__file__).resolve().parent.parent
# regra "nunca desativar" do CLAUDE.md do projeto
# appsedge: desativado, o "Abrir em tela dividida" dos Recentes falha e o dashcam perde a divisao (teste A/B, 30/10)
PROTEGIDOS = [r"^com\.android\.", r"^com\.google\.android\.gms", r"webview", r"knox", r"launcher", r"inputmethod",
              r"honeyboard", r"dialer", r"incallui", r"telephony", r"telecom", r"messag", r"contacts", r"systemui",
              r"^com\.osp\.app\.signin", r"gallery3d", r"myfiles", r"app\.camera", r"^android$", r"appsedge"]


def sh(cmd, timeout=60):
    r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def pacotes(flag):
    saida = sh(f"pm list packages {flag}")
    return {l.split(":", 1)[1].strip() for l in saida.splitlines() if l.startswith("package:")}


def bateria_ok(minimo=3):
    b = sh("dumpsys battery")
    n = re.search(r"level:\s*(\d+)", b)
    s = re.search(r"status:\s*(\d+)", b)
    if not n or not s:
        sys.exit("ABORTADO: nao consegui ler a bateria (aparelho offline?)")
    nivel, status = int(n.group(1)), int(s.group(1))
    ligado = status in (2, 5)  # 2 = carregando, 5 = cheia (100% com o cabo ligado nao e "carregando")
    print(f"bateria {nivel}% carregando={ligado}")
    if nivel < minimo or not ligado:
        sys.exit(f"ABORTADO: bateria abaixo de {minimo}% ou sem carregar (portao G1 do PLANO.md)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lote")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--remover", action="store_true",
                    help="pm uninstall -k --user 0 (mantem os dados): so pacote JA desativado, de lote com substituto "
                         "declarado ou com 'remocao_autorizada' (decisao do Rafael, 30/10 -- menos reversivel que o padrao do projeto)")
    ap.add_argument("--restaurar", action="store_true")
    ap.add_argument("--bateria-minima", type=int, default=3,
                    help="piso de bateria em %% (padrao 3, regra do Rafael; a USB do PC nao carrega, entao so baixe em fase reversivel)")
    a = ap.parse_args()
    if sum([a.aplicar, a.remover, a.restaurar]) > 1:
        sys.exit("ABORTADO: use so uma de --aplicar / --remover / --restaurar por vez")

    lotes = json.loads((RAIZ / "scripts" / "lotes-bloatware.json").read_text(encoding="utf-8"))
    if a.lote not in lotes:
        sys.exit(f"lote {a.lote!r} nao existe; opcoes: {', '.join(lotes)}")
    lote = lotes[a.lote]
    if (a.aplicar or a.remover) and not lote.get("aplicavel", False):
        sys.exit(f"ABORTADO: o lote {a.lote} esta marcado como nao aplicavel (precisa de decisao do Rafael)")
    subs = lote.get("substitutos", {})  # original -> substituto de codigo aberto, que precisa estar instalado e ativo
    livres = set(lote.get("permitidos", [])) | set(subs)  # fora da regra "nunca desativar", com o motivo no manifesto
    ruins = [p for p in lote["pacotes"] if p not in livres and any(re.search(rx, p, re.I) for rx in PROTEGIDOS)]
    if ruins and not a.restaurar:
        sys.exit("ABORTADO: pacote protegido no lote: " + ", ".join(ruins))
    if a.remover:
        sem_substituto = [p for p in lote["pacotes"] if p not in subs]
        if sem_substituto and not lote.get("remocao_autorizada"):
            sys.exit("ABORTADO: --remover so vale para pacote com substituto declarado no lote (ou lote com "
                     "'remocao_autorizada' no manifesto, decisao do Rafael); sem substituto: " + ", ".join(sem_substituto))
    modelo = sh("getprop ro.product.model")
    if "SM-A125" not in modelo:
        sys.exit(f"ABORTADO: aparelho inesperado: {modelo!r}")

    todos, off = pacotes(""), pacotes("-d")
    estado = {p: ("ausente" if p not in todos else "desativado" if p in off else "ativo") for p in lote["pacotes"]}
    print(f"lote {a.lote}: {lote['descricao']}")
    for p, e in estado.items():
        print(f"  {e:<10} {p}")

    if subs and not a.restaurar:
        ativos = pacotes("-e")
        # --remover age em pacote JA desativado: o substituto tambem e cobrado ali (senao o aparelho ficaria sem o app)
        cobrados = ("ativo", "desativado") if a.remover else ("ativo",)
        faltam = [f"{p} (falta {s})" for p, s in subs.items() if estado.get(p) in cobrados and s not in ativos]
        if faltam:
            sys.exit("ABORTADO: substituto nao instalado ou nao ativo: " + ", ".join(faltam))

    if a.restaurar:
        fila = [p for p, e in estado.items() if e in ("desativado", "ausente")]
        verbo = "reativados"
    elif a.remover:
        fila = [p for p, e in estado.items() if e == "desativado"]
        pulados = [p for p, e in estado.items() if e == "ativo"]
        if pulados:
            print("PULADO (ainda ativo; rode --aplicar antes de --remover): " + ", ".join(pulados))
        verbo = "removidos (pm uninstall -k --user 0)"
    else:
        fila = [p for p, e in estado.items() if e == "ativo"]
        verbo = "desativados"

    if not (a.restaurar or a.remover):
        # teclado em uso (regra do CLAUDE.md): 'substitutos'/'permitidos' tiram o pacote de PROTEGIDOS, entao a trava e esta
        teclados = [p for p in fila if re.search(r"inputmethod|honeyboard", p, re.I)]
        if teclados:
            ime = sh("settings get secure default_input_method").strip().split("/")[0]
            em_uso = [p for p in teclados if p == ime]
            if em_uso:
                sys.exit("ABORTADO: o teclado em uso esta na fila (troque o teclado padrao antes): " + ", ".join(em_uso))

    if not (a.aplicar or a.remover or a.restaurar):
        print(f"SIMULACAO: {len(fila)} pacote(s) seriam {verbo}. Nada foi alterado.")
        return
    if not fila:
        print("Nada a fazer.")
        return
    bateria_ok(a.bateria_minima)

    pasta = RAIZ / "diagnostico" / datetime.datetime.now().strftime("%Y%m%d-%H%M")
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"lote_{a.lote}_antes.txt").write_text("\n".join(f"{e} {p}" for p, e in estado.items()), encoding="utf-8")

    for p in fila:
        if a.restaurar:
            cmd = f"cmd package install-existing {p}" if estado[p] == "ausente" else f"pm enable {p}"
        elif a.remover:
            cmd = f"pm uninstall -k --user 0 {p}"  # -k: mantem os dados do app (ex.: notas); achado pelo Claude local, 30/10
        else:
            cmd = f"pm disable-user --user 0 {p}"
        print(f"  {sh(cmd)[:140]}")

    todos2, off2 = pacotes(""), pacotes("-d")
    if a.restaurar:
        falhou = [p for p in fila if p not in todos2 or p in off2]
    elif a.remover:
        falhou = [p for p in fila if p in todos2]
    else:
        falhou = [p for p in fila if p not in off2]
    print(f"RESULTADO: {len(fila) - len(falhou)} ok, {len(falhou)} falhou" + (": " + ", ".join(falhou) if falhou else ""))
    sys.exit(1 if falhou else 0)


if __name__ == "__main__":
    main()
