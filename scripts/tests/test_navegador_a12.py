"""Testes do scripts/navegador-a12.py: protocolo Marionette, validacao de endereco e, principalmente, a garantia de que a depuracao SEMPRE desliga. adb e socket sao falsos."""
import base64
import json

import pytest


@pytest.fixture
def nav(importa_script):
    return importa_script("navegador-a12.py")


class MarionetteFalsa:
    def __init__(self, respostas=None, erro_em=None):
        self.comandos = []
        self.respostas = respostas or {}
        self.erro_em = erro_em

    def cmd(self, nome, params=None):
        self.comandos.append((nome, params))
        if self.erro_em == nome:
            raise self.Falha("recusou " + nome)
        return self.respostas.get(nome, {"value": None})

    def sistema(self, script, args=None, assincrono=False):
        self.comandos.append(("sistema", script, args, assincrono))
        if "getAddonByID" in script:
            return self.respostas.get("addon", {"ativa": True})
        if "getAddonsByTypes" in script:
            return self.respostas.get("estado", {"trr_modo": 2, "trr_uri": "https://x/dns-query", "extensoes": [{"id": "u", "nome": "uBlock Origin", "versao": "1", "ativa": True, "desligada_pelo_usuario": False}]})
        return True


class Falso:
    def __init__(self, nav, marionette=None, modelo="SM-A125M", instalado=True, foco="com.sec.android.app.launcher", conecta_apos=0, sujo=False, falha_em=None, fennec_vivo=False, forward_preso=False):
        self.sujo, self.falha_em = sujo, falha_em
        self.fennec_vivo, self.forward_preso = fennec_vivo, forward_preso
        self.nav = nav
        self.m = marionette or MarionetteFalsa()
        self.m.Falha = nav.Falha
        self.modelo, self.instalado, self.foco = modelo, instalado, foco
        self.conecta_apos = conecta_apos
        self.tentativas = 0
        self.adbs = []
        self.gravados = {}
        self.dormiu = 0

    def adb(self, *args, timeout=40):
        self.adbs.append(" ".join(args))
        j = " ".join(args)
        if self.falha_em and self.falha_em in j:
            raise OSError("adb caiu")
        if "echo LIMPO" in j:
            if self.fennec_vivo and "pidof" not in j:
                return "LIMPO"  # versao antiga da conferencia, que nao olhava o processo
            return "" if (self.sujo or self.fennec_vivo) else "LIMPO"
        if j == "forward --list":
            return "emulator-5554 tcp:2828 tcp:2828" if self.forward_preso else ""
        if "getprop ro.product.model" in j:
            return self.modelo
        if "pm list packages" in j:
            return "package:" + self.nav.PACOTE if self.instalado else ""
        if "mCurrentFocus" in j:
            return "mCurrentFocus=Window{1 u0 %s/x}" % self.foco
        return ""

    def conecta(self):
        self.tentativas += 1
        if self.tentativas <= self.conecta_apos:
            raise ConnectionRefusedError("ainda nao")
        return self.m

    def dorme(self, s):
        self.dormiu += s

    def grava(self, caminho, dados):
        self.gravados[caminho] = dados

    def limpou(self):
        """A limpeza completa aconteceu DEPOIS de a depuracao ser ligada?"""
        j = self.adbs
        lig = next((i for i, c in enumerate(j) if "set-debug-app" in c), None)
        if lig is None:
            return False
        depois = j[lig:]
        return all(any(p in c for c in depois) for p in ("find %s -delete" % self.nav.CONFIG, "am clear-debug-app", "forward --remove tcp:2828"))


RESP = {"WebDriver:GetTitle": {"value": "Titulo X"}, "WebDriver:GetCurrentURL": {"value": "https://a.com/"}, "WebDriver:GetPageSource": {"value": "<html>oi</html>"},
        "WebDriver:ExecuteScript": {"value": {"tempo_ms": 10}}, "WebDriver:TakeScreenshot": {"value": base64.b64encode(b"PNG").decode()},
        "WebDriver:NewSession": {"capabilities": {"browserVersion": "159.0"}}}


# ---------------------------------------------------------------- endereco e protocolo

@pytest.mark.parametrize("u", ["https://a.com", "http://a.com/x?y=1", "HTTPS://A.COM/"])
def test_url_valida(nav, u):
    assert nav.url_valida(u)


@pytest.mark.parametrize("u", ["", None, "file:///etc/hosts", "about:config", "chrome://browser", "moz-extension://x/y", "javascript:alert(1)", "https://a.com/'; reboot;'", "https://a b.com", "https://a.com/$(id)", "https://a.com/`id`", "ftp://a.com"])
def test_url_invalida_nunca_chega_ao_navegador(nav, capsys, u):
    f = Falso(nav, MarionetteFalsa(RESP))
    assert nav.cmd_abrir(f, u, None, None, False) == 1
    assert "RECUSADO" in capsys.readouterr().out
    assert not f.adbs, "recusa antes de mexer no celular"


