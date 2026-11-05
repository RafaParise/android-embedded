"""Testes de scripts/privacidade.py: aborta em aparelho errado; simulacao nao muda nada;
aplicar/restaurar e reversivel (round-trip completo com adb falso)."""
import json
import sys
import types

import pytest


def test_aborta_se_aparelho_inesperado(importa_script, monkeypatch):
    mod = importa_script("privacidade.py")
    monkeypatch.setattr(sys, "argv", ["privacidade.py"])

    def fake_run(cmd, **kw):
        return types.SimpleNamespace(stdout="SM-G960F", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "ABORTADO" in str(exc.value)


def test_simulacao_nao_aplica_nada(importa_script, monkeypatch, capsys):
    mod = importa_script("privacidade.py")

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c == "pm list packages":
            saida = "package:com.instagram.android"  # waze, teams, chrome, w4b: ausentes
        elif c == "dumpsys package com.instagram.android":
            saida = "android.permission.ACCESS_FINE_LOCATION: granted=true\nandroid.permission.CAMERA: granted=true"
        elif c == "cmd appops get com.instagram.android RUN_ANY_IN_BACKGROUND":
            saida = "RUN_ANY_IN_BACKGROUND: allow"
        elif c.startswith(("pm revoke", "pm grant", "cmd appops set")):
            raise AssertionError(f"SIMULACAO nao deveria mudar nada: {c!r}")
        else:
            raise AssertionError(f"comando nao mapeado no fake: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["privacidade.py"])

    mod.main()

    saida = capsys.readouterr().out
    assert "SIMULACAO" in saida
    assert not list((mod.RAIZ / "diagnostico").glob("*/privacidade_antes.json"))


def test_aplicar_e_restaurar_e_reversivel(importa_script, monkeypatch, capsys):
    """--aplicar revoga so o que estava concedido (registrando em diagnostico/) e
    --restaurar devolve exatamente o que tinha antes, lendo o mesmo registro."""
    mod = importa_script("privacidade.py")
    concedido = {"ACCESS_FINE_LOCATION": True, "CAMERA": True}
    fundo = {"modo": "allow"}

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c == "pm list packages":
            saida = "package:com.instagram.android"
        elif c == "dumpsys package com.instagram.android":
            saida = "\n".join(
                f"android.permission.{p}: granted=true" for p, v in concedido.items() if v
            )
        elif c == "cmd appops get com.instagram.android RUN_ANY_IN_BACKGROUND":
            saida = f"RUN_ANY_IN_BACKGROUND: {fundo['modo']}"
        elif c == "pm revoke com.instagram.android android.permission.ACCESS_FINE_LOCATION":
            concedido["ACCESS_FINE_LOCATION"] = False
            saida = ""
        elif c == "pm revoke com.instagram.android android.permission.CAMERA":
            concedido["CAMERA"] = False
            saida = ""
        elif c == "cmd appops set com.instagram.android RUN_ANY_IN_BACKGROUND ignore":
            fundo["modo"] = "ignore"
            saida = ""
        elif c == "pm grant com.instagram.android android.permission.ACCESS_FINE_LOCATION":
            concedido["ACCESS_FINE_LOCATION"] = True
            saida = ""
        elif c == "pm grant com.instagram.android android.permission.CAMERA":
            concedido["CAMERA"] = True
            saida = ""
        elif c == "cmd appops set com.instagram.android RUN_ANY_IN_BACKGROUND allow":
            fundo["modo"] = "allow"
            saida = ""
        else:
            raise AssertionError(f"comando nao mapeado no fake: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    monkeypatch.setattr(sys, "argv", ["privacidade.py", "--aplicar"])
    mod.main()
    assert concedido == {"ACCESS_FINE_LOCATION": False, "CAMERA": False}
    assert fundo["modo"] == "ignore"
    registros = list((mod.RAIZ / "diagnostico").glob("*/privacidade_antes.json"))
    assert len(registros) == 1
    dados = json.loads(registros[0].read_text(encoding="utf-8"))
    assert sorted(dados["com.instagram.android"]["perms"]) == ["ACCESS_FINE_LOCATION", "CAMERA"]

    monkeypatch.setattr(sys, "argv", ["privacidade.py", "--restaurar"])
    mod.main()
    assert concedido == {"ACCESS_FINE_LOCATION": True, "CAMERA": True}
    assert fundo["modo"] == "allow"
    assert "restaurado" in capsys.readouterr().out


class Aparelho:
    """Celular falso com estado: permissoes do Instagram e modo de segundo plano. falha_revoke/falha_grant = permissoes que o pm recusa."""

    def __init__(self, falha_revoke=(), falha_grant=()):
        self.concedido = {"ACCESS_FINE_LOCATION": True, "CAMERA": True}
        self.fundo, self.comandos = "allow", []
        self.falha_revoke, self.falha_grant = set(falha_revoke), set(falha_grant)

    def __call__(self, cmd, **kw):
        c = cmd[2].strip()
        self.comandos.append(c)
        pkg = "com.instagram.android"
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c == "pm list packages":
            saida = "package:" + pkg
        elif c == f"dumpsys package {pkg}":
            saida = chr(10).join(f"android.permission.{p}: granted=true" for p, v in self.concedido.items() if v)
        elif c == f"cmd appops get {pkg} RUN_ANY_IN_BACKGROUND":
            saida = f"RUN_ANY_IN_BACKGROUND: {self.fundo}"
        elif c.startswith(f"pm revoke {pkg} android.permission."):
            p = c.rsplit(".", 1)[1]
            saida = "Exception: SecurityException" if p in self.falha_revoke else ""
            if not saida:
                self.concedido[p] = False
        elif c.startswith(f"pm grant {pkg} android.permission."):
            p = c.rsplit(".", 1)[1]
            saida = "Exception: SecurityException" if p in self.falha_grant else ""
            if not saida:
                self.concedido[p] = True
        elif c.startswith(f"cmd appops set {pkg} RUN_ANY_IN_BACKGROUND "):
            self.fundo = c.rsplit(" ", 1)[1]
            saida = ""
        else:
            raise AssertionError(f"comando nao mapeado no fake: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")


def test_segundo_aplicar_nao_esconde_o_registro_original(importa_script, monkeypatch):
    mod = importa_script("privacidade.py")
    ap = Aparelho()
    monkeypatch.setattr(mod.subprocess, "run", ap)
    monkeypatch.setattr(sys, "argv", ["privacidade.py", "--aplicar"])
    mod.main()
    time_stub = iter(["20991231-000001", "20991231-000002"])
    monkeypatch.setattr(mod.time, "strftime", lambda *_: next(time_stub))
    mod.main()  # segunda vez: nada novo a revogar
    monkeypatch.setattr(sys, "argv", ["privacidade.py", "--restaurar"])
    mod.main()
    assert ap.concedido == {"ACCESS_FINE_LOCATION": True, "CAMERA": True}
    assert ap.fundo == "allow"


def test_aplicar_com_revoke_que_falha_sai_com_erro(importa_script, monkeypatch, capsys):
    mod = importa_script("privacidade.py")
    ap = Aparelho(falha_revoke={"CAMERA"})
    monkeypatch.setattr(mod.subprocess, "run", ap)
    monkeypatch.setattr(sys, "argv", ["privacidade.py", "--aplicar"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code not in (0, None)
    saida = capsys.readouterr().out
    assert "CAMERA" in str(exc.value) or "CAMERA" in saida
    assert "aplicado;" not in saida


def test_restaurar_com_grant_que_falha_sai_com_erro(importa_script, monkeypatch, capsys):
    mod = importa_script("privacidade.py")
    ap = Aparelho(falha_grant={"CAMERA"})
    monkeypatch.setattr(mod.subprocess, "run", ap)
    monkeypatch.setattr(sys, "argv", ["privacidade.py", "--aplicar"])
    mod.main()
    monkeypatch.setattr(sys, "argv", ["privacidade.py", "--restaurar"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code not in (0, None)
    assert "CAMERA" in str(exc.value) or "CAMERA" in capsys.readouterr().out
