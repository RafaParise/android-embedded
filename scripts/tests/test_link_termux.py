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


# ---- link tela --som (06/11): ScreenStream no modo RTSP -> ffmpeg do Termux -> HLS no navegador (ffmpeg e RTSP FALSOS)
FALSO_FFMPEG = """#!/bin/bash
echo "ffmpeg $*" >> "$FAKE_LOG"
[ -e "$FAKE_DIR/ffmpeg_falha" ] && { echo "rtsp://x: Connection refused"; exit 1; }
if [ -e "$FAKE_DIR/hevc" ]; then echo "  Stream #0:0: Video: hevc (Main), yuv420p, 720x1600"; else echo "  Stream #0:0: Video: h264 (High), yuv420p, 720x1600"; fi
[ -e "$FAKE_DIR/sem_audio" ] || echo "  Stream #0:1: Audio: opus, 48000 Hz, stereo"
saida="${@: -1}"; pasta=$(dirname "$saida")
printf 'quadro-ts' > "$pasta/s00000.ts"
printf '#EXTM3U\\n#EXT-X-TARGETDURATION:1\\n#EXTINF:1.0,\\ns00000.ts\\n' > "$saida"
while true; do sleep 1; done
"""


class Som:
    """Amb + ffmpeg falso + um 'RTSP' falso (so aceita a conexao: o ffmpeg e falso)."""

    def __init__(self, amb, rtsp=True):
        self.amb = amb
        (amb.bin / "ffmpeg").write_text(FALSO_FFMPEG)
        (amb.bin / "ffmpeg").chmod(0o755)
        self.rtsp_porta = porta_livre()
        self.sock = None
        if rtsp:
            self.sock = socket.socket()
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("127.0.0.1", self.rtsp_porta))
            self.sock.listen(8)
        amb_env = amb.env

        def env():
            e = amb_env()
            e.update({"LINK_RTSP_PORTA": str(self.rtsp_porta), "LINK_HLSJS_URL": "http://127.0.0.1:1/hls.min.js",
                      "LINK_HLSJS_ARQ": str(amb.base / "kit" / "hls.min.js")})
            return e
        amb.env = env

    def fecha(self):
        if self.sock:
            self.sock.close()


@pytest.fixture
def som(amb):
    s = Som(amb)
    yield s
    amb.roda("parar")
    s.fecha()


def test_som_sem_ffmpeg_ensina_a_instalar(amb):
    rc, out = amb.roda("tela", "--som")  # sem ffmpeg no PATH do teste
    assert rc == 1 and "pkg install ffmpeg" in out


def test_som_sem_rtsp_explica_o_modo(amb):
    s = Som(amb, rtsp=False)
    rc, out = amb.roda("tela", "--som", "--local")
    s.fecha()
    assert rc == 1 and "RTSP" in out and "Audio do dispositivo" in out
    assert "ffmpeg -" not in amb.log.read_text()


