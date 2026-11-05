#!/usr/bin/env python3
"""Microfone do fone Bluetooth no celular, fora de chamada, e bloqueio do microfone do proprio celular (A12).

  python scripts/microfone-bt.py status           so le: fone, canal, gravacao, microfone do celular
  python scripts/microfone-bt.py auto             canal de voz so enquanto um app grava; musica em AAC no resto (padrao)
  python scripts/microfone-bt.py fixo             canal aberto com o fone conectado: sem atraso, mas o som fica em qualidade de telefone
  python scripts/microfone-bt.py desligar         nao abre o canal
  python scripts/microfone-bt.py celular-mudo     silencia o microfone do celular quando nao houver fone nem fio
  python scripts/microfone-bt.py celular-ligado   devolve o microfone do celular agora
  python scripts/microfone-bt.py medir [SEG]      grava pelo PC, mede nivel, ruido e faixa, e apaga a gravacao

Reconhece sozinho conectar e desconectar. Roda dentro do processo do Wi-Fi em alto desempenho (Tela wifi-turbo): nenhum processo a mais.
Em toque de chamada ou chamada o microfone do celular volta sempre. Guia: memoria/OBS-ESTUDIO.md.
"""
import array
import cmath
import math
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import wave

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

DIR = "/data/local/tmp"
DEX = f"{DIR}/tela.dex"
MODO = f"{DIR}/mic-bt.modo"
BLOQUEIO = f"{DIR}/mic-celular.bloqueado"
MODELO = "SM-A125M"
MODOS = ("auto", "fixo", "desligado")
BANDAS = ((100, 4000), (4000, 8000), (8000, 16000))
SILENCIO_DB = -85.0
DESCARTA_S = 3


