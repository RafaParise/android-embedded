"""Testes de scripts/sonda-a12.py: sonda SOMENTE LEITURA, sem --aplicar nem flag nenhuma.

Sem 'if __name__' (roda tudo ao importar), e grava diagnostico/ a partir de uma RAIZ
calculada de __file__ (nao de uma variavel que de para sobrescrever depois). Por isso a
copia do script vai para scripts/ dentro de um tmp_path ANTES do runpy.run_path: assim
RAIZ e a pasta diagnostico/ caem no tmp, nunca no repositorio real. ADB = shutil.which
("adb") or <caminho absoluto> igual ao sd-adotar.py (NUVEM.md secao 5): com o PATH vazio
da fixture autouse, tambem cai no .exe absoluto, e quem bloqueia de verdade e o
subprocess.run falso.
"""
import runpy
import shutil
import subprocess
import sys
import types

from conftest import SCRIPTS

ESCRITAS = ("pm disable", "pm enable", "pm grant", "pm revoke", "settings put",
            "sm partition", "sm mount", "device_config put", "cmd appops set", "bmgr")


def _copia_isolada(tmp_path):
    raiz = tmp_path / "raiz"
    (raiz / "scripts").mkdir(parents=True)
    destino = raiz / "scripts" / "sonda-a12.py"
    shutil.copy(SCRIPTS / "sonda-a12.py", destino)
    return raiz, destino


def test_sonda_nunca_escreve_no_aparelho_e_isola_o_diagnostico(monkeypatch, tmp_path, capsys):
    raiz, caminho = _copia_isolada(tmp_path)
    monkeypatch.setattr(sys, "argv", ["sonda-a12.py"])

    chamados = []

    def fake_run(cmd, **kw):
        if len(cmd) == 2 and cmd[1] == "devices":
            return types.SimpleNamespace(stdout="List of devices attached\nABC123\tdevice\n", stderr="")
        c = cmd[2].strip()
        chamados.append(c)  # o sh() da sonda engole excecoes: a prova e a lista, nao um raise
        if c.startswith("getprop "):
            saida = {"ro.product.model": "SM-A125M", "ro.build.version.release": "12"}.get(
                c.split(" ", 1)[1], "valor-teste")
        elif c == "pm list packages":
            saida = "package:com.termux\npackage:io.github.rafaparise.arena"
        elif c in ("pm list packages -d", "pm list packages -3"):
            saida = ""
        elif c.startswith("dumpsys diskstats"):
            saida = ("App Size: 0\nApp Data Size: 0\nApp Cache Size: 0\nPhotos Size: 0\n"
                      "Videos Size: 0\nSystem Size: 0\nOther Size: 0\n"
                      "Package Names: []\nApp Sizes: []\nApp Data Sizes: []\nCache Sizes: []")
        else:
            saida = ""  # demais leituras (settings get, dumpsys battery/meminfo, df, sm list-volumes, ime list, uname -r...): vazio basta
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runpy.run_path(str(caminho), run_name="__main__")

    saida = capsys.readouterr().out
    assert "SM-A125M" in saida
    assert chamados, "a sonda nao chamou nada: o fake nao foi exercitado"
    escritas = [c for c in chamados if c.startswith(ESCRITAS)]
    assert not escritas, f"a sonda e so leitura, mas chamou: {escritas!r}"
    # prova que a isolacao funcionou: a sonda grava, mas so dentro do tmp, nunca no repo real
    assert list((raiz / "diagnostico").glob("*/sonda.json"))


def test_sonda_aborta_sem_aparelho_autorizado(monkeypatch, tmp_path):
    _raiz, caminho = _copia_isolada(tmp_path)
    monkeypatch.setattr(sys, "argv", ["sonda-a12.py"])

    def fake_run(cmd, **kw):
        if len(cmd) == 2 and cmd[1] == "devices":
            return types.SimpleNamespace(stdout="List of devices attached\n", stderr="")
        raise AssertionError(f"nao deveria ler nada sem aparelho autorizado: {cmd!r}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    try:
        runpy.run_path(str(caminho), run_name="__main__")
        raise AssertionError("deveria ter saido com SystemExit (nenhum aparelho autorizado)")
    except SystemExit as exc:
        assert "aparelho" in str(exc)
