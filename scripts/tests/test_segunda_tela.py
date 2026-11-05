"""Testes do segunda-tela.py com adb, tailscale, scrcpy e sc FALSOS (nada abre e nenhum aparelho e tocado)."""
import importlib.util
import json
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "segunda-tela.py"


class R:
    def __init__(self, rc=0, out=""):
        self.returncode, self.stdout, self.stderr = rc, out, ""


@pytest.fixture
def m():
    spec = importlib.util.spec_from_file_location("segunda_tela", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    e = {"cabo": True, "tcp": False, "sunshine": None, "chamadas": []}
    mod.estado = e

    def falso(cmd, **kw):
        e["chamadas"].append(cmd)
        if cmd[:2] == ["tailscale", "status"]:
            return R(0, json.dumps({"Peer": {"x": {"HostName": "samsung-a12", "TailscaleIPs": ["100.99.1.2"]}}}))
        if cmd[:2] == ["adb", "devices"]:
            ls = ["List of devices attached"] + (["RQ8\tdevice"] if e["cabo"] else []) + (["100.99.1.2:5555\tdevice"] if e["tcp"] else [])
            return R(0, "\n".join(ls) + "\n")
        if cmd[:2] == ["adb", "connect"]:
            e["tcp"] = True
            return R(0, "connected")
        if cmd[:2] == ["adb", "disconnect"]:
            e["tcp"] = False
            return R(0, "")
        if cmd[:2] == ["sc", "query"]:
            if e["sunshine"] is None:
                return R(1060, "nao existe")
            return R(0, "STATE: 4 RUNNING" if e["sunshine"] else "STATE: 1 STOPPED")
        return R(0, "")
    mod._executa = falso
    mod.scrcpy = lambda: "scrcpy.exe"
    mod.tamanho_monitor = lambda: (1440, 900)
    return mod


def scrcpys(m):
    return [c for c in m.estado["chamadas"] if c[0] == "scrcpy.exe"]


def test_celular_pelo_cabo(m):
    assert m.main(["celular"]) == 0
    (c,) = scrcpys(m)
    assert c[1:3] == ["-s", "RQ8"] and "--stay-awake" in c


def test_nunca_apaga_a_tela_do_celular(m):
    m.main(["celular"])
    m.main(["extra"])
    for c in scrcpys(m):
        assert not [a for a in c if "turn-screen-off" in a or a == "-S"]


def test_sem_cabo_vai_pela_tailscale_e_solta(m):
    m.estado["cabo"] = False
    assert m.main(["celular", "--leve"]) == 0
    (c,) = scrcpys(m)
    assert c[1:3] == ["-s", "100.99.1.2:5555"] and "--video-bit-rate=2M" in c and "--stay-awake" not in c
    assert m.estado["chamadas"][-1] == ["adb", "disconnect", "100.99.1.2:5555"]


def test_extra_cria_tela_nova_com_app(m):
    assert m.main(["extra", "--app", "org.fossify.notes"]) == 0
    (c,) = scrcpys(m)
    assert "--new-display=1440x900/160" in c and "--start-app=org.fossify.notes" in c


def test_extra_padrao_abre_o_navegador(m):
    m.main(["extra"])
    assert "--start-app=org.mozilla.fennec_fdroid" in scrcpys(m)[0]


@pytest.mark.parametrize("ruim", ["a;b", "x y", "../z", ""])
def test_app_com_nome_estranho_e_recusado(m, ruim):
    assert m.main(["extra", "--app", ruim]) == 2
    assert not scrcpys(m)


def test_pc_sem_sunshine_manda_instalar(m, capsys):
    assert m.main(["pc"]) == 2
    assert "segunda-tela-instalar.cmd" in capsys.readouterr().out


def test_pc_liga_o_sunshine_parado(m):
    m.estado["sunshine"] = False
    assert m.main(["pc"]) == 0
    assert ["sc", "start", "SunshineService"] in m.estado["chamadas"]


def test_sem_conexao_nao_abre(m):
    m.estado["cabo"] = False

    antigo = m._executa

    def recusa(cmd, **kw):
        if cmd[:2] == ["adb", "connect"]:
            m.estado["chamadas"].append(cmd)
            return R(1, "failed")
        return antigo(cmd, **kw)
    m._executa = recusa
    assert m.main(["celular"]) == 1
    assert not scrcpys(m)