def adb(*a, timeout=30):
    r = subprocess.run(["adb", *a], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.stdout.replace("\r\n", "\n")


def sh(cmd, timeout=30):
    return adb("shell", cmd, timeout=timeout)


def confere_aparelho():
    if sh("getprop ro.product.model").strip() != MODELO:
        sys.exit(f"ABORTADO: esperava {MODELO} com a depuracao USB ligada.")


def tela(*a):
    return sh(f"CLASSPATH={DEX} app_process / Tela {' '.join(a)} 2>&1")


def le_olhada(texto):
    """Transforma a saida de 'Tela mic-olha' em dicionario."""
    d = {"fone": False, "fio": False, "usb": False, "sco": False, "mudo": False, "modo": 0, "gravando": 0}
    for linha in texto.splitlines():
        c = linha.split()
        if len(c) == 4 and c[0] == "disp" and c[3] == "1":
            d.update({"80000008": {"fone": True}, "80000010": {"fio": True}, "80001000": {"usb": True}}.get(c[1], {}))
        elif len(c) == 2 and c[0] in ("sco", "mudo"):
            d[c[0]] = c[1] == "true"
        elif len(c) == 2 and c[0] in ("modo", "gravando") and c[1].isdigit():
            d[c[0]] = int(c[1])
    return d


def processo_vivo():
    return sh("ps -A -o ARGS | grep -c 'Tela wifi-turb[o]'").strip() not in ("", "0")


def status():
    confere_aparelho()
    d = le_olhada(tela("mic-olha"))
    modo = sh(f"cat {MODO} 2>/dev/null").strip() or "auto"
    bloq = sh(f"[ -e {BLOQUEIO} ] && echo sim").strip() == "sim"
    print(f"Fone Bluetooth: {'conectado' if d['fone'] else 'nao'} | fio ou USB: {'sim' if d['fio'] or d['usb'] else 'nao'}")
    print(f"Modo: {modo} | canal de voz: {'aberto' if d['sco'] else 'fechado'} | gravando agora: {d['gravando']}")
    print(f"Microfone do celular: {'MUDO' if d['mudo'] else 'ligado'} | bloqueio pedido: {'sim' if bloq else 'nao'}")
    print(f"Processo: {'de pe' if processo_vivo() else 'PARADO (rode: python scripts/tela-apagada.py iniciar)'}")
    return 0


def define_modo(modo):
    confere_aparelho()
    if modo not in MODOS:
        sys.exit("modo invalido")
    sh(f"echo {modo} > {MODO}")
    print(f"Modo do microfone do fone: {modo}.")
    if not processo_vivo():
        print("AVISO: o processo nao esta de pe. Rode: python scripts/tela-apagada.py iniciar")
        return 1
    return 0


def celular_mudo():
    confere_aparelho()
    sh(f"touch {BLOQUEIO}")
    print("Bloqueio ligado: sem fone nem fio, o microfone do celular fica mudo. Em toque de chamada e em chamada ele volta sozinho.")
    if not processo_vivo():
        print("AVISO: o processo nao esta de pe. Rode: python scripts/tela-apagada.py iniciar")
        return 1
    return 0


def celular_ligado():
    confere_aparelho()
    sh(f"rm -f {BLOQUEIO}")
    print(tela("mic-solta").strip())
    return 0


def fft(x):
    n = len(x)
    if n == 1:
        return x
    par, impar = fft(x[0::2]), fft(x[1::2])
    fator = [cmath.exp(-2j * math.pi * k / n) * impar[k] for k in range(n // 2)]
    return [par[k] + fator[k] for k in range(n // 2)] + [par[k] - fator[k] for k in range(n // 2)]


def db(v):
    return 20 * math.log10(v) if v > 0 else -120.0


def mede_amostras(a, taxa):
    """Nivel de pico, ruido de fundo (trecho mais baixo), corte e energia por faixa. Nada da gravacao fica guardado."""
    if not a:
        return None
    janela = max(1, taxa // 10)
    rms = [math.sqrt(sum(v * v for v in a[i:i + janela]) / len(a[i:i + janela])) for i in range(0, len(a), janela)]
    n = 4096
    energia = [0.0] * len(BANDAS)
    forte = sorted(range(len(rms)), key=lambda i: rms[i], reverse=True)[:12]
    for i in forte:
        trecho = list(a[i * janela:i * janela + n])
        if len(trecho) < n:
            continue
        hann = [trecho[k] * (0.5 - 0.5 * math.cos(2 * math.pi * k / (n - 1))) for k in range(n)]
        esp = fft([complex(v) for v in hann])
        for b, (lo, hi) in enumerate(BANDAS):
            energia[b] += sum(abs(esp[k]) ** 2 for k in range(int(lo * n / taxa), min(n // 2, int(hi * n / taxa))))
    total = sum(energia) or 1.0
    return {
        "pico_db": db(max(abs(v) for v in a) / 32768),
        "ruido_db": db(sorted(rms)[len(rms) // 10] / 32768),
        "voz_db": db(sorted(rms)[-max(1, len(rms) // 10)] / 32768),
        "corte": sum(abs(v) >= 32760 for v in a) / len(a),
        "faixas": [e / total for e in energia],
    }


def veredito(m):
    """O que a medida diz, em palavras. A faixa mostra o codec: voz estreita corta em 4 kHz, voz larga vai a 8 kHz."""
    if m["voz_db"] < SILENCIO_DB:
        return "silencio: microfone mudo ou sem sinal"
    if m["faixas"][1] < 0.0005:
        faixa = "voz estreita (ate 4 kHz, como telefone antigo)"
    else:
        faixa = "voz larga (ate 8 kHz)"
    nivel = "CORTANDO: fale mais longe do microfone" if m["corte"] > 0.001 else "baixo: aproxime o microfone" if m["voz_db"] < -40 else "bom"
    return f"{faixa}; nivel {nivel}"


def medir(seg=10):
    confere_aparelho()
    d = tempfile.mkdtemp(prefix="mic-")
    arq = pathlib.Path(d) / "m.wav"
    seg += DESCARTA_S
    print(f"Fale normalmente por {seg} s, com uma pausa no meio, a partir de agora. Os {DESCARTA_S} primeiros nao contam.")
    try:
        subprocess.run(["scrcpy", "--no-video", "--no-playback", "--audio-source=mic", "--audio-codec=raw", f"--record={arq}", f"--time-limit={seg}"],
                       capture_output=True, timeout=seg + 40)
        if not arq.exists():
            print("A gravacao nao saiu.")
            return 1
        with wave.open(str(arq)) as w:
            taxa, canais = w.getframerate(), w.getnchannels()
            bruto = array.array("h", w.readframes(w.getnframes()))
        m = mede_amostras(bruto[::canais][taxa * DESCARTA_S:], taxa)  # o comeco e a abertura do canal, nao a voz
        if not m:
            print("Gravacao vazia.")
            return 1
        print(f"Voz {m['voz_db']:.1f} dB | pico {m['pico_db']:.1f} dB | ruido de fundo {m['ruido_db']:.1f} dB | corte {100 * m['corte']:.2f}%")
        print("Faixas: " + " | ".join(f"{lo / 1000:g}-{hi / 1000:g} kHz {100 * f:.2f}%" for (lo, hi), f in zip(BANDAS, m["faixas"])))
        print(veredito(m))
        return 0
    finally:
        if arq.exists():
            arq.unlink()  # a voz dele nao fica em arquivo
        os.rmdir(d)


def main():
    a = sys.argv[1:]
    if a == ["status"]:
        return status()
    if a == ["ligar"] or a == ["fixo"]:
        return define_modo("fixo")
    if a == ["auto"]:
        return define_modo("auto")
    if a == ["desligar"]:
        return define_modo("desligado")
    if a == ["celular-mudo"]:
        return celular_mudo()
    if a == ["celular-ligado"]:
        return celular_ligado()
    if a and a[0] == "medir" and (len(a) == 1 or (len(a) == 2 and re.fullmatch(r"\d{1,3}", a[1]))):
        return medir(int(a[1]) if len(a) == 2 else 10)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
