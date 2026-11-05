#!/usr/bin/env python3
"""Permissoes minimas por ADB, com registro para desfazer (pm revoke/grant e appops). So o que o Rafael nao usa ou nao precisa:
  - apps nunca usados (Instagram, Waze, Teams): revoga todas as permissoes sensiveis e proibe segundo plano
  - Chrome (reserva, o navegador agora e o Fennec): revoga localizacao, contatos, microfone, camera, contas, Bluetooth
  - WhatsApp Business: revoga SMS (so serve para o codigo de verificacao) e registro de ligacoes
O app volta a pedir a permissao quando precisar de verdade (Android 12).

  python scripts/privacidade.py              simulacao
  python scripts/privacidade.py --aplicar    aplica e grava diagnostico/<data>/privacidade_antes.json
  python scripts/privacidade.py --restaurar  desfaz o ultimo registro
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

RAIZ = pathlib.Path(__file__).resolve().parent.parent
TODAS = {"ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION", "ACCESS_BACKGROUND_LOCATION", "CAMERA", "RECORD_AUDIO", "READ_CONTACTS",
         "WRITE_CONTACTS", "READ_SMS", "RECEIVE_SMS", "SEND_SMS", "READ_CALL_LOG", "WRITE_CALL_LOG", "READ_PHONE_STATE",
         "READ_PHONE_NUMBERS", "CALL_PHONE", "READ_CALENDAR", "WRITE_CALENDAR", "BODY_SENSORS", "ACTIVITY_RECOGNITION",
         "READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE", "BLUETOOTH_CONNECT", "BLUETOOTH_SCAN", "GET_ACCOUNTS"}
CHROME = TODAS - {"READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE", "READ_PHONE_STATE", "READ_PHONE_NUMBERS", "CALL_PHONE",
                  "READ_CALENDAR", "WRITE_CALENDAR", "READ_CALL_LOG", "WRITE_CALL_LOG", "READ_SMS", "RECEIVE_SMS", "SEND_SMS"}
PERFIS = [  # (pacote, permissoes a revogar, proibir segundo plano?)
    ("com.instagram.android", TODAS, True),
    ("com.waze", TODAS, True),
    ("com.microsoft.teams", TODAS, True),
    ("com.android.chrome", CHROME, False),
    # WhatsApp Business: sem localizacao (pede de novo so ao enviar a localizacao); camera, microfone, contatos (le e grava: o adaptador de
    # sincronizacao dele precisa de WRITE_CONTACTS para manter os contatos da conta WhatsApp) e telefone ficam
    ("com.whatsapp.w4b", {"READ_SMS", "RECEIVE_SMS", "SEND_SMS", "READ_CALL_LOG", "WRITE_CALL_LOG", "ACCESS_FINE_LOCATION",
                          "ACCESS_COARSE_LOCATION", "ACCESS_BACKGROUND_LOCATION"}, False),
]


def sh(cmd, timeout=60):
    r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def concedidas(pkg, alvo):
    """Permissoes de execucao hoje concedidas ao app que estao no conjunto alvo."""
    achadas = re.findall(r"android\.permission\.(\w+): granted=true", sh(f"dumpsys package {pkg}"))
    return sorted({p for p in achadas if p in alvo})


def fundo_atual(pkg):
    m = re.search(r"RUN_ANY_IN_BACKGROUND: (\w+)", sh(f"cmd appops get {pkg} RUN_ANY_IN_BACKGROUND"))
    return m.group(1) if m else "default"


def fundo_confere(pkg, esperado):
    atual = fundo_atual(pkg)
    return atual != "ignore" if esperado == "default" else atual == esperado  # "default" pode ler como allow


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--restaurar", action="store_true")
    a = ap.parse_args()
    if "SM-A125" not in sh("getprop ro.product.model"):
        sys.exit("ABORTADO: aparelho nao encontrado ou inesperado")

    if a.restaurar:
        regs = sorted((RAIZ / "diagnostico").glob("*/privacidade_antes.json"))
        if not regs:
            sys.exit("nenhum registro de privacidade em diagnostico/")
        falhas = []
        for pkg, d in json.loads(regs[-1].read_text(encoding="utf-8")).items():
            for p in d["perms"]:
                sh(f"pm grant {pkg} android.permission.{p}")
            if d["fundo"]:
                sh(f"cmd appops set {pkg} RUN_ANY_IN_BACKGROUND {d['fundo']}")
            # as saidas do pm/appops nao dizem nada: le de volta e confere
            falhas += [f"{pkg} {p}: continua revogada" for p in d["perms"] if p not in concedidas(pkg, set(d["perms"]))]
            if d["fundo"] and not fundo_confere(pkg, d["fundo"]):
                falhas.append(f"{pkg} segundo plano: nao voltou para {d['fundo']}")
        if falhas:
            sys.exit("FALHOU, nem tudo voltou (registro " + str(regs[-1]) + "):" + chr(10) + "  " + (chr(10) + "  ").join(falhas))
        print("restaurado a partir de", regs[-1])
        return

    registro, instalados = {}, sh("pm list packages")
    for pkg, alvo, fundo in PERFIS:
        if f"package:{pkg}" not in instalados:
            print(f"  ausente  {pkg}")
            continue
        perms = concedidas(pkg, alvo)
        antes = fundo_atual(pkg) if fundo else None
        proibir = fundo and antes != "ignore"  # ja proibido: o original esta no registro anterior, nao regravar "ignore" como se fosse ele
        if not perms and not proibir:
            print(f"  {pkg:<26} nada novo a revogar")
            continue
        registro[pkg] = {"perms": perms, "fundo": antes if proibir else None}
        print(f"  {pkg:<26} revogar {len(perms)}: {','.join(perms) or '-'}" + ("  + segundo plano proibido" if proibir else ""))
    if not a.aplicar:
        print("SIMULACAO: nada foi alterado (use --aplicar).")
        return
    if not registro:  # nada novo: nao grava registro vazio, que esconderia o original no --restaurar
        print("nada a aplicar; o ultimo registro continua valendo para --restaurar.")
        return
    pasta = RAIZ / "diagnostico" / time.strftime("%Y%m%d-%H%M%S")
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "privacidade_antes.json").write_text(json.dumps(registro, indent=1), encoding="utf-8")
    for pkg, d in registro.items():
        for p in d["perms"]:
            sh(f"pm revoke {pkg} android.permission.{p}")
        if d["fundo"] is not None:
            sh(f"cmd appops set {pkg} RUN_ANY_IN_BACKGROUND ignore")
    # as saidas do pm/appops nao dizem nada: le de volta e confere
    falhas = []
    for pkg, d in registro.items():
        ainda = concedidas(pkg, set(d["perms"]))
        falhas += [f"{pkg} {p}: continua concedida" for p in ainda]
        if d["fundo"] is not None and fundo_atual(pkg) != "ignore":
            falhas.append(f"{pkg} segundo plano: nao ficou em ignore")
    if falhas:
        sys.exit("FALHOU, nem tudo foi aplicado (registro em " + str(pasta / "privacidade_antes.json") + " serve para --restaurar):"
                 + chr(10) + "  " + (chr(10) + "  ").join(falhas))
    print("aplicado; registro para desfazer:", pasta / "privacidade_antes.json")


if __name__ == "__main__":
    main()
