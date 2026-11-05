"""Testes de scripts/sd-adotar.py (apaga o cartao: o mais perigoso do projeto).

O script roda tudo no nivel do modulo, sem 'if __name__ == "__main__"', entao e preciso
runpy.run_path (nao um import normal) com sys.argv e subprocess.run falsos ja no lugar
antes de rodar. subprocess.run e o mesmo objeto global que a fixture autouse do
conftest.py patcheia, entao o stub de cada teste so precisa sobrescreve-lo de novo.
"""
import runpy
import subprocess
import sys
import time
import types

import pytest

from conftest import SCRIPTS

CAMINHO = SCRIPTS / "sd-adotar.py"


@pytest.mark.parametrize("modo", ["private", "mixed"])
def test_adotar_e_recusado_antes_de_tocar_no_celular(monkeypatch, modo):
    """Ate com --confirmo-apagar: adotar corrompeu 1.412 arquivos em 28/10 e a decisao e nao adotar de novo."""
    monkeypatch.setattr(sys, "argv", ["sd-adotar.py", "--modo", modo, "--uuid", "", "--confirmo-apagar"])

    def fake_run(cmd, **kw):
        raise AssertionError(f"nao deveria falar com o celular: {cmd!r}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(CAMINHO), run_name="__main__")
    assert "ABORTADO" in str(exc.value) and "proibido" in str(exc.value)


def test_simulacao_nao_apaga_nem_particiona_nada(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sd-adotar.py", "--modo", "public", "--uuid", "1A2B-3C4D"])

    def fake_run(cmd, **kw):
        c = cmd[2]
        if c == "sm list-disks":
            saida = "disk:179,96"
        elif c == "sm list-volumes all":
            saida = "public:179,97,1A2B-3C4D"
        elif "DiskInfo" in c:
            saida = 'DiskInfo{disk:179,96}:\n  size=512000000000 flags=4 label="SD-Card"'
        elif "dumpsys battery" in c:
            saida = "  level: 55\n  USB powered: true"
        elif c.startswith("sm partition"):
            raise AssertionError(f"SIMULACAO nao deveria particionar/apagar: {c!r}")
        else:
            raise AssertionError(f"comando nao mapeado no fake: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(CAMINHO), run_name="__main__")
    assert "SIMULACAO" in str(exc.value)


def test_aborta_se_nao_tiver_exatamente_um_disco(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sd-adotar.py", "--modo", "public", "--uuid", ""])

    def fake_run(cmd, **kw):
        c = cmd[2]
        if c == "sm list-disks":
            return types.SimpleNamespace(stdout="disk:179,96 disk:179,97", stderr="")
        raise AssertionError(f"nao deveria chegar a checar outra coisa: {c!r}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(CAMINHO), run_name="__main__")
    assert "ABORTADO" in str(exc.value)


def test_aborta_com_bateria_abaixo_de_3_porcento(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sd-adotar.py", "--modo", "public", "--uuid", ""])

    def fake_run(cmd, **kw):
        c = cmd[2]
        if c == "sm list-disks":
            saida = "disk:179,96"
        elif c == "sm list-volumes all":
            saida = ""
        elif "DiskInfo" in c:
            saida = 'size=512000000000 label="SD"'
        elif "dumpsys battery" in c:
            saida = "  level: 2\n  USB powered: true"
        else:
            raise AssertionError(f"comando nao mapeado no fake: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(CAMINHO), run_name="__main__")
    assert "ABORTADO" in str(exc.value) and "bateria" in str(exc.value)


def test_aborta_sem_carregar_mesmo_com_bateria_alta(monkeypatch):
    """98% sem cabo tambem aborta: a trava e nivel E carregando, nao um ou outro."""
    monkeypatch.setattr(sys, "argv", ["sd-adotar.py", "--modo", "public", "--uuid", ""])

    def fake_run(cmd, **kw):
        c = cmd[2]
        if c == "sm list-disks":
            saida = "disk:179,96"
        elif c == "sm list-volumes all":
            saida = ""
        elif "DiskInfo" in c:
            saida = 'size=512000000000 label="SD"'
        elif "dumpsys battery" in c:
            saida = "  level: 98\n  USB powered: false\n  AC powered: false"
        else:
            raise AssertionError(f"comando nao mapeado no fake: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(CAMINHO), run_name="__main__")
    assert "ABORTADO" in str(exc.value) and "bateria" in str(exc.value)


def test_confirmo_apagar_so_particiona_depois_de_todos_os_portoes(monkeypatch):
    """Caminho --confirmo-apagar inteiro, 100% com adb falso: sm partition so pode ser
    chamado depois de disco unico, tamanho+flag SD e bateria >=3% carregando."""
    monkeypatch.setattr(sys, "argv",
                         ["sd-adotar.py", "--modo", "public", "--uuid", "1A2B-3C4D", "--confirmo-apagar"])
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    chamadas = []

    def fake_run(cmd, **kw):
        c = cmd[2]
        chamadas.append(c)
        if c == "sm list-disks":
            saida = "disk:179,96"
        elif c == "sm list-volumes all":
            saida = "public:179,97,1A2B-3C4D"
        elif "DiskInfo" in c:
            saida = 'size=512000000000 label="SD"'
        elif "dumpsys battery" in c:
            saida = "  level: 80\n  AC powered: true"
        elif c.startswith("sm partition"):
            # cada portao (disco unico, UUID, tamanho+SD, bateria) tem de ter sido lido ANTES, nesta ordem
            ordem = [chamadas.index(x) for x in
                     ("sm list-disks", "sm list-volumes all")] +                     [next(i for i, x in enumerate(chamadas) if "DiskInfo" in x),
                     next(i for i, x in enumerate(chamadas) if "dumpsys battery" in x)]
            assert ordem == sorted(ordem), f"portoes fora de ordem: {chamadas!r}"
            saida = "Success"
        else:
            saida = ""
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runpy.run_path(str(CAMINHO), run_name="__main__")

    assert any(c.startswith("sm partition disk:179,96 public") for c in chamadas)


@pytest.mark.parametrize("saida_partition, volumes", [
    ("[timeout]", ""),
    ("Error: failed", "disk-sem-volume"),
    ("Success", "public:179,97 unmountable"),
])
def test_particao_que_nao_resulta_em_volume_public_sai_com_falhou(monkeypatch, saida_partition, volumes):
    """Depois do sm partition so vale como portatil se aparecer um volume public: montavel; senao FALHOU, codigo != 0."""
    monkeypatch.setattr(sys, "argv",
                         ["sd-adotar.py", "--modo", "public", "--uuid", "", "--confirmo-apagar"])
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    apos = {"particionou": False}

    def fake_run(cmd, **kw):
        c = cmd[2]
        if c.startswith("sm partition"):
            apos["particionou"] = True
            saida = saida_partition
        elif c == "sm list-disks":
            saida = "disk:179,96"
        elif c == "sm list-volumes all":
            saida = volumes if apos["particionou"] else ""
        elif "DiskInfo" in c:
            saida = 'size=512000000000 label="SD"'
        elif "dumpsys battery" in c:
            saida = "  level: 80\n  AC powered: true"
        else:
            saida = ""
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(CAMINHO), run_name="__main__")
    assert apos["particionou"]
    assert "FALHOU" in str(exc.value)
