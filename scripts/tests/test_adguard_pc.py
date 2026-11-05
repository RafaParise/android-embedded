"""Testes do scripts/adguard-pc.py: regras, validacao de dominio, pacote DNS e a conversa com a API. Nada toca rede: o servidor e falso."""
import json
import struct

import pytest


@pytest.fixture
def ag(importa_script):
    return importa_script("adguard-pc.py")


class Falso:
    """Finge a API do AdGuard Home v0.107: guarda regras e o que recebeu."""

    def __init__(self, regras=None, dns_ok=True, dns_bloqueia=True, assistente=False, protecao=True, filtros=None, cod_forcado=None):
        self.regras = list(regras or [])
        self.dns_ok, self.dns_bloqueia = dns_ok, dns_bloqueia
        self.assistente = assistente
        self.protecao = protecao
        self.filtros = filtros if filtros is not None else []
        self.chamadas = []
        self.cod_forcado = cod_forcado
        self.acesso = "acesso-falso.json"
        self.ip_dns = "100.64.0.1"
        self.guardado = None

    def guarda_credenciais(self, usuario, senha):
        self.guardado = (usuario, senha)

    def api(self, caminho, corpo=None, autentica=True, timeout=30, metodo=None):
        self.chamadas.append((caminho, corpo, autentica, metodo))
        if self.cod_forcado:
            return self.cod_forcado, {}
        if caminho == "install/get_addresses":
            return (200, {}) if self.assistente else (404, {})
        if caminho == "install/configure":
            return 200, {}
        if caminho == "status":
            return 200, {"version": "v0.107.79", "running": True, "protection_enabled": self.protecao, "protection_disabled_duration": 0 if self.protecao else 90000, "dns_addresses": ["100.64.0.1"], "dns_port": 53}
        if caminho == "filtering/status":
            return 200, {"user_rules": list(self.regras), "filters": self.filtros}
        if caminho == "filtering/set_rules":
            self.regras = list(corpo["rules"])
            return 200, {}
        if caminho == "stats":
            return 200, {"num_dns_queries": 10, "num_blocked_filtering": 3, "top_blocked_domains": [{"anuncio.exemplo.com": 7}, {"rastreio.exemplo.net": 2}]}
        if caminho.startswith("filtering/check_host"):
            return 200, {"reason": "FilteredBlackList" if "anuncio" in caminho else "NotFilteredNotFound", "rules": [{"text": "||anuncio.exemplo.com^"}] if "anuncio" in caminho else []}
        if caminho in ("protection", "dns_config", "querylog/config/update", "stats/config/update", "filtering/add_url", "filtering/set_url"):
            return 200, {}
        raise AssertionError("caminho inesperado: " + caminho)

    def dns(self, nome):
        if not self.dns_ok:
            return None
        if nome == "doubleclick.net" and self.dns_bloqueia:
            return 0, ["0.0.0.0"]
        return 0, ["192.0.2.10"]

    def corpo_de(self, caminho):
        return [c[1] for c in self.chamadas if c[0] == caminho]

    def metodo_de(self, caminho):
        return [c[3] for c in self.chamadas if c[0] == caminho]


# ---------------------------------------------------------------- dominio e regras

