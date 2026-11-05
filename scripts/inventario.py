#!/usr/bin/env python3
"""Inventario do Galaxy A12 (somente leitura): pacotes x classe UAD-ng x ultimo uso x permissoes sensiveis x INTERNET.
Grava diagnostico/<data>/inventario.tsv (tabela completa) e resume na tela. Nao altera nada no aparelho.

  python scripts/inventario.py [--uad diagnostico/uad_lists.json] [--ver usuario|sistema|desconhecidos|permissoes]
"""
import argparse
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SENSIVEIS = {
    "ACCESS_FINE_LOCATION": "loc", "ACCESS_COARSE_LOCATION": "loc", "ACCESS_BACKGROUND_LOCATION": "locBG",
    "CAMERA": "cam", "RECORD_AUDIO": "mic", "READ_CONTACTS": "contatos", "WRITE_CONTACTS": "contatos",
    "READ_SMS": "sms", "RECEIVE_SMS": "sms", "SEND_SMS": "sms", "READ_CALL_LOG": "ligacoes", "WRITE_CALL_LOG": "ligacoes",
    "READ_PHONE_STATE": "telefone", "READ_PHONE_NUMBERS": "telefone", "CALL_PHONE": "telefone",
    "READ_CALENDAR": "agenda", "WRITE_CALENDAR": "agenda", "BODY_SENSORS": "sensores", "ACTIVITY_RECOGNITION": "atividade",
    "READ_EXTERNAL_STORAGE": "arquivos", "WRITE_EXTERNAL_STORAGE": "arquivos", "READ_MEDIA_IMAGES": "arquivos",
    "BLUETOOTH_CONNECT": "bt", "BLUETOOTH_SCAN": "bt", "NEARBY_WIFI_DEVICES": "wifi", "GET_ACCOUNTS": "contas",
}


def sh(cmd, timeout=180):
    r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return r.stdout


def lista(flag):
    return {l.split(":", 1)[1].strip() for l in sh(f"pm list packages {flag}").splitlines() if l.startswith("package:")}


def uso():
    """pacote -> (ultimo uso, minutos totais, aberturas): maior valor entre os blocos diario, semanal, mensal e anual do usagestats."""
    texto = sh("dumpsys usagestats")
    r = {}
    rx = re.compile(r'package=(\S+) totalTimeUsed="(?:(\d+):)?(\d+):(\d+)" lastTimeUsed="([\d\- :]+)".*?lastTimeVisible="([\d\- :]+)".*?appLaunchCount=(\d+)')
    for m in rx.finditer(texto):
        pkg, h, mi, seg, ult, vis, n = m.groups()  # formato do Android: [H:]MM:SS (DateUtils.formatElapsedTime)
        ultimo = max(ult, vis)
        if ultimo.startswith("1969"):
            ultimo = ""
        antes_ult, antes_min, antes_n = r.get(pkg, ("", 0, 0))
        r[pkg] = (max(ultimo, antes_ult), max(antes_min, int(h or 0) * 60 + int(mi)), max(antes_n, int(n)))
    return r


def permissoes():
    """pacote -> (permissoes sensiveis concedidas, tem INTERNET) lido do 'dumpsys package' inteiro."""
    perms, net, atual = {}, set(), None
    for linha in sh("dumpsys package", timeout=300).splitlines():
        m = re.match(r"\s*Package \[([^\]]+)\]", linha)
        if m:
            atual = m.group(1)
            continue
        if atual is None:
            continue
        s = linha.strip()
        m = re.match(r"([\w.]+): granted=(true|false)", s)
        if m and m.group(2) == "true":
            nome = m.group(1).rsplit(".", 1)[-1]
            if nome == "INTERNET":
                net.add(atual)
            elif nome in SENSIVEIS:
                perms.setdefault(atual, set()).add(SENSIVEIS[nome])
    return perms, net


