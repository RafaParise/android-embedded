"""Testes de scripts/inventario.py: so leitura, nunca escreve no aparelho."""
import shutil
import sys
import types

import pytest

from conftest import SCRIPTS

ESCRITAS = ("pm disable", "pm enable", "pm grant", "pm revoke", "settings put",
            "sm partition", "device_config put", "cmd appops set")


def test_aborta_se_aparelho_inesperado(importa_script, monkeypatch):
    mod = importa_script("inventario.py")
    monkeypatch.setattr(sys, "argv", ["inventario.py"])

    def fake_run(cmd, **kw):
        return types.SimpleNamespace(stdout="SM-G960F", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "ABORTADO" in str(exc.value)


def test_so_le_e_isola_a_tabela(importa_script, monkeypatch, capsys):
    mod = importa_script("inventario.py")
    # protegidos() importa scripts/lote-pacotes.py pela RAIZ (ja isolada no tmp_path): precisa existir ali
    shutil.copy(SCRIPTS / "lote-pacotes.py", mod.RAIZ / "scripts" / "lote-pacotes.py")

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c == "pm list packages":
            saida = "package:com.termux\npackage:com.android.chrome"
        elif c == "pm list packages -d":
            saida = ""
        elif c == "pm list packages -s":
            saida = "package:com.android.chrome"
        elif c == "pm list packages -e":
            saida = "package:com.termux\npackage:com.android.chrome"
        elif c == "dumpsys usagestats":
            saida = ""  # sem uso registrado: ultimo_uso vazio para todos, sem crash no regex
        elif c == "dumpsys package":
            saida = ("Package [com.termux] (abc):\n"
                      "    android.permission.INTERNET: granted=true\n"
                      "Package [com.android.chrome] (def):\n"
                      "    android.permission.ACCESS_FINE_LOCATION: granted=true\n")
        elif c.startswith(ESCRITAS):
            raise AssertionError(f"inventario e so leitura, nao deveria chamar: {c!r}")
        else:
            saida = ""
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["inventario.py"])

    mod.main()

    saida = capsys.readouterr().out
    assert "pacotes: 2" in saida
    tabelas = list((mod.RAIZ / "diagnostico").glob("*/inventario.tsv"))
    assert len(tabelas) == 1
    linhas = tabelas[0].read_text(encoding="utf-8").splitlines()
    por_pacote = {l.split("\t")[0]: l for l in linhas[1:]}
    assert "sim" in por_pacote["com.android.chrome"]  # protegido (com.android.*) e com permissao de localizacao
    assert "com.termux" in por_pacote and "sim" not in por_pacote["com.termux"].split("\t")[-1]


def _usagestats(mod, monkeypatch, texto):
    monkeypatch.setattr(mod.subprocess, "run", lambda cmd, **kw: types.SimpleNamespace(stdout=texto, stderr=""))
    return mod.uso()


BLOCO = ('package=%s totalTimeUsed="%s" lastTimeUsed="2026-11-01 10:00:00" lastTimeVisible="2026-11-01 10:05:00" '
         'lastTimeForegroundServiceUsed="1969-12-31 21:00:00" totalTimeForegroundServiceUsed="00:00" appLaunchCount=%d')


def test_uso_le_totaltimeused_como_minutos_e_segundos(importa_script, monkeypatch):
    mod = importa_script("inventario.py")
    r = _usagestats(mod, monkeypatch, BLOCO % ("app.curto", "12:34", 3))
    assert r["app.curto"][1] == 12  # 12 min 34 s = 12 min, nao 754


def test_uso_le_totaltimeused_com_horas(importa_script, monkeypatch):
    mod = importa_script("inventario.py")
    r = _usagestats(mod, monkeypatch, BLOCO % ("app.longo", "1:02:03", 7))
    assert r["app.longo"] == ("2026-11-01 10:05:00", 62, 7)  # o bloco nao pode ser descartado
