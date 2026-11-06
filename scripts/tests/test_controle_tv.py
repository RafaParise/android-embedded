"""Testes do controle-tv (celular-kit/bin/controle-tv) com TVs FALSAS em 127.0.0.1: Roku, Samsung, LG, DLNA, DIAL e SSDP."""
import base64
import hashlib
import http.server
import importlib.machinery
import importlib.util
import json
import pathlib
import socket
import struct
import threading

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "celular-kit" / "bin" / "controle-tv"


@pytest.fixture
def ct(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTROLE_TV_DIR", str(tmp_path / "casa"))
    monkeypatch.setenv("CONTROLE_TV_TEMPO", "1")
    loader = importlib.machinery.SourceFileLoader("controle_tv", str(SCRIPT))
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader("controle_tv", loader))
    loader.exec_module(m)
    monkeypatch.setattr(m, "porta_aberta", lambda ip, porta, tempo=0.6: False)
    return m


def servidor_http(handler):
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


class Registro(http.server.BaseHTTPRequestHandler):
    pedidos = []
    respostas = {}

    def _responde(self):
        n = int(self.headers.get("Content-Length") or 0)
        corpo = self.rfile.read(n) if n else b""
        Registro.pedidos.append((self.command, self.path, dict(self.headers), corpo))
        st, txt, cab = Registro.respostas.get(self.path, (200, b"", {}))
        self.send_response(st)
        for k, v in cab.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(txt)))
        self.end_headers()
        self.wfile.write(txt)

    do_GET = do_POST = _responde

    def log_message(self, *a):
        pass


@pytest.fixture
def http_falso():
    Registro.pedidos, Registro.respostas = [], {}
    s = servidor_http(Registro)
    yield s.server_address[1]
    s.shutdown()


def test_sintaxe_ascii_e_sem_crlf():
    t = SCRIPT.read_bytes()
    t.decode("ascii")
    assert b"\r" not in t and t.startswith(b"#!/usr/bin/env python3")


def test_teclas_e_repeticao(ct):
    assert ct.expande(["volume+x3", "ok"]) == ["volume+"] * 3 + ["ok"]
    assert ct.expande(["volume-x99"]) == ["volume-"] * 30
    with pytest.raises(ct.Erro, match="desconhecida"):
        ct.expande(["formatar"])


def test_roku_manda_keypress_e_abre_app(ct, http_falso):
    tv = {"ip": "127.0.0.1", "tipo": "roku", "porta_roku": http_falso}
    ct.manda(tv, ["volume+", "ok", "netflix"])
    caminhos = [(m, p) for m, p, _, _ in Registro.pedidos]
    assert caminhos == [("POST", "/keypress/VolumeUp"), ("POST", "/keypress/Select"), ("POST", "/launch/12")]


def test_roku_recusada_explica(ct, http_falso):
    Registro.respostas["/keypress/VolumeUp"] = (403, b"", {})
    with pytest.raises(ct.Erro, match="Controle por apps"):
        ct.roku({"ip": "127.0.0.1", "porta_roku": http_falso}, "volume+")


RC = "urn:schemas-upnp-org:service:RenderingControl:1"


def test_descricao_acha_volume_e_dial_e_recusa_doctype(ct, http_falso):
    desc = (f'<?xml version="1.0"?><root xmlns="urn:schemas-upnp-org:device-1-0"><device><friendlyName>TV da Sala</friendlyName>'
            f'<manufacturer>Philco</manufacturer><serviceList><service><serviceType>{RC}</serviceType>'
            f'<controlURL>/rc</controlURL></service></serviceList></device></root>').encode()
    Registro.respostas["/desc.xml"] = (200, desc, {"Application-URL": f"http://127.0.0.1:{http_falso}/apps/"})
    info = ct.descricao(f"http://127.0.0.1:{http_falso}/desc.xml")
    assert info["nome"] == "TV da Sala" and info["fabricante"] == "Philco"
    assert info["rc_url"] == f"http://127.0.0.1:{http_falso}/rc" and info["app_url"].endswith("/apps/")
    Registro.respostas["/mal.xml"] = (200, b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "x">]><root><friendlyName>&a;</friendlyName></root>', {})
    assert "nome" not in ct.descricao(f"http://127.0.0.1:{http_falso}/mal.xml")
    assert ct.descricao("file:///etc/passwd") == {}


