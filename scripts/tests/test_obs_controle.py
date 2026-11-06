"""Testes do obs-controle.py com um obs-websocket FALSO (127.0.0.1, porta livre): autenticacao, quadros e as operacoes."""
import base64
import hashlib
import json
import socket
import struct
import threading

import pytest

PALAVRA = "abc-teste"


@pytest.fixture
def oc(importa_script):
    return importa_script("obs-controle.py")


def le_quadro(c):
    def le(n):
        b = b""
        while len(b) < n:
            d = c.recv(n - len(b))
            if not d:
                raise ConnectionError
            b += d
        return b
    b0, b1 = le(2)
    n = b1 & 0x7F
    if n == 126:
        n = struct.unpack(">H", le(2))[0]
    elif n == 127:
        n = struct.unpack(">Q", le(8))[0]
    assert b1 & 0x80, "o cliente tem que mascarar"
    m = le(4)
    return json.loads(bytes(x ^ m[i % 4] for i, x in enumerate(le(n))))


def envia(c, obj):
    d = json.dumps(obj).encode()
    cab = bytes([0x81, len(d)]) if len(d) < 126 else bytes([0x81, 126]) + struct.pack(">H", len(d))
    c.sendall(cab + d)


class FalsoObs:
    def __init__(self):
        self.estado = {"vcam": False, "rec": False, "cena": "1 Jogo", "pasta": "C:/nao/existe"}
        self.pedidos = []
        self.dados = []
        self.s = socket.socket()
        self.s.bind(("127.0.0.1", 0))
        self.s.listen(5)
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
            chave = [l.split(b": ")[1] for l in req.split(b"\r\n") if l.lower().startswith(b"sec-websocket-key")][0]
            aceita = base64.b64encode(hashlib.sha1(chave + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
            c.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + aceita + b"\r\n\r\n")
            envia(c, {"op": 0, "d": {"rpcVersion": 1, "authentication": {"challenge": "desafio", "salt": "sal"}}})
            ident = le_quadro(c)
            seg = base64.b64encode(hashlib.sha256((PALAVRA + "sal").encode()).digest()).decode()
            certo = base64.b64encode(hashlib.sha256((seg + "desafio").encode()).digest()).decode()
            if ident["d"].get("authentication") != certo:
                c.sendall(bytes([0x88, 0]))
                return
            envia(c, {"op": 2, "d": {"negotiatedRpcVersion": 1}})
            while True:
                r = le_quadro(c)["d"]
                self.pedidos.append(r["requestType"])
                self.dados.append((r["requestType"], r.get("requestData", {})))
                envia(c, {"op": 7, "d": {"requestId": r["requestId"], **self.responde(r["requestType"], r.get("requestData", {}))}})
        except (ConnectionError, OSError, IndexError):
            pass
        finally:
            c.close()

    def responde(self, t, dados):
        e, ok = self.estado, {"requestStatus": {"result": True, "code": 100}}
        tabela = {
            "GetVirtualCamStatus": {"outputActive": e["vcam"]}, "GetRecordStatus": {"outputActive": e["rec"], "outputTimecode": "00:00:05"},
            "GetStreamStatus": {"outputActive": False}, "GetCurrentProgramScene": {"currentProgramSceneName": e["cena"]},
            "GetSceneList": {"scenes": [{"sceneName": "1 Jogo"}, {"sceneName": "2 Jogo com Webcam"}, {"sceneName": "3 Só Webcam"}]},
            "GetSceneItemList": {"sceneItems": [{"sourceName": "Webcam do Celular", "sceneItemId": 7}, {"sourceName": "Som do celular", "sceneItemId": 8}]
                                 if "Webcam" in dados.get("sceneName", "") else [{"sourceName": "Jogo", "sceneItemId": 1}]},
            "GetRecordDirectory": {"recordDirectory": e["pasta"]}, "GetVersion": {"obsVersion": "32", "obsWebSocketVersion": "5"},
            "GetVideoSettings": {"baseWidth": 1920, "baseHeight": 1080},
        }
        if t == "StartVirtualCam":
            e["vcam"] = True
        elif t == "StartRecord":
            e["rec"] = True
        elif t == "StopRecord":
            e["rec"] = False
            return {**ok, "responseData": {"outputPath": "D:/x.mp4"}}
        elif t == "SetCurrentProgramScene":
            e["cena"] = dados["sceneName"]
        elif t == "StartStream":
            return {"requestStatus": {"result": False, "code": 500, "comment": "sem destino configurado"}}
        return {**ok, "responseData": tabela.get(t, {})}


@pytest.fixture
def falso():
    f = FalsoObs()
    yield f
    f.s.close()


def test_resposta_auth_segue_a_formula_do_obs(oc):
    seg = base64.b64encode(hashlib.sha256(b"abcsal").digest()).decode()
    assert oc.resposta_auth("abc", "sal", "des") == base64.b64encode(hashlib.sha256((seg + "des").encode()).digest()).decode()


@pytest.mark.parametrize("n", [5, 200, 70000])
def test_quadro_mascarado_com_os_tres_tamanhos(oc, n):
    q = oc.quadro("x" * n, b"\1\2\3\4")
    assert q[0] == 0x81 and q[1] & 0x80
    corpo = q[-n:]
    assert bytes(b ^ (1, 2, 3, 4)[i % 4] for i, b in enumerate(corpo)) == b"x" * n


def test_liga_camera_virtual_e_troca_para_a_cena_da_webcam(oc, falso):
    with oc.Obs(falso.porta, PALAVRA) as o:
        assert oc.cena_com_webcam(o) == ("3 Só Webcam", True) or oc.cena_com_webcam(o)[0].endswith("Webcam")
        assert oc.camera_virtual(o, True) == "ligada agora"
        assert oc.camera_virtual(o, True) == "ja estava ligada"
    assert falso.estado["vcam"] and "Webcam" in falso.estado["cena"] and "Jogo" not in falso.estado["cena"]


def test_cena_que_ja_tem_a_webcam_fica(oc, falso):
    falso.estado["cena"] = "3 Só Webcam"
    with oc.Obs(falso.porta, PALAVRA) as o:
        assert oc.cena_com_webcam(o) == ("3 Só Webcam", False)
    assert "SetCurrentProgramScene" not in falso.pedidos


def test_gravar_e_parar(oc, falso):
    with oc.Obs(falso.porta, PALAVRA) as o:
        assert oc.gravar(o, "iniciar").startswith("gravando")
        assert oc.gravar(o, "iniciar") == "ja estava gravando"
        assert oc.gravar(o, "parar") == "gravacao salva: D:/x.mp4"
        assert oc.gravar(o, "parar") == "nao estava gravando"


def test_recusa_do_obs_vira_erro_com_o_motivo(oc, falso):
    with oc.Obs(falso.porta, PALAVRA) as o:
        with pytest.raises(oc.ErroObs, match="sem destino"):
            oc.transmitir(o, "iniciar")


def test_senha_errada_nao_conecta(oc, falso):
    with pytest.raises(oc.ErroObs):
        oc.Obs(falso.porta, "errada").conecta()


def test_obs_fechado_e_config_desligada(oc, tmp_path):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    with pytest.raises(oc.ErroObs, match="fechado"):
        oc.Obs(porta, PALAVRA, tempo=1).conecta()
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"server_enabled": False, "server_port": 4455}))
    with pytest.raises(oc.ErroObs, match="desligado"):
        oc.le_config(cfg)
    cfg.write_text(json.dumps({"server_enabled": True, "server_port": 4460, "auth_required": True, "server_password": "p"}))
    assert oc.le_config(cfg) == (4460, "p")


