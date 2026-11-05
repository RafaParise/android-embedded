#!/usr/bin/env python3
"""vpn-celular.py - VPN sempre ativa e SAIDA DE INTERNET PELO PC (Tailscale) no Galaxy A12.

  python scripts\\vpn-celular.py status
  python scripts\\vpn-celular.py saida ligar    [--aplicar] [--sem-lan]
  python scripts\\vpn-celular.py saida desligar [--aplicar]

Padrao = SIMULACAO (so le e mostra o que faria); --aplicar executa. Regras (01/11/2026, memoria/VPN-SEMPRE-ATIVA.md):
- "saida ligar" so roda se o PC anuncia a saida E o painel da Tailscale a aprovou E o PC e o celular estao online E a VPN do celular esta
  conectada. Sem isso o celular ficaria SEM INTERNET (a Tailscale nao volta sozinha para a rede normal quando a saida some).
- Depois de ligar, confere em ate 45 s se a internet entrou no tunel e se o Android validou a internet pela VPN; se nao, DESFAZ sozinho.
  Com "acesso a rede local" ligado (o padrao) o app NAO usa 0.0.0.0/0: divide em ~130 rotas deixando a rede local de fora (medido em 02/11),
  por isso a conferencia soma o espaco de enderecos que passa pelo tunel.
- Este comando NAO liga o guarda. Para o dia a dia use `saida ligar` no Termux (celular-kit/bin/saida): se o PC some, o guarda devolve a internet sozinho.
- Nao mexe em "VPN sempre ativada" (isso e da tela de VPN do Android) nem em "Bloquear conexoes sem VPN" (fica desligado de proposito:
  o login do Wi-Fi da escola precisa da rede sem VPN).
- Nada de chave, conta ou token: so le o estado e manda a intencao USE_EXIT_NODE ao app (acao com.tailscale.ipn.USE_EXIT_NODE,
  extras exitNode = nome do PC na Tailscale e allowLanAccess; exitNode vazio = sem saida).
Saida: 0 = ok, 1 = recusado ou desfeito, 2 = nao deu para ler/falha de ambiente."""
import argparse
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import time

PACOTE = "com.tailscale.ipn"
RECEPTOR = "com.tailscale.ipn/.IPNReceiver"
ACAO_SAIDA = "com.tailscale.ipn.USE_EXIT_NODE"
MODELO = "SM-A125"
TS_PADRAO = r"C:\Program Files\Tailscale\tailscale.exe"
ESPERA_S = 45
TERMUX_PS1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "termux.ps1")


# ---------------------------------------------------------------- leitura (funcoes puras, testadas com textos de exemplo)

def rota_de_saida(rotas):
    """A internet passa pelo tunel? Sim se as rotas IPv4 do tunel cobrem ao menos metade do espaco de enderecos (0.0.0.0/0 ou a divisao que deixa a rede local de fora)."""
    redes = []
    for m in re.finditer(r"([0-9.]+/\d+) -> \S+ (tun\d+)", rotas or ""):
        try:
            redes.append(ipaddress.ip_network(m.group(1), strict=False))
        except ValueError:
            continue
    return sum(n.num_addresses for n in ipaddress.collapse_addresses(redes)) >= 2 ** 31


def le_vpn(dump):
    """Estado da VPN a partir de `dumpsys connectivity`: conectada, validada pelo Android, saida de internet em uso, rede de base."""
    r = {"conectada": False, "validada": False, "saida_ativa": False, "base": "?"}
    linha = next((l for l in dump.splitlines() if "ni{VPN CONNECTED" in l), "")
    if not linha:
        return r
    r["conectada"] = True
    caps = re.search(r"Capabilities: ([A-Z_&]+)", linha)
    r["validada"] = bool(caps) and "VALIDATED" in caps.group(1).split("&")
    rotas = re.search(r"Routes: \[([^\]]*)\]", linha)
    r["saida_ativa"] = bool(rotas) and rota_de_saida(rotas.group(1))
    base = re.search(r"underlying\{\[(\d+)", linha)
    if base:
        outra = next((l for l in dump.splitlines() if f"NetworkAgentInfo{{network{{{base.group(1)}}}" in l), "")
        t = re.search(r"Transports: ([A-Z|]+)", outra)
        r["base"] = t.group(1) if t else "?"
    return r


def le_sempre_ativa(app, bloqueio):
    return {"app": app.strip(), "sempre_ativa": app.strip() == PACOTE, "bloqueio": bloqueio.strip() == "1"}


