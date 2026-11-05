"""Testes do scripts/navegador.py (Chromium sem tela). Nada abre navegador nem rede: `roda` e `resolve` sao falsos."""
import subprocess
import types

import pytest


@pytest.fixture
def nv(importa_script):
    return importa_script("navegador.py")


def publico(host, _p):
    return [(2, 1, 6, "", ("93.184.216.34", 0))]


def roda_falso(html="<html><head><title>Oi</title></head><body><p>texto</p></body></html>", rc=0):
    chamadas = []

    def roda(args, capture_output=True, timeout=0):
        chamadas.append(args)
        for a in args:
            if a.startswith("--screenshot="):
                open(a.split("=", 1)[1], "wb").write(b"PNG")
        return types.SimpleNamespace(returncode=rc, stdout=html.encode("utf-8"), stderr=b"")
    roda.chamadas = chamadas
    return roda


@pytest.mark.parametrize("html,titulo,texto", [
    ("<title>T</title><p>a</p><p>b</p>", "T", "a\nb"),
    ("<title> T  x\n y </title>", "T x y", ""),
    ("<head><title>T</title><meta name=x></head><script>ruim()</script><style>.a{}</style><noscript>n</noscript><svg><text>s</text></svg><template>t</template><p>fim</p>", "T", "fim"),
    ("<p>caf&eacute; &amp; p&atilde;o</p>", "", "café & pão"),
    ("", "", ""),
    ("<p>sem fechar", "", "sem fechar"),
    ("<script>nao fecha", "", ""),
    ("<title>Primeiro</title><title>Segundo</title><p>x</p>", "Primeiro", "x"),
])
def test_extrai_titulo_e_texto_visivel(nv, html, titulo, texto):
    assert nv.extrai(html) == (titulo, texto)


@pytest.mark.parametrize("u", ["https://a.com", "http://a.com/x?y=1&z=2", "HTTPS://A.COM/"])
def test_formato_ok(nv, u):
    assert nv.url_de_formato_ok(u)


@pytest.mark.parametrize("u", ["", None, 5, "file:///c:/x", "about:blank", "javascript:alert(1)", "ftp://a.com", "--dump-dom", "https://a b.com", "https://a.com/'x", 'https://a.com/"x', "https://a.com/$(id)", "https://a.com/`id`", "https://a.com/|x", "https://a.com/\\x", "https://a.com\n"])
def test_formato_recusa(nv, u):
    assert not nv.url_de_formato_ok(u)


@pytest.mark.parametrize("u", ["http://localhost", "http://127.0.0.1:20128", "http://[::1]/", "http://192.168.0.1", "http://10.0.0.1", "http://172.16.0.1", "http://100.64.0.1:20130/saude", "http://100.100.100.100", "http://169.254.169.254/latest", "http://0.0.0.0", "http://224.0.0.1"])
def test_endereco_interno_nunca_e_publico(nv, u):
    assert nv.endereco_publico(u, lambda h, p: [(2, 1, 6, "", ("127.0.0.1", 0))]) is False


@pytest.mark.parametrize("u", ["http://[abc/", "http://[::1"])
def test_url_com_colchete_invalido_vira_falha_e_nao_valueerror(nv, u):
    assert not nv.url_de_formato_ok(u)
    assert nv.endereco_publico(u, lambda h, p: []) is False
    for local in (False, True):
        with pytest.raises(nv.Falha):
            nv.ler(u, local=local, exe="x", roda=lambda *a, **k: pytest.fail("nao pode abrir o motor"))


def test_nome_que_aponta_para_ip_interno_e_recusado(nv):
    assert nv.endereco_publico("https://painel.exemplo.com", lambda h, p: [(2, 1, 6, "", ("192.168.0.5", 0))]) is False


def test_nome_com_um_ip_interno_entre_varios_e_recusado(nv):
    assert nv.endereco_publico("https://a.com", lambda h, p: [(2, 1, 6, "", ("93.184.216.34", 0)), (2, 1, 6, "", ("10.0.0.1", 0))]) is False


def test_nome_publico_passa_e_o_que_nao_resolve_nao(nv):
    assert nv.endereco_publico("https://a.com", publico) is True

    def nao_resolve(h, p):
        raise OSError("sem nome")
    assert nv.endereco_publico("https://a.com", nao_resolve) is False
    assert nv.endereco_publico("https://a.com", lambda h, p: []) is False


def test_ler_devolve_titulo_e_texto_com_perfil_descartavel(nv):
    r = roda_falso()
    s = nv.ler("https://a.com", exe="motor.exe", roda=r, resolve=publico)
    assert s == {"url": "https://a.com", "titulo": "Oi", "texto": "texto", "truncado": False}
    a = r.chamadas[0]
    assert a[0] == "motor.exe" and a[-2:] == ["--dump-dom", "https://a.com"]
    assert any(x.startswith("--user-data-dir=") for x in a) and "--disable-extensions" in a


def test_ler_recusa_interno_sem_abrir_o_navegador(nv):
    r = roda_falso()
    with pytest.raises(nv.Falha, match="interno"):
        nv.ler("http://127.0.0.1:20128", exe="motor.exe", roda=r, resolve=publico)
    assert not r.chamadas


def test_ler_com_local_libera_interno(nv):
    r = roda_falso()
    assert nv.ler("http://127.0.0.1:20128", local=True, exe="motor.exe", roda=r)["titulo"] == "Oi"


