"""Testes do `link` do Termux (scripts/celular-kit/bin/link): compartilhar a tela do ScreenStream, arquivos e apps por link.
cloudflared, cmd e o ScreenStream sao FALSOS; bash, python3 (servidor de arquivos) e curl sao de verdade (rodam no WSL).
Nada toca o celular nem a internet."""
import http.client
import http.server
import pathlib
import re
import socket
import subprocess
import threading
import urllib.parse

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPT = RAIZ / "scripts" / "celular-kit" / "bin" / "link"
BASH = next((p for p in ("/bin/bash", "/usr/bin/bash") if pathlib.Path(p).exists()), None)
pytestmark = pytest.mark.skipif(BASH is None or not pathlib.Path("/usr/bin/curl").exists(), reason="precisa de bash e curl (WSL)")

FALSO_CLOUDFLARED = """#!/bin/bash
echo "cloudflared $*" >> "$FAKE_LOG"
[ -e "$FAKE_DIR/sem_tunel" ] && { echo "ERR failed to request quick Tunnel" >&2; exit 1; }
echo "INF |  https://teste-abc-def.trycloudflare.com  |" >&2
while true; do sleep 1; done
"""
FALSO_CMD = """#!/bin/bash
echo "cmd $*" >> "$FAKE_LOG"
if [ "$1 $2" = "package path" ]; then
  case "$3" in
    app.unico) echo "package:$FAKE_DIR/base.apk" ;;
    app.split) echo "package:$FAKE_DIR/base.apk"; echo "package:$FAKE_DIR/split.apk" ;;
  esac
  exit 0
fi
[ "$1 $2" = "package dump" ] && echo "    versionName=1.2"
exit 0
"""


