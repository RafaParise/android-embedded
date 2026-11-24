"""Testes de scripts/olhar-a12.py: qual conexão com o A12 ele escolhe (cabo, DMZ, Wi-Fi ou Tailscale)."""
import pytest


@pytest.fixture
def ol(importa_script):
    return importa_script("olhar-a12.py")


def test_cabo_usb_primeiro(ol):
    assert ol.escolher_serie("List of devices attached\n10.0.10.50:5555\tdevice\nRQ8\tdevice\n") == "RQ8"


def test_dmz_antes_da_tailscale(ol):
    assert ol.escolher_serie("List\n100.64.0.2:5555\tdevice\n10.0.10.50:5555\tdevice\n") == "10.0.10.50:5555"


def test_qualquer_sem_fio_pronto_e_nada_quando_offline(ol):
    assert ol.escolher_serie("List\n100.64.0.2:5555\tdevice\n") == "100.64.0.2:5555"
    assert ol.escolher_serie("List\n10.0.10.50:5555\toffline\nRQ8\tunauthorized\n") == ""
