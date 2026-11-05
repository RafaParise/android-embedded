"""Testes de scripts/ajustes-script.py: aborta em aparelho errado; simulacao nao escreve nada."""
import sys
import types

import pytest


def test_aplicar_cobre_todas_as_settings_sem_pular_nenhuma(importa_script, monkeypatch):
    """Revisao de 30/10: aplicar() tinha uma condicao morta (a.dns_so, vestigio de um
    parametro nunca alcancavel nesse ponto do fluxo) que parecia pular settings mas nunca
    pulava de verdade. Removida; este teste trava que TODAS as SETTINGS sejam aplicadas."""
    mod = importa_script("ajustes-script.py")
    aplicadas = []

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if c.startswith("settings put"):
            aplicadas.append(c)
        return types.SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    mod.aplicar()

    chaves_esperadas = {f"settings put {ns} {k} {v}" for ns, k, v in mod.SETTINGS}
    assert set(aplicadas) == chaves_esperadas


def test_aborta_se_aparelho_inesperado(importa_script, monkeypatch):
    mod = importa_script("ajustes-script.py")
    monkeypatch.setattr(sys, "argv", ["ajustes-script.py"])

    def fake_run(cmd, **kw):
        return types.SimpleNamespace(stdout="SM-G960F", stderr="")  # outro aparelho

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "ABORTADO" in str(exc.value)


def test_simulacao_nao_aplica_nada(importa_script, monkeypatch, capsys):
    mod = importa_script("ajustes-script.py")

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c.startswith("settings get"):
            saida = "null"
        elif c.startswith("cmd appops get"):
            op = c.split()[4]  # cmd appops get PKG OP
            saida = f"{op}: allow"
        elif c.startswith("dumpsys package"):
            saida = ""
        elif c.startswith("am get-standby-bucket"):
            saida = "10"
        elif c == "dumpsys deviceidle whitelist":
            saida = ""
        elif c.startswith("device_config get"):
            saida = "null"
        elif c == "device_config is_sync_disabled_for_tests":
            saida = "false"
        elif c.startswith(("settings put", "cmd appops set", "pm grant", "pm revoke",
                            "am set-standby-bucket", "dumpsys deviceidle whitelist +",
                            "device_config put", "device_config set_sync_disabled_for_tests")):
            raise AssertionError(f"SIMULACAO nao deveria escrever nada: {c!r}")
        else:
            raise AssertionError(f"comando nao mapeado no fake: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["ajustes-script.py"])

    mod.main()

    saida = capsys.readouterr().out
    assert "SIMULACAO" in saida
    assert "RUN_IN_BACKGROUND" in saida and "allow" in saida  # a regex do script casou "OP: allow" (antes o fake devolvia o pacote)
    assert not list((mod.RAIZ / "diagnostico").glob("*/ajustes_antes.json"))


def test_leitura_do_estado_anterior_que_falha_aborta_sem_gravar_registro_nem_escrever(importa_script, monkeypatch):
    """adb que falha (cabo mexido) devolve texto de erro: ele nao pode virar 'valor anterior' do registro de desfazer."""
    mod = importa_script("ajustes-script.py")
    escritas = []
    leituras = {"n": 0}

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if c == "getprop ro.product.model":
            return types.SimpleNamespace(returncode=0, stdout="SM-A125M", stderr="")
        if c.startswith(("settings put", "cmd appops set", "pm grant", "am set-standby-bucket", "device_config put")):
            escritas.append(c)
        if c.startswith("settings get"):
            leituras["n"] += 1
            if leituras["n"] == 2:
                return types.SimpleNamespace(returncode=1, stdout="", stderr="error: closed")
        return types.SimpleNamespace(returncode=0, stdout="null", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["ajustes-script.py", "--aplicar"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "ABORTADO" in str(exc.value) and "error: closed" in str(exc.value)
    assert escritas == []
    assert not list((mod.RAIZ / "diagnostico").glob("*/ajustes_antes.json"))
