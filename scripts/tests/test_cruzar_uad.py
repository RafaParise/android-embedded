"""Testes de scripts/cruzar-uad.py: so leitura (nao importa subprocess; sem risco de adb).

Sem 'if __name__' (roda tudo ao importar) e grava/le diagnostico/ a partir de uma RAIZ
fixa calculada de __file__: mesma tecnica de isolar copiando para scripts/ dentro de um
tmp_path. Precisa tambem de diagnostico/uad_lists.json e de uma pasta de sonda com
pacotes_todos.txt/pacotes_desativados.txt (senao o script baixa da internet ou aborta).
"""
import json
import runpy
import shutil
import sys

from conftest import SCRIPTS


def _prepara(tmp_path):
    raiz = tmp_path / "raiz"
    (raiz / "scripts").mkdir(parents=True)
    caminho = raiz / "scripts" / "cruzar-uad.py"
    shutil.copy(SCRIPTS / "cruzar-uad.py", caminho)
    shutil.copy(SCRIPTS / "lote-pacotes.py", raiz / "scripts" / "lote-pacotes.py")  # os regex PROTEGIDOS
    diag = raiz / "diagnostico"
    diag.mkdir()
    (diag / "uad_lists.json").write_text(json.dumps({
        "com.termux": {"removal": "Recommended", "list": "general", "description": "terminal"},
        "com.android.chrome": {"removal": "Advanced", "list": "general", "description": "navegador"},
        # ativos, Recommended e PROTEGIDOS: um so pela lista fixa, os outros so pelos regex de lote-pacotes.py
        "com.google.android.apps.turbo": {"removal": "Recommended", "list": "google", "description": "bem-estar"},
        "com.android.egg": {"removal": "Recommended", "list": "aosp", "description": "easter egg"},
        "com.samsung.android.knox.attestation": {"removal": "Recommended", "list": "oem", "description": "knox"},
        "com.samsung.android.app.appsedge": {"removal": "Advanced", "list": "oem", "description": "edge"},
    }), encoding="utf-8")
    sonda = diag / "20261030-0000"
    sonda.mkdir()
    (sonda / "pacotes_todos.txt").write_text("com.termux\ncom.android.chrome\ncom.osp.app.signin\ncom.google.android.apps.turbo\ncom.android.egg\ncom.samsung.android.knox.attestation\ncom.samsung.android.app.appsedge\n", encoding="utf-8")
    (sonda / "pacotes_desativados.txt").write_text("com.osp.app.signin\n", encoding="utf-8")
    return caminho


def test_recomendados_exclui_protegidos_e_nao_recommended(monkeypatch, tmp_path, capsys):
    caminho = _prepara(tmp_path)
    monkeypatch.setattr(sys, "argv", ["cruzar-uad.py", "--recomendados"])

    runpy.run_path(str(caminho), run_name="__main__")

    saida = capsys.readouterr().out
    assert "com.termux" in saida  # Recommended, ativo, nao protegido: deve aparecer
    assert "com.android.chrome" not in saida  # Advanced, nao Recommended: nao deve aparecer
    assert "com.osp.app.signin" not in saida  # desativado (fora de todos-desat) E protegido
    # ativos + Recommended + protegidos: so o filtro de protegidos os tira da lista de candidatos
    recomendados = saida.split("RECOMMENDED (sem os protegidos):")[-1]
    for protegido in ("com.google.android.apps.turbo", "com.android.egg", "com.samsung.android.knox.attestation"):
        assert protegido not in recomendados
    assert "com.termux" in recomendados


def test_arquivo_marca_protegidos_da_lista_fixa_e_dos_regex(monkeypatch, tmp_path, capsys):
    caminho = _prepara(tmp_path)
    alvo = tmp_path / "script.txt"
    alvo.write_text("com.android.egg com.samsung.android.app.appsedge com.termux", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["cruzar-uad.py", str(alvo)])
    runpy.run_path(str(caminho), run_name="__main__")
    linhas = {l.split(" | ")[0]: l for l in capsys.readouterr().out.splitlines() if " | " in l}
    assert "PROTEGIDO" in linhas["com.android.egg"] and "PROTEGIDO" in linhas["com.samsung.android.app.appsedge"]
    assert "PROTEGIDO" not in linhas["com.termux"]


def test_arquivo_lista_pacotes_e_marca_ausentes(monkeypatch, tmp_path, capsys):
    caminho = _prepara(tmp_path)
    alvo = tmp_path / "script_para_ler.txt"
    alvo.write_text("desative com.termux e tambem com.inexistente.pacote", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["cruzar-uad.py", str(alvo)])

    runpy.run_path(str(caminho), run_name="__main__")

    saida = capsys.readouterr().out
    assert "com.termux | ativo | Recommended" in saida
    assert "com.inexistente.pacote" in saida.split("AUSENTES:")[-1]
