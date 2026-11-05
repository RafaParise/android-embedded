"""Testes do depuracao-sem-fio.py com adb FALSO (nenhum aparelho e tocado)."""
import importlib.util
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "depuracao-sem-fio.py"


@pytest.fixture
def m():
    spec = importlib.util.spec_from_file_location("depuracao_sem_fio", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.estado_falso = {"cabo": True, "valor": "0", "chamadas": []}

    def falso(cmd, **kw):
        e = mod.estado_falso
        e["chamadas"].append(cmd)
        if cmd[1:] == ["get-state"]:
            return type("R", (), {"returncode": 0 if e["cabo"] else 1, "stdout": "device" if e["cabo"] else ""})()
        if cmd[1:4] == ["shell", "settings", "put"]:
            e["valor"] = cmd[-1]
        return type("R", (), {"returncode": 0, "stdout": e["valor"] + "\n"})()
    mod._executa = falso
    return mod


def test_ligar_liga_e_confere(m, capsys):
    assert m.main(["ligar"]) == 0
    assert m.estado_falso["valor"] == "1" and "LIGADA" in capsys.readouterr().out
    assert ["adb", "shell", "settings", "put", "global", "adb_wifi_enabled", "1"] in m.estado_falso["chamadas"]


def test_status_nao_muda_nada(m):
    assert m.main(["status"]) == 1
    assert not [c for c in m.estado_falso["chamadas"] if "put" in c]


def test_ja_ligada_nao_regrava(m):
    m.estado_falso["valor"] = "1"
    assert m.main(["ligar"]) == 0
    assert not [c for c in m.estado_falso["chamadas"] if "put" in c]


def test_sem_cabo_nao_faz_nada(m, capsys):
    m.estado_falso["cabo"] = False
    assert m.main(["ligar"]) == 2
    assert "cabo" in capsys.readouterr().out and len(m.estado_falso["chamadas"]) == 1


def test_comando_desconhecido_nao_roda(m):
    assert m.main(["desligar"]) == 2 and not m.estado_falso["chamadas"]


def test_porta5555_ja_ligada_nao_reinicia_o_adb(m, capsys):
    m.estado_falso["valor"] = "5555"
    assert m.main(["porta5555"]) == 0
    assert "LIGADA" in capsys.readouterr().out
    assert not [c for c in m.estado_falso["chamadas"] if "tcpip" in c]


def test_porta5555_sem_cabo(m):
    m.estado_falso["cabo"] = False
    assert m.main(["porta5555"]) == 2
