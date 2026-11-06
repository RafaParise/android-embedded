#!/usr/bin/env python3
"""Controla o OBS ABERTO por comando (obs-websocket 5, que vem dentro do OBS 28+), so neste PC (127.0.0.1).

  python scripts/obs-controle.py status
  python scripts/obs-controle.py camera-virtual ligar|desligar
  python scripts/obs-controle.py gravar iniciar|parar|status
  python scripts/obs-controle.py transmitir iniciar|parar|status   (a chave da live o Rafael poe no OBS; este script nunca a le)
  python scripts/obs-controle.py cenas
  python scripts/obs-controle.py cena "3 So Webcam"

Por que existe (05/11/2026): na aula do CMSP Web o OBS do Estudio estava aberto SEM a camera virtual ligada e o site
mostrava a imagem de espera do OBS (logo + camera riscada). Agora o webcam-celular.py liga a camera virtual sozinho.
Seguranca: o websocket do OBS fica ligado com senha (config do proprio OBS, %APPDATA%/obs-studio/plugin_config/obs-websocket)
e o firewall BLOQUEIA a entrada de fora no obs64.exe (regra "OBS so local (bloqueia entrada)"); este script so fala com
127.0.0.1 e nunca imprime a senha. Saida: 0 = ok; 1 = o OBS recusou; 2 = OBS fechado ou websocket desligado.
"""
import base64
import hashlib
import json
import os
import pathlib
import socket
import struct
import sys

HOST = "127.0.0.1"
CONFIG = pathlib.Path(os.environ.get("APPDATA", "")) / "obs-studio" / "plugin_config" / "obs-websocket" / "config.json"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


class ErroObs(Exception):
    pass


def le_config(caminho=None):
    p = pathlib.Path(caminho) if caminho else CONFIG
    try:
        c = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise ErroObs("config do obs-websocket nao encontrada: abra o OBS uma vez")
    if not c.get("server_enabled"):
        raise ErroObs("o websocket do OBS esta desligado (OBS > Ferramentas > Configuracoes do WebSocket)")
    return int(c.get("server_port", 4455)), (c.get("server_password") or "") if c.get("auth_required", True) else ""


def resposta_auth(senha, sal, desafio):
    """obs-websocket 5: base64(sha256(base64(sha256(senha + sal)) + desafio))."""
    segredo = base64.b64encode(hashlib.sha256((senha + sal).encode()).digest()).decode()
    return base64.b64encode(hashlib.sha256((segredo + desafio).encode()).digest()).decode()


def quadro(texto, mascara=None):
    """Quadro de texto do WebSocket (cliente sempre mascara, RFC 6455)."""
    dados = texto.encode("utf-8")
    mascara = mascara if mascara is not None else os.urandom(4)
    n = len(dados)
    cab = bytes([0x81])
    if n < 126:
        cab += bytes([0x80 | n])
    elif n < 65536:
        cab += bytes([0x80 | 126]) + struct.pack(">H", n)
    else:
        cab += bytes([0x80 | 127]) + struct.pack(">Q", n)
    return cab + mascara + bytes(b ^ mascara[i % 4] for i, b in enumerate(dados))


class Obs:
    def __init__(self, porta=None, senha=None, tempo=8.0, config=None):
        if porta is None:
            porta, senha = le_config(config)
        self.porta, self.senha, self.tempo = porta, senha or "", tempo
        self.s = None
        self.buf = b""
        self.n = 0

    # ---- transporte
    def _le(self, n):
        while len(self.buf) < n:
            d = self.s.recv(65536)
            if not d:
                raise ErroObs("o OBS fechou a conexao")
            self.buf += d
        r, self.buf = self.buf[:n], self.buf[n:]
        return r

    def _recebe(self):
        partes = b""
        while True:
            b0, b1 = self._le(2)
            op, n = b0 & 0x0F, b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._le(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._le(8))[0]
            m = self._le(4) if b1 & 0x80 else None
            dados = self._le(n)
            if m:
                dados = bytes(b ^ m[i % 4] for i, b in enumerate(dados))
            if op == 0x8:
                raise ErroObs("o OBS encerrou a conexao (senha errada?)")
            if op == 0x9:  # ping -> pong
                self.s.sendall(bytes([0x8A, 0x80 | len(dados)]) + b"\0\0\0\0" + dados)
                continue
            if op in (0x1, 0x0):
                partes += dados
                if b0 & 0x80:
                    return json.loads(partes.decode("utf-8"))

    def _envia(self, obj):
        self.s.sendall(quadro(json.dumps(obj)))

    def conecta(self):
        try:
            self.s = socket.create_connection((HOST, self.porta), timeout=self.tempo)
        except OSError:
            raise ErroObs("o OBS esta fechado (ou o websocket desligado)")
        chave = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET / HTTP/1.1\r\nHost: {HOST}:{self.porta}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {chave}\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: obswebsocket.json\r\n\r\n").encode())
        while b"\r\n\r\n" not in self.buf:
            d = self.s.recv(4096)
            if not d:
                raise ErroObs("o OBS recusou a conexao")
            self.buf += d
        cab, self.buf = self.buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in cab.split(b"\r\n", 1)[0]:
            raise ErroObs("o OBS recusou o websocket")
        ola = self._recebe()
        ident = {"rpcVersion": 1, "eventSubscriptions": 0}
        auth = ola.get("d", {}).get("authentication")
        if auth:
            if not self.senha:
                raise ErroObs("o OBS pede senha e a config nao tem")
            ident["authentication"] = resposta_auth(self.senha, auth["salt"], auth["challenge"])
        self._envia({"op": 1, "d": ident})
        r = self._recebe()
        if r.get("op") != 2:
            raise ErroObs("o OBS nao aceitou a identificacao")
        return self

    def pede(self, tipo, dados=None):
        self.n += 1
        rid = f"r{self.n}"
        self._envia({"op": 6, "d": {"requestType": tipo, "requestId": rid, **({"requestData": dados} if dados else {})}})
        while True:
            r = self._recebe()
            if r.get("op") == 7 and r["d"].get("requestId") == rid:
                st = r["d"].get("requestStatus", {})
                if not st.get("result"):
                    raise ErroObs(f"{tipo}: {st.get('comment') or 'recusado'} (codigo {st.get('code')})")
                return r["d"].get("responseData") or {}

    def fecha(self):
        if self.s:
            try:
                self.s.close()
            except OSError:
                pass

    def __enter__(self):
        return self.conecta()

    def __exit__(self, *a):
        self.fecha()


