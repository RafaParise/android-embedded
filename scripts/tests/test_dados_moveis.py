"""Testes de scripts/dados-moveis.py: soma por uid e tipo de rede, ignora tag, VPN e secao seguinte do dumpsys,
respeita a janela de dias, nomeia uid especial (hotspot) e so chama comandos de LEITURA no aparelho.
"""
import sys
import types

import pytest

AGORA = 10_000_000
UM_DIA = 86400


def _ident(tipo, uid, conjunto="DEFAULT", tag="0x0"):
    return (f"  ident=[{{type={tipo}, subType=0, subscriberId=7, metered=true, defaultNetwork=true, oemManaged=0}}] "
            f"uid={uid} set={conjunto} tag={tag}\n    NetworkStatsHistory: bucketDuration=7200\n")


def _bloco(inicio, rb, tb):
    return f"      st={inicio} rb={rb} rp=1 tb={tb} tp=1 op=0\n"


def _dumpsys(dias_antes=1):
    recente = AGORA - dias_antes * UM_DIA
    antigo = AGORA - 60 * UM_DIA
    return (
        "Active interfaces:\n  iface=rmnet0\n"
        "UID stats:\n  Pending bytes: 0\n  Complete history:\n"
        + _ident(0, 10001) + _bloco(antigo, 100, 50) + _bloco(recente, 1000, 500)
        + _ident(0, 10001, "FOREGROUND") + _bloco(recente, 2000, 0)
        + _ident(0, 10001, tag="0x1") + _bloco(recente, 99999, 99999)       # etiquetado: ja esta dentro do total, nao soma de novo
        + _ident(1, 10001) + _bloco(recente, 7, 3)                           # Wi-Fi
        + _ident(0, -5) + _bloco(recente, 5000, 1000)                        # hotspot
        + _ident(17, 10001) + _bloco(recente, 123456, 123456)                # VPN: ignorada
        + "UID tag stats:\n"
        + _ident(0, 10001) + _bloco(recente, 777777777, 1)                   # outra secao: fora da conta
    )


def test_somar_junta_por_tipo_e_uid_e_respeita_janela(importa_script):
    mod = importa_script("dados-moveis.py")
    t = mod.somar(_dumpsys(), AGORA - 30 * UM_DIA)
    assert dict(t[mod.TIPO_MOVEL]) == {10001: [3000, 500], -5: [5000, 1000]}
    assert dict(t[mod.TIPO_WIFI]) == {10001: [7, 3]}


def test_somar_janela_maior_inclui_o_bloco_antigo(importa_script):
    mod = importa_script("dados-moveis.py")
    t = mod.somar(_dumpsys(), AGORA - 90 * UM_DIA)
    assert t[mod.TIPO_MOVEL][10001] == [3100, 550]


def test_somar_sem_secao_uid_stats_devolve_none(importa_script):
    mod = importa_script("dados-moveis.py")
    assert mod.somar("Dev stats:\n  nada\n", 0) is None


def test_pacotes_por_uid_e_nomes_especiais(importa_script):
    mod = importa_script("dados-moveis.py")
    nomes = mod.pacotes_por_uid("package:a.b uid:10001\npackage:c.d uid:10001\npackage:e.f uid:10001\npackage:g.h uid:10002\nlixo\n")
    assert nomes == {10001: ["a.b", "c.d", "e.f"], 10002: ["g.h"]}
    assert mod.nome_do_uid(10001, nomes) == "a.b, c.d (+1)"
    assert mod.nome_do_uid(10002, nomes) == "g.h"
    assert mod.nome_do_uid(-5, nomes).startswith("hotspot")
    assert mod.nome_do_uid(-4, nomes) == "apps ja desinstalados"
    assert mod.nome_do_uid(10999, nomes) == "uid 10999"


def _prepara_main(mod, monkeypatch, modelo="SM-A125M", netstats=None):
    chamados = []

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        chamados.append(c)
        if c == "getprop ro.product.model":
            return types.SimpleNamespace(stdout=modelo, stderr="")
        if c == "dumpsys netstats --full":
            return types.SimpleNamespace(stdout=_dumpsys() if netstats is None else netstats, stderr="")
        if c == "pm list packages -U -u":
            return types.SimpleNamespace(stdout="package:org.mozilla.fennec_fdroid uid:10001\n", stderr="")
        raise AssertionError(f"comando fora da lista de LEITURA: {c!r}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod.time, "time", lambda: AGORA)
    return chamados


def test_main_mostra_hotspot_e_app_e_so_le(importa_script, monkeypatch, capsys):
    mod = importa_script("dados-moveis.py")
    chamados = _prepara_main(mod, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["dados-moveis.py", "--dias", "30", "--top", "5"])
    mod.main()
    saida = capsys.readouterr().out
    assert "MOVEL 0.00 GB" in saida  # 3500 + 6000 bytes de teste: arredonda para 0,00 GB
    assert "hotspot/tethering (outros aparelhos)" in saida
    assert "org.mozilla.fennec_fdroid" in saida
    assert saida.index("hotspot") < saida.index("org.mozilla.fennec_fdroid")  # o maior vem primeiro (6000 contra 3500)
    assert chamados == ["getprop ro.product.model", "dumpsys netstats --full", "pm list packages -U -u"]


def test_main_aborta_se_nao_for_o_a12(importa_script, monkeypatch):
    mod = importa_script("dados-moveis.py")
    _prepara_main(mod, monkeypatch, modelo="Pixel 7")
    monkeypatch.setattr(sys, "argv", ["dados-moveis.py"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "ABORTADO" in str(exc.value)


def test_main_aborta_se_o_formato_do_dumpsys_mudou(importa_script, monkeypatch):
    mod = importa_script("dados-moveis.py")
    _prepara_main(mod, monkeypatch, netstats="outra coisa\n")
    monkeypatch.setattr(sys, "argv", ["dados-moveis.py"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "UID stats" in str(exc.value)


@pytest.mark.parametrize("args", [["--dias", "0"], ["--top", "0"]])
def test_main_recusa_dias_ou_top_invalidos_antes_do_adb(importa_script, monkeypatch, args):
    mod = importa_script("dados-moveis.py")

    def fake_run(cmd, **kw):
        raise AssertionError(f"nao deveria chamar adb: {cmd!r}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["dados-moveis.py", *args])
    with pytest.raises(SystemExit):
        mod.main()
