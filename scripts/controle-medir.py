#!/usr/bin/env python3
"""Mede o intervalo entre os pacotes de cada controle no A12: serve para comparar Bluetooth, cabo USB-C e Wi-Fi ligado ou desligado.

  python scripts/controle-medir.py                 espera voce mexer os analogicos e mostra os numeros de cada controle
  python scripts/controle-medir.py --wifi          mede com o Wi-Fi ligado, desliga, mede de novo e RELIGA sempre
  python scripts/controle-medir.py --botoes 30     depois da medida, escuta 30 s e lista os botoes apertados

Sem cronometro: comeca quando o controle se mexe, porque ele desliga sozinho e ninguem acerta a hora.
Controle no USB-C ocupa a unica porta do celular: rode antes `adb connect 100.64.0.2:5555` (Wi-Fi ou 4G) ou plugue so depois.
So le a entrada; a unica mudanca e o --wifi, sempre desfeita. O numero nao e o atraso total ate a tela.
Saida: 0 = mediu; 1 = ninguem mexeu no tempo; 2 = sem controle ou sem celular. Medidas: memoria/CONTROLES-GAMESIR.md.
"""
import argparse
import collections
import re
import statistics
import subprocess
import sys
import threading
import time

LINHA = re.compile(r"\[\s*(\d+\.\d+)\]\s+(\S+)\s+(\S+)\s+(\S+)")
BARRAMENTO = {"0003": "USB", "0005": "Bluetooth"}


def adb(comando, timeout=60):
    return subprocess.run(["adb", "shell", comando], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout).stdout


def acha_controles(texto):
    """Blocos do 'getevent -pl': controle e o no que tem botao de gamepad (nao a 'Consumer Control', que so tem teclas de midia)."""
    res = {}
    for bloco in re.split(r"(?=^add device)", texto, flags=re.M):
        ev = re.search(r"/dev/input/event(\d+)", bloco)
        nome = re.search(r'name:\s+"(.*)"', bloco)
        if ev and nome and re.search(r"\bBTN_(GAMEPAD|SOUTH|A)\b", bloco):
            res[ev.group(1)] = nome.group(1)
    return res


def barramentos(texto):
    """Do 'dumpsys input': nome do aparelho -> Bluetooth ou USB."""
    res = {}
    for nome, bus in re.findall(r"^\s*\d+: (.+?)\s*\n(?:.*\n){0,12}?\s*Identifier: bus=0x([0-9a-f]{4})", texto, flags=re.M):
        res[nome] = BARRAMENTO.get(bus, "bus " + bus)
    return res


def le_linha(linha):
    m = LINHA.search(linha)
    return (float(m.group(1)), m.group(2), m.group(3), m.group(4)) if m else None


def intervalos(eventos):
    """Em ms, entre pacotes seguidos; parada de mais de 250 ms nao conta: e a mao, nao o radio."""
    t = [e[0] for e in eventos if e[1] == "EV_SYN" and e[2] == "SYN_REPORT"]
    return sorted((b - a) * 1000 for a, b in zip(t, t[1:]) if b - a < 0.25)


def resumo(g):
    if len(g) < 30:
        return f"{len(g)} pacotes: pouco movimento, sem numero confiavel"
    q = lambda f: g[min(len(g) - 1, int(len(g) * f))]
    return (f"{len(g)} pacotes; mediana {statistics.median(g):.1f} ms; p90 {q(.9):.1f}; p99 {q(.99):.1f}; pior {g[-1]:.0f}; "
            f"cerca de {1000 / statistics.mean(g):.0f} por segundo; acima de 30 ms: {100 * sum(x > 30 for x in g) / len(g):.1f}%")


def botoes(eventos):
    return dict(collections.Counter(e[2] for e in eventos if e[1] == "EV_KEY" and e[3] == "DOWN"))


class Escuta:
    """Um 'adb shell -tt getevent' por controle: com terminal ele entrega na hora; em arquivo ou pipe, so em blocos (03/11)."""

    def __init__(self, controles):
        self.dados = {e: [] for e in controles}
        self.procs = [subprocess.Popen(["adb", "shell", "-tt", "getevent", "-lt", f"/dev/input/event{e}"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace") for e in controles]
        for e, p in zip(controles, self.procs):
            threading.Thread(target=self._le, args=(e, p), daemon=True).start()

    def _le(self, e, p):
        for linha in p.stdout or []:
            ev = le_linha(linha)
            if ev:
                self.dados[e].append(ev)

    def marca(self):
        return {e: len(v) for e, v in self.dados.items()}

    def desde(self, m):
        return {e: v[m[e]:] for e, v in self.dados.items()}

    def maior(self, m):
        return max((sum(1 for x in v if x[1] == "EV_SYN") for v in self.desde(m).values()), default=0)

    def espera(self, m, alvo, limite):
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            if self.maior(m) >= alvo:
                return True
            time.sleep(0.3)
        return False

    def fecha(self):
        for p in self.procs:
            p.kill()


def mostra(rotulo, por_no, nomes, tipos):
    print(f"== {rotulo}")
    for e, ev in por_no.items():
        print(f" {nomes[e]} ({tipos.get(nomes[e], '?')}, event{e}): {resumo(intervalos(ev))}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Mede os pacotes dos controles no A12")
    ap.add_argument("--wifi", action="store_true", help="compara Wi-Fi ligado e desligado; religa sempre")
    ap.add_argument("--pacotes", type=int, default=350)
    ap.add_argument("--espera", type=int, default=600, help="segundos esperando alguem mexer no controle")
    ap.add_argument("--botoes", type=int, default=0, metavar="SEGUNDOS")
    a = ap.parse_args(argv)
    try:
        nomes = acha_controles(adb("getevent -pl 2>/dev/null"))
        tipos = barramentos(adb("dumpsys input"))
    except (subprocess.TimeoutExpired, OSError):
        print("O celular nao respondeu pelo adb.")
        return 2
    if not nomes:
        print("Nenhum controle ligado: toque em Mode (Bluetooth) ou confira o cabo.")
        return 2
    print("Mexa os analogicos sem parar. Esperando...", flush=True)
    es = Escuta(list(nomes))
    todos_antes = es.marca()
    codigo = 0
    try:
        m = es.marca()
        if not es.espera(m, a.pacotes, a.espera):
            print("Ninguem mexeu no controle a tempo; nada foi alterado.")
            codigo = 1
        else:
            mostra("Wi-Fi ligado" if a.wifi else "Medida", es.desde(m), nomes, tipos)
            if a.wifi:
                try:
                    adb("svc wifi disable")
                    time.sleep(1.5)
                    m = es.marca()
                    es.espera(m, a.pacotes, 45)
                    mostra("Wi-Fi desligado", es.desde(m), nomes, tipos)
                finally:
                    adb("svc wifi enable")
                    print("Wi-Fi religado.")
            if a.botoes:
                print(f"Aperte os botoes ({a.botoes} s)...", flush=True)
                time.sleep(a.botoes)
                for e, ev in es.desde(todos_antes).items():
                    print(f" {nomes[e]}: {botoes(ev)}")
    finally:
        es.fecha()
    return codigo


if __name__ == "__main__":
    sys.exit(main())