def le_pc(prefs_json, status_json):
    """O PC anuncia a saida? O painel aprovou? Qual o nome? Quem e o celular (peer android) e esta online?"""
    r = {"anuncia": False, "aprovado": False, "online": False, "nome": "", "sem_usuario": False, "celular_online": False, "celular_nome": ""}
    try:
        p = json.loads(prefs_json or "{}")
        s = json.loads(status_json or "{}")
    except ValueError:
        return r
    rotas = p.get("AdvertiseRoutes") or []
    r["anuncia"] = "0.0.0.0/0" in rotas and "::/0" in rotas
    r["sem_usuario"] = bool(p.get("ForceDaemon"))
    eu = s.get("Self") or {}
    # o nome que o app da Tailscale mostra e o do DNS (rafaparise), nao o HostName do Windows (RafaParise)
    r["nome"] = str(eu.get("DNSName") or "").split(".")[0] or eu.get("HostName", "")
    r["online"] = bool(eu.get("Online"))
    r["aprovado"] = bool(eu.get("ExitNodeOption")) or "0.0.0.0/0" in (eu.get("AllowedIPs") or [])
    for peer in (s.get("Peer") or {}).values():
        if str(peer.get("OS", "")).lower() == "android":
            r["celular_online"] = bool(peer.get("Online"))
            r["celular_nome"] = peer.get("HostName", "")
    return r


def veredito(pc, vpn, aa):
    """Lista de (marca, texto) e o proximo passo."""
    m = []
    m.append(("ok" if pc["anuncia"] else "FALTA", "PC anuncia a saida de internet (0.0.0.0/0 e ::/0)"))
    m.append(("ok" if pc["aprovado"] else "FALTA", "painel da Tailscale APROVOU o PC como saida (login.tailscale.com/admin/machines > ... > Edit route settings > Use as exit node)"))
    m.append(("ok" if pc["sem_usuario"] else "aviso", "Tailscale do PC em modo sem usuario (segue de pe com o Windows bloqueado ou sem sessao)"))
    m.append(("ok" if pc["online"] else "FALTA", "PC online na Tailscale"))
    m.append(("ok" if pc["celular_online"] else "FALTA", "celular online na Tailscale"))
    m.append(("ok" if vpn["conectada"] else "FALTA", "VPN conectada no celular (base: %s)" % vpn["base"]))
    m.append(("ok" if aa["sempre_ativa"] else "FALTA", "VPN sempre ativada no celular (Configuracoes > Conexoes > Mais configuracoes > VPN > engrenagem do Tailscale)"))
    m.append(("ok" if not aa["bloqueio"] else "aviso", "Bloquear conexoes sem VPN DESLIGADO (ligado atrapalha o login do Wi-Fi da escola e o religamento depois do boot)"))
    m.append(("em uso" if vpn["saida_ativa"] else "desligada", "saida de internet pelo PC (internet passando pelo tunel)" + ("; validada pelo Android" if vpn["saida_ativa"] and vpn["validada"] else "")))
    if not pc["anuncia"]:
        passo = "No PC: tailscale set --advertise-exit-node"
    elif not pc["aprovado"]:
        passo = "Aprovar o PC como saida no painel da Tailscale (um clique do dono da conta)"
    elif not (pc["online"] and pc["celular_online"] and vpn["conectada"]):
        passo = "Conectar a Tailscale no celular e no PC antes de ligar a saida"
    elif not vpn["saida_ativa"]:
        passo = "Tudo pronto: no Termux, saida ligar (liga com o guarda)"
    else:
        passo = "Saida em uso. Sem o guarda de pe, se a internet sumir (PC desligado ou rede que bloqueia a Tailscale): no Termux, saida desligar; ou no app Tailscale > Exit node > None"
    return m, passo


# ---------------------------------------------------------------- ambiente (trocado por falsos nos testes)

class Ambiente:
    def adb(self, comando, timeout=40):
        r = subprocess.run(["adb", "shell", comando], capture_output=True, timeout=timeout)
        if r.returncode != 0:  # sem aparelho, offline ou nao autorizado: nunca tratar a leitura vazia como estado do celular
            raise RuntimeError("adb falhou (codigo %s): %s" % (r.returncode, r.stderr.decode("utf-8", "replace").strip()[:100]))
        return r.stdout.decode("utf-8", "replace")

    def ts(self, *args, timeout=40):
        exe = TS_PADRAO if os.path.exists(TS_PADRAO) else (shutil.which("tailscale") or "tailscale")
        r = subprocess.run([exe, *args], capture_output=True, timeout=timeout)
        if r.returncode != 0:  # servico parado: nao e "o PC nao anuncia a saida"
            raise RuntimeError("tailscale falhou (codigo %s): %s" % (r.returncode, r.stderr.decode("utf-8", "replace").strip()[:100]))
        return r.stdout.decode("utf-8", "replace")

    def guarda(self):
        """O que o guarda do Termux diz (vazio se nao deu para falar com o Termux). Le pelo cabo; nunca muda nada."""
        pwsh = shutil.which("pwsh")
        if not pwsh or not os.path.exists(TERMUX_PS1):
            return ""
        r = subprocess.run([pwsh, "-NoProfile", "-File", TERMUX_PS1, "-Comando", "~/bin/saida status"], capture_output=True, timeout=60)
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""

    def dorme(self, s):
        time.sleep(s)


