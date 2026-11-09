#!/usr/bin/env python3
"""Religa a Depuracao por Wi-Fi do A12 pelo cabo (o Android a desliga sozinho ao trocar de rede ou reiniciar).

  python scripts/depuracao-sem-fio.py status    so mostra (0 = ligada, 1 = desligada, 2 = sem celular no cabo)
  python scripts/depuracao-sem-fio.py ligar     liga e confere lendo de volta
  python scripts/depuracao-sem-fio.py porta5555 liga o adb pela porta 5555 (vale em qualquer rede; cai ao reiniciar)

Por que existe: o Termux nao consegue religar sozinho (o Android recusa o comando `settings` vindo de app, mesmo com
WRITE_SECURE_SETTINGS; conferido em 05/11). O Rafael ligou a Depuracao por Wi-Fi e pediu para mante-la ("manter o telefone
ativo em depuracao"); este script so devolve o estado que ele escolheu. Desfazer: Opcoes do desenvolvedor > Depuracao por Wi-Fi.
"""
import subprocess
import sys

CHAVE = "adb_wifi_enabled"
_executa = subprocess.run  # os testes trocam por um falso


def adb(*args, limite=20):
    try:
        p = _executa(["adb", *args], capture_output=True, text=True, timeout=limite)
        return p.returncode, (p.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def no_cabo():
    rc, saida = adb("get-state")
    return rc == 0 and saida == "device"


def estado():
    _, saida = adb("shell", "settings", "get", "global", CHAVE)
    return saida.strip()


def porta5555():
    """Liga o adb pela porta 5555 (adb tcpip): o parise-core e o PC comandam o celular em QUALQUER rede (dados moveis tambem).
    Autorizado pelo Rafael em 05/11, com o risco explicado (a porta fica visivel na rede; so entra chave autorizada ou
    quem ele aceitar no aviso da tela). Cai ao reiniciar o celular."""
    _, porta = adb("shell", "getprop", "service.adb.tcp.port")
    if porta.strip() != "5555":
        adb("tcpip", "5555")
        for _ in range(10):
            import time
            time.sleep(1)
            _, porta = adb("shell", "getprop", "service.adb.tcp.port")
            if porta.strip() == "5555":
                break
    ok = porta.strip() == "5555"
    print("Porta 5555 do adb: " + ("LIGADA (parise-core e PC alcancam o celular em qualquer rede, pela Tailscale)" if ok else "nao ligou"))
    return 0 if ok else 1


def main(args):
    cmd = args[0] if args else "status"
    if cmd == "porta5555":
        if not no_cabo():
            print("O celular nao esta no cabo (adb): a porta 5555 so se liga por aqui com o cabo ligado.")
            return 2
        return porta5555()
    if cmd not in ("status", "ligar"):
        print(__doc__.strip())
        return 2
    if not no_cabo():
        print("O celular nao esta no cabo (adb): a Depuracao por Wi-Fi so se religa por aqui com o cabo ligado.")
        return 2
    if cmd == "ligar" and estado() != "1":
        adb("shell", "settings", "put", "global", CHAVE, "1")
    ligada = estado() == "1"
    print("Depuracao por Wi-Fi: " + ("LIGADA" if ligada else "desligada") + (" (o cel do Termux reconecta sozinho)" if ligada else ""))
    return 0 if ligada else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
