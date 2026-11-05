#!/usr/bin/env python3
"""navegador-a12.py - navegador de TESTE no proprio celular: comanda o Fennec do A12 pelo cabo (Marionette, o protocolo de depuracao do Firefox). So biblioteca padrao.

  python scripts\\navegador-a12.py abrir <url> [--foto arq.png] [--texto arq.txt]   abre a pagina no Fennec, mostra titulo, endereco final e quanto carregou
  python scripts\\navegador-a12.py status                                            versao, DNS seguro e extensoes (com o estado do uBlock Origin)
  python scripts\\navegador-a12.py dns-seguro [ligar|desligar]                       DNS proprio do navegador (DoH), independente do AdGuard do PC
  python scripts\\navegador-a12.py ublock [ligar|desligar]                           liga ou desliga o uBlock Origin inteiro (site a site e o botao dele no navegador)
  python scripts\\navegador-a12.py limpar                                            apaga a depuracao, se uma execucao anterior tiver sido interrompida

Como funciona e por que e seguro: a depuracao liga SO durante o comando e e desligada no fim, mesmo com erro (arquivo de configuracao apagado, debug-app limpo, porta do
adb fechada), e o script CONFERE no aparelho que limpou; se nao conseguir (cabo solto), avisa e sai com erro. Enquanto ela esta ligada, qualquer app do celular poderia comandar o navegador pela porta 2828.
Ocupa a tela durante o comando e no fim fecha o Fennec e volta a tela inicial (na proxima vez ele abre normal e as abas voltam). Recusa se o Fennec estiver em primeiro plano, para nao
interromper quem o estiver usando (--forcar passa por cima, antes ou depois do subcomando).
Saida: 0 = ok, 1 = recusado ou falhou, 2 = nao deu para falar com o celular."""
import argparse
import base64
import json
import re
import socket
import subprocess
import sys
import time

PACOTE = "org.mozilla.fennec_fdroid"
ATIVIDADE = PACOTE + "/org.mozilla.fenix.HomeActivity"
CONFIG = "/data/local/tmp/%s-geckoview-config.yaml" % PACOTE
PORTA = 2828
MODELO = "SM-A125"
UBLOCK = "uBlock0@raymondhill.net"
# DoH "aumentado" (2): usa o DNS proprio e cai no do sistema se ele falhar (o login do Wi-Fi da escola segue funcionando). 3 seria sem esse recurso.
TRR_MODO = 2
TRR_URI = "https://mozilla.cloudflare-dns.com/dns-query"
LE_ESTADO = """
const cb = arguments[arguments.length - 1];
const { AddonManager } = ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
AddonManager.getAddonsByTypes(['extension']).then(l => cb({
  trr_modo: Services.prefs.getIntPref('network.trr.mode', -1),
  trr_uri: Services.prefs.getStringPref('network.trr.uri', ''),
  extensoes: l.filter(a => !a.isBuiltin && !a.isSystem).map(a => ({id: a.id, nome: a.name, versao: a.version, ativa: a.isActive, desligada_pelo_usuario: a.userDisabled}))
})).catch(e => cb({erro: String(e)}));
"""
GRAVA_DNS = """
Services.prefs.setIntPref('network.trr.mode', arguments[0]);
Services.prefs.setStringPref('network.trr.uri', arguments[1]);
Services.prefs.savePrefFile(null);
return true;
"""
MUDA_ADDON = """
const cb = arguments[arguments.length - 1];
const { AddonManager } = ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
AddonManager.getAddonByID(arguments[0]).then(async a => {
  if (!a) { cb({erro: 'nao instalada'}); return; }
  if (arguments[1]) { await a.enable(); } else { await a.disable(); }
  cb({ativa: a.isActive});
}).catch(e => cb({erro: String(e)}));
"""
TEMPOS_DA_PAGINA = "return window.performance.getEntriesByType('navigation').map(n => ({tempo_ms: Math.round(n.duration), tamanho: n.transferSize}))[0] || {};"


class Falha(Exception):
    pass


# ---------------------------------------------------------------- funcoes puras

def yaml_de_depuracao():
    return "args:\n  - -marionette\nenv:\n  MOZ_REMOTE_ALLOW_SYSTEM_ACCESS: 1\n"


def url_valida(u):
    """So http/https; nada de file:, about:, chrome: (dariam acesso ao aparelho) nem caractere que quebraria o comando."""
    u = (u or "").strip()
    return bool(re.fullmatch(r"https?://[^\s'\"`$\\<>]+", u, re.I))


def valor(r):
    return r["value"] if isinstance(r, dict) and "value" in r else r


def quadro(payload):
    return str(len(payload)).encode("ascii") + b":" + payload