class SemLeitura(Exception):
    """Nao deu para ler o celular (sem aparelho no ADB, cabo caiu, dump vazio): o estado e DESCONHECIDO, nunca "desligado"."""


def confere_modelo(amb):
    modelo = amb.adb("getprop ro.product.model").strip()
    if not modelo:
        raise SemLeitura("nenhum aparelho respondeu no ADB (cabo, depuracao USB ou autorizacao)")
    if MODELO not in modelo:
        raise SystemExit("ABORTADO: o aparelho no ADB nao e o SM-A125M (%r)" % modelo[:30])


def le_vpn_vivo(amb):
    dump = amb.adb("dumpsys connectivity")
    if not dump.strip():
        raise SemLeitura("o celular nao devolveu o estado da rede (dumpsys vazio)")
    return le_vpn(dump)


def coleta(amb):
    confere_modelo(amb)
    vpn = le_vpn_vivo(amb)
    aa = le_sempre_ativa(amb.adb("settings get secure always_on_vpn_app"), amb.adb("settings get secure always_on_vpn_lockdown"))
    pc = le_pc(amb.ts("debug", "prefs"), amb.ts("status", "--json"))
    return pc, vpn, aa


def manda_saida(amb, nome, lan):
    # as aspas simples ficam por conta do shell do aparelho (extra vazio = sem saida)
    arg = "--es exitNode '%s' --ez allowLanAccess %s" % (nome, "true" if lan else "false")
    return "Broadcast completed" in amb.adb("am broadcast -n %s -a %s %s" % (RECEPTOR, ACAO_SAIDA, arg))


def espera(amb, cond, segundos=ESPERA_S):
    t0 = 0
    while t0 <= segundos:
        vpn = le_vpn_vivo(amb)
        if cond(vpn):
            return vpn
        amb.dorme(3)
        t0 += 3
    return le_vpn_vivo(amb)


# ---------------------------------------------------------------- comandos

def cmd_status(amb):
    pc, vpn, aa = coleta(amb)
    m, passo = veredito(pc, vpn, aa)
    for marca, texto in m:
        print("[%-9s] %s" % (marca, texto))
    try:
        g = amb.guarda()
    except Exception:  # noqa: BLE001 - o guarda e informacao extra: sem Termux o status segue valendo
        g = ""
    if "Guarda: rodando" in g:
        print("[ok       ] guarda do Termux rodando" + (" (saida SUSPENSA: o PC sumiu e a internet esta saindo direto)" if "SUSPENSA" in g else ""))
    elif vpn["saida_ativa"]:
        print("[aviso    ] guarda do Termux " + ("PARADO" if g else "nao conferido (Termux fora do alcance)") + ": sem ele, PC desligado = celular sem internet. No Termux: "
              + ("saida guarda" if "Guarda: PARADO" in g else "saida ligar"))
    print("proximo passo: " + passo)
    return 0