def test_som_local_serve_a_pagina_e_o_hls_so_com_a_chave(amb, som):
    rc, out = amb.roda("tela", "--som", "--local")
    assert rc == 0, out
    k = chave(out)
    log = amb.log.read_text()
    assert f"rtsp://127.0.0.1:{som.rtsp_porta}/screen" in log and "-c:v copy" in log and "-c:a aac" in log
    assert "cloudflared" not in log and "ATENCAO" not in out
    st, _, cab = pega(f"http://127.0.0.1:{amb.porta}/{k}")
    assert st == 301 and cab["Location"] == f"/{k}/"  # sem a barra: manda para a pagina, sem laco
    st, corpo, _ = pega(f"http://127.0.0.1:{amb.porta}/{k}/")
    assert st == 200 and b"<video" in corpo and b"tela.m3u8" in corpo and b"Toque para ouvir" in corpo
    st, corpo, cab = pega(f"http://127.0.0.1:{amb.porta}/{k}/tela.m3u8")
    assert st == 200 and corpo.startswith(b"#EXTM3U") and "mpegurl" in cab["Content-Type"] and cab["Cache-Control"] == "no-cache"
    assert pega(f"http://127.0.0.1:{amb.porta}/{k}/s00000.ts")[1] == b"quadro-ts"
    # sem a chave, outro nome, caminho para fora ou extensao nao servida: nada
    for ruim in ("/", "/tela.m3u8", f"/{'0' * 24}/tela.m3u8", f"/{k}/../link-hls.py", f"/{k}/%2e%2e/link-hls.py",
                 f"/{k}/link-hls.py", f"/{k}/x/tela.m3u8"):
        assert pega(f"http://127.0.0.1:{amb.porta}{ruim}")[0] == 404, ruim
    assert "tela com som" in amb.roda("status")[1] and "ffmpeg (RTSP -> HLS): ligado" in amb.roda("status")[1]
    # sem o hls.js (sem internet no teste) a pagina continua, avisando
    assert "Sem o hls.js" in out and not (amb.run / "hls" / k / "hls.min.js").exists()
    amb.roda("parar")
    assert not (amb.run / "hls" / k).exists() and not (amb.run / "ffmpeg.pid").exists()


def test_som_publico_tunel_aponta_para_o_servidor_hls(amb, som):
    rc, out = amb.roda("tela", "--som")
    assert rc == 0, out
    k = chave(out)
    assert f"https://teste-abc-def.trycloudflare.com/{k}/" in out
    assert f"--url http://127.0.0.1:{amb.porta}" in amb.log.read_text()


def test_som_avisa_hevc_e_falta_de_audio(amb, som):
    (amb.base / "hevc").write_text("")
    (amb.base / "sem_audio").write_text("")
    rc, out = amb.roda("tela", "--som", "--local")
    assert rc == 0 and "H.265" in out and "SEM som" in out


def test_som_ffmpeg_falha_mostra_o_motivo_e_limpa(amb, som):
    (amb.base / "ffmpeg_falha").write_text("")
    rc, out = amb.roda("tela", "--som", "--local")
    assert rc == 1 and "Connection refused" in out
    assert not (amb.run / "hls.pid").exists() and "Nada compartilhado" in amb.roda("status")[1]


class FalsoCDN(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        corpo = b"/* hls.js adulterado */"
        self.send_response(200)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *a):
        pass


def test_som_recusa_hls_js_com_sha_diferente(amb, som):
    p = porta_livre()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", p), FalsoCDN)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    velho = amb.env

    def env():
        e = velho()
        e["LINK_HLSJS_URL"] = f"http://127.0.0.1:{p}/hls.min.js"
        return e
    amb.env = env
    try:
        rc, out = amb.roda("tela", "--som", "--local")
    finally:
        srv.shutdown()
    k = chave(out)
    assert rc == 0 and "Sem o hls.js" in out
    assert not (amb.base / "kit" / "hls.min.js").exists() and not (amb.run / "hls" / k / "hls.min.js").exists()


# ---- link internet (06/11): proxy do celular para o notebook do hotspot sair pelo PC (sem o filtro da rede da escola)
class SiteFalso(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        corpo = b"site:" + self.path.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *a):
        pass


def proxy_env(amb, **extra):
    velho = amb.env
    amb.proxy_porta = porta_livre()

    def env():
        e = velho()
        e.update({"LINK_PROXY_PORTA": str(amb.proxy_porta)}, **extra)
        return e
    amb.env = env


def conversa(porta, texto, ler=True):
    s = socket.create_connection(("127.0.0.1", porta), timeout=5)
    try:
        s.sendall(texto)
        if not ler:
            return s
        dados = b""
        while True:
            try:
                b = s.recv(65536)
            except socket.timeout:
                break
            if not b:
                break
            dados += b
        return dados
    finally:
        if ler:
            s.close()


def test_internet_sem_hotspot_explica(amb):
    proxy_env(amb, LINK_IPS="wlan0=127.0.0.1")
    rc, out = amb.roda("internet")
    assert rc == 1 and "hotspot do celular esta desligado" in out and not (amb.run / "internet.pid").exists()


