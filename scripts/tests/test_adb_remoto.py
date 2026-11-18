"""Testes do adb-remoto.py com adb e tailscale FALSOS (nenhum aparelho e tocado)."""
import importlib.util
import json
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "adb-remoto.py"
IP = "100.64.0.2"


class R:
    def __init__(self, rc=0, out=""):
        self.returncode, self.stdout, self.stderr = rc, out, ""


@pytest.fixture
def m():
    spec = importlib.util.spec_from_file_location("adb_remoto", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    e = {"cabo": False, "tcp": False, "porta_aberta": True, "chamadas": [], "ip": "100.99.1.2"}
    mod.estado = e

    def falso(cmd, **kw):
        e["chamadas"].append(cmd)
        if cmd[:2] == ["tailscale", "status"]:
            return R(0, json.dumps({"Peer": {"x": {"HostName": "samsung-a12", "TailscaleIPs": [e["ip"], "fd7a::1"]},
                                             "y": {"HostName": "outro", "TailscaleIPs": ["100.1.1.1"]}}}))
        if cmd[:2] == ["adb", "devices"]:
            linhas = ["List of devices attached"]
            if e["cabo"]:
                linhas.append("SERIAL0001\tdevice")
            if e["tcp"]:
                linhas.append(e["ip"] + ":5555\tdevice")
            return R(0, "\n".join(linhas) + "\n")
        if cmd[:2] == ["adb", "connect"]:
            e["tcp"] = e["porta_aberta"]
            return R(0, "connected to " + cmd[2] if e["porta_aberta"] else "failed to connect")
        if cmd[:2] == ["adb", "disconnect"]:
            e["tcp"] = False
            return R(0, "disconnected")
        return R(1, "")
    mod._executa = falso
    return mod


def test_ip_vem_da_tailscale(m):
    assert m.ip_celular() == "100.99.1.2"


def test_ip_reserva_sem_tailscale(m):
    m._executa = lambda cmd, **kw: R(1, "")
    assert m.ip_celular() == m.IP_RESERVA == IP


def test_com_cabo_usa_o_cabo_e_nao_conecta(m, capsys):
    m.estado["cabo"] = True
    assert m.main(["garantir"]) == 0
    assert capsys.readouterr().out.startswith("cabo")
    assert not [c for c in m.estado["chamadas"] if c[:2] == ["adb", "connect"]]


def test_cabo_e_tailnet_juntos_solta_a_tailnet(m):
    m.estado["cabo"] = m.estado["tcp"] = True
    assert m.main(["garantir"]) == 0
    assert ["adb", "disconnect", "100.99.1.2:5555"] in m.estado["chamadas"]


def test_sem_cabo_conecta_pela_tailscale(m, capsys):
    assert m.main(["garantir"]) == 0
    assert capsys.readouterr().out.startswith("tailscale-nova")
    assert ["adb", "connect", "100.99.1.2:5555"] in m.estado["chamadas"]


def test_ja_conectado_nao_e_nova(m, capsys):
    m.estado["tcp"] = True
    assert m.main(["garantir"]) == 0
    assert capsys.readouterr().out.startswith("tailscale\n")


def test_porta_fechada_falha_e_limpa(m, capsys):
    m.estado["porta_aberta"] = False
    assert m.main(["garantir"]) == 1
    assert "sem conexao" in capsys.readouterr().out


def test_soltar_so_mexe_na_tailnet(m):
    m.estado["cabo"] = m.estado["tcp"] = True
    m.main(["soltar"])
    desc = [c for c in m.estado["chamadas"] if c[:2] == ["adb", "disconnect"]]
    assert desc == [["adb", "disconnect", "100.99.1.2:5555"]]



class Proc:
    """Processo falso: termina com `rc` depois de `voltas` olhadas (ou quando o teste mandar)."""
    def __init__(self, cmd, rc, voltas):
        self.cmd, self.rc, self.voltas, self.terminado = cmd, rc, voltas, False

    def poll(self):
        if self.terminado:
            return 15
        self.voltas -= 1
        return self.rc if self.voltas < 0 else None

    def terminate(self):
        self.terminado = True

    def wait(self, timeout=None):
        return 15


def _espelho(m, roteiro, presentes, cabo=lambda: ""):
    """roteiro: lista de (rc, voltas) para cada abertura do programa."""
    m.OLHADA = 0.001
    m.TEMPO_TROCA = 0.5
    m.ESPERA = 0.01
    abertos, avisos = [], []
    fila = list(roteiro)
    escolhas = iter(presentes["escolhas"])
    e = m.Espelho(lambda: next(escolhas, (None, None)), lambda serial, tipo: ["scrcpy", "-s", serial, tipo], "RQ8", "cabo",
                  iniciar=lambda cmd, **kw: abertos.append(cmd) or Proc(cmd, *fila.pop(0)), aviso=avisos.append,
                  cabo=cabo, presentes=lambda: presentes["agora"])
    return e, abertos, avisos


def test_espelho_fechado_pela_pessoa_acaba_sem_trocar(m):
    e, abertos, _ = _espelho(m, [(0, 2)], {"agora": {"RQ8": "device"}, "escolhas": []})
    assert e.start().wait(5) == 0 and len(abertos) == 1


def test_espelho_cabo_solto_troca_para_o_sem_fio_e_continua(m):
    """12/11/2026: comecou no cabo, o cabo saiu (o scrcpy sai com 2): reabre pela Tailscale sozinho."""
    trocas = []
    e, abertos, avisos = _espelho(m, [(2, 2), (0, 3)], {"agora": {}, "escolhas": [("100.1.2.3:5555", "dados")]})
    e.ao_trocar = lambda s, t: trocas.append((s, t))
    assert e.start().wait(5) == 0
    assert abertos == [["scrcpy", "-s", "RQ8", "cabo"], ["scrcpy", "-s", "100.1.2.3:5555", "dados"]]
    assert trocas == [("100.1.2.3:5555", "dados")] and any("DADOS MOVEIS" in a for a in avisos)


def test_espelho_no_sem_fio_passa_ao_cabo_quando_ele_aparece(m):
    cabo = {"ligado": False}
    e, abertos, _ = _espelho(m, [(None, 10**9), (0, 2)], {"agora": {}, "escolhas": [("RQ8", "cabo")]},
                             cabo=lambda: "RQ8" if cabo["ligado"] else "")
    e.serial, e.tipo = "100.1.2.3:5555", "wifi"
    e.start()
    cabo["ligado"] = True
    assert e.wait(5) == 0 and abertos[-1] == ["scrcpy", "-s", "RQ8", "cabo"]


def test_espelho_sem_nenhuma_conexao_desiste(m):
    e, abertos, avisos = _espelho(m, [(2, 1)], {"agora": {}, "escolhas": []})
    assert e.start().wait(5) == 2 and len(abertos) == 1 and any("Nenhuma conexao" in a for a in avisos)


def test_espelho_erro_com_o_celular_presente_nao_fica_reabrindo(m):
    e, abertos, _ = _espelho(m, [(1, 1)], {"agora": {"RQ8": "device"}, "escolhas": [("RQ8", "cabo")]})
    assert e.start().wait(5) == 1 and len(abertos) == 1