class Marionette:
    """Protocolo: cada mensagem e `tamanho:json`; comando = [0, id, nome, params]; resposta = [1, id, erro, resultado]."""

    def __init__(self, conexao):
        self.s = conexao
        self.i = 0
        self.ola = self._le()

    def _le(self):
        cab = b""
        while not cab.endswith(b":"):
            c = self.s.recv(1)
            if not c or len(cab) > 12:
                raise Falha("a depuracao fechou a conexao")
            cab += c
        n = int(cab[:-1])
        d = b""
        while len(d) < n:
            c = self.s.recv(n - len(d))
            if not c:
                raise Falha("a depuracao fechou a conexao")
            d += c
        return json.loads(d.decode("utf-8"))

    def cmd(self, nome, params=None):
        self.i += 1
        self.s.sendall(quadro(json.dumps([0, self.i, nome, params or {}]).encode("utf-8")))
        while True:
            r = self._le()
            if isinstance(r, list) and len(r) == 4 and r[0] == 1 and r[1] == self.i:
                if r[2]:
                    erro = r[2].get("message", r[2]) if isinstance(r[2], dict) else r[2]
                    raise Falha("o navegador recusou %s: %s" % (nome, str(erro)[:200]))
                return r[3]

    def sistema(self, script, args=None, assincrono=False):
        """Roda no contexto de sistema e volta ao de pagina."""
        self.cmd("Marionette:SetContext", {"value": "chrome"})
        try:
            nome = "WebDriver:ExecuteAsyncScript" if assincrono else "WebDriver:ExecuteScript"
            return valor(self.cmd(nome, {"script": script, "args": args or [], "sandbox": "system"}))
        finally:
            self.cmd("Marionette:SetContext", {"value": "content"})


# ---------------------------------------------------------------- ambiente (trocado por falsos nos testes)

class Ambiente:
    def adb(self, *args, timeout=40):
        r = subprocess.run(["adb", *args], capture_output=True, timeout=timeout)
        return (r.stdout + r.stderr).decode("utf-8", "replace").strip()

    def conecta(self):
        s = socket.create_connection(("127.0.0.1", PORTA), timeout=10)
        s.settimeout(90)
        try:
            return Marionette(s)
        except BaseException:
            s.close()
            raise

    def dorme(self, s):
        time.sleep(s)

    def grava(self, caminho, dados):
        with open(caminho, "wb") as f:
            f.write(dados)


def confere_aparelho(amb):
    m = amb.adb("shell", "getprop ro.product.model")
    if MODELO not in m:
        raise Falha("o aparelho no ADB nao e o SM-A125M (%r)" % m[:40])
    if PACOTE not in amb.adb("shell", "pm list packages " + PACOTE):
        raise Falha("o Fennec nao esta instalado")


def em_primeiro_plano(amb):
    return PACOTE in amb.adb("shell", "dumpsys window | grep -m1 mCurrentFocus")


def limpa(amb):
    """Desliga a depuracao de verdade: arquivo, debug-app e porta. Cada passo roda mesmo se o anterior falhar. No fim CONFERE no aparelho e devolve True se ficou limpo
    (o adb nao levanta erro com o cabo solto: so a conferencia prova)."""
    for args in (("shell", "am force-stop " + PACOTE), ("shell", "find %s -delete" % CONFIG), ("shell", "am clear-debug-app"), ("forward", "--remove", "tcp:%d" % PORTA)):
        try:
            amb.adb(*args)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        # o Fennec com a porta 2828 nao pode estar vivo (um force-stop que falhou sozinho nao pode dar LIMPO) nem o forward do adb de pe
        limpo = "LIMPO" in amb.adb("shell", '[ ! -e %s ] && [ "$(settings get global debug_app)" = null ] && [ -z "$(pidof %s)" ] && echo LIMPO' % (CONFIG, PACOTE))
        return limpo and ("tcp:%d" % PORTA) not in amb.adb("forward", "--list")
    except (OSError, subprocess.SubprocessError):
        return False


