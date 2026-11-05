"""Testes de scripts/auditoria-nativos.py: so leitura (7 parsers de dumpsys/ps), nunca escreve.

inventario() chama, por dentro, 'subprocess.run([sys.executable, ...scripts/inventario.py...])'
(um processo Python separado, nao um comando adb); se ele sair com codigo != 0 o script ABORTA (nao usa TSV velho); depois confere se
apareceu um diagnostico/*/inventario.tsv. Por isso o fake_run so precisa decidir pelo cmd[0]
('adb' ou nao) e o teste pre-cria o inventario.tsv direto, sem deixar o processo aninhado rodar
de verdade (ele tentaria chamar adb de novo, sem PATH, e so gastaria tempo para um resultado
que o script descarta mesmo).
"""
import sys
import types

import pytest

ESCRITAS = ("pm disable", "pm enable", "pm grant", "pm revoke", "settings put",
            "sm partition", "device_config put", "cmd appops set")

CAB = ("pacote", "tipo", "estado", "uad", "lista", "ultimo_uso", "min", "aberturas", "internet", "sensiveis", "protegido")


def _prepara_inventario_tsv(raiz, linhas):
    pasta = raiz / "diagnostico" / "20261030-0000"
    pasta.mkdir(parents=True, exist_ok=True)
    texto = "\n".join(["\t".join(CAB)] + ["\t".join(l) for l in linhas])
    (pasta / "inventario.tsv").write_text(texto, encoding="utf-8")


def test_aborta_se_aparelho_inesperado(importa_script, monkeypatch):
    mod = importa_script("auditoria-nativos.py")
    monkeypatch.setattr(sys, "argv", ["auditoria-nativos.py"])

    def fake_run(cmd, **kw):
        if cmd[0] != "adb":
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        return types.SimpleNamespace(stdout="SM-G960F", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "ABORTADO" in str(exc.value)


def test_so_le_nunca_escreve_e_roda_sem_crash(importa_script, monkeypatch, capsys):
    mod = importa_script("auditoria-nativos.py", copiar_lotes_json=True)
    _prepara_inventario_tsv(mod.RAIZ, [("com.android.chrome", "sistema", "ativo", "-", "-", "", "0", "0", "", "", "")])

    def fake_run(cmd, **kw):
        if cmd[0] != "adb":  # chamada aninhada a inventario.py (processo Python, nao adb): terminou bem
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        c = cmd[2].strip()
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c == "pm list packages -U -s -e":
            saida = "package:com.android.chrome uid:1000"
        elif c == "pm list packages -e":
            saida = ""
        elif c.startswith("ps -A -o UID,TIME"):
            saida = "UID TIME NAME\n" if "ETIME" not in c else "UID TIME ETIME NAME\n"
        elif c.startswith(ESCRITAS):
            raise AssertionError(f"auditoria-nativos e so leitura, nao deveria chamar: {c!r}")
        else:
            saida = ""  # dumpsys netstats/alarm/jobscheduler/activity services/power: vazio basta
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["auditoria-nativos.py"])

    mod.main()

    saida = capsys.readouterr().out
    assert "lotes: 0 pacote(s)" in saida


def test_falha_do_inventario_aborta_e_nao_usa_o_tsv_de_outro_dia(importa_script, monkeypatch, capsys):
    mod = importa_script("auditoria-nativos.py")
    monkeypatch.setattr(sys, "argv", ["auditoria-nativos.py"])
    _prepara_inventario_tsv(mod.RAIZ, [("com.android.chrome", "sistema", "ativo", "-", "-", "", "0", "0", "", "", "")])  # TSV antigo

    def fake_run(cmd, **kw):
        if cmd[0] != "adb":
            return types.SimpleNamespace(returncode=1, stdout="", stderr="adb caiu")
        c = cmd[2].strip()
        saida = "SM-A125M" if c == "getprop ro.product.model" else ""
        return types.SimpleNamespace(returncode=0, stdout=saida, stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "inventario.py falhou" in str(exc.value)
