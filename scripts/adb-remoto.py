#!/usr/bin/env python3
"""adb do PC com o A12 SEM cabo, pela Tailscale (porta 5555), de qualquer lugar (Wi-Fi ou dados moveis).

  python scripts/adb-remoto.py garantir   cabo ligado? usa o cabo. Sem cabo: conecta <IP do celular na tailnet>:5555
                                          (saida 0 e a 1a linha diz "cabo", "tailscale" ou "tailscale-nova"; 1 = sem conexao)
  python scripts/adb-remoto.py soltar     desconecta SO a conexao da tailnet (o cabo nunca e tocado)
  python scripts/adb-remoto.py status     mostra o que ha

Autorizado pelo Rafael em 05/11 ("esse poder desbloqueado a qualquer lugar do mundo com dados moveis... nao deve depender
de cabo"), com o risco explicado: a porta 5555 do celular (adb tcpip) fica visivel em qualquer rede em que ele estiver;
so entra quem ja tem a chave autorizada (PC e Termux) ou quem ele aceitar no aviso da tela. Ela cai ao reiniciar o celular;
religa: com o cabo (`depuracao-sem-fio.py porta5555`) ou o `cel` do Termux, no Wi-Fi com a Depuracao sem fio.
A ponte do PC usa `garantir` antes de cada acao_pc e `soltar` depois, para nunca ficarem dois aparelhos no adb
(os scripts do projeto chamam `adb` sem -s).
"""
import json
import subprocess
import sys

PORTA = 5555
IP_RESERVA = "100.64.0.2"  # IP do A12 na tailnet em 05/11 (o script prefere o que a Tailscale diz agora)
NOME = "samsung-a12"
_executa = subprocess.run  # os testes trocam por um falso


def roda(cmd, limite=20):
    try:
        p = _executa(cmd, capture_output=True, text=True, timeout=limite)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def ip_celular():
    rc, s = roda(["tailscale", "status", "--json"])
    if rc == 0:
        try:
            for par in (json.loads(s).get("Peer") or {}).values():
                if NOME in (par.get("HostName", "") + par.get("DNSName", "")).lower():
                    ips = [i for i in par.get("TailscaleIPs", []) if i.startswith("100.")]
                    if ips:
                        return ips[0]
        except ValueError:
            pass
    return IP_RESERVA


def aparelhos():
    """{serial: estado} do `adb devices`."""
    _, s = roda(["adb", "devices"])
    r = {}
    for linha in s.splitlines()[1:]:
        partes = linha.split("\t")
        if len(partes) == 2:
            r[partes[0].strip()] = partes[1].strip()
    return r


def garantir():
    lista = aparelhos()
    alvo = "%s:%d" % (ip_celular(), PORTA)
    if any(e == "device" and ":" not in s for s, e in lista.items()):
        if alvo in lista:  # cabo e tailnet juntos: o adb sem -s falharia; fica so o cabo
            roda(["adb", "disconnect", alvo])
        print("cabo")
        return 0
    if lista.get(alvo) == "device":
        print("tailscale")
        return 0
    roda(["adb", "connect", alvo], limite=15)
    if aparelhos().get(alvo) == "device":
        print("tailscale-nova")
        return 0
    roda(["adb", "disconnect", alvo])
    print("sem conexao: nem cabo nem a porta 5555 pela Tailscale (o celular reiniciou? religue com o cabo ou pelo cel no Wi-Fi)")
    return 1


def soltar():
    alvo = "%s:%d" % (ip_celular(), PORTA)
    roda(["adb", "disconnect", alvo])
    print("solto: " + alvo)
    return 0


def status():
    lista = aparelhos()
    alvo = "%s:%d" % (ip_celular(), PORTA)
    cabo = [s for s, e in lista.items() if e == "device" and ":" not in s]
    print("cabo: " + (", ".join(cabo) if cabo else "nao"))
    print("tailnet: " + alvo + " -> " + lista.get(alvo, "nao conectado"))
    return 0


def main(args):
    cmd = args[0] if args else "status"
    if cmd == "garantir":
        return garantir()
    if cmd == "soltar":
        return soltar()
    if cmd == "status":
        return status()
    print(__doc__.strip())
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