def com_depuracao(amb, forcar, trabalho):
    confere_aparelho(amb)
    if not forcar and em_primeiro_plano(amb):
        print("RECUSADO: o Fennec esta aberto na tela (fechar interromperia quem o usa). Saia dele ou use --forcar.")
        return 1
    try:
        amb.adb("shell", "am set-debug-app --persistent " + PACOTE)
        amb.adb("shell", "printf '" + yaml_de_depuracao().replace("\n", "\\n") + "' > " + CONFIG)
        amb.adb("shell", "am force-stop " + PACOTE)
        amb.adb("shell", "am start -W -n " + ATIVIDADE)
        amb.adb("forward", "tcp:%d" % PORTA, "tcp:%d" % PORTA)
        m = None
        for _ in range(30):
            amb.dorme(2)
            try:
                m = amb.conecta()
                break
            except (OSError, ValueError, Falha):
                continue
        if m is None:
            raise Falha("a depuracao nao respondeu em 60 s")
        sessao = m.cmd("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {}}})
        caps = sessao.get("capabilities", {}) if isinstance(sessao, dict) else {}
        print("Fennec %s conectado (depuracao ligada so durante este comando)" % caps.get("browserVersion", "?"))
        cod = trabalho(m)
    finally:
        limpo = limpa(amb)
        if not limpo:
            print("ATENCAO: nao confirmei que a depuracao desligou. Com o celular conectado, rode: python scripts\\navegador-a12.py limpar")
        try:
            amb.adb("shell", "input keyevent KEYCODE_HOME")
        except (OSError, subprocess.SubprocessError):
            pass
    return cod if limpo else 1


# ---------------------------------------------------------------- comandos

def cmd_abrir(amb, url, foto, texto, forcar):
    if not url_valida(url):
        print("RECUSADO: so endereco http:// ou https:// (recebi %r)." % (url or "")[:80])
        return 1

    def trabalho(m):
        m.cmd("WebDriver:Navigate", {"url": url})
        print("Titulo: %s" % valor(m.cmd("WebDriver:GetTitle")))
        print("Endereco final: %s" % valor(m.cmd("WebDriver:GetCurrentURL")))
        fonte = str(valor(m.cmd("WebDriver:GetPageSource")))
        print("HTML: %d caracteres; navegacao: %s" % (len(fonte), valor(m.cmd("WebDriver:ExecuteScript", {"script": TEMPOS_DA_PAGINA, "args": []}))))
        if foto:
            amb.grava(foto, base64.b64decode(str(valor(m.cmd("WebDriver:TakeScreenshot", {"full": False})))))
            print("Foto: %s" % foto)
        if texto:
            amb.grava(texto, fonte.encode("utf-8"))
            print("HTML gravado: %s" % texto)
        return 0

    return com_depuracao(amb, forcar, trabalho)


def _mostra_estado(e):
    if "erro" in e:
        raise Falha("nao li o estado: %s" % e["erro"])
    print("DNS seguro do navegador: %s" % ("LIGADO (%s, modo %s)" % (e.get("trr_uri") or "padrao", e["trr_modo"]) if e.get("trr_modo") in (2, 3) else "desligado (modo %s)" % e.get("trr_modo")))
    exts = e.get("extensoes") or []
    if not exts:
        print("Nenhuma extensao instalada.")
    for x in exts:
        print("Extensao: %s %s: %s" % (x["nome"], x["versao"], "ATIVA" if x["ativa"] else ("desligada por voce" if x.get("desligada_pelo_usuario") else "INATIVA")))


def cmd_status(amb, forcar):
    def trabalho(m):
        _mostra_estado(m.sistema(LE_ESTADO, assincrono=True))
        return 0
    return com_depuracao(amb, forcar, trabalho)


def cmd_dns(amb, acao, forcar):
    def trabalho(m):
        if acao == "ligar":
            m.sistema(GRAVA_DNS, [TRR_MODO, TRR_URI])
        else:
            m.sistema(GRAVA_DNS, [5, ""])   # 5 = desligado por escolha do usuario
        _mostra_estado(m.sistema(LE_ESTADO, assincrono=True))
        return 0
    return com_depuracao(amb, forcar, trabalho)


def cmd_ublock(amb, acao, forcar):
    def trabalho(m):
        r = m.sistema(MUDA_ADDON, [UBLOCK, acao == "ligar"], assincrono=True)
        if isinstance(r, dict) and r.get("erro"):
            print("FALHOU: %s" % r["erro"])
            return 1
        _mostra_estado(m.sistema(LE_ESTADO, assincrono=True))
        return 0
    return com_depuracao(amb, forcar, trabalho)


def main(argv=None, amb=None):
    ap = argparse.ArgumentParser(description="Navegador de teste no A12 (Fennec pelo cabo)")
    ap.add_argument("--forcar", action="store_true", help="fecha o Fennec mesmo se estiver na tela")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_ = sub.add_parser("abrir")
    a_.add_argument("url")
    a_.add_argument("--foto")
    a_.add_argument("--texto")
    sub.add_parser("status")
    sub.add_parser("dns-seguro").add_argument("acao", nargs="?", choices=["ligar", "desligar"], default="ligar")
    sub.add_parser("ublock").add_argument("acao", nargs="?", choices=["ligar", "desligar"], default="ligar")
    sub.add_parser("limpar")
    for sp in sub.choices.values():  # --forcar tambem depois do subcomando (o natural apos o RECUSADO); SUPPRESS nao zera o valor de antes
        sp.add_argument("--forcar", action="store_true", default=argparse.SUPPRESS, help="o mesmo de --forcar antes do subcomando")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    amb = amb or Ambiente()
    try:
        if a.cmd == "abrir":
            return cmd_abrir(amb, a.url, a.foto, a.texto, a.forcar)
        if a.cmd == "status":
            return cmd_status(amb, a.forcar)
        if a.cmd == "dns-seguro":
            return cmd_dns(amb, a.acao, a.forcar)
        if a.cmd == "ublock":
            return cmd_ublock(amb, a.acao, a.forcar)
        if limpa(amb):
            print("Depuracao desligada (conferido no aparelho).")
            return 0
        print("NAO CONFIRMEI que a depuracao desligou: confira o cabo e rode de novo.")
        return 2
    except Falha as e:
        print("FALHOU: %s" % e)
        return 1
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        print("ABORTADO: %s: %s" % (type(e).__name__, str(e)[:120]))
        return 2


if __name__ == "__main__":
    sys.exit(main())
