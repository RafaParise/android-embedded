"""Testes de scripts/fdroid-baixar.py: a trava que importa e "hash errado nunca instala",
mesmo com --instalar. A cadeia de confianca do indice (indice_verificado/escolher: JAR assinado,
digests, certificado oficial da F-Droid) e matematica de verificacao, nao comando de adb — aqui
ela e substituida por um fake direto, e o teste cobre so a parte que decide se chama 'adb install'.
"""
import hashlib
import sys
import types

import pytest


def test_hash_errado_nunca_instala_mesmo_com_instalar(importa_script, monkeypatch, tmp_path):
    mod = importa_script("fdroid-baixar.py")
    monkeypatch.setattr(mod, "indice_verificado", lambda pasta: {"apps": [], "packages": {}})
    monkeypatch.setattr(mod, "escolher", lambda indice, pkg: {
        "apkName": f"{pkg}.apk", "versionName": "1.0", "hashType": "sha256", "hash": "0" * 64,
    })
    (tmp_path / "net.sourceforge.opencamera.apk").write_bytes(b"conteudo que nao bate com o hash fake")
    # o arquivo difere do indice, entao o script tenta baixar de novo: este stub evita a rede
    # (sem ele, com internet, o teste faria um pedido real ao f-droid.org e passaria so porque o download falha)
    baixados = []
    monkeypatch.setattr(mod, "baixar_arquivo", lambda url, destino: baixados.append(url))
    chamadas = []

    def fake_run(cmd, **kw):
        # nao levanta excecao: main() captura Exception por pacote e contaria como falha comum (exit 1),
        # e o teste passaria mesmo que o 'adb install' fosse chamado
        chamadas.append(cmd)
        return types.SimpleNamespace(stdout="Success", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv",
                         ["fdroid-baixar.py", "--pasta", str(tmp_path), "--instalar", "net.sourceforge.opencamera"])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    assert chamadas == [], f"hash errado nao pode chegar ao adb install: {chamadas!r}"
    assert len(baixados) == 1  # tentou baixar de novo (stub, sem rede) e o arquivo continuou errado


def test_hash_certo_com_instalar_chama_adb_install_no_apk_certo(importa_script, monkeypatch, tmp_path):
    mod = importa_script("fdroid-baixar.py")
    dados = b"conteudo de teste do apk"
    hash_certo = hashlib.sha256(dados).hexdigest()
    monkeypatch.setattr(mod, "indice_verificado", lambda pasta: {"apps": [], "packages": {}})
    monkeypatch.setattr(mod, "escolher", lambda indice, pkg: {
        "apkName": f"{pkg}.apk", "versionName": "1.0", "hashType": "sha256", "hash": hash_certo,
    })
    (tmp_path / "net.sourceforge.opencamera.apk").write_bytes(dados)
    chamadas = []

    def fake_run(cmd, **kw):
        chamadas.append(cmd)
        return types.SimpleNamespace(stdout="Success", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv",
                         ["fdroid-baixar.py", "--pasta", str(tmp_path), "--instalar", "net.sourceforge.opencamera"])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0
    assert chamadas == [["adb", "install", "-r", str(tmp_path / "net.sourceforge.opencamera.apk")]]


def test_sem_instalar_nunca_chama_adb(importa_script, monkeypatch, tmp_path):
    mod = importa_script("fdroid-baixar.py")
    dados = b"conteudo de teste do apk"
    monkeypatch.setattr(mod, "indice_verificado", lambda pasta: {"apps": [], "packages": {}})
    monkeypatch.setattr(mod, "escolher", lambda indice, pkg: {
        "apkName": f"{pkg}.apk", "versionName": "1.0", "hashType": "sha256", "hash": hashlib.sha256(dados).hexdigest(),
    })
    (tmp_path / "net.sourceforge.opencamera.apk").write_bytes(dados)

    def fake_run(cmd, **kw):
        raise AssertionError(f"sem --instalar nao deveria chamar nada: {cmd!r}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["fdroid-baixar.py", "--pasta", str(tmp_path), "net.sourceforge.opencamera"])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0
