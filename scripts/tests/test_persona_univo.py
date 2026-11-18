"""Persona do Univo (17/11/2026): fonte única em scripts/celular-kit/persona, copiada pelo scripts/persona.py para o
QWEN.md (Qwen Code e OpenCode no celular), o bin/ia (persona compacta: ia chat e ia qwen) e o SOUL.md do Hermes no PC.
"""
import importlib.util
import pathlib
import shutil
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
KIT = RAIZ / "scripts" / "celular-kit"
BASH = next((p for p in ("/bin/bash", "/usr/bin/bash") if pathlib.Path(p).exists()), None)


def _persona():
    spec = importlib.util.spec_from_file_location("persona_univo", RAIZ / "scripts" / "persona.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_todos_os_destinos_estao_iguais_a_fonte():
    assert _persona().processa(gravar=False) == []


@pytest.mark.parametrize("regra", ["Zero bajulação", "Sinceridade cirúrgica", "Humor ácido, seco e irônico",
                                   "Responde à altura à preguiça intelectual", "Orientação acima de conforto"])
def test_a_fonte_traz_as_5_regras_do_rafael(regra):
    assert regra in (KIT / "persona" / "UNIVO-PERSONA.md").read_text(encoding="utf-8")


def test_a_regra_da_preguica_nao_trava_os_comandos_do_aparelho_nem_as_travas():
    t = (KIT / "persona" / "UNIVO-PERSONA.md").read_text(encoding="utf-8")
    assert "Isto NÃO é preguiça" in t and "FRASE → COMANDO" in t, "comando direto do Rafael se faz na hora, sem sermão"
    assert "segurança e travas > verdade dos fatos" in t and "nunca dispensa o \"sim\" do irreversível" in t


def test_qwen_md_tem_um_bloco_so_e_nao_sobrou_a_personalidade_antiga_duplicada():
    t = (KIT / "QWEN.md").read_text(encoding="utf-8")
    assert t.count("UNIVO-PERSONA:INICIO") == 1 and t.count("UNIVO-PERSONA:FIM") == 1
    assert "**Desculpas e críticas" not in t and "Robô de missão espacial (TARS)" not in t
    assert "Nunca se apresente como Qwen" in t, "a identidade do celular fica fora do bloco comum"


def test_persona_compacta_cabe_no_modelo_pequeno_e_nas_aspas_do_bash():
    texto = _persona().compacta()
    assert len(texto) <= 1200 and "'" not in texto
    for trecho in ("UNIVO", "bajulacao", "desculpas", "portugues do Brasil", "Nunca invente"):
        assert trecho in texto


@pytest.mark.skipif(BASH is None, reason="precisa de bash (os testes rodam no WSL)")
def test_o_bin_ia_carrega_a_persona_compacta_igual_a_fonte():
    ia = (KIT / "bin" / "ia").read_text(encoding="utf-8")
    ini = ia.index("# UNIVO-PERSONA-COMPACTA:INICIO")
    fim = ia.index("# UNIVO-PERSONA-COMPACTA:FIM")
    assert BASH
    # Popen e nao run: o conftest.py barra o subprocess.run (protecao contra adb de verdade)
    p = subprocess.Popen([BASH, "-c", ia[ini:fim] + '\nprintf %s "$PERSONA_COMPACTA"'], env={"PATH": "/usr/bin:/bin"},
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    saida, _ = p.communicate(timeout=10)
    assert p.returncode == 0 and saida == _persona().compacta()


def _kit_falso(tmp_path, monkeypatch):
    """Cópia falsa do kit em tmp_path: os testes que gravam nunca tocam os arquivos de verdade."""
    mod = _persona()
    kit = tmp_path / "celular-kit"
    (kit / "bin").mkdir(parents=True)
    shutil.copytree(KIT / "persona", kit / "persona")
    (kit / "QWEN.md").write_text("# topo\n<!-- UNIVO-PERSONA:INICIO -->\nvelho\n<!-- UNIVO-PERSONA:FIM -->\n## resto\n", encoding="utf-8")
    (kit / "bin" / "ia").write_text("#!/bin/bash\n# UNIVO-PERSONA-COMPACTA:INICIO\nPERSONA_COMPACTA=''\n# UNIVO-PERSONA-COMPACTA:FIM\necho fim\n", encoding="utf-8")
    monkeypatch.setattr(mod, "KIT", kit)
    monkeypatch.setattr(mod, "FONTE", kit / "persona" / "UNIVO-PERSONA.md")
    monkeypatch.setattr(mod, "FONTE_COMPACTA", kit / "persona" / "UNIVO-PERSONA-COMPACTA.txt")
    return mod, kit


def test_sincronizar_reescreve_so_o_bloco_e_e_idempotente(tmp_path, monkeypatch):
    mod, kit = _kit_falso(tmp_path, monkeypatch)
    soul = tmp_path / "SOUL.md"
    soul.write_bytes(b"# SOUL\r\n<!-- UNIVO-PERSONA:INICIO -->\r\nvelho\r\n<!-- UNIVO-PERSONA:FIM -->\r\n## O Rafael\r\n")
    assert len(mod.processa(gravar=False, soul=soul)) == 3
    assert mod.processa(gravar=True, soul=soul) == []
    assert mod.processa(gravar=False, soul=soul) == []
    q = (kit / "QWEN.md").read_text(encoding="utf-8")
    assert q.startswith("# topo\n") and q.endswith("## resto\n") and "velho" not in q and "Zero bajulação" in q
    s = soul.read_bytes()
    assert s.endswith(b"## O Rafael\r\n") and b"\n" not in s.replace(b"\r\n", b""), "SOUL.md com CRLF segue CRLF"


def test_destino_sem_marcador_e_problema_e_nao_e_reescrito(tmp_path, monkeypatch):
    mod, _kit = _kit_falso(tmp_path, monkeypatch)
    soul = tmp_path / "SOUL.md"
    soul.write_text("# SOUL sem marcador\n", encoding="utf-8")
    problemas = mod.processa(gravar=True, soul=soul)
    assert any("esperava 1 bloco" in p for p in problemas)
    assert soul.read_text(encoding="utf-8") == "# SOUL sem marcador\n"