@pytest.mark.parametrize("h", ["localhost", "127.*", "10.*", "192.168.*", "169.254.*", "*.ts.net", "172.16.*", "172.31.*", "100.64.*", "100.127.*", "::1"])
def test_motor_recebe_a_lista_de_internos_para_redirecionamento(nv, tmp_path, h):
    r = roda_falso()
    nv.ler("https://a.com", foto=str(tmp_path / "f.png"), exe="motor.exe", roda=r, resolve=publico)
    assert len(r.chamadas) == 2
    for a in r.chamadas:
        regra = next(x for x in a if x.startswith("--host-resolver-rules="))
        assert ("MAP %s ~NOTFOUND" % h) in regra.split("=", 1)[1].split(", ")


def test_lista_nao_pega_ip_publico_vizinho(nv):
    p = nv.BLOQUEIA_INTERNOS.split(", ")
    assert "MAP 172.15.* ~NOTFOUND" not in p and "MAP 172.32.* ~NOTFOUND" not in p and "MAP 100.63.* ~NOTFOUND" not in p and "MAP 100.128.* ~NOTFOUND" not in p


def test_com_local_o_motor_nao_recebe_a_lista(nv, tmp_path):
    r = roda_falso()
    nv.ler("http://127.0.0.1:20128", foto=str(tmp_path / "f.png"), local=True, exe="motor.exe", roda=r)
    assert len(r.chamadas) == 2 and not any(x.startswith("--host-resolver-rules=") for a in r.chamadas for x in a)


def test_formato_ruim_e_recusado_mesmo_com_local(nv):
    r = roda_falso()
    with pytest.raises(nv.Falha, match="http"):
        nv.ler("file:///c:/segredo", local=True, exe="motor.exe", roda=r)
    assert not r.chamadas


def test_ler_corta_o_texto_e_avisa(nv):
    r = roda_falso("<p>" + "a" * (nv.MAX_TEXTO + 50) + "</p>")
    s = nv.ler("https://a.com", exe="motor.exe", roda=r, resolve=publico)
    assert len(s["texto"]) == nv.MAX_TEXTO and s["truncado"] is True


def test_navegador_com_erro_vira_falha(nv):
    with pytest.raises(nv.Falha, match="erro"):
        nv.ler("https://a.com", exe="motor.exe", roda=roda_falso(rc=3), resolve=publico)


def test_tempo_esgotado_vira_falha(nv):
    def roda(args, capture_output=True, timeout=0):
        raise subprocess.TimeoutExpired(args, timeout)
    with pytest.raises(nv.Falha, match="nao terminou"):
        nv.ler("https://a.com", exe="motor.exe", roda=roda, resolve=publico)


def test_foto_grava_e_informa(nv, tmp_path):
    f = tmp_path / "p.png"
    r = roda_falso()
    s = nv.ler("https://a.com", foto=str(f), exe="motor.exe", roda=r, resolve=publico)
    assert s["foto"] == str(f) and f.read_bytes() == b"PNG" and len(r.chamadas) == 2


def test_foto_que_nao_saiu_vira_falha(nv, tmp_path):
    chamadas = []

    def roda(args, capture_output=True, timeout=0):
        chamadas.append(args)
        return types.SimpleNamespace(returncode=0, stdout=b"<title>x</title>", stderr=b"")
    with pytest.raises(nv.Falha, match="foto"):
        nv.ler("https://a.com", foto=str(tmp_path / "nao.png"), exe="motor.exe", roda=roda, resolve=publico)


def test_sem_motor_falha_e_diz_como_instalar(nv, monkeypatch, tmp_path):
    monkeypatch.delenv("NAVEGADOR_EXE", raising=False)
    with pytest.raises(nv.Falha, match="npx playwright install"):
        nv.acha_motor(str(tmp_path / "nada" / "*.exe"))


def test_variavel_escolhe_o_navegador(nv, monkeypatch, tmp_path):
    x = tmp_path / "outro.exe"
    x.write_text("x")
    monkeypatch.setenv("NAVEGADOR_EXE", str(x))
    assert nv.acha_motor() == str(x)


def test_variavel_apontando_para_o_nada_cai_no_cache(nv, monkeypatch, tmp_path):
    a = tmp_path / "chromium_headless_shell-1234" / "w"
    a.mkdir(parents=True)
    (a / "s.exe").write_text("x")
    monkeypatch.setenv("NAVEGADOR_EXE", str(tmp_path / "nao-existe.exe"))
    assert nv.acha_motor(str(tmp_path / "chromium_headless_shell-*" / "*" / "*.exe")) == str(a / "s.exe")


def test_usa_a_versao_mais_nova_por_numero_e_nao_por_texto(nv, monkeypatch, tmp_path):
    monkeypatch.delenv("NAVEGADOR_EXE", raising=False)
    for v in ("999", "1234", "1248"):
        a = tmp_path / ("chromium_headless_shell-" + v) / "w"
        a.mkdir(parents=True)
        (a / "s.exe").write_text("x")
    achado = nv.acha_motor(str(tmp_path / "chromium_headless_shell-*" / "*" / "*.exe"))
    assert "chromium_headless_shell-1248" in achado


def test_main_recusa_com_saida_1(nv, capsys):
    assert nv.main(["file:///c:/x"]) == 1
    assert "FALHOU" in capsys.readouterr().out
