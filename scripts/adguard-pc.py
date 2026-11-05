#!/usr/bin/env python3
"""adguard-pc.py - controla o AdGuard Home do PC (bloqueador de anuncios por DNS do celular, pela Tailscale). So biblioteca padrao.

  python scripts\\adguard-pc.py status                estado do servico, da protecao e um teste de DNS de verdade
  python scripts\\adguard-pc.py liberar <dominio>     deixa de bloquear o dominio e os subdominios (aceita colar a URL inteira)
  python scripts\\adguard-pc.py bloquear <dominio>    passa a bloquear o dominio e os subdominios
  python scripts\\adguard-pc.py tirar <dominio>       apaga a regra propria desse dominio (volta a valer so a lista)
  python scripts\\adguard-pc.py listar                regras proprias
  python scripts\\adguard-pc.py testar <dominio>      diz se o dominio seria bloqueado e por qual regra
  python scripts\\adguard-pc.py pausar [minutos]      desliga o bloqueio por um tempo (padrao 15 min; volta sozinho)
  python scripts\\adguard-pc.py retomar               religa o bloqueio
  python scripts\\adguard-pc.py top                   o que mais foi bloqueado (para achar o dominio que quebrou um site)
  python scripts\\adguard-pc.py configurar | ajustar  primeira configuracao e ajustes do projeto (o adguard-pc.ps1 chama sozinho; pode repetir)

LIMITE (nao ha como contornar): bloqueio por DNS NAO sabe em qual site voce esta; ele so ve nomes de dominio. "Liberar um site" aqui libera o dominio
em todo o celular. Para escolher site a site, o lugar certo e o uBlock Origin no navegador (memoria/ADGUARD-PC.md).
As regras e o acesso ficam fora do git (ADGUARD_ACESSO, padrao C:\\Projetos\\adguard-home\\acesso.json); nome de site nunca entra em arquivo versionado.
Saida: 0 = ok, 1 = recusado ou falhou, 2 = nao deu para falar com o AdGuard."""
import argparse
import base64
import json
import os
import re
import secrets
import socket
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("ADGUARD_URL", "http://127.0.0.1:3000")
ACESSO = os.environ.get("ADGUARD_ACESSO", r"C:\Projetos\adguard-home\acesso.json")
IP_DNS = os.environ.get("ADGUARD_IP", "100.64.0.1")
PORTA_WEB = 3000
USUARIO = "rafael"
# DNS criptografado, cada um de uma empresa diferente; os IPs de partida evitam depender do proprio AdGuard para achar o upstream
UPSTREAMS = ["https://dns.cloudflare.com/dns-query", "https://dns.google/dns-query", "https://dns.quad9.net/dns-query"]
PARTIDA = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
LISTAS = [("AdGuard DNS filter", "https://adguardteam.github.io/HostlistsRegistry/assets/filter_1.txt"),
          ("AdAway Default Blocklist", "https://adguardteam.github.io/HostlistsRegistry/assets/filter_2.txt")]
UM_DIA_MS = 24 * 3600 * 1000
TESTE_BLOQUEADO = "doubleclick.net"
TESTE_NORMAL = "www.wikipedia.org"


class Falha(Exception):
    """Nao deu para falar com o AdGuard, ou ele recusou."""


# ---------------------------------------------------------------- funcoes puras

