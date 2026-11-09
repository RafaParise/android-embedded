"""A ponte entrega ao parise-core-android o indice de TODOS os projetos (o projetos.py do parise-core-windows), 07/11/2026.

Projeto falso em pasta temporaria; o indice tambem (PROJETOS_DIR). Nada do PC de verdade e lido.
"""
import importlib.util
import pathlib
import subprocess
import types

import pytest

PROJETOS_PY = next((p for p in (pathlib.Path("/mnt/c/Projetos/parise-core-windows/bin/projetos.py"),
                                pathlib.Path(r"C:\Projetos\parise-core-windows\bin\projetos.py")) if p.is_file()), None)
pytestmark = pytest.mark.skipif(PROJETOS_PY is None, reason="precisa do parise-core-windows\\bin\\projetos.py")
SEGREDO_FALSO = "sk-or-v1-" + "a1" * 20


def _so_git(cmd, *args, **kw):
    """O conftest bloqueia todo subprocess.run (o cabo do A12 pode estar ligado); aqui so o git passa, e nada mais."""
    if not isinstance(cmd, list) or cmd[:1] != ["git"]:
        pytest.fail("so o git pode rodar neste teste: %r" % (cmd,))
    entrada = kw.pop("input", None)
    timeout = kw.pop("timeout", 60)
    check = kw.pop("check", False)
    kw.pop("capture_output", None)
    kw.pop("stdin", None)
    kw.pop("creationflags", None)
    kw.setdefault("env", {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "GIT_CONFIG_NOSYSTEM": "1"})
    p = subprocess.Popen(["/usr/bin/git"] + cmd[1:], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, **kw)
    saida, erro = p.communicate(entrada, timeout=timeout)
    r = subprocess.CompletedProcess(cmd, p.returncode, saida, erro)
    if check and p.returncode:
        raise subprocess.CalledProcessError(p.returncode, cmd, saida, erro)
    return r


@pytest.fixture
def mundo(tmp_path, importa_script, monkeypatch):
    monkeypatch.setenv("PROJETOS_DIR", str(tmp_path / "indice"))
    monkeypatch.setenv("PROJETOS_COPIAS", str(tmp_path / "copias"))
    monkeypatch.setattr(subprocess, "run", _so_git)
    m = importa_script("ponte-pc.py")
    spec = importlib.util.spec_from_file_location("projetos_teste", PROJETOS_PY)
    pj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pj)
    repo = tmp_path / "arena"
    (repo / "servidor").mkdir(parents=True)
    (repo / "CLAUDE.md").write_text("# ARENA\nRegra: caminho relativo.\n", encoding="utf-8")
    (repo / "servidor" / "hardware.py").write_text('"""Placa de video."""\ndef teto_da_placa():\n    return 3\n'
                                                     "CHAVE = '%s'\n" % SEGREDO_FALSO, encoding="utf-8")
    for args in (["init", "-q"], ["add", "."], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"]):
        subprocess.run(["git", "-C", str(repo)] + args, check=True, capture_output=True)
    pj.REGISTRO = [{"id": "arena", "nome": "ARENA", "pasta": str(repo), "publico": True, "o_que": "Lancador.", "comecar": ["CLAUDE.md"],
                    "fora": [], "comandos": {}, "limites": ["Nada de push."]}]
    pj.indexar(saida=lambda *_: None)
    proj, base = tmp_path / "proj", tmp_path / "base"
    (proj / "memoria").mkdir(parents=True)
    (proj / "CLAUDE.md").write_text("# casa\n", encoding="utf-8")
    ponte = m.Ponte(proj, base)
    ponte._projetos = pj
    ponte.pasta_projetos = tmp_path / "nenhum"
    return types.SimpleNamespace(m=m, ponte=ponte, pj=pj)


def test_lista_busca_e_le_pelo_mesmo_indice(mundo):
    assert mundo.ponte.projetos_lista()["projetos"][0]["id"] == "arena"
    achado = mundo.ponte.projetos_buscar("teto placa", "arena")["achados"][0]
    assert (achado["caminho"], achado["projeto"]) == ("servidor/hardware.py", "arena")
    lido = mundo.ponte.projetos_ler("arena", "servidor/hardware.py", 2, 3)
    assert "def teto_da_placa" in lido["texto"] and lido["fim"] == 3


def test_segredo_nunca_sai_pela_ponte(mundo):
    assert SEGREDO_FALSO not in mundo.ponte.projetos_ler("arena", "servidor/hardware.py")["texto"]
    assert mundo.ponte.projetos_buscar(SEGREDO_FALSO[:20], "arena")["achados"] == []


@pytest.mark.parametrize("projeto, caminho", [("arena", "../fora.md"), ("inventado", "CLAUDE.md"), ("arena", "C:/Windows/win.ini")])
def test_recusa_vira_erro_limpo(mundo, projeto, caminho):
    with pytest.raises(mundo.m.ErroPonte) as e:
        mundo.ponte.projetos_ler(projeto, caminho)
    assert e.value.status == 400 and "Traceback" not in e.value.mensagem


def test_mapa_em_fatias_e_na_memoria_do_celular(mundo):
    fatia = mundo.ponte.projetos_mapa("arena", 1, 5)
    assert fatia["inicio"] == 1 and "Mapa do projeto arena" in fatia["texto"]
    arquivos = mundo.ponte.memoria_pacote()["arquivos"]
    assert "pc-projeto-arena.md" in arquivos and "Nada de push." in arquivos["pc-projeto-arena.md"]
    assert "pc-projeto-indice.md" in arquivos


def test_ferramentas_mcp_novas(mundo):
    nomes = {f["name"] for f in mundo.m.Ponte.FERRAMENTAS}
    assert {"projetos_lista", "projetos_mapa", "projetos_buscar", "projetos_ler"} <= nomes
    assert mundo.ponte.chamar("projetos_buscar", {"texto": "teto placa"})["achados"]


def test_sem_o_projetos_py_a_ponte_avisa(mundo, monkeypatch, tmp_path):
    monkeypatch.setenv("PONTE_PROJETOS_PY", str(tmp_path / "nao-existe.py"))
    mundo.ponte._projetos = None
    with pytest.raises(mundo.m.ErroPonte) as e:
        mundo.ponte.projetos_lista()
    assert e.value.status == 503
    assert "pc-projeto-arena.md" not in mundo.ponte.memoria_pacote()["arquivos"]      # a memoria continua sem os mapas