def test_dlna_volume_e_mudo(ct, http_falso):
    Registro.respostas["/rc"] = (200, b"<CurrentVolume>20</CurrentVolume><CurrentMute>0</CurrentMute>", {})
    tv = {"ip": "127.0.0.1", "tipo": "dlna", "rc_url": f"http://127.0.0.1:{http_falso}/rc", "rc_tipo": RC}
    ct.manda(tv, ["volume+", "mudo"])
    corpos = [c.decode() for _, _, _, c in Registro.pedidos]
    assert "<DesiredVolume>25</DesiredVolume>" in corpos[1] and "<DesiredMute>1</DesiredMute>" in corpos[3]
    assert all({k.lower(): v for k, v in h.items()}["soapaction"].startswith(f'"{RC}#') for _, _, h, _ in Registro.pedidos)
    with pytest.raises(ct.Erro, match="so ha volume"):
        ct.dlna(tv, "cima")


def test_dial_abre_youtube(ct, http_falso):
    tv = {"ip": "127.0.0.1", "tipo": "dial", "app_url": f"http://127.0.0.1:{http_falso}/apps/"}
    ct.manda(tv, ["youtube"])
    assert Registro.pedidos[-1][:2] == ("POST", "/apps/YouTube")


def test_ssdp_classifica_pelos_cabecalhos(ct):
    cab = ct.resposta_ssdp("HTTP/1.1 200 OK\r\nST: roku:ecp\r\nLOCATION: http://x/\r\nSERVER: Roku/9\r\n\r\n")
    assert cab["location"] == "http://x/" and ct.tipo_por_cabecalho(cab) == "roku"
    assert ct.tipo_por_cabecalho({"server": "Linux UPnP/1.0 Samsung"}) == "samsung"
    assert ct.tipo_por_cabecalho({"server": "WebOS/4.0 LGE"}) == "lg"
    assert ct.tipo_por_cabecalho({"st": "urn:schemas-upnp-org:device:MediaRenderer:1"}) == "dlna"
    assert ct.tipo_por_cabecalho({"server": "roteador"}) == ""


def test_procurar_por_ssdp_unicast_e_ignora_o_que_nao_e_tv(ct, monkeypatch, http_falso):
    Registro.respostas["/d.xml"] = (200, f'<root><device><friendlyName>Philco 42</friendlyName><serviceList><service><serviceType>{RC}'
                                         f'</serviceType><controlURL>/rc</controlURL></service></serviceList></device></root>'.encode(), {})
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    u.bind(("127.0.0.1", 0))
    porta = u.getsockname()[1]

    def responde():
        for _ in range(4):
            try:
                _, quem = u.recvfrom(2048)
            except OSError:
                return
            u.sendto(f"HTTP/1.1 200 OK\r\nST: urn:schemas-upnp-org:device:MediaRenderer:1\r\nLOCATION: http://127.0.0.1:{http_falso}/d.xml\r\n\r\n".encode(), quem)

    threading.Thread(target=responde, daemon=True).start()
    monkeypatch.setattr(ct, "SSDP_ALVO", f"127.0.0.1:{porta}")
    tvs = ct.procurar()
    u.close()
    assert len(tvs) == 1 and tvs[0]["nome"] == "Philco 42" and tvs[0]["tipo"] == "dlna"
    assert ct.le_json("tvs.json", [])[0]["ip"] == "127.0.0.1"


# ---------------------------------------------------------------- WebSocket falso (Samsung e LG)
def le_quadro(c):
    def le(n):
        b = b""
        while len(b) < n:
            d = c.recv(n - len(b))
            if not d:
                raise ConnectionError
            b += d
        return b
    _, b1 = le(2)
    n = b1 & 0x7F
    if n == 126:
        n = struct.unpack(">H", le(2))[0]
    m = le(4)
    return bytes(x ^ m[i % 4] for i, x in enumerate(le(n))).decode()


def envia(c, texto):
    d = texto.encode()
    c.sendall((bytes([0x81, len(d)]) if len(d) < 126 else bytes([0x81, 126]) + struct.pack(">H", len(d))) + d)