def protegidos():
    spec = importlib.util.spec_from_file_location("lote_pacotes", RAIZ / "scripts" / "lote-pacotes.py")
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return [re.compile(x, re.I) for x in mod.PROTEGIDOS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uad", default=str(RAIZ / "diagnostico" / "uad_lists.json"))
    ap.add_argument("--ver", choices=["usuario", "sistema", "desconhecidos", "permissoes"])
    a = ap.parse_args()

    if "SM-A125" not in sh("getprop ro.product.model"):
        sys.exit("ABORTADO: aparelho nao encontrado ou inesperado")
    uad = json.loads(pathlib.Path(a.uad).read_text(encoding="utf-8")) if pathlib.Path(a.uad).exists() else {}
    todos, off, sis, ativos = lista(""), lista("-d"), lista("-s"), lista("-e")
    ultimo_uso, (perms, net), prot = uso(), permissoes(), protegidos()

    pasta = RAIZ / "diagnostico" / time.strftime("%Y%m%d-%H%M%S")
    pasta.mkdir(parents=True, exist_ok=True)
    linhas = []
    for p in sorted(todos):
        u = uad.get(p, {})
        ult, minutos, aberturas = ultimo_uso.get(p, ("", 0, 0))
        linhas.append({
            "pacote": p, "tipo": "sistema" if p in sis else "usuario", "estado": "ativo" if p in ativos else "desativado",
            "uad": u.get("removal", "-") if u else "-", "lista": u.get("list", "-") if u else "-",
            "ultimo_uso": ult[:16], "min": minutos, "aberturas": aberturas, "internet": "sim" if p in net else "",
            "sensiveis": ",".join(sorted(perms.get(p, ()))), "protegido": "sim" if any(r.search(p) for r in prot) else "",
        })
    cab = list(linhas[0])
    (pasta / "inventario.tsv").write_text("\n".join(["\t".join(cab)] + ["\t".join(str(l[c]) for c in cab) for l in linhas]),
                                          encoding="utf-8")

    ativas = [l for l in linhas if l["estado"] == "ativo"]
    print(f"pacotes: {len(todos)} | ativos {len(ativas)} | desativados {len(off)} | tabela: {pasta / 'inventario.tsv'}")
    usuario = [l for l in ativas if l["tipo"] == "usuario"]
    sistema = [l for l in ativas if l["tipo"] == "sistema"]

    if a.ver in (None, "usuario"):
        print(f"\napps instalados pelo usuario ({len(usuario)}), do mais antigo ao mais recente no uso:")
        for l in sorted(usuario, key=lambda x: x["ultimo_uso"] or "0"):
            print(f"  {l['pacote']:<46} uso={l['ultimo_uso'] or 'nunca':<16} min={l['min']:<5} abre={l['aberturas']:<4}"
                  f" {'NET ' if l['internet'] else '    '}{l['sensiveis']}")
    if a.ver in (None, "sistema"):
        por = {}
        for l in sistema:
            por.setdefault(l["uad"], []).append(l)
        print(f"\nsistema ativo ({len(sistema)}) por classe UAD-ng: " + ", ".join(f"{k}={len(v)}" for k, v in sorted(por.items())))
        for classe in ("Recommended", "Advanced", "Expert"):
            if classe in por:
                print(f"\n  {classe} ainda ativos (nao protegidos):")
                for l in por[classe]:
                    if not l["protegido"]:
                        print(f"    {l['pacote']:<58} uso={l['ultimo_uso'] or '-':<16} {'NET ' if l['internet'] else ''}{l['sensiveis']}")
    if a.ver in (None, "desconhecidos"):
        desc = [l for l in sistema if l["uad"] == "-" and not l["protegido"]]
        print(f"\nsistema ativo FORA da lista UAD-ng e nao protegido ({len(desc)}):")
        for l in desc:
            print(f"    {l['pacote']:<58} {'NET ' if l['internet'] else ''}{l['sensiveis']}")
    if a.ver in (None, "permissoes"):
        sens = [l for l in ativas if l["sensiveis"] and ("loc" in l["sensiveis"] or "mic" in l["sensiveis"] or "cam" in l["sensiveis"]
                                                          or "locBG" in l["sensiveis"] or "contatos" in l["sensiveis"]
                                                          or "sms" in l["sensiveis"] or "ligacoes" in l["sensiveis"])]
        print(f"\nativos com localizacao/camera/microfone/contatos/SMS/ligacoes concedidos ({len(sens)}):")
        for l in sorted(sens, key=lambda x: x["pacote"]):
            print(f"    {l['pacote']:<52} {l['tipo'][:3]} {l['sensiveis']}")


if __name__ == "__main__":
    main()
