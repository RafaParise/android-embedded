"""Comando 'linux' do Termux, com proot-distro falso. Nada aqui fala com o celular."""
import os
import pathlib
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
LINUX = RAIZ / "celular-kit" / "bin" / "linux"


@pytest.fixture
def amb(tmp_path):
    prefixo = tmp_path / "usr"
    falsos = tmp_path / "falsos"
    falsos.mkdir()
    registro = tmp_path / "registro"
    falso = falsos / "proot-distro"
    falso.write_text(f'#!/bin/sh\necho "$@" >> "{registro}"\n', encoding="utf-8")
    falso.chmod(0o755)
    env = {**os.environ, "PREFIX": str(prefixo), "PATH": f"{falsos}:/usr/bin:/bin"}

    def roda(*a, entrada=""):
        p = subprocess.Popen(["/bin/sh", str(LINUX), *a], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        saida, erro = p.communicate(entrada, timeout=30)
        return p.returncode, saida + erro

    def instala():
        (prefixo / "var/lib/proot-distro/containers/debian").mkdir(parents=True)

    def registrado():
        return registro.read_text(encoding="utf-8") if registro.exists() else ""

    return roda, instala, registrado


def test_sem_debian_avisa_e_nao_chama(amb):
    roda, _, reg = amb
    cod, s = roda()
    assert cod == 1 and "nao instalado" in s
    assert reg() == ""


def test_c_sem_debian_recusa(amb):
    roda, _, reg = amb
    assert roda("-c", "ls")[0] == 1
    assert reg() == ""


def test_abre_o_debian(amb):
    roda, instala, reg = amb
    instala()
    assert roda()[0] == 0
    assert reg().strip() == "login debian --shared-tmp"


def test_c_passa_o_comando_inteiro(amb):
    roda, instala, reg = amb
    instala()
    assert roda("-c", "echo a", "b")[0] == 0
    assert reg().strip() == "login debian --shared-tmp -- /bin/bash -lc echo a b"


def test_status_conta_sem_duplicar(amb):
    roda, instala, _ = amb
    instala()
    cod, s = roda("status")
    assert cod == 0 and "Debian instalado" in s
    assert len([l for l in s.splitlines() if "Rodando agora" in l]) == 1
    assert "Rodando agora: 0 processo" in s or "Rodando agora: 1 processo" not in s


def test_remover_pede_a_palavra(amb):
    roda, instala, reg = amb
    instala()
    assert "Nada foi apagado" in roda("remover", entrada="sim\n")[1]
    assert reg() == ""
    roda("remover", entrada="APAGAR\n")
    assert reg().strip() == "remove debian"


def test_argumento_desconhecido(amb):
    roda, _, reg = amb
    assert roda("xyz")[0] == 2
    assert reg() == ""