def test_internet_proxy_http_e_connect_ate_site_publico(amb):
    proxy_env(amb, LINK_PROXY_TESTE_LOCAL="1")
    site = porta_livre()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", site), SiteFalso)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        rc, out = amb.roda("internet", "--minutos", "5")
        assert rc == 0, out
        assert f"Endereco: 127.0.0.1 | Porta: {amb.proxy_porta}" in out and "DESATIVE" in out and "saida status" in out
        assert "internet" in amb.roda("status")[1]
        # a porta web do teste nao e 80/8080: so o CONNECT a 443/8443 e o HTTP a 80/8080 passam
        r = conversa(amb.proxy_porta, f"GET http://127.0.0.1:{site}/x HTTP/1.1\r\nHost: a\r\n\r\n".encode())
        assert r.startswith(b"HTTP/1.1 403")
        r = conversa(amb.proxy_porta, f"CONNECT 127.0.0.1:{site} HTTP/1.1\r\n\r\n".encode())
        assert r.startswith(b"HTTP/1.1 403")
    finally:
        srv.shutdown()
    assert "Nada compartilhado" not in amb.roda("status")[1]
    amb.roda("parar")
    assert not (amb.run / "internet.pid").exists()


def test_internet_proxy_conecta_na_porta_web(amb):
    """CONNECT de verdade ate um 'site' na porta 8443 (precisa estar livre na maquina de teste)."""
    proxy_env(amb, LINK_PROXY_TESTE_LOCAL="1")
    try:
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8443), SiteFalso)
    except OSError:
        pytest.skip("porta 8443 ocupada")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert amb.roda("internet")[0] == 0
        s = conversa(amb.proxy_porta, b"CONNECT 127.0.0.1:8443 HTTP/1.1\r\nHost: x\r\n\r\n", ler=False)
        cab = b""
        while b"\r\n\r\n" not in cab:
            cab += s.recv(1024)
        assert cab.startswith(b"HTTP/1.1 200")
        s.sendall(b"GET /dentro HTTP/1.0\r\n\r\n")
        dados = b""
        while True:
            b = s.recv(65536)
            if not b:
                break
            dados += b
        s.close()
        assert dados.endswith(b"site:/dentro")
    finally:
        srv.shutdown()


@pytest.mark.parametrize("alvo", ["127.0.0.1:443", "10.72.29.179:443", "192.168.0.1:443", "100.64.0.1:443",
                                  "169.254.1.1:443", "localhost:443"])
def test_internet_recusa_endereco_interno(amb, alvo):
    proxy_env(amb)  # sem a chave de teste: o 127.0.0.1 tambem e interno
    assert amb.roda("internet")[0] == 0
    assert conversa(amb.proxy_porta, f"CONNECT {alvo} HTTP/1.1\r\n\r\n".encode()).startswith(b"HTTP/1.1 403")


@pytest.mark.parametrize("pedido", [b"CONNECT smtp.exemplo.com:25 HTTP/1.1\r\n\r\n", b"GET ftp://a/b HTTP/1.1\r\n\r\n",
                                    b"lixo\r\n\r\n", b"GET http://exemplo.com:22/ HTTP/1.1\r\n\r\n"])
def test_internet_recusa_porta_e_pedido_estranho(amb, pedido):
    proxy_env(amb)
    assert amb.roda("internet")[0] == 0
    assert re.match(rb"HTTP/1.1 40[03]", conversa(amb.proxy_porta, pedido))


def test_internet_so_atende_quem_esta_no_hotspot(amb):
    proxy_env(amb, LINK_PROXY_TESTE_LOCAL="1", LINK_PROXY_REDE="10.9.9.0/24")
    assert amb.roda("internet")[0] == 0
    try:
        r = conversa(amb.proxy_porta, b"CONNECT 127.0.0.1:8443 HTTP/1.1\r\n\r\n")
    except ConnectionResetError:
        r = b""
    assert r == b""  # fecha sem responder