def test_uso_errado_nao_conecta(oc, capsys):
    assert oc.main(["gravar", "apagar"]) == 2
    assert oc.main(["formatar"]) == 2


def test_encaixa_ocupa_a_tela_inteira_e_corta_a_tarja(oc, falso):
    falso.estado["cena"] = "3 Só Webcam"
    with oc.Obs(falso.porta, PALAVRA) as o:
        cena, tam, feitos = oc.encaixa(o, (0, 90, 0, 90))
    assert cena == "3 Só Webcam" and tam == (1920, 1080) and feitos == ["Webcam do Celular"]  # o som nao e mexido
    envios = [d for tp, d in falso.dados if tp == "SetSceneItemTransform"]
    assert len(envios) == 1 and envios[0]["sceneItemId"] == 7
    tr = envios[0]["sceneItemTransform"]
    assert tr["boundsType"] == "OBS_BOUNDS_SCALE_OUTER" and (tr["boundsWidth"], tr["boundsHeight"]) == (1920.0, 1080.0)
    assert (tr["cropTop"], tr["cropBottom"], tr["cropLeft"], tr["cropRight"]) == (90, 90, 0, 0) and tr["positionX"] == 0.0


def test_encaixa_sem_fonte_do_celular_nao_mexe_em_nada(oc, falso):
    with oc.Obs(falso.porta, PALAVRA) as o:  # cena "1 Jogo": so o jogo
        assert oc.encaixa(o)[2] == []
    assert "SetSceneItemTransform" not in falso.pedidos