def test_quadro_tem_tamanho_e_json(nav):
    assert nav.quadro(b'{"a":1}') == b'7:{"a":1}'


class SocketFalso:
    def __init__(self, entrada=b""):
        self.entrada = entrada
        self.saida = b""

    def recv(self, n):
        d, self.entrada = self.entrada[:n], self.entrada[n:]
        return d

    def sendall(self, b):
        self.saida += b


def _msg(o):
    p = json.dumps(o).encode()
    return str(len(p)).encode() + b":" + p


def test_marionette_le_ola_manda_comando_e_recebe_resposta(nav):
    s = SocketFalso(_msg({"applicationType": "gecko"}) + _msg([1, 1, None, {"value": "ok"}]))
    m = nav.Marionette(s)
    assert m.ola["applicationType"] == "gecko"
    assert m.cmd("WebDriver:GetTitle") == {"value": "ok"}
    assert json.loads(s.saida.split(b":", 1)[1]) == [0, 1, "WebDriver:GetTitle", {}]


def test_marionette_ignora_resposta_de_outro_id(nav):
    s = SocketFalso(_msg({"x": 1}) + _msg([1, 99, None, {"value": "velha"}]) + _msg([1, 1, None, {"value": "certa"}]))
    assert nav.Marionette(s).cmd("A") == {"value": "certa"}


def test_marionette_erro_vira_falha_com_mensagem_curta(nav):
    s = SocketFalso(_msg({"x": 1}) + _msg([1, 1, {"error": "e", "message": "m" * 500}, None]))
    with pytest.raises(nav.Falha) as e:
        nav.Marionette(s).cmd("A")
    assert len(str(e.value)) < 260


def test_marionette_conexao_fechada_vira_falha(nav):
    with pytest.raises(nav.Falha):
        nav.Marionette(SocketFalso(b""))
    with pytest.raises(nav.Falha):
        nav.Marionette(SocketFalso(b"50:{\"a\""))


def test_marionette_cabecalho_gigante_nao_trava(nav):
    with pytest.raises(nav.Falha):
        nav.Marionette(SocketFalso(b"9" * 40))


def test_marionette_cabecalho_sem_fim_para_no_limite(nav):
    """Porta que manda digitos para sempre: precisa desistir pelo limite, nao so quando a conexao fechar."""
    class SemFim:
        n = 0

        def recv(self, _):
            self.n += 1
            assert self.n < 100, "leu sem limite"
            return b"9"
    with pytest.raises(nav.Falha):
        nav.Marionette(SemFim())


def test_sistema_volta_ao_contexto_de_pagina_mesmo_com_erro(nav):
    s = SocketFalso(_msg({"x": 1}) + _msg([1, 1, None, {"value": None}]) + _msg([1, 2, {"message": "falhou"}, None]) + _msg([1, 3, None, {"value": None}]))
    m = nav.Marionette(s)
    with pytest.raises(nav.Falha):
        m.sistema("return 1")
    assert b'"value": "content"' in s.saida


def test_yaml_liga_marionette_e_acesso_de_sistema(nav):
    y = nav.yaml_de_depuracao()
    assert "-marionette" in y and "MOZ_REMOTE_ALLOW_SYSTEM_ACCESS: 1" in y and "'" not in y and "%" not in y


# ---------------------------------------------------------------- a depuracao sempre desliga

def test_abrir_ok_limpa_e_volta_para_a_tela_inicial(nav, capsys):
    f = Falso(nav, MarionetteFalsa(RESP))
    assert nav.cmd_abrir(f, "https://a.com", None, None, False) == 0
    assert f.limpou()
    assert f.adbs[-1] == "shell input keyevent KEYCODE_HOME"
    s = capsys.readouterr().out
    assert "Titulo X" in s and "159.0" in s and "HTML: 15 caracteres" in s


def test_yaml_e_gravado_com_quebra_de_linha_de_verdade(nav):
    f = Falso(nav, MarionetteFalsa(RESP))
    nav.cmd_abrir(f, "https://a.com", None, None, False)
    c = next(c for c in f.adbs if "printf" in c)
    assert c.startswith("shell printf 'args:\\n  - -marionette") and "printf '%s'" not in c and c.endswith("> " + nav.CONFIG)


def test_erro_no_meio_ainda_limpa(nav):
    f = Falso(nav, MarionetteFalsa(RESP, erro_em="WebDriver:Navigate"))
    with pytest.raises(nav.Falha):
        nav.cmd_abrir(f, "https://a.com", None, None, False)
    assert f.limpou()


