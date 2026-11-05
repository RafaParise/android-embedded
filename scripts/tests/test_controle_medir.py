"""Testes de scripts/controle-medir.py: achar so o controle, numeros certos e Wi-Fi sempre religado. O adb nunca e aberto."""
import subprocess

import pytest


@pytest.fixture
def cm(importa_script):
    return importa_script("controle-medir.py")


GETEVENT = """add device 1: /dev/input/event13
  name:     "GameSir-Nova Lite Consumer Control"
  events:
    KEY (0001): KEY_VOLUMEDOWN KEY_SYSRQ
add device 2: /dev/input/event12
  name:     "GameSir-Nova Lite"
  events:
    KEY (0001): BTN_GAMEPAD BTN_EAST BTN_NORTH
    ABS (0003): ABS_X ABS_Y
add device 3: /dev/input/event3
  name:     "sec_touchscreen"
  events:
    KEY (0001): BTN_TOUCH
add device 4: /dev/input/event15
  name:     "Generic X-Box pad"
  events:
    KEY (0001): BTN_A BTN_B
"""


def test_acha_so_os_controles(cm):
    assert cm.acha_controles(GETEVENT) == {"12": "GameSir-Nova Lite", "15": "Generic X-Box pad"}
    assert cm.acha_controles("") == {}


def test_barramento_separa_bluetooth_de_usb(cm):
    t = ("    11: GameSir-Nova Lite\n      Classes: GAMEPAD\n      Path: /dev/input/event12\n      Identifier: bus=0x0005, vendor=0x3537\n"
         "    20: Generic X-Box pad\n      Classes: GAMEPAD\n      Identifier: bus=0x0003, vendor=0x045e\n")
    assert cm.barramentos(t) == {"GameSir-Nova Lite": "Bluetooth", "Generic X-Box pad": "USB"}


def test_le_linha_do_getevent(cm):
    assert cm.le_linha("[   12345.678901] EV_SYN       SYN_REPORT           00000000\r\n") == (12345.678901, "EV_SYN", "SYN_REPORT", "00000000")
    assert cm.le_linha("add device 1") is None


def syn(*tempos):
    return [(t, "EV_SYN", "SYN_REPORT", "0") for t in tempos]


def test_intervalos_ignoram_a_mao_parada_e_outros_eventos(cm):
    ev = syn(1.000, 1.020, 2.000, 2.010) + [(2.02, "EV_ABS", "ABS_X", "1")]
    assert cm.intervalos(ev) == pytest.approx([10.0, 20.0])  # a parada de quase 1 s nao conta


def test_resumo_nao_inventa_numero_com_pouco_dado(cm):
    assert "sem numero confiavel" in cm.resumo([20.0] * 29)
    r = cm.resumo([10.0] * 50 + [20.0] * 49 + [40.0])
    assert "100 pacotes" in r and "pior 40" in r and "acima de 30 ms: 1.0%" in r


def test_botoes_conta_so_o_aperto(cm):
    ev = [(1.0, "EV_KEY", "BTN_GAMEPAD", "DOWN"), (1.1, "EV_KEY", "BTN_GAMEPAD", "UP"), (1.2, "EV_KEY", "BTN_GAMEPAD", "DOWN"), (1.3, "EV_ABS", "ABS_X", "DOWN")]
    assert cm.botoes(ev) == {"BTN_GAMEPAD": 2}


class FalsaEscuta:
    respostas = []

    def __init__(self, controles):
        self.ctl = controles

    def marca(self):
        return {}

    def desde(self, m):
        return {e: syn(*[1 + i * 0.02 for i in range(40)]) for e in self.ctl}

    def espera(self, m, alvo, limite):
        return self.respostas.pop(0)

    def fecha(self):
        pass


def prepara(cm, monkeypatch, respostas, falha=None):
    chamadas = []

    def falso(cmd, timeout=60):
        chamadas.append(cmd)
        if falha and cmd == falha:
            raise subprocess.TimeoutExpired(cmd, 1)
        return GETEVENT if cmd.startswith("getevent") else ""

    monkeypatch.setattr(cm, "adb", falso)
    monkeypatch.setattr(cm, "Escuta", FalsaEscuta)
    monkeypatch.setattr(cm.time, "sleep", lambda s: None)
    FalsaEscuta.respostas = list(respostas)
    return chamadas


def test_medida_simples_nao_mexe_em_nada(cm, monkeypatch, capsys):
    c = prepara(cm, monkeypatch, [True])
    assert cm.main([]) == 0
    assert not any("svc" in x for x in c)
    assert "mediana 20.0" in capsys.readouterr().out


def test_ninguem_mexeu_nao_toca_no_wifi(cm, monkeypatch):
    c = prepara(cm, monkeypatch, [False])
    assert cm.main(["--wifi"]) == 1
    assert not any("svc" in x for x in c)


def test_wifi_e_religado(cm, monkeypatch):
    c = prepara(cm, monkeypatch, [True, True])
    assert cm.main(["--wifi"]) == 0
    assert c.index("svc wifi disable") < c.index("svc wifi enable")


def test_wifi_e_religado_mesmo_com_falha_na_segunda_medida(cm, monkeypatch):
    c = prepara(cm, monkeypatch, [True])  # a segunda espera estoura (lista vazia) depois de desligar
    with pytest.raises(IndexError):
        cm.main(["--wifi"])
    assert "svc wifi enable" in c


def test_sem_controle_ou_sem_celular_sai_com_2(cm, monkeypatch, capsys):
    monkeypatch.setattr(cm, "adb", lambda cmd, timeout=60: "")
    assert cm.main([]) == 2
    assert "Nenhum controle" in capsys.readouterr().out

    def cai(cmd, timeout=60):
        raise OSError("adb")

    monkeypatch.setattr(cm, "adb", cai)
    assert cm.main([]) == 2