def porta_livre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Amb:
    def __init__(self, base):
        self.base = base
        self.bin = base / "bin"
        self.bin.mkdir()
        self.run = base / "run"
        self.log = base / "log"
        self.log.write_text("")
        for nome, texto in (("cloudflared", FALSO_CLOUDFLARED), ("cmd", FALSO_CMD)):
            (self.bin / nome).write_text(texto)
            (self.bin / nome).chmod(0o755)
        (base / "base.apk").write_bytes(b"PK-apk-de-teste")
        self.porta = porta_livre()
        self.ss_porta = porta_livre()

    def env(self):
        return {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.base), "LINK_RUN": str(self.run),
                "LINK_PORTA": str(self.porta), "LINK_SS_PORTA": str(self.ss_porta), "LINK_IPS": "127.0.0.1",
                "FAKE_LOG": str(self.log), "FAKE_DIR": str(self.base)}

    def roda(self, *args):
        p = subprocess.Popen([BASH, str(SCRIPT), *args], env=self.env(), stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        saida, _ = p.communicate(timeout=90)
        return p.returncode, saida


@pytest.fixture
def amb(tmp_path):
    a = Amb(tmp_path)
    yield a
    a.roda("parar")


def pega(url):
    """GET so no 127.0.0.1 do teste (o conftest bloqueia o urlopen, que poderia sair para a rede de verdade)."""
    u = urllib.parse.urlsplit(url)
    assert u.hostname == "127.0.0.1"
    c = http.client.HTTPConnection("127.0.0.1", u.port, timeout=5)
    try:
        c.request("GET", u.path or "/")
        r = c.getresponse()
        return r.status, r.read(), r.headers
    finally:
        c.close()


def chave(saida):
    return re.search(r"http://127\.0\.0\.1:\d+/([0-9a-f]{24})/", saida).group(1)


def test_sintaxe_e_ascii():
    p = subprocess.Popen([BASH, "-n", str(SCRIPT)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    p.communicate(timeout=20)
    assert p.returncode == 0
    t = SCRIPT.read_bytes()
    t.decode("ascii")
    assert b"\r" not in t


def test_arquivo_local_entrega_so_com_a_chave(amb, tmp_path):
    f = tmp_path / "aula.pdf"
    f.write_bytes(b"%PDF-conteudo")
    rc, out = amb.roda("arquivo", str(f), "--local")
    assert rc == 0, out
    k = chave(out)
    st, corpo, _ = pega(f"http://127.0.0.1:{amb.porta}/{k}/")
    assert st == 200 and b"aula.pdf" in corpo
    st, corpo, cab = pega(f"http://127.0.0.1:{amb.porta}/{k}/0")
    assert st == 200 and corpo == b"%PDF-conteudo" and "aula.pdf" in cab["Content-Disposition"]
    assert pega(f"http://127.0.0.1:{amb.porta}/")[0] == 404
    assert pega(f"http://127.0.0.1:{amb.porta}/{'0' * 24}/0")[0] == 404
    assert pega(f"http://127.0.0.1:{amb.porta}/{k}/9")[0] == 404
    assert "cloudflared" not in amb.log.read_text()  # --local nao abre tunel
    assert "arquivos" in amb.roda("status")[1]
    amb.roda("parar")
    with pytest.raises(OSError):
        pega(f"http://127.0.0.1:{amb.porta}/{k}/")


def test_arquivo_publico_monta_o_link_com_a_chave(amb, tmp_path):
    f = tmp_path / "foto.jpg"
    f.write_bytes(b"jpg")
    rc, out = amb.roda("arquivo", str(f))
    assert rc == 0, out
    k = chave(out)
    assert f"https://teste-abc-def.trycloudflare.com/{k}/" in out
    assert f"--url http://127.0.0.1:{amb.porta}" in amb.log.read_text()
    assert "teste-abc-def" in amb.roda("status")[1]


def test_sem_tunel_o_local_segue(amb, tmp_path):
    (tmp_path / "sem_tunel").write_text("")
    f = tmp_path / "a.txt"
    f.write_text("oi")
    rc, out = amb.roda("arquivo", str(f))
    assert rc == 0 and "nao saiu" in out
    k = chave(out)
    assert pega(f"http://127.0.0.1:{amb.porta}/{k}/0")[1] == b"oi"


@pytest.mark.parametrize("nome", [".env", "id_ed25519", "minha-senha.txt", "MAPAO_2A.xlsx"])
def test_recusa_segredo(amb, tmp_path, nome):
    f = tmp_path / nome
    f.write_text("x")
    rc, out = amb.roda("arquivo", str(f))
    assert rc == 3 and "Recusado" in out
    assert not (amb.run / "servidor.pid").exists()


def test_arquivo_inexistente(amb):
    assert amb.roda("arquivo", "/nao/existe.pdf")[0] == 2


def test_app_unico_vira_apk_com_nome_e_versao(amb):
    rc, out = amb.roda("app", "app.unico", "--local")
    assert rc == 0, out
    k = chave(out)
    st, corpo, cab = pega(f"http://127.0.0.1:{amb.porta}/{k}/0")
    assert corpo == b"PK-apk-de-teste" and "app.unico-1.2.apk" in cab["Content-Disposition"]
    assert "android.package-archive" in cab["Content-Type"]


def test_app_split_explica_e_nao_compartilha(amb):
    rc, out = amb.roda("app", "app.split")
    assert rc == 1 and "LocalSend" in out


@pytest.mark.parametrize("pac", ["", "a;b", "../x"])
def test_app_nome_invalido(amb, pac):
    assert amb.roda("app", pac)[0] == 2


def test_tela_sem_screenstream_explica(amb):
    rc, out = amb.roda("tela")
    assert rc == 1 and "Iniciar transmissao" in out
    assert "cloudflared" not in amb.log.read_text()


PAGINA_SS = b'<html><title>ScreenStream</title><script>new WebsocketHeartbeat("ws://" + window.location.host + "/socket");</script>'


class FalsoSS(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        corpo = PAGINA_SS if self.path == "/" else b"--quadro-mjpeg--"
        self.send_response(200)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *a):
        pass


def test_tela_com_screenstream_abre_o_tunel_pelo_intermediario(amb):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", amb.ss_porta), FalsoSS)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        rc, out = amb.roda("tela")
        assert rc == 0, out
        assert "https://teste-abc-def.trycloudflare.com" in out and "PIN" in out
        assert f"--url http://127.0.0.1:{amb.porta}" in amb.log.read_text()  # o tunel vai ao intermediario
        assert f"http://127.0.0.1:{amb.ss_porta}" in out  # o local segue direto no ScreenStream
        # o intermediario troca o ws:// fixo (bloqueado em pagina https) e deixa o resto igual
        st, corpo, _ = pega(f"http://127.0.0.1:{amb.porta}/")
        assert st == 200 and b'"wss://"' in corpo and b'"ws://" + window' not in corpo
        assert pega(f"http://127.0.0.1:{amb.porta}/stream.mjpeg")[1] == b"--quadro-mjpeg--"
    finally:
        srv.shutdown()


def test_tela_local_nao_sobe_intermediario_nem_tunel(amb):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", amb.ss_porta), FalsoSS)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        rc, out = amb.roda("tela", "--local")
    finally:
        srv.shutdown()
    assert rc == 0 and "cloudflared" not in amb.log.read_text() and not (amb.run / "proxy.pid").exists()


def test_parar_sem_nada_e_status_vazio(amb):
    assert amb.roda("parar")[0] == 0
    assert "Nada compartilhado" in amb.roda("status")[1]


def test_comando_desconhecido(amb):
    assert amb.roda("formatar")[0] == 2
