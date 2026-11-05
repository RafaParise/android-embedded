"""Chao de seguranca dos testes: nenhum script aqui pode tocar um adb de verdade (nem rede de verdade).

NUVEM.md secao 5 (N2): sd-adotar.py e sonda-a12.py caem num adb.exe de caminho
absoluto quando 'adb' nao esta no PATH, entao PATH vazio sozinho NAO protege.
A trava real e esta: subprocess.run vira uma funcao que reprova o teste se for
chamada sem o teste ter posto o proprio stub no lugar (ver _bloqueia_tudo).

ia-celular.py fala HTTP direto (urllib), nao so adb: mesma trava, mesmo motivo
(nenhum teste deveria depender de rede de verdade, nem da porta 8080 do llama-server).
"""
import importlib.util
import pathlib
import shutil
import subprocess
import urllib.request

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPTS = RAIZ / "scripts"


def _bloqueia_tudo(cmd, *args, **kwargs):
    pytest.fail(
        "subprocess.run chamado sem stub do teste (bloqueado antes de poder tocar em adb): "
        f"{cmd!r}"
    )


def _bloqueia_rede(req, *args, **kwargs):
    pytest.fail(
        "urllib.request.urlopen chamado sem stub do teste (bloqueado antes de poder tocar rede de verdade): "
        f"{req!r}"
    )


@pytest.fixture(autouse=True)
def sem_adb_de_verdade(monkeypatch, tmp_path):
    """Autouse: todo teste comeca sem PATH, com ANDROID_SERIAL inexistente e subprocess.run
    recusando qualquer chamada que o proprio teste nao tenha substituido."""
    caminho_vazio = tmp_path / "path-vazio"
    caminho_vazio.mkdir()
    monkeypatch.setenv("PATH", str(caminho_vazio))
    monkeypatch.setenv("ANDROID_SERIAL", "NAO-EXISTE")
    monkeypatch.setattr(subprocess, "run", _bloqueia_tudo)

    # segunda trava, mais baixa que o subprocess.run: qualquer processo cujo comando cite 'adb' falha antes de existir,
    # mesmo que um teste restaure o subprocess.run original ou chame Popen direto (o cabo do A12 pode estar ligado)
    popen_original = subprocess.Popen.__init__

    def popen_sem_adb(self, args, *a, **kw):
        texto = args if isinstance(args, str) else " ".join(str(x) for x in args)
        if "adb" in texto.lower():
            pytest.fail(f"Popen com adb bloqueado (nenhum teste pode abrir o adb de verdade): {texto!r}")
        return popen_original(self, args, *a, **kw)

    monkeypatch.setattr(subprocess.Popen, "__init__", popen_sem_adb)
    monkeypatch.setattr(urllib.request, "urlopen", _bloqueia_rede)


@pytest.fixture
def importa_script(tmp_path, monkeypatch):
    """Importa um script de scripts/ por caminho (nomes com hifen nao dao import normal).

    Se o modulo tiver RAIZ (lote-pacotes.py, ajustes-script.py, privacidade.py), redireciona
    para uma pasta temporaria, para que nenhum teste grave diagnostico/ no repositorio real.
    copiar_lotes_json=True tambem copia o scripts/lotes-bloatware.json de verdade para a
    pasta falsa, para testes que precisam dos lotes reais.
    """

    def _importa(nome_arquivo, copiar_lotes_json=False):
        caminho = SCRIPTS / nome_arquivo
        nome_modulo = caminho.stem.replace("-", "_")
        spec = importlib.util.spec_from_file_location(nome_modulo, caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        if hasattr(modulo, "RAIZ"):
            raiz_falsa = tmp_path / f"raiz-{nome_modulo}"
            (raiz_falsa / "scripts").mkdir(parents=True, exist_ok=True)
            if copiar_lotes_json:
                shutil.copy(SCRIPTS / "lotes-bloatware.json", raiz_falsa / "scripts" / "lotes-bloatware.json")
            modulo.RAIZ = raiz_falsa
        return modulo

    return _importa