def test_excecao_qualquer_no_meio_ainda_limpa(nav):
    f = Falso(nav, MarionetteFalsa(RESP))

    def explode(m):
        raise RuntimeError("bug")
    with pytest.raises(RuntimeError):
        nav.com_depuracao(f, False, explode)
    assert f.limpou()


def test_depuracao_que_nunca_responde_desiste_e_limpa(nav):
    f = Falso(nav, MarionetteFalsa(RESP), conecta_apos=999)
    with pytest.raises(nav.Falha, match="60 s"):
        nav.cmd_abrir(f, "https://a.com", None, None, False)
    assert f.limpou() and f.tentativas == 30


def test_espera_a_depuracao_subir(nav):
    f = Falso(nav, MarionetteFalsa(RESP), conecta_apos=3)
    assert nav.cmd_abrir(f, "https://a.com", None, None, False) == 0
    assert f.tentativas == 4


def test_limpa_apaga_o_arquivo_com_find_e_nada_mais(nav):
    f = Falso(nav)
    nav.limpa(f)
    apaga = [c for c in f.adbs if "delete" in c]
    assert apaga == ["shell find %s -delete" % nav.CONFIG]
    assert nav.CONFIG.startswith("/data/local/tmp/") and nav.PACOTE in nav.CONFIG


def test_comando_limpar(nav, capsys):
    f = Falso(nav)
    assert nav.main(["limpar"], amb=f) == 0
    assert any("am clear-debug-app" in c for c in f.adbs)
    assert "conferido" in capsys.readouterr().out


def test_limpar_sem_confirmacao_no_aparelho_nao_diz_que_limpou(nav, capsys):
    assert nav.main(["limpar"], amb=Falso(nav, sujo=True)) == 2
    s = capsys.readouterr().out
    assert "NAO CONFIRMEI" in s and "desligada" not in s


def test_conferencia_olha_o_arquivo_e_o_debug_app(nav):
    f = Falso(nav)
    assert nav.limpa(f) is True
    c = [x for x in f.adbs if "echo LIMPO" in x][-1]
    assert nav.CONFIG in c and "debug_app" in c and "pidof %s" % nav.PACOTE in c and "echo LIMPO" in c


def test_fennec_ainda_vivo_ou_forward_preso_nao_conta_como_limpo(nav):
    assert nav.limpa(Falso(nav, fennec_vivo=True)) is False
    assert nav.limpa(Falso(nav, forward_preso=True)) is False


def test_forcar_vale_tambem_depois_do_subcomando(nav):
    f = Falso(nav, foco=nav.PACOTE)
    assert nav.main(["status", "--forcar"], amb=f) in (0, 1)  # parse aceito (antes: SystemExit 2) e nao recusou por estar na tela
    g = Falso(nav, foco=nav.PACOTE)
    nav.main(["status"], amb=g)
    assert not any("am set-debug-app" in c for c in g.adbs)  # sem --forcar o Fennec na tela e RECUSADO
    assert any("am set-debug-app" in c for c in f.adbs)


def test_um_passo_que_falha_nao_impede_os_outros(nav):
    f = Falso(nav, falha_em="am force-stop")
    assert nav.limpa(f) is True
    assert any("find %s -delete" % nav.CONFIG in c for c in f.adbs) and any("am clear-debug-app" in c for c in f.adbs) and any("forward --remove" in c for c in f.adbs)


def test_conferencia_que_falha_nao_conta_como_limpo(nav):
    assert nav.limpa(Falso(nav, falha_em="echo LIMPO")) is False


def test_comando_que_nao_limpou_avisa_e_sai_com_erro(nav, capsys):
    f = Falso(nav, MarionetteFalsa(RESP), sujo=True)
    assert nav.cmd_abrir(f, "https://a.com", None, None, False) == 1
    assert "ATENCAO" in capsys.readouterr().out and f.adbs[-1] == "shell input keyevent KEYCODE_HOME"


def test_tela_inicial_que_falha_nao_estraga_o_resultado(nav, capsys):
    assert nav.cmd_abrir(Falso(nav, MarionetteFalsa(RESP), falha_em="KEYCODE_HOME"), "https://a.com", None, None, False) == 0


def test_conexao_que_nao_cumprimenta_fecha_o_socket(nav, monkeypatch):
    class S(SocketFalso):
        fechado = False

        def settimeout(self, t):
            pass

        def close(self):
            self.fechado = True
    s = S(b"")
    monkeypatch.setattr(nav.socket, "create_connection", lambda *a, **k: s)
    with pytest.raises(nav.Falha):
        nav.Ambiente().conecta()
    assert s.fechado