# ---- operacoes usadas tambem pelo webcam-celular.py
def camera_virtual(obs, ligar=True):
    ativa = obs.pede("GetVirtualCamStatus").get("outputActive")
    if ligar and not ativa:
        obs.pede("StartVirtualCam")
        return "ligada agora"
    if not ligar and ativa:
        obs.pede("StopVirtualCam")
        return "desligada agora"
    return "ja estava ligada" if ativa else "ja estava desligada"


def cena_com_webcam(obs):
    """Garante que a cena NO AR mostra a janela do scrcpy: se a atual nao tem, troca para a 1a cena que tem 'Webcam' no nome."""
    atual = obs.pede("GetCurrentProgramScene").get("currentProgramSceneName", "")
    itens = obs.pede("GetSceneItemList", {"sceneName": atual}).get("sceneItems", [])
    nomes = [i.get("sourceName", "") for i in itens]
    if any("webcam" in n.lower() or "scrcpy" in n.lower() or "celular" in n.lower() for n in nomes):
        return atual, False
    cenas = [c["sceneName"] for c in obs.pede("GetSceneList").get("scenes", [])]
    for c in sorted(cenas):
        if "webcam" in c.lower() and "jogo" not in c.lower():
            obs.pede("SetCurrentProgramScene", {"sceneName": c})
            return c, True
    return atual, False


def gravar(obs, acao):
    st = obs.pede("GetRecordStatus")
    if acao == "iniciar":
        if st.get("outputActive"):
            return "ja estava gravando"
        obs.pede("StartRecord")
        pasta = obs.pede("GetRecordDirectory").get("recordDirectory", "?")
        return f"gravando (pasta: {pasta})"
    if acao == "parar":
        if not st.get("outputActive"):
            return "nao estava gravando"
        r = obs.pede("StopRecord")
        return f"gravacao salva: {r.get('outputPath', '?')}"
    return f"gravando ha {st.get('outputTimecode', '?')}" if st.get("outputActive") else "parado"


def transmitir(obs, acao):
    st = obs.pede("GetStreamStatus")
    if acao == "iniciar":
        if st.get("outputActive"):
            return "a live ja estava no ar"
        obs.pede("StartStream")
        return "live iniciada (destino e chave sao os que o Rafael configurou no OBS)"
    if acao == "parar":
        if not st.get("outputActive"):
            return "nao havia live no ar"
        obs.pede("StopStream")
        return "live encerrada"
    return f"live no ar ha {st.get('outputTimecode', '?')}" if st.get("outputActive") else "sem live"


def status(obs):
    v = obs.pede("GetVersion")
    linhas = [f"OBS {v.get('obsVersion', '?')} (websocket {v.get('obsWebSocketVersion', '?')})",
              f"cena no ar: {obs.pede('GetCurrentProgramScene').get('currentProgramSceneName', '?')}",
              f"camera virtual: {'LIGADA' if obs.pede('GetVirtualCamStatus').get('outputActive') else 'desligada'}",
              f"gravacao: {gravar(obs, 'status')}", f"live: {transmitir(obs, 'status')}"]
    return "\n".join(linhas)


USO = __doc__.split("\n\n")[1]


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a:
        print(USO)
        return 2
    cmd, resto = a[0], a[1:]
    validos = {"status": [], "cenas": [], "camera-virtual": ["ligar", "desligar"], "gravar": ["iniciar", "parar", "status"],
               "transmitir": ["iniciar", "parar", "status"], "cena": None}
    if cmd not in validos or (validos[cmd] and (len(resto) != 1 or resto[0] not in validos[cmd])) or (cmd == "cena" and len(resto) != 1):
        print(USO)
        return 2
    try:
        with Obs() as obs:
            if cmd == "status":
                print(status(obs))
            elif cmd == "cenas":
                print("\n".join(c["sceneName"] for c in reversed(obs.pede("GetSceneList").get("scenes", []))))
            elif cmd == "camera-virtual":
                print("camera virtual:", camera_virtual(obs, resto[0] == "ligar"))
            elif cmd == "gravar":
                print(gravar(obs, resto[0]))
            elif cmd == "transmitir":
                print(transmitir(obs, resto[0]))
            elif cmd == "cena":
                obs.pede("SetCurrentProgramScene", {"sceneName": resto[0]})
                print("cena no ar:", resto[0])
        return 0
    except ErroObs as e:
        print("OBS:", e)
        return 2 if "fechado" in str(e) or "desligado" in str(e) or "config" in str(e) else 1


if __name__ == "__main__":
    sys.exit(main())
