"""Testes de scripts/checklist-script.py: so leitura, grava relatorio isolado do repo real.

'E, D, U = lista("-e"), lista("-d"), lista("-u")' roda no NIVEL DO MODULO (antes de main()),
entao o subprocess.run falso precisa estar no lugar ANTES de importa_script() chamar
exec_module — e nao depois, como nos outros scripts cujo unico ponto de entrada e main().
"""
import subprocess
import sys
import types

import pytest

ESCRITAS = ("pm disable", "pm enable", "pm grant", "pm revoke", "settings put", "sm partition",
            "device_config put", "cmd appops set", "am set-standby-bucket", "dumpsys deviceidle whitelist +")


def _fake_run_leitura(cmd, **kw):
    c = cmd[2].strip()
    if c == "getprop ro.product.model":
        return types.SimpleNamespace(stdout="SM-A125M", stderr="")
    if c.startswith(ESCRITAS):
        raise AssertionError(f"checklist-script.py e so leitura, nao deveria chamar: {c!r}")
    if c == "pm list packages -e":
        return types.SimpleNamespace(stdout="package:com.termux", stderr="")
    if c.startswith("pm list packages"):
        return types.SimpleNamespace(stdout="", stderr="")
    if c.startswith("settings get") or c.startswith("device_config get"):
        return types.SimpleNamespace(stdout="null", stderr="")
    if c.startswith("cmd appops get"):
        op = c.split()[4]  # cmd appops get PKG OP
        return types.SimpleNamespace(stdout=f"{op}: default", stderr="")
    if c.startswith("am get-standby-bucket"):
        return types.SimpleNamespace(stdout="?", stderr="")
    if c == "dumpsys deviceidle whitelist":
        return types.SimpleNamespace(stdout="", stderr="")
    if "status=" in c:
        return types.SimpleNamespace(stdout="", stderr="")
    if c == "sm list-volumes all":
        return types.SimpleNamespace(stdout="public:179,97 mounted null", stderr="")
    return types.SimpleNamespace(stdout="", stderr="")


def test_roda_sem_crash_e_isola_o_relatorio(importa_script, monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "run", _fake_run_leitura)  # antes do import: E/D/U rodam no nivel do modulo
    mod = importa_script("checklist-script.py")
    (mod.RAIZ / "memoria").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sys, "argv", ["checklist-script.py"])

    mod.main()

    saida = capsys.readouterr().out
    assert "itens:" in saida
    relatorio = mod.RAIZ / "memoria" / "CHECKLIST-SCRIPT.md"
    assert relatorio.exists()
    texto = relatorio.read_text(encoding="utf-8")
    assert "FEITO" in texto
    # com o indice certo no fake, a regex "OP: default" do script casa (antes todo appop saia '?')
    assert "`appops com.termux RUN_IN_BACKGROUND` | ignore | default |" in texto
    assert "| ignore | ? |" not in texto
    # itens fixos nao fingem leitura do aparelho, e a nota do Termux nao repete o que o projeto desmentiu em 02/11
    assert "historico (28/10), nao lido agora" in texto and "adotado e ocioso" not in texto
    assert "so roda com a tela aberta" not in texto and "Termux:Boot" in texto


def test_appop_recusado_mas_concedido_na_pratica_vira_pendente_nao_feito(importa_script, monkeypatch, capsys):
    """Revisao de 30/10: 'RECUSADO if atual != modo else FEITO' rotulava de FEITO o caso em que um
    appop que o projeto recusou conceder (SYSTEM_ALERT_WINDOW) aparece concedido na pratica (por
    qualquer outra via) - o oposto do que a decisao registrada diz. Corrigido para PENDENTE, no
    mesmo padrao usado para 'manter' (pacote) quando o estado real nao confirma a decisao."""
    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if c == "pm list packages -e":
            return types.SimpleNamespace(stdout="package:com.termux\npackage:net.sourceforge.opencamera\npackage:app.organicmaps", stderr="")
        if c.startswith("cmd appops get") and "SYSTEM_ALERT_WINDOW" in c:
            return types.SimpleNamespace(stdout="SYSTEM_ALERT_WINDOW: allow", stderr="")
        return _fake_run_leitura(cmd, **kw)

    monkeypatch.setattr(subprocess, "run", fake_run)
    mod = importa_script("checklist-script.py")
    (mod.RAIZ / "memoria").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sys, "argv", ["checklist-script.py"])

    mod.main()

    saida = capsys.readouterr().out
    assert "[PENDENTE]" in saida
    relatorio = (mod.RAIZ / "memoria" / "CHECKLIST-SCRIPT.md").read_text(encoding="utf-8")
    assert "SYSTEM_ALERT_WINDOW` | allow | allow | **PENDENTE**" in relatorio
    assert "SYSTEM_ALERT_WINDOW` | allow | allow | **FEITO**" not in relatorio


def test_aborta_se_aparelho_inesperado(importa_script, monkeypatch):
    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if c == "getprop ro.product.model":
            return types.SimpleNamespace(stdout="SM-G960F", stderr="")
        return types.SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    mod = importa_script("checklist-script.py")
    monkeypatch.setattr(sys, "argv", ["checklist-script.py"])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "ABORTADO" in str(exc.value)