# ---------------------------------------------------------------- travas

def test_recusa_outro_aparelho_sem_ligar_nada(nav, capsys):
    f = Falso(nav, modelo="SM-G999")
    assert nav.main(["status"], amb=f) == 1
    assert "nao e o SM-A125M" in capsys.readouterr().out
    assert not any("set-debug-app" in c for c in f.adbs)


def test_recusa_sem_fennec(nav, capsys):
    f = Falso(nav, instalado=False)
    assert nav.main(["status"], amb=f) == 1
    assert "nao esta instalado" in capsys.readouterr().out


def test_recusa_com_o_fennec_na_tela_e_forcar_passa(nav, capsys):
    f = Falso(nav, foco=nav.PACOTE)
    assert nav.main(["status"], amb=f) == 1
    assert "RECUSADO" in capsys.readouterr().out
    assert not any("force-stop" in c for c in f.adbs)
    assert nav.main(["--forcar", "status"], amb=f) == 0


# ---------------------------------------------------------------- comandos

def test_abrir_grava_foto_e_html(nav, capsys):
    f = Falso(nav, MarionetteFalsa(RESP))
    assert nav.cmd_abrir(f, "https://a.com", "f.png", "p.html", False) == 0
    assert f.gravados == {"f.png": b"PNG", "p.html": b"<html>oi</html>"}


def test_status_mostra_dns_e_extensoes(nav, capsys):
    assert nav.main(["status"], amb=Falso(nav, MarionetteFalsa(RESP))) == 0
    s = capsys.readouterr().out
    assert "LIGADO" in s and "uBlock Origin 1: ATIVA" in s


@pytest.mark.parametrize("estado,trecho", [
    ({"trr_modo": 0, "trr_uri": "", "extensoes": []}, "desligado (modo 0)"),
    ({"trr_modo": 5, "trr_uri": "", "extensoes": []}, "Nenhuma extensao"),
    ({"trr_modo": 3, "trr_uri": "u", "extensoes": [{"nome": "U", "versao": "1", "ativa": False, "desligada_pelo_usuario": True}]}, "desligada por voce"),
    ({"trr_modo": 3, "trr_uri": "u", "extensoes": [{"nome": "U", "versao": "1", "ativa": False, "desligada_pelo_usuario": False}]}, "INATIVA"),
])
def test_mostra_estados(nav, capsys, estado, trecho):
    r = dict(RESP)
    r["estado"] = estado
    assert nav.main(["status"], amb=Falso(nav, MarionetteFalsa(r))) == 0
    assert trecho in capsys.readouterr().out


def test_estado_com_erro_vira_falha(nav, capsys):
    r = dict(RESP)
    r["estado"] = {"erro": "x"}
    assert nav.main(["status"], amb=Falso(nav, MarionetteFalsa(r))) == 1
    assert "nao li o estado" in capsys.readouterr().out


def test_dns_seguro_ligar_usa_modo_2_que_mantem_o_login_do_wifi(nav):
    m = MarionetteFalsa(RESP)
    assert nav.main(["dns-seguro", "ligar"], amb=Falso(nav, m)) == 0
    c = next(c for c in m.comandos if c[0] == "sistema" and "setIntPref" in c[1])
    assert c[2][0] == 2 and c[2][1].startswith("https://")


def test_dns_seguro_desligar_usa_modo_5(nav):
    m = MarionetteFalsa(RESP)
    assert nav.main(["dns-seguro", "desligar"], amb=Falso(nav, m)) == 0
    c = next(c for c in m.comandos if c[0] == "sistema" and "setIntPref" in c[1])
    assert c[2][0] == 5


@pytest.mark.parametrize("acao,esperado", [("ligar", True), ("desligar", False)])
def test_ublock_liga_e_desliga_so_o_ublock(nav, acao, esperado):
    m = MarionetteFalsa(RESP)
    assert nav.main(["ublock", acao], amb=Falso(nav, m)) == 0
    c = next(c for c in m.comandos if c[0] == "sistema" and "getAddonByID" in c[1])
    assert c[2] == [nav.UBLOCK, esperado]


def test_ublock_nao_instalado_falha(nav, capsys):
    r = dict(RESP)
    r["addon"] = {"erro": "nao instalada"}
    assert nav.main(["ublock", "ligar"], amb=Falso(nav, MarionetteFalsa(r))) == 1
    assert "nao instalada" in capsys.readouterr().out


def test_erro_de_adb_vira_saida_2(nav, capsys):
    class Quebrado(Falso):
        def adb(self, *a, timeout=40):
            raise FileNotFoundError("adb")
    assert nav.main(["status"], amb=Quebrado(nav)) == 2
    assert "ABORTADO" in capsys.readouterr().out