def cmd_ligar(amb, aplicar, lan):
    pc, vpn, _ = coleta(amb)
    faltas = []
    if not pc["anuncia"]:
        faltas.append("o PC nao anuncia a saida (tailscale set --advertise-exit-node)")
    if not pc["aprovado"]:
        faltas.append("o painel da Tailscale ainda nao aprovou o PC como saida")
    if not pc["online"] or not pc["nome"]:
        faltas.append("o PC nao esta online na Tailscale")
    if not pc["celular_online"]:
        faltas.append("o celular nao esta online na Tailscale")
    if not vpn["conectada"]:
        faltas.append("a VPN do celular nao esta conectada")
    if faltas:
        print("RECUSADO (o celular ficaria sem internet): " + "; ".join(faltas))
        return 1
    if vpn["saida_ativa"]:
        print("A saida pelo PC ja esta em uso (nada a fazer).")
        return 0
    if not aplicar:
        print("SIMULACAO: mandaria ao app a saida '%s' (acesso a rede local %s) e conferiria em ate %d s; desfaz sozinho se a internet nao passar." % (pc["nome"], "ligado" if lan else "desligado", ESPERA_S))
        return 0
    print("Ligando a saida pelo PC (%s)..." % pc["nome"])
    try:
        if not manda_saida(amb, pc["nome"], lan):
            print("FALHOU: o app da Tailscale nao aceitou o pedido. Nada foi mudado.")
            return 1
        r = espera(amb, lambda v: v["saida_ativa"] and v["validada"])
    except Exception as e:  # noqa: BLE001 - cabo caiu ou adb travou: a saida pode ter ficado ligada
        print("ESTADO DESCONHECIDO (%s: %s). Tentando desfazer; confira no app Tailscale > Exit node > None." % (type(e).__name__, str(e)[:100]))
        try:
            manda_saida(amb, "", lan)
        except Exception:  # noqa: BLE001 - sem cabo nao ha o que fazer daqui
            pass
        return 2
    if r["saida_ativa"] and r["validada"]:
        print("OK: saida pelo PC em uso e validada pelo Android (rede de base: %s)." % r["base"])
        print("ATENCAO: por aqui o guarda NAO fica vigiando. Para ele devolver a internet quando o PC sumir, no Termux: saida ligar")
        return 0
    motivo = "a internet nao entrou no tunel (o app recusou? veja a notificacao do Tailscale)" if not r["saida_ativa"] else "o Android nao validou a internet pela saida"
    print("FALHOU: %s. DESFAZENDO para o celular nao ficar sem internet..." % motivo)
    try:
        if not manda_saida(amb, "", lan):
            raise SemLeitura("o app nao aceitou o pedido de desfazer")
        r2 = espera(amb, lambda v: not v["saida_ativa"], 30)
    except Exception as e:  # noqa: BLE001
        print("NAO CONFIRMEI o desfazer (%s: %s): a saida pode estar ligada. Abra o app Tailscale > Exit node > None." % (type(e).__name__, str(e)[:100]))
        return 2
    print("Desfeito: saida %s." % ("desligada" if not r2["saida_ativa"] else "AINDA LIGADA: abra o app Tailscale > Exit node > None"))
    return 1


def cmd_desligar(amb, aplicar):
    confere_modelo(amb)
    vpn = le_vpn_vivo(amb)
    if not vpn["conectada"] or not vpn["saida_ativa"]:
        try:
            g = amb.guarda()
        except Exception:  # noqa: BLE001 - sem Termux so nao da para conferir o guarda
            g = ""
        if "SUSPENSA" in g:
            print("A saida esta SUSPENSA pelo guarda do Termux, que a RELIGA quando o PC voltar. Para parar de vez, no Termux: saida desligar")
            return 1
        print("A saida pelo PC ja esta desligada (nada a fazer).")
        return 0
    if not aplicar:
        print("SIMULACAO: mandaria ao app 'sem saida' e conferiria que a internet saiu do tunel.")
        return 0
    try:
        if not manda_saida(amb, "", True):
            raise SemLeitura("o app nao aceitou o pedido")
        r = espera(amb, lambda v: not v["saida_ativa"], 30)
    except Exception as e:  # noqa: BLE001 - cabo caiu: nao afirmar que desligou
        print("ESTADO DESCONHECIDO (%s: %s). Confira no app Tailscale > Exit node > None." % (type(e).__name__, str(e)[:100]))
        return 2
    if r["saida_ativa"]:
        print("A internet AINDA esta no tunel: abra o app Tailscale > Exit node > None.")
        return 1
    print("OK: saida pelo PC desligada (a VPN segue conectada). Se o guarda estava de pe, pare-o tambem: no Termux, saida desligar")
    return 0


def main(argv=None, amb=None):
    ap = argparse.ArgumentParser(description="VPN sempre ativa e saida de internet pelo PC (Tailscale) no A12")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    s = sub.add_parser("saida")
    s.add_argument("acao", choices=["ligar", "desligar"])
    s.add_argument("--aplicar", action="store_true")
    s.add_argument("--sem-lan", action="store_true", help="nao deixar a rede local (impressora, roteador) fora do tunel")
    a = ap.parse_args(argv)
    amb = amb or Ambiente()
    try:
        if a.cmd == "status":
            return cmd_status(amb)
        if a.acao == "ligar":
            return cmd_ligar(amb, a.aplicar, not a.sem_lan)
        return cmd_desligar(amb, a.aplicar)
    except SystemExit:
        raise
    except SemLeitura as e:
        print("ABORTADO: %s" % e)
        return 2
    except Exception as e:  # leitura falhou (adb ausente, tailscale ausente...)
        print("ABORTADO: %s: %s" % (type(e).__name__, str(e)[:120]))
        return 2


if __name__ == "__main__":
    sys.exit(main())
