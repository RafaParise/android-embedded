"""Testes do chaveador do Matrix (o programa Python que mora dentro de scripts/celular-kit/bin/ia, entre CHAVEADOR_FIM).

Ele escuta em 127.0.0.1 e manda cada pedido do Qwen ao OmniRoute do PC ou, se o PC cair, ao do celular (com a chave local).
Aqui o "PC" e a "reserva" sao servidores HTTP de teste em portas livres do proprio computador; nada toca rede nem celular.
"""
import json
import os
import pathlib
import re
import signal
import socket
import subprocess
import sys
import time

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
IA = RAIZ / "scripts" / "celular-kit" / "bin" / "ia"
pytestmark = pytest.mark.skipif(os.name == "nt", reason="o chaveador roda no Termux; os testes rodam no WSL")

SERVIDOR = r'''
import json, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
nome, porta, log = sys.argv[1], int(sys.argv[2]), sys.argv[3]
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self): self.responde()
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n); self.responde()
    def responde(self):
        with open(log, "a") as f:
            f.write(json.dumps({"de": nome, "auth": self.headers.get("Authorization"), "host": self.headers.get("Host"), "conn": self.headers.get("Connection")}) + "\n")
        corpo = json.dumps({"de": nome}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(corpo))); self.end_headers(); self.wfile.write(corpo)
ThreadingHTTPServer.allow_reuse_address = True
ThreadingHTTPServer(("127.0.0.1", porta), H).serve_forever()
'''


def codigo_do_chaveador():
    t = IA.read_text(encoding="utf-8")
    m = re.search(r"cat <<'CHAVEADOR_FIM'\n(.*?)\nCHAVEADOR_FIM\n", t, re.S)
    assert m, "o chaveador sumiu do ia"
    return m.group(1)


def porta_livre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def espera(cond, t=15):
    fim = time.time() + t
    while time.time() < fim:
        if cond():
            return True
        time.sleep(0.1)
    return False


def pede(porta, chave="chave-do-pc", corpo=b'{"model":"codigo"}', t=20):
    s = socket.create_connection(("127.0.0.1", porta), timeout=t)
    s.sendall(b"POST /v1/chat/completions HTTP/1.1\r\nHost: 127.0.0.1:20128\r\nAuthorization: Bearer " + chave.encode()
              + b"\r\nConnection: keep-alive\r\nContent-Type: application/json\r\nContent-Length: " + str(len(corpo)).encode() + b"\r\n\r\n" + corpo)
    dados = b""
    while True:
        d = s.recv(65536)
        if not d:
            break
        dados += d
    s.close()
    cab, _, resto = dados.partition(b"\r\n\r\n")
    return cab.decode(errors="replace"), resto