@pytest.mark.parametrize("entrada,esperado", [
    ("exemplo.com", "exemplo.com"),
    ("EXEMPLO.com", "exemplo.com"),
    ("  exemplo.com  ", "exemplo.com"),
    ("https://www.exemplo.com/filme?id=1", "exemplo.com"),
    ("http://sub.exemplo.com:8080/x", "sub.exemplo.com"),
    ("sub.exemplo.com/pagina", "sub.exemplo.com"),
    ("exemplo.com.", "exemplo.com"),
    ("a-b.exemplo.com.br", "a-b.exemplo.com.br"),
])
def test_dominio_aceita_dominio_e_url_colada(ag, entrada, esperado):
    assert ag.dominio_de(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", "   ", "localhost", "exemplo", "1.2.3.4", "*.exemplo.com", "exem plo.com", "-a.exemplo.com", "a-.exemplo.com", "a..com", "x" * 64 + ".com", "exemplo.com;rm", "||exemplo.com^", "http://[abc", "https://[::1", None, ".".join(["abcdefgh"] * 40)])
def test_dominio_recusa_o_que_nao_e_dominio(ag, entrada):
    assert ag.dominio_de(entrada) is None


def test_regras_tem_o_formato_do_adguard_e_voltam_ao_dominio(ag):
    assert ag.regra_liberar("a.com") == "@@||a.com^$important"
    assert ag.regra_bloquear("a.com") == "||a.com^"
    assert ag.dominio_da_regra("@@||a.com^$important") == "a.com"
    assert ag.dominio_da_regra("||a.com^") == "a.com"
    assert ag.dominio_da_regra("# comentario") is None
    assert ag.dominio_da_regra("/regex/") is None
    assert ag.sem_regras_de(["||a.com^", "||b.com^", "@@||a.com^$important", "# x"], "a.com") == ["||b.com^", "# x"]


# ---------------------------------------------------------------- pacote DNS

def _resposta(ident=0x1234, rcode=0, ips=("192.0.2.1",), tipo=1):
    d = struct.pack(">HHHHHH", ident, 0x8180 | rcode, 1, len(ips), 0, 0)
    d += b"\x01a\x03com\x00" + struct.pack(">HH", 1, 1)
    for ip in ips:
        d += b"\xc0\x0c" + struct.pack(">HHIH", tipo, 1, 60, 4) + bytes(int(x) for x in ip.split("."))
    return d


def test_consulta_dns_tem_o_formato_certo(ag):
    q = ag.monta_consulta("a.com")
    assert q[:2] == b"\x12\x34" and q[12:19] == b"\x01a\x03com\x00" and q[-4:] == struct.pack(">HH", 1, 1)


def test_le_resposta_com_ips_e_codigo(ag):
    assert ag.le_resposta(_resposta(ips=("192.0.2.1", "192.0.2.2"))) == (0, ["192.0.2.1", "192.0.2.2"])
    assert ag.le_resposta(_resposta(rcode=3, ips=())) == (3, [])


def test_le_resposta_ignora_o_que_nao_e_ipv4(ag):
    assert ag.le_resposta(_resposta(tipo=5)) == (0, [])


@pytest.mark.parametrize("ruim", [b"", b"\x12\x34", _resposta(ident=0x9999), struct.pack(">HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)])
def test_le_resposta_recusa_pacote_de_outra_consulta_ou_curto(ag, ruim):
    with pytest.raises(ValueError):
        ag.le_resposta(ruim)


def test_le_resposta_truncada_nao_quebra_com_outro_erro(ag):
    r = _resposta()
    with pytest.raises(ValueError):
        ag.le_resposta(r[:-2])
    with pytest.raises(ValueError):
        ag.le_resposta(r[:14])


@pytest.mark.parametrize("rcode,ips,esperado", [(0, ["0.0.0.0"], True), (3, [], True), (5, [], True), (0, ["192.0.2.1"], False), (0, [], False), (0, ["0.0.0.0", "192.0.2.1"], False), (2, [], False)])
def test_bloqueou(ag, rcode, ips, esperado):
    assert ag.bloqueou(rcode, ips) is esperado


# ---------------------------------------------------------------- comandos

def test_liberar_troca_a_regra_antiga_do_dominio_e_preserva_as_outras(ag, capsys):
    f = Falso(["||site.com^", "||outro.com^", "# minha nota"])
    assert ag.main(["liberar", "https://www.site.com/filme"], amb=f) == 0
    assert f.regras == ["||outro.com^", "# minha nota", "@@||site.com^$important"]
    assert "LIBERADO: site.com" in capsys.readouterr().out


def test_bloquear_troca_a_liberacao_antiga(ag):
    f = Falso(["@@||site.com^$important"])
    assert ag.main(["bloquear", "site.com"], amb=f) == 0
    assert f.regras == ["||site.com^"]


def test_tirar_apaga_so_daquele_dominio(ag, capsys):
    f = Falso(["||a.com^", "@@||b.com^$important"])
    assert ag.main(["tirar", "b.com"], amb=f) == 0
    assert f.regras == ["||a.com^"]
    capsys.readouterr()
    assert ag.main(["tirar", "nada.com"], amb=f) == 0
    assert "nada mudou" in capsys.readouterr().out
    assert f.regras == ["||a.com^"]


@pytest.mark.parametrize("cmd", ["liberar", "bloquear", "tirar", "testar"])
def test_dominio_invalido_nao_grava_nada(ag, capsys, cmd):
    f = Falso(["||a.com^"])
    assert ag.main([cmd, "isto nao e dominio"], amb=f) == 1
    assert f.regras == ["||a.com^"] and not f.corpo_de("filtering/set_rules")
    assert "RECUSADO" in capsys.readouterr().out


def test_listar_mostra_cada_tipo(ag, capsys):
    assert ag.main(["listar"], amb=Falso(["@@||a.com^$important", "||b.com^", "# nota"])) == 0
    s = capsys.readouterr().out
    assert "liberado  a.com" in s and "bloqueado b.com" in s and "outra     # nota" in s
    assert ag.main(["listar"], amb=Falso()) == 0
    assert "Nenhuma regra" in capsys.readouterr().out


def test_testar_diz_bloqueado_ou_passa(ag, capsys):
    assert ag.main(["testar", "anuncio.exemplo.com"], amb=Falso()) == 0
    assert "BLOQUEADO" in capsys.readouterr().out
    assert ag.main(["testar", "site.exemplo.com"], amb=Falso()) == 0
    assert "PASSA" in capsys.readouterr().out


def test_testar_codifica_o_dominio_na_url(ag):
    f = Falso()
    ag.main(["testar", "anuncio.exemplo.com"], amb=f)
    assert any(c[0] == "filtering/check_host?name=anuncio.exemplo.com" for c in f.chamadas)


def test_pausar_manda_milissegundos_e_retomar_religa(ag, capsys):
    f = Falso()
    assert ag.main(["pausar", "10"], amb=f) == 0
    assert f.corpo_de("protection") == [{"enabled": False, "duration": 600000}]
    assert ag.main(["pausar"], amb=f) == 0
    assert f.corpo_de("protection")[-1]["duration"] == 900000
    assert ag.main(["retomar"], amb=f) == 0
    assert f.corpo_de("protection")[-1] == {"enabled": True}
    assert "LIGADO" in capsys.readouterr().out


@pytest.mark.parametrize("m", ["0", "-5", "1441"])
def test_pausar_recusa_tempo_fora_da_faixa(ag, capsys, m):
    f = Falso()
    assert ag.main(["pausar", "--", m] if m.startswith("-") else ["pausar", m], amb=f) == 1
    assert not f.corpo_de("protection")


def test_top_mostra_os_mais_bloqueados(ag, capsys):
    assert ag.main(["top"], amb=Falso()) == 0
    s = capsys.readouterr().out
    assert "anuncio.exemplo.com" in s and "7" in s


def test_status_tudo_certo(ag, capsys):
    f = Falso(filtros=[{"enabled": True, "rules_count": 100}, {"enabled": False, "rules_count": 50}])
    assert ag.main(["status"], amb=f) == 0
    s = capsys.readouterr().out
    assert "rodando" in s and "LIGADO" in s and "Listas ativas: 1 (100 regras)" in s and "doubleclick.net bloqueado" in s


def test_status_acusa_dns_que_nao_responde(ag, capsys):
    assert ag.main(["status"], amb=Falso(dns_ok=False)) == 1
    assert "TESTE DE DNS FALHOU" in capsys.readouterr().out


def test_status_acusa_bloqueio_ligado_que_nao_bloqueia(ag, capsys):
    assert ag.main(["status"], amb=Falso(dns_bloqueia=False)) == 1
    assert "TESTE DE BLOQUEIO FALHOU" in capsys.readouterr().out


def test_status_pausado_nao_acusa_bloqueio(ag, capsys):
    assert ag.main(["status"], amb=Falso(dns_bloqueia=False, protecao=False)) == 0
    s = capsys.readouterr().out
    assert "PAUSADO por mais 2 min" in s and "bloqueio pausado" in s


@pytest.mark.parametrize("cod", [401, 403])
def test_senha_recusada_vira_mensagem_e_saida_2(ag, capsys, cod):
    assert ag.main(["listar"], amb=Falso(cod_forcado=cod)) == 2
    assert "recusou a senha" in capsys.readouterr().out


def test_erro_http_vira_saida_2_sem_mostrar_corpo(ag, capsys):
    assert ag.main(["liberar", "a.com"], amb=Falso(cod_forcado=500)) == 2
    assert "HTTP 500" in capsys.readouterr().out


# ---------------------------------------------------------------- configuracao

def test_configurar_no_assistente_guarda_senha_e_liga_so_na_tailnet(ag, capsys):
    f = Falso(assistente=True)
    assert ag.main(["configurar", "--ip", "100.64.0.9"], amb=f) == 0
    c = f.corpo_de("install/configure")[0]
    assert c["dns"] == {"ip": "100.64.0.9", "port": 53} and c["web"] == {"ip": "127.0.0.1", "port": 3000}
    assert f.guardado and f.guardado[1] == c["password"] and len(c["password"]) >= 16
    assert c["password"] not in capsys.readouterr().out, "a senha nao aparece na tela"
    assert all(ch[2] is False for ch in f.chamadas), "o assistente nao usa autenticacao"


def test_configurar_de_novo_nao_troca_a_senha(ag, capsys):
    f = Falso(assistente=False)
    assert ag.main(["configurar"], amb=f) == 0
    assert f.guardado is None and not f.corpo_de("install/configure")
    assert "ja tinha sido concluido" in capsys.readouterr().out


def test_configurar_senhas_sao_diferentes_a_cada_instalacao(ag):
    a, b = Falso(assistente=True), Falso(assistente=True)
    ag.main(["configurar"], amb=a)
    ag.main(["configurar"], amb=b)
    assert a.guardado[1] != b.guardado[1]


def test_ajustar_usa_put_e_milissegundos_e_nao_duplica_lista(ag):
    url1, url2 = ag.LISTAS[0][1], ag.LISTAS[1][1]
    f = Falso(filtros=[{"url": url1, "enabled": True}, {"url": url2, "enabled": False}])
    assert ag.main(["ajustar"], amb=f) == 0
    assert f.metodo_de("querylog/config/update") == ["PUT"] and f.metodo_de("stats/config/update") == ["PUT"]
    assert f.corpo_de("querylog/config/update")[0]["interval"] == 24 * 3600 * 1000
    assert f.corpo_de("stats/config/update")[0]["interval"] == 7 * 24 * 3600 * 1000
    assert not f.corpo_de("filtering/add_url"), "lista que ja existe nao e adicionada de novo"
    assert f.corpo_de("filtering/set_url")[0]["data"]["enabled"] is True and f.corpo_de("filtering/set_url")[0]["url"] == url2


def test_ajustar_adiciona_a_lista_que_falta(ag):
    f = Falso(filtros=[{"url": ag.LISTAS[0][1], "enabled": True}])
    assert ag.main(["ajustar"], amb=f) == 0
    assert [c["url"] for c in f.corpo_de("filtering/add_url")] == [ag.LISTAS[1][1]]


def test_upstreams_sao_criptografados_e_tem_ip_de_partida(ag):
    f = Falso()
    ag.main(["ajustar"], amb=f)
    c = f.corpo_de("dns_config")[0]
    assert all(u.startswith("https://") for u in c["upstream_dns"]) and len(c["upstream_dns"]) >= 2
    assert all(p[0].isdigit() for p in c["bootstrap_dns"])


# ---------------------------------------------------------------- arquivo e segredos

def test_credencial_ausente_vira_mensagem_que_manda_instalar(ag, tmp_path):
    a = ag.Ambiente(acesso=str(tmp_path / "nao-existe.json"))
    with pytest.raises(ag.Falha, match="adguard-pc.ps1 -Instalar"):
        a.credenciais()


def test_credencial_guardada_e_lida(ag, tmp_path):
    p = tmp_path / "sub" / "acesso.json"
    a = ag.Ambiente(acesso=str(p))
    a.guarda_credenciais("rafael", "segredo-falso")
    assert a.credenciais() == ("rafael", "segredo-falso")
    assert json.loads(p.read_text(encoding="utf-8"))["usuario"] == "rafael"


def test_o_script_nao_traz_site_nem_chave():
    import pathlib
    t = pathlib.Path(__file__).resolve().parent.parent.joinpath("adguard-pc.py").read_text(encoding="ascii")
    import hashlib
    import re
    # o site escolhido pelo Rafael nao entra em arquivo versionado: nem neste teste (por isso o hash do nome)
    assert "3decc3406b5d526890b88563cccae2c5ef2e5ff9354e47fc41c4d18cdfcff2de" not in {hashlib.sha256(p.encode()).hexdigest() for p in re.findall(r"[a-z0-9]+", t.lower())}
    assert "password" in t and "gerada = secrets.token_urlsafe" in t  # a senha nasce em tempo de execucao (secrets), nao fica no arquivo


def test_o_varredor_de_segredos_nao_recusa_o_proprio_script(importa_script):
    """Ate 02/11 "senha = secrets..." fazia o sync-memoria recusar o envio do projeto inteiro."""
    import pathlib
    t = pathlib.Path(__file__).resolve().parent.parent.joinpath("adguard-pc.py").read_text(encoding="ascii")
    assert not importa_script("ponte-pc.py").tem_segredo(t)
