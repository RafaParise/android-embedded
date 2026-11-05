#!/usr/bin/env python3
"""Quem gastou dados MOVEIS (e Wi-Fi) no aparelho: soma o historico que o proprio Android guarda, por aplicativo.
SO LEITURA (dumpsys netstats e pm list; nada e alterado). Substitui, sem VPN, a visibilidade que o NetGuard daria:
a VPN dele disputaria o unico slot de VPN com a Tailscale.

  python scripts/dados-moveis.py                  ultimos 30 dias, os 12 maiores
  python scripts/dados-moveis.py --dias 7 --top 20

Como ler: o Android guarda o historico em blocos de 2 horas, por aplicativo (uid) e por tipo de rede. Aqui somo recebido +
enviado, primeiro plano + fundo, so o trafego sem etiqueta (tag 0x0; o etiquetado ja esta dentro do total).
  uid -5  = o que o celular repassou a OUTROS aparelhos (hotspot e tethering por USB ou Bluetooth)
  uid -4  = aplicativos que ja foram desinstalados (o historico deles fica aqui)
Limite honesto: o ciclo da operadora nao e lido; a janela e em dias corridos (em 31/10, 30 dias deram 27,43 GB contra o aviso de
27,35 GB do Android, mas isso depende de quando o ciclo comeca). O Android so guarda alguns meses de historico.
"""
import argparse
import re
import subprocess
import sys
import time
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

TIPO_MOVEL = 0   # NetworkTemplate / ConnectivityManager.TYPE_MOBILE
TIPO_WIFI = 1    # TYPE_WIFI (a VPN, tipo 17, e ignorada: o trafego dela ja aparece na rede de baixo)
NOMES_ESPECIAIS = {-5: "hotspot/tethering (outros aparelhos)", -4: "apps ja desinstalados", 0: "root", 1000: "sistema Android",
                   1001: "telefonia (radio)", 2000: "shell (adb)"}
RE_IDENT = re.compile(r"\s+ident=\[\{type=(\d+).*\}\] uid=(-?\d+) set=(\w+) tag=(0x[0-9a-f]+)")
RE_BLOCO = re.compile(r"\s+st=(\d+) rb=(\d+) rp=\d+ tb=(\d+) tp=\d+")


def sh(cmd, timeout=120):
    r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).replace("\r", "")


def somar(texto, desde):
    """{tipo: {uid: [recebido, enviado]}} so dos blocos que comecam em 'desde' (epoch, s) ou depois, so redes movel e Wi-Fi, so tag 0x0."""
    totais = {TIPO_MOVEL: defaultdict(lambda: [0, 0]), TIPO_WIFI: defaultdict(lambda: [0, 0])}
    linhas = texto.splitlines()
    inicio = next((i for i, linha in enumerate(linhas) if linha.strip() == "UID stats:"), None)
    if inicio is None:
        return None
    ident = None
    for linha in linhas[inicio + 1:]:
        if linha and not linha[0].isspace():
            break  # proxima secao do dumpsys (ex.: "UID tag stats:"): nao entra na conta
        m = RE_IDENT.match(linha)
        if m:
            ident = (int(m.group(1)), int(m.group(2)), m.group(4))
            continue
        b = RE_BLOCO.match(linha)
        if b and ident and ident[2] == "0x0" and ident[0] in totais and int(b.group(1)) >= desde:
            soma = totais[ident[0]][ident[1]]
            soma[0] += int(b.group(2))
            soma[1] += int(b.group(3))
    return totais


def pacotes_por_uid(saida):
    nomes = {}
    for linha in saida.splitlines():
        m = re.match(r"package:(\S+) uid:(\d+)", linha.strip())
        if m:
            nomes.setdefault(int(m.group(2)), []).append(m.group(1))
    return nomes


def nome_do_uid(uid, nomes):
    if uid in nomes:
        return ", ".join(nomes[uid][:2]) + (" (+%d)" % (len(nomes[uid]) - 2) if len(nomes[uid]) > 2 else "")
    return NOMES_ESPECIAIS.get(uid, f"uid {uid}")


def tamanho(n):
    return f"{n / 1e9:6.2f} GB" if n >= 1e8 else f"{n / 1e6:6.1f} MB"


def relatorio(totais, nomes, dias, top):
    linhas = []
    movel = sum(r + e for r, e in totais[TIPO_MOVEL].values())
    wifi = sum(r + e for r, e in totais[TIPO_WIFI].values())
    linhas.append(f"ultimos {dias} dias: MOVEL {movel / 1e9:.2f} GB | WI-FI {wifi / 1e9:.2f} GB")
    for titulo, tipo in (("MOVEL (dados da operadora)", TIPO_MOVEL), ("WI-FI", TIPO_WIFI)):
        linhas.append(f"--- {titulo}, os {top} maiores (recebido + enviado):")
        ordem = sorted(totais[tipo].items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:top]
        for uid, (rec, env) in ordem:
            if rec + env == 0:
                continue
            linhas.append(f"  {tamanho(rec + env)}  (baixou {tamanho(rec).strip()}, enviou {tamanho(env).strip()})  {nome_do_uid(uid, nomes)}")
    return linhas


def main():
    ap = argparse.ArgumentParser(description="Quem gastou dados moveis e Wi-Fi (so leitura).")
    ap.add_argument("--dias", type=int, default=30)
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args()
    if a.dias < 1 or a.top < 1:
        sys.exit("--dias e --top precisam ser 1 ou mais")
    if "SM-A125" not in sh("getprop ro.product.model", timeout=30):
        sys.exit("ABORTADO: celular nao encontrado no ADB (cabo, depuracao USB)")
    totais = somar(sh("dumpsys netstats --full"), int(time.time()) - a.dias * 86400)
    if totais is None:
        sys.exit("ABORTADO: o dumpsys netstats nao trouxe a secao 'UID stats:' (o formato do Android mudou?)")
    nomes = pacotes_por_uid(sh("pm list packages -U -u", timeout=60))
    print("\n".join(relatorio(totais, nomes, a.dias, a.top)))


if __name__ == "__main__":
    main()
