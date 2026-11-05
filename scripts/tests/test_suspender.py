"""Testes de scripts/suspender.py: nunca suspende pacote protegido; simulacao nao chama pm;
--aplicar/--restaurar sao mutuamente exclusivos; falha de verdade (estado nao mudou) vira FALHOU.
"""
import shutil
import sys
import types

import pytest

from conftest import SCRIPTS


def test_aborta_antes_de_qualquer_adb_se_pacote_protegido(importa_script, monkeypatch):
    mod = importa_script("suspender.py")
    shutil.copy(SCRIPTS / "lote-pacotes.py", mod.RAIZ / "scripts" / "lote-pacotes.py")

    def fake_run(cmd, **kw):
        raise AssertionError(f"nao deveria chamar adb: abortou antes ({cmd!r})")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["suspender.py", "com.android.vending"])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "protegido" in str(exc.value)


@pytest.mark.parametrize("nome", ["com.exemplo; reboot", "com.exemplo.app$(id)", "../x", "semponto", "com..exemplo", "com.exemplo."])
def test_nome_de_pacote_invalido_aborta_antes_do_adb(importa_script, monkeypatch, nome):
    """Revisao do Claude local (30/10): o nome vai direto para o shell do aparelho (pm suspend {p}); so passa nome de pacote de verdade."""
    mod = importa_script("suspender.py")
    shutil.copy(SCRIPTS / "lote-pacotes.py", mod.RAIZ / "scripts" / "lote-pacotes.py")

    def fake_run(cmd, **kw):
        raise AssertionError(f"nao deveria chamar adb: abortou antes ({cmd!r})")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["suspender.py", nome, "--aplicar"])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "nome de pacote invalido" in str(exc.value)


def test_aplicar_e_restaurar_sao_exclusivos(importa_script, monkeypatch):
    mod = importa_script("suspender.py")
    shutil.copy(SCRIPTS / "lote-pacotes.py", mod.RAIZ / "scripts" / "lote-pacotes.py")

    def fake_run(cmd, **kw):
        raise AssertionError(f"nao deveria chamar adb: abortou antes ({cmd!r})")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["suspender.py", "com.microsoft.teams", "--aplicar", "--restaurar"])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "ou --restaurar" in str(exc.value)