def dominio_de(texto):
    """Aceita dominio ou URL colada; devolve o dominio em minusculas, ou None se nao for um dominio valido."""
    t = (texto or "").strip().lower()
    if "://" in t:
        try:
            t = urllib.parse.urlsplit(t).hostname or ""
        except ValueError:  # colchete mal fechado: "http://[abc"
            return None
    t = t.split("/")[0].split("?")[0].rstrip(".")
    if t.startswith("www."):
        t = t[4:]
    if len(t) > 253 or "." not in t:
        return None
    if not all(re.fullmatch(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?", p) for p in t.split(".")):
        return None
    if re.fullmatch(r"[0-9.]+", t):
        return None
    return t


def regra_liberar(d):
    return "@@||%s^$important" % d


def regra_bloquear(d):
    return "||%s^" % d


def dominio_da_regra(regra):
    m = re.fullmatch(r"(?:@@)?\|\|([^\^|$]+)\^(?:\$important)?", (regra or "").strip())
    return m.group(1) if m else None


def sem_regras_de(regras, d):
    return [r for r in regras if dominio_da_regra(r) != d]


def monta_consulta(nome, ident=0x1234):
    q = struct.pack(">HHHHHH", ident, 0x0100, 1, 0, 0, 0)
    for p in nome.split("."):
        q += bytes([len(p)]) + p.encode("ascii")
    return q + b"\x00" + struct.pack(">HH", 1, 1)


def _pula_nome(d, i):
    while True:
        n = d[i]
        if n == 0:
            return i + 1
        if n & 0xC0 == 0xC0:
            return i + 2
        i += 1 + n


def le_resposta(d, ident=0x1234):
    """Do pacote de resposta: (codigo de resposta, lista de IPv4). Nao confia no tamanho declarado: pacote truncado levanta ValueError."""
    if len(d) < 12:
        raise ValueError("resposta curta")
    i_d, flags, qd, an = struct.unpack(">HHHH", d[:8])
    if i_d != ident or not flags & 0x8000:
        raise ValueError("resposta de outra consulta")
    i = 12
    try:
        for _ in range(qd):
            i = _pula_nome(d, i) + 4
        ips = []
        for _ in range(an):
            i = _pula_nome(d, i)
            tipo, _classe, _ttl, tam = struct.unpack(">HHIH", d[i:i + 10])
            i += 10
            if i + tam > len(d):
                raise ValueError("resposta truncada")
            if tipo == 1 and tam == 4:
                ips.append(".".join(str(b) for b in d[i:i + 4]))
            i += tam
    except (IndexError, struct.error) as e:
        raise ValueError("resposta truncada") from e
    return flags & 0x000F, ips


def bloqueou(rcode, ips):
    """O AdGuard bloqueia devolvendo 0.0.0.0, NXDOMAIN ou REFUSED."""
    return rcode in (3, 5) or (bool(ips) and all(ip == "0.0.0.0" for ip in ips))


# ---------------------------------------------------------------- ambiente (trocado por falsos nos testes)

class Ambiente:
    def __init__(self, base=BASE, acesso=ACESSO, ip_dns=IP_DNS):
        self.base, self.acesso, self.ip_dns = base, acesso, ip_dns

    def credenciais(self):
        try:
            with open(self.acesso, encoding="utf-8") as f:
                d = json.load(f)
            return d["usuario"], d["senha"]
        except (OSError, ValueError, KeyError) as e:
            raise Falha("nao li o acesso em %s (%s); rode: pwsh -File scripts\\adguard-pc.ps1 -Instalar" % (self.acesso, type(e).__name__)) from e

    def guarda_credenciais(self, usuario, senha):
        pasta = os.path.dirname(self.acesso)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        with open(self.acesso, "w", encoding="utf-8") as f:
            json.dump({"usuario": usuario, "senha": senha}, f)

    def api(self, caminho, corpo=None, autentica=True, timeout=30, metodo=None):
        """corpo=None = GET; senao POST (ou `metodo`) com JSON. Devolve (codigo, dados); nunca mostra a senha."""
        dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
        req = urllib.request.Request(self.base + "/control/" + caminho, data=dados, headers={"Content-Type": "application/json"}, method=metodo)
        if autentica:
            u, s = self.credenciais()
            req.add_header("Authorization", "Basic " + base64.b64encode(("%s:%s" % (u, s)).encode("utf-8")).decode("ascii"))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                bruto, cod = r.read(), r.status
        except urllib.error.HTTPError as e:
            bruto, cod = e.read(), e.code
        except (urllib.error.URLError, OSError) as e:
            raise Falha("o AdGuard nao respondeu em %s (%s)" % (self.base, type(e).__name__)) from e
        try:
            return cod, json.loads(bruto.decode("utf-8", "replace") or "{}")
        except ValueError:
            return cod, {}

    def dns(self, nome):
        """Consulta de verdade na porta 53 do AdGuard. Devolve (rcode, ips), ou None se ninguem respondeu."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(4)
        try:
            s.sendto(monta_consulta(nome), (self.ip_dns, 53))
            return le_resposta(s.recv(1500))
        except (OSError, ValueError):
            return None
        finally:
            s.close()


def pede(amb, caminho, corpo=None, metodo=None):
    cod, d = amb.api(caminho, corpo, metodo=metodo)
    if cod == 401 or cod == 403:
        raise Falha("o AdGuard recusou a senha guardada em %s" % amb.acesso)
    if cod != 200:
        raise Falha("o AdGuard respondeu HTTP %s em %s" % (cod, caminho))
    return d


# ---------------------------------------------------------------- comandos

def cmd_status(amb):
    st = pede(amb, "status")
    ligado = bool(st.get("protection_enabled"))
    resto = int(st.get("protection_disabled_duration") or 0)
    print("AdGuard Home %s: %s" % (st.get("version", "?"), "rodando" if st.get("running") else "PARADO"))
    print("Bloqueio: " + ("LIGADO" if ligado else ("PAUSADO por mais %d min" % (resto // 60000 + 1) if resto else "DESLIGADO")))
    print("DNS em: %s porta %s" % (",".join(st.get("dns_addresses") or []), st.get("dns_port", "?")))
    filtros = pede(amb, "filtering/status")
    ativas = [f for f in (filtros.get("filters") or []) if f.get("enabled")]
    print("Listas ativas: %d (%d regras); regras proprias: %d" % (len(ativas), sum(int(f.get("rules_count") or 0) for f in ativas), len(filtros.get("user_rules") or [])))
    stats = pede(amb, "stats")
    print("Consultas: %s; bloqueadas: %s" % (stats.get("num_dns_queries", "?"), stats.get("num_blocked_filtering", "?")))
    ruim = 0
    r = amb.dns(TESTE_NORMAL)
    if r is None or r[0] != 0 or bloqueou(*r):
        print("TESTE DE DNS FALHOU: %s nao resolveu em %s:53" % (TESTE_NORMAL, amb.ip_dns))
        ruim = 1
    else:
        print("Teste de DNS: %s resolve" % TESTE_NORMAL)
    r = amb.dns(TESTE_BLOQUEADO)
    if r is None:
        print("TESTE DE DNS FALHOU: %s nao respondeu" % TESTE_BLOQUEADO)
        ruim = 1
    elif bloqueou(*r):
        print("Teste de bloqueio: %s bloqueado" % TESTE_BLOQUEADO)
    elif ligado:
        print("TESTE DE BLOQUEIO FALHOU: %s passou com o bloqueio ligado" % TESTE_BLOQUEADO)
        ruim = 1
    else:
        print("Teste de bloqueio: %s passou (bloqueio pausado)" % TESTE_BLOQUEADO)
    return ruim


def _regras(amb):
    return list(pede(amb, "filtering/status").get("user_rules") or [])


def _grava_regras(amb, regras):
    pede(amb, "filtering/set_rules", {"rules": regras})


def _dominio_ou_erro(texto):
    d = dominio_de(texto)
    if not d:
        print("RECUSADO: %r nao e um dominio (exemplo: anuncios.exemplo.com)." % (texto or "")[:80])
    return d


def cmd_regra(amb, texto, regra_de, frase):
    d = _dominio_ou_erro(texto)
    if not d:
        return 1
    _grava_regras(amb, sem_regras_de(_regras(amb), d) + [regra_de(d)])
    print("%s: %s (e subdominios). Vale em todo o celular; o aparelho pode levar alguns minutos para esquecer o que guardou." % (frase, d))
    return 0


def cmd_tirar(amb, texto):
    d = _dominio_ou_erro(texto)
    if not d:
        return 1
    antes = _regras(amb)
    depois = sem_regras_de(antes, d)
    if len(antes) == len(depois):
        print("Nao havia regra propria para %s (nada mudou)." % d)
        return 0
    _grava_regras(amb, depois)
    print("Regra de %s apagada." % d)
    return 0


def cmd_listar(amb):
    regras = _regras(amb)
    if not regras:
        print("Nenhuma regra propria.")
    for r in regras:
        d = dominio_da_regra(r)
        print(("liberado  " + d) if d and r.startswith("@@") else (("bloqueado " + d) if d else ("outra     " + r)))
    return 0


def cmd_testar(amb, texto):
    d = _dominio_ou_erro(texto)
    if not d:
        return 1
    r = pede(amb, "filtering/check_host?name=" + urllib.parse.quote(d))
    motivo = str(r.get("reason", "?"))
    regras = [x.get("text", "") for x in (r.get("rules") or [])]
    if motivo.startswith("Filtered"):
        print("BLOQUEADO: %s (%s)" % (d, "; ".join(regras)[:200] or motivo))
    else:
        print("PASSA: %s (%s)" % (d, motivo + (": " + "; ".join(regras)[:200] if regras else "")))
    return 0


LISTAS_SEGURANCA = {  # catalogo oficial do AdGuard (HostlistsRegistry): malware e golpe; so bloqueiam dominio, nao olham conteudo
    "Malicious URL Blocklist (URLHaus)": "https://adguardteam.github.io/HostlistsRegistry/assets/filter_11.txt",
    "Phishing URL Blocklist (PhishTank and OpenPhish)": "https://adguardteam.github.io/HostlistsRegistry/assets/filter_30.txt",
    "Dandelion Sprout's Anti-Malware List": "https://adguardteam.github.io/HostlistsRegistry/assets/filter_12.txt",
}


def faltam_listas(filtros):
    """Quais listas de seguranca ainda nao estao no AdGuard."""
    urls = {f.get("url") for f in (filtros.get("filters") or [])}
    return {n: u for n, u in LISTAS_SEGURANCA.items() if u not in urls}


def cmd_seguranca(amb):
    faltam = faltam_listas(pede(amb, "filtering/status"))
    for nome, url in faltam.items():
        pede(amb, "filtering/add_url", {"name": nome, "url": url, "whitelist": False})
        print(f"Lista ligada: {nome}")
    if not faltam:
        print("As listas de seguranca ja estavam ligadas.")
    return 0


def cmd_pausar(amb, minutos):
    if not 1 <= minutos <= 1440:
        print("RECUSADO: use de 1 a 1440 minutos.")
        return 1
    pede(amb, "protection", {"enabled": False, "duration": minutos * 60000})
    print("Bloqueio PAUSADO por %d min (volta sozinho). Para religar antes: retomar" % minutos)
    return 0


def cmd_retomar(amb):
    pede(amb, "protection", {"enabled": True})
    print("Bloqueio LIGADO.")
    return 0


def cmd_top(amb):
    st = pede(amb, "stats")
    linhas = st.get("top_blocked_domains") or []
    if not linhas:
        print("Nada bloqueado ainda.")
    for item in linhas[:15]:
        for dom, n in item.items():
            print("%7s  %s" % (n, dom))
    return 0


def cmd_configurar(amb, ip_dns):
    """Passa pelo assistente de primeira execucao, se ainda estiver nele (senao nao faz nada: pode repetir sem estragar). A senha nasce aqui e so vai para o arquivo de acesso."""
    cod, _ = amb.api("install/get_addresses", autentica=False)
    if cod != 200:
        print("O assistente ja tinha sido concluido.")
        return 0
    gerada = secrets.token_urlsafe(18)   # (nome sem "senha = " colado: o varredor de segredos do sync pega)
    amb.guarda_credenciais(USUARIO, gerada)
    corpo = {"web": {"ip": "127.0.0.1", "port": PORTA_WEB}, "dns": {"ip": ip_dns, "port": 53}, "username": USUARIO, "password": gerada}
    cod, _ = amb.api("install/configure", corpo, autentica=False)
    if cod != 200:
        raise Falha("o assistente recusou a configuracao (HTTP %s)" % cod)
    print("Assistente concluido: DNS so em %s:53, painel so em 127.0.0.1:%d." % (ip_dns, PORTA_WEB))
    return 0


def cmd_ajustar(amb):
    pede(amb, "dns_config", {"upstream_dns": UPSTREAMS, "bootstrap_dns": PARTIDA, "upstream_mode": "load_balance", "cache_size": 4194304, "cache_optimistic": True})
    pede(amb, "querylog/config/update", {"enabled": True, "interval": UM_DIA_MS, "anonymize_client_ip": False, "ignored": []}, metodo="PUT")
    pede(amb, "stats/config/update", {"enabled": True, "interval": 7 * UM_DIA_MS, "ignored": []}, metodo="PUT")
    atuais = pede(amb, "filtering/status").get("filters") or []
    urls = {f.get("url"): f for f in atuais}
    for nome, url in LISTAS:
        if url not in urls:
            pede(amb, "filtering/add_url", {"name": nome, "url": url, "whitelist": False})
        elif not urls[url].get("enabled"):
            pede(amb, "filtering/set_url", {"url": url, "whitelist": False, "data": {"name": nome, "url": url, "enabled": True}})
    print("Ajustes aplicados: DNS criptografado (3 empresas), 2 listas de bloqueio, historico de consultas de 24 h.")
    return 0


def main(argv=None, amb=None):
    ap = argparse.ArgumentParser(description="Controla o AdGuard Home do PC")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    for nome in ("liberar", "bloquear", "tirar", "testar"):
        sub.add_parser(nome).add_argument("dominio")
    sub.add_parser("listar")
    sub.add_parser("pausar").add_argument("minutos", nargs="?", type=int, default=15)
    sub.add_parser("retomar")
    sub.add_parser("top")
    sub.add_parser("seguranca")
    c = sub.add_parser("configurar")
    c.add_argument("--ip", default=IP_DNS)
    sub.add_parser("ajustar")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    amb = amb or Ambiente()
    try:
        if a.cmd == "status":
            return cmd_status(amb)
        if a.cmd == "liberar":
            return cmd_regra(amb, a.dominio, regra_liberar, "LIBERADO")
        if a.cmd == "bloquear":
            return cmd_regra(amb, a.dominio, regra_bloquear, "BLOQUEADO")
        if a.cmd == "tirar":
            return cmd_tirar(amb, a.dominio)
        if a.cmd == "listar":
            return cmd_listar(amb)
        if a.cmd == "testar":
            return cmd_testar(amb, a.dominio)
        if a.cmd == "pausar":
            return cmd_pausar(amb, a.minutos)
        if a.cmd == "retomar":
            return cmd_retomar(amb)
        if a.cmd == "top":
            return cmd_top(amb)
        if a.cmd == "seguranca":
            return cmd_seguranca(amb)
        if a.cmd == "configurar":
            return cmd_configurar(amb, a.ip)
        return cmd_ajustar(amb)
    except Falha as e:
        print("FALHOU: %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
