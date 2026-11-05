#!/usr/bin/env python3
"""Reinicia o A12 e espera ele voltar: boot completo e usuario destravado (o Rafael digita o PIN/biometria).

  python scripts/reiniciar.py [--espera-destravar 300] [--assentar 90]
"""
import argparse
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


def adb(*args, timeout=30):
    try:
        r = subprocess.run(["adb", *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--espera-destravar", type=int, default=300)
    ap.add_argument("--assentar", type=int, default=90)
    a = ap.parse_args()

    modelo = adb("shell", "getprop ro.product.model")
    if "SM-A125" not in modelo:
        sys.exit(f"ABORTADO: o aparelho no ADB nao e o SM-A125M ({modelo[:40]!r}): nao reiniciei nada.")
    t0 = time.time()
    adb("reboot")
    time.sleep(25)  # deixa o aparelho sair da lista antes de esperar por ele
    try:
        subprocess.run(["adb", "wait-for-device"], timeout=240)
    except subprocess.TimeoutExpired:
        sys.exit("TEMPO: o aparelho nao voltou ao ADB em 4 min")
    while adb("shell", "getprop", "sys.boot_completed") != "1":
        if time.time() - t0 > 420:
            sys.exit("TEMPO: o boot nao terminou em 7 min")
        time.sleep(3)
    print(f"boot completo em {int(time.time() - t0)} s", flush=True)

    t1 = time.time()
    avisou = False
    while "UNLOCKED" not in adb("shell", "am", "get-started-user-state", "0"):
        if not avisou:
            print("aguardando o Rafael destravar a tela do celular...", flush=True)
            avisou = True
        if time.time() - t1 > a.espera_destravar:
            sys.exit(f"TEMPO: ainda travado depois de {a.espera_destravar} s")
        time.sleep(3)
    print(f"destravado apos {int(time.time() - t1)} s; assentando {a.assentar} s", flush=True)
    time.sleep(a.assentar)
    print("pronto")


if __name__ == "__main__":
    main()
