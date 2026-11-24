"""Testes do `ligar-pc` do Termux (scripts/celular-kit/bin/ligar-pc): para onde vai o pacote mágico em cada rede."""
import importlib.machinery
import importlib.util
import pathlib

import pytest

LIGAR = pathlib.Path(__file__).resolve().parent.parent / "celular-kit" / "bin" / "ligar-pc"


@pytest.fixture
def lp():
    carregador = importlib.machinery.SourceFileLoader("ligar_pc_kit", str(LIGAR))
    spec = importlib.util.spec_from_loader("ligar_pc_kit", carregador)
    m = importlib.util.module_from_spec(spec)
    carregador.exec_module(m)
    return m


def conf(lp, tmp_path, monkeypatch, **extra):
    import json
    c = {"mac": "AA:BB:CC:DD:EE:FF", "destinos": ["192.168.1.40"], "pc": "192.168.1.17", **extra}
    f = tmp_path / "ligar-pc.json"
    f.write_text(json.dumps(c), encoding="utf-8")
    monkeypatch.setattr(lp, "CONF", str(f))
    return lp.ler_conf()


def test_na_dmz_manda_tambem_ao_pc_na_rede_do_cabo(lp, tmp_path, monkeypatch):
    c = lp.com_dmz(conf(lp, tmp_path, monkeypatch), "10.0.10.50")
    assert c["alvos"][0][1] == ["10.0.20.100", "192.168.1.40"]


def test_no_wifi_de_casa_fica_so_o_que_o_json_diz(lp, tmp_path, monkeypatch):
    c = lp.com_dmz(conf(lp, tmp_path, monkeypatch), "192.168.1.4")
    assert c["alvos"][0][1] == ["192.168.1.40"]


def test_pc_confere_pela_tailscale_tambem(lp, tmp_path, monkeypatch):
    c = conf(lp, tmp_path, monkeypatch, pc_tailscale="100.1.2.3", pc_cabo="10.0.20.9")
    assert c["pcs"] == ["192.168.1.17", "100.1.2.3"]
    assert lp.com_dmz(c, "10.0.10.51")["alvos"][0][1][0] == "10.0.20.9"
    vistos = []
    monkeypatch.setattr(lp, "pc_no_ar", lambda ip, porta, prazo=2.0: vistos.append(ip) or ip == "100.1.2.3")
    assert lp.algum_no_ar(c) and vistos == ["192.168.1.17", "100.1.2.3"]