class WsFalso:
    def __init__(self, roteiro):
        self.roteiro, self.recebidos, self.caminhos = roteiro, [], []
        self.s = socket.socket()
        self.s.bind(("127.0.0.1", 0))
        self.s.listen(4)
        self.porta = self.s.getsockname()[1]
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                c, _ = self.s.accept()
            except OSError:
                return
            threading.Thread(target=self.atende, args=(c,), daemon=True).start()

    def atende(self, c):
        try:
            req = b""
            while b"\r\n\r\n" not in req:
                req += c.recv(4096)
            self.caminhos.append(req.split(b" ")[1].decode())
            k = [l.split(b": ")[1] for l in req.split(b"\r\n") if l.lower().startswith(b"sec-websocket-key")][0]
            ac = base64.b64encode(hashlib.sha1(k + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
            c.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + ac + b"\r\n\r\n")
            self.roteiro(self, c)
        except (ConnectionError, OSError, IndexError):
            pass


def test_samsung_guarda_o_token_e_manda_as_teclas(ct, monkeypatch):
    def roteiro(f, c):
        envia(c, json.dumps({"event": "ms.channel.connect", "data": {"token": "12345678"}}))
        while True:
            f.recebidos.append(json.loads(le_quadro(c)))

    f = WsFalso(roteiro)
    tv = {"ip": "127.0.0.1", "tipo": "samsung", "porta_samsung": f.porta}
    monkeypatch.setattr(ct, "time", type("T", (), {"sleep": staticmethod(lambda s: None), "time": staticmethod(lambda: 0)}))
    ct.manda(tv, ["volume+", "youtube"])
    import time as _t
    _t.sleep(0.3)
    assert f.recebidos[0]["params"]["DataOfCmd"] == "KEY_VOLUP"
    assert f.recebidos[1]["params"]["data"]["appId"] == "111299001912"
    assert ct.le_json("chaves.json", {})["127.0.0.1"] == "12345678"
    ct.manda(tv, ["mudo"])
    assert "token=12345678" in f.caminhos[-1]


def test_lg_registra_guarda_a_chave_e_usa_ssap(ct, monkeypatch):
    def roteiro(f, c):
        while True:
            m = json.loads(le_quadro(c))
            f.recebidos.append(m)
            if m["type"] == "register":
                envia(c, json.dumps({"type": "response", "id": "reg0", "payload": {"pairingType": "PROMPT"}}))
                envia(c, json.dumps({"type": "registered", "id": "reg0", "payload": {"client-key": "chave-lg"}}))
            elif m.get("uri") == "ssap://audio/getStatus":
                envia(c, json.dumps({"type": "response", "id": m["id"], "payload": {"mute": False}}))
            else:
                envia(c, json.dumps({"type": "response", "id": m["id"], "payload": {"returnValue": True}}))

    f = WsFalso(roteiro)
    monkeypatch.setattr(ct, "time", type("T", (), {"sleep": staticmethod(lambda s: None), "time": staticmethod(lambda: 0)}))
    tv = {"ip": "127.0.0.1", "tipo": "lg", "porta_lg": f.porta}
    ct.manda(tv, ["volume-", "mudo", "netflix"])
    uris = [m.get("uri") for m in f.recebidos if m["type"] == "request"]
    assert uris == ["ssap://audio/volumeDown", "ssap://audio/getStatus", "ssap://audio/setMute", "ssap://system.launcher/launch"]
    assert [m for m in f.recebidos if m.get("uri") == "ssap://audio/setMute"][0]["payload"] == {"mute": True}
    assert ct.le_json("chaves.json", {})["127.0.0.1"] == "chave-lg"


def test_certificado_fixado_na_primeira_vez_e_troca_recusada(ct):
    ct.confere_certificado("10.0.0.5", 8002, b"cert-A")
    ct.confere_certificado("10.0.0.5", 8002, b"cert-A")
    with pytest.raises(ct.Erro, match="MUDOU"):
        ct.confere_certificado("10.0.0.5", 8002, b"cert-B")


def test_ligar_sem_mac_explica(ct):
    with pytest.raises(ct.Erro, match="MAC"):
        ct.manda({"ip": "127.0.0.1", "tipo": "samsung"}, ["ligar"])


def test_escolhe_e_uso(ct, capsys):
    assert ct.main([]) == 2
    assert ct.main(["teclas"]) == 0 and "volume+" in capsys.readouterr().out
    assert ct.main(["volume+"]) == 1  # sem TV conhecida
    assert ct.main(["3", "volume+"]) == 1
    assert ct.main(["1", "apagar"]) == 2
    assert ct.main(["lista"]) == 0 and "Nenhuma TV" in capsys.readouterr().out