class Mundo:
    def __init__(self, base):
        self.base = base
        self.log = base / "pedidos.jsonl"
        self.log.write_text("")
        self.srv = base / "servidor.py"
        self.srv.write_text(SERVIDOR)
        self.prog = base / "chaveador.py"
        self.prog.write_text(codigo_do_chaveador())
        self.chave = base / "cliente-local.key"
        self.chave.write_text("chave-local\n")
        self.env_qwen = base / ".env"
        self.env_qwen.write_text("PONTE_PC_TOKEN=outro\nOMNIROUTE_API_KEY=chave-do-pc\n")
        self.pc_porta, self.loc_porta, self.porta = porta_livre(), porta_livre(), porta_livre()
        self.pc = None
        self.loc = None
        self.ch = None

    def liga_pc(self):
        self.pc = subprocess.Popen([sys.executable, str(self.srv), "pc", str(self.pc_porta), str(self.log)])
        assert espera(lambda: self.aberta(self.pc_porta))

    def desliga_pc(self):
        self.pc.kill(); self.pc.wait()
        assert espera(lambda: not self.aberta(self.pc_porta))

    def liga_local(self):
        self.loc = subprocess.Popen([sys.executable, str(self.srv), "celular", str(self.loc_porta), str(self.log)])
        assert espera(lambda: self.aberta(self.loc_porta))

    @staticmethod
    def aberta(p):
        try:
            socket.create_connection(("127.0.0.1", p), timeout=0.3).close()
            return True
        except OSError:
            return False

    def chaveador(self, inicio="pc", liga=True, **extra):
        # a "reserva": o comando de ligar sobe o servidor do celular e marca; o de desligar so marca
        pid = self.base / "reserva.pid"
        cmd_liga = f"/bin/sh -c '{sys.executable} {self.srv} celular {self.loc_porta} {self.log} & echo $! > {pid}; echo ligou >> {self.base}/marcas; sleep 0.8'"
        env = dict(os.environ, CH_PC=f"127.0.0.1:{self.pc_porta}", CH_LOCAL=f"127.0.0.1:{self.loc_porta}", CH_PORTA=str(self.porta),
                   CH_CHAVE_LOCAL=str(self.chave), CH_CHAVE_PC=str(self.env_qwen), CH_LIGA=cmd_liga if liga else "",
                   CH_DESLIGA=f"/bin/sh -c 'echo desligou >> {self.base}/marcas; kill $(cat {pid})'",
                   CH_ESTADO=str(self.base / "cerebro"), CH_INICIO=inicio, CH_INTERVALO="0.3", CH_CONECTA="0.5",
                   PATH="/usr/bin:/bin", CH_AVISO=f"/bin/sh -c 'echo \"$0\" >> {self.base}/avisos'", CH_ESPERA_LOCAL="10")
        env.update({k: str(v) for k, v in extra.items()})
        self.ch = subprocess.Popen([sys.executable, str(self.prog)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        assert espera(lambda: self.aberta(self.porta))

    def pedidos(self):
        return [json.loads(l) for l in self.log.read_text().splitlines() if l.strip()]

    def marcas(self):
        f = self.base / "marcas"
        return f.read_text().split() if f.exists() else []

    def avisos(self):
        f = self.base / "avisos"
        return f.read_text() if f.exists() else ""

    def cerebro(self):
        f = self.base / "cerebro"
        return f.read_text().split()[0] if f.exists() and f.read_text().strip() else ""

    def fecha(self):
        for p in (self.ch, self.pc, self.loc):
            if p and p.poll() is None:
                p.kill(); p.wait()
        pid = self.base / "reserva.pid"   # a reserva que o "ligar" subiu
        if pid.exists():
            try:
                os.kill(int(pid.read_text().strip()), signal.SIGKILL)
            except (OSError, ValueError):
                pass


@pytest.fixture
def mundo(tmp_path):
    m = Mundo(tmp_path)
    yield m
    m.fecha()


def test_com_o_pc_no_ar_o_pedido_vai_ao_pc_com_a_chave_do_pc_e_um_pedido_por_conexao(mundo):
    mundo.liga_pc()
    mundo.chaveador()
    cab, corpo = pede(mundo.porta)
    assert " 200 " in cab.splitlines()[0] and json.loads(corpo) == {"de": "pc"}
    assert "Connection: close" in cab   # 06/11: sem isso o Qwen reaproveitava a conexao e via "400 (no body)"
    p = mundo.pedidos()[-1]
    assert p["auth"] == "Bearer chave-do-pc" and p["host"] == f"127.0.0.1:{mundo.pc_porta}" and p["conn"] == "close"
    assert mundo.cerebro() == "pc" and mundo.marcas() == []   # a reserva nem foi ligada


def test_com_o_pc_fora_o_pedido_vai_a_reserva_com_a_chave_local_e_nunca_a_do_pc(mundo):
    mundo.liga_local()
    mundo.chaveador(inicio="local")
    cab, corpo = pede(mundo.porta)
    assert json.loads(corpo) == {"de": "celular"}
    p = mundo.pedidos()[-1]
    assert p["auth"] == "Bearer chave-local" and "chave-do-pc" not in json.dumps(mundo.pedidos())
    assert mundo.cerebro() == "local"


def test_pc_cai_no_meio_da_conversa_liga_a_reserva_sozinho_e_avisa(mundo):
    mundo.liga_pc()
    mundo.chaveador()
    assert json.loads(pede(mundo.porta)[1]) == {"de": "pc"}
    mundo.desliga_pc()
    assert espera(lambda: "ligou" in mundo.marcas())   # a vigia ja liga a reserva antes do proximo pedido
    assert json.loads(pede(mundo.porta)[1]) == {"de": "celular"}
    assert mundo.pedidos()[-1]["auth"] == "Bearer chave-local"
    assert mundo.cerebro() == "local" and espera(lambda: "PC fora" in mundo.avisos())


def test_pc_volta_o_chaveador_volta_ao_pc_e_desliga_a_reserva_parada(mundo):
    mundo.liga_pc()
    mundo.chaveador(CH_OCIOSO="0")
    mundo.desliga_pc()
    assert json.loads(pede(mundo.porta)[1]) == {"de": "celular"}
    mundo.liga_pc()
    assert espera(lambda: mundo.cerebro() == "pc")
    assert json.loads(pede(mundo.porta)[1]) == {"de": "pc"}
    assert espera(lambda: "desligou" in mundo.marcas()) and "PC de volta" in mundo.avisos()


def test_reserva_ociosa_fica_ligada_ate_o_tempo_acabar(mundo):
    mundo.liga_pc()
    mundo.chaveador(CH_OCIOSO="300")
    mundo.desliga_pc()
    pede(mundo.porta)
    mundo.liga_pc()
    assert espera(lambda: mundo.cerebro() == "pc")
    time.sleep(1)
    assert "desligou" not in mundo.marcas()


def test_sem_pc_e_sem_reserva_responde_503_explicando_e_nao_trava(mundo):
    mundo.chaveador(inicio="local", liga=False)
    cab, corpo = pede(mundo.porta, t=15)
    assert " 503 " in cab.splitlines()[0] and "ia status" in json.loads(corpo)["error"]["message"]


def test_reserva_que_recusa_ligar_nao_faz_esperar(mundo):
    mundo.chaveador(inicio="local", CH_LIGA="/bin/sh -c 'exit 1'", CH_ESPERA_LOCAL="60")
    t0 = time.time()
    cab, _ = pede(mundo.porta, t=30)
    assert " 503 " in cab.splitlines()[0] and time.time() - t0 < 10


def test_ao_ser_desligado_o_chaveador_desliga_a_reserva_que_ele_ligou(mundo):
    mundo.liga_pc()
    mundo.chaveador()
    mundo.desliga_pc()
    pede(mundo.porta)
    mundo.ch.send_signal(signal.SIGTERM)
    mundo.ch.wait(timeout=10)
    assert "desligou" in mundo.marcas()


def test_resposta_grande_chega_inteira(mundo, tmp_path):
    grande = tmp_path / "grande.py"
    grande.write_text(r'''
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        corpo = bytes(range(256)) * 2000
        self.send_response(200); self.send_header("Content-Length", str(len(corpo))); self.end_headers(); self.wfile.write(corpo)
ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
''')
    mundo.pc = subprocess.Popen([sys.executable, str(grande), str(mundo.pc_porta)])
    assert espera(lambda: mundo.aberta(mundo.pc_porta))
    mundo.chaveador()
    _, corpo = pede(mundo.porta, corpo=b"x" * 200000)
    assert corpo == bytes(range(256)) * 2000


def test_so_escuta_em_127_0_0_1_e_nao_usa_shell():
    t = codigo_do_chaveador()
    assert 'start_server(atende, "127.0.0.1", PORTA)' in t
    assert "shell=True" not in t and "create_subprocess_shell" not in t
    assert all(ord(c) < 128 for c in t)   # o ia vai colado no guia: so ASCII


def test_o_ia_so_usa_o_chaveador_com_a_reserva_pronta_e_permite_desligar():
    t = IA.read_text(encoding="utf-8")
    assert 'usa_chaveador() { [ "${IA_CHAVEADOR:-1}" != 0 ] && command -v python3 >/dev/null 2>&1 && gw_pronto; }' in t
    assert "export QWEN_CODE_NO_RELAUNCH=true" in t   # um node so, sem o supervisor


@pytest.mark.parametrize("chave", ["", "chave-errada", "chave-do-pc-e-mais", "chave-local"])
def test_sem_a_chave_do_matrix_recusa_401_sem_repassar_nem_ligar_a_reserva(mundo, chave):
    # outro app do celular abre a 20128: nao pode usar a reserva (nem a chave local injetada) sem saber a chave do Matrix
    mundo.liga_pc()
    mundo.chaveador(inicio="local")
    cab, corpo = pede(mundo.porta, chave=chave)
    assert " 401 " in cab.splitlines()[0] and "chave invalida" in corpo.decode()
    assert mundo.pedidos() == [] and mundo.marcas() == []


def test_sem_o_arquivo_da_chave_recusa_tudo(mundo):
    mundo.liga_pc()
    mundo.env_qwen.unlink()
    mundo.chaveador()
    cab, _ = pede(mundo.porta)
    assert " 401 " in cab.splitlines()[0] and mundo.pedidos() == []