def test_simulacao_nunca_chama_pm_suspend(importa_script, monkeypatch, capsys):
    mod = importa_script("suspender.py")
    shutil.copy(SCRIPTS / "lote-pacotes.py", mod.RAIZ / "scripts" / "lote-pacotes.py")

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if c == "getprop ro.product.model":
            return types.SimpleNamespace(stdout="SM-A125M", stderr="")
        if c.startswith("dumpsys package"):
            return types.SimpleNamespace(stdout="", stderr="")
        if c.startswith("pm suspend") or c.startswith("pm unsuspend"):
            raise AssertionError(f"SIMULACAO nao deveria chamar pm suspend/unsuspend: {c!r}")
        raise AssertionError(f"comando nao mapeado no fake: {c!r}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["suspender.py", "com.microsoft.teams"])

    mod.main()

    assert "SIMULACAO" in capsys.readouterr().out


def test_aplicar_chama_pm_suspend_e_confirma_com_dumpsys_depois(importa_script, monkeypatch, capsys):
    mod = importa_script("suspender.py")
    shutil.copy(SCRIPTS / "lote-pacotes.py", mod.RAIZ / "scripts" / "lote-pacotes.py")
    suspenso = {"valor": False}
    chamadas = []

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        chamadas.append(c)
        if c == "getprop ro.product.model":
            return types.SimpleNamespace(stdout="SM-A125M", stderr="")
        if c == "pm list packages":
            return types.SimpleNamespace(stdout="package:com.microsoft.teams\npackage:org.fossify.phone", stderr="")
        if c == "settings get secure default_input_method":
            return types.SimpleNamespace(stdout="helium314.keyboard/.Ime", stderr="")
        if c.startswith("cmd role get-role-holders"):
            return types.SimpleNamespace(stdout="org.fossify.phone", stderr="")
        if c == "dumpsys package com.microsoft.teams":
            saida = "suspended=true" if suspenso["valor"] else "suspended=false"
            return types.SimpleNamespace(stdout=saida, stderr="")
        if c == "pm suspend com.microsoft.teams":
            suspenso["valor"] = True
            return types.SimpleNamespace(stdout="Package(s) suspended: com.microsoft.teams", stderr="")
        raise AssertionError(f"comando nao mapeado no fake: {c!r}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["suspender.py", "com.microsoft.teams", "--aplicar"])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0
    assert "pm suspend com.microsoft.teams" in chamadas
    assert "0 falhou" in capsys.readouterr().out


def _fake_aparelho(chamadas, instalados="package:org.fossify.phone\npackage:helium314.keyboard\npackage:com.exemplo.app"):
    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        chamadas.append(c)
        if c == "getprop ro.product.model":
            return types.SimpleNamespace(stdout="SM-A125M", stderr="")
        if c == "pm list packages":
            return types.SimpleNamespace(stdout=instalados, stderr="")
        if c == "settings get secure default_input_method":
            return types.SimpleNamespace(stdout="helium314.keyboard/.LatinIME", stderr="")
        if c == "cmd role get-role-holders --user 0 android.app.role.DIALER":
            return types.SimpleNamespace(stdout="org.fossify.phone", stderr="")
        if c.startswith("cmd role get-role-holders"):
            return types.SimpleNamespace(stdout="", stderr="")
        if c.startswith("dumpsys package"):
            return types.SimpleNamespace(stdout="suspended=false", stderr="")
        return types.SimpleNamespace(stdout="", stderr="")
    return fake_run


@pytest.mark.parametrize("pacote", ["helium314.keyboard", "org.fossify.phone"])
def test_aplicar_recusa_teclado_em_uso_e_discador_padrao(importa_script, monkeypatch, pacote):
    mod = importa_script("suspender.py")
    shutil.copy(SCRIPTS / "lote-pacotes.py", mod.RAIZ / "scripts" / "lote-pacotes.py")
    chamadas = []
    monkeypatch.setattr(mod.subprocess, "run", _fake_aparelho(chamadas))
    monkeypatch.setattr(sys, "argv", ["suspender.py", pacote, "--aplicar"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "teclado em uso" in str(exc.value)
    assert not any(c.startswith("pm suspend") for c in chamadas)


def test_restaurar_com_nome_errado_aborta_sem_chamar_unsuspend(importa_script, monkeypatch):
    mod = importa_script("suspender.py")
    shutil.copy(SCRIPTS / "lote-pacotes.py", mod.RAIZ / "scripts" / "lote-pacotes.py")
    chamadas = []
    monkeypatch.setattr(mod.subprocess, "run", _fake_aparelho(chamadas))
    monkeypatch.setattr(sys, "argv", ["suspender.py", "com.microsft.teams", "--restaurar"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "nao instalado" in str(exc.value)
    assert not any("unsuspend" in c for c in chamadas)


def test_aplicar_detecta_falha_de_verdade_quando_estado_nao_muda(importa_script, monkeypatch, capsys):
    """O proprio Android recusa suspender certos pacotes (launcher, IME ativo, etc.) -- pm suspend
    pode responder sem erro, mas o estado real nao muda. O script tem que pegar isso, nao confiar
    so na saida de texto do comando."""
    mod = importa_script("suspender.py")
    shutil.copy(SCRIPTS / "lote-pacotes.py", mod.RAIZ / "scripts" / "lote-pacotes.py")

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if c == "getprop ro.product.model":
            return types.SimpleNamespace(stdout="SM-A125M", stderr="")
        if c == "pm list packages":
            return types.SimpleNamespace(stdout="package:com.exemplo.recusado", stderr="")
        if c == "settings get secure default_input_method":
            return types.SimpleNamespace(stdout="helium314.keyboard/.Ime", stderr="")
        if c.startswith("cmd role get-role-holders"):
            return types.SimpleNamespace(stdout="org.fossify.phone", stderr="")
        if c == "dumpsys package com.exemplo.recusado":
            return types.SimpleNamespace(stdout="suspended=false", stderr="")  # nunca muda
        if c == "pm suspend com.exemplo.recusado":
            # Android recusa (launcher/discador/etc.) mas nao necessariamente com erro visivel
            return types.SimpleNamespace(stdout="Package(s) suspended: ", stderr="")
        raise AssertionError(f"comando nao mapeado no fake: {c!r}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["suspender.py", "com.exemplo.recusado", "--aplicar"])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    assert "1 falhou: com.exemplo.recusado" in capsys.readouterr().out


# Saida REAL do aparelho (A12, Android 12), medida em 30/10 com o Teams: 'pm suspend' responde
# "Package com.microsoft.teams new suspended state: true" e o dumpsys traz "User 0: ... suspended=<estado> ...".
_DUMPSYS_REAL = (
    "Packages:\n  Package [com.microsoft.teams] (a1b2c3):\n"
    "    User 0: ceDataInode=1223220 installed=true hidden=false suspended={estado} distractionFlags=0 stopped=false "
    "notLaunched=false enabled=0 instant=false virtual=false\n"
    "    Suspend params:\n      suspendingPackage=com.android.shell\n"
)


@pytest.mark.parametrize("estado,esperado", [("true", True), ("false", False)])
def test_esta_suspenso_le_a_linha_real_do_dumpsys_do_android_12(importa_script, monkeypatch, estado, esperado):
    mod = importa_script("suspender.py")
    monkeypatch.setattr(mod, "sh", lambda cmd, timeout=60: _DUMPSYS_REAL.format(estado=estado))
    assert mod.esta_suspenso("com.microsoft.teams") is esperado
