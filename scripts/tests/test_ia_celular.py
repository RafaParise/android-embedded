"""Testes de scripts/ia-celular.py: aborta limpo se o celular ou a IA nao estao no ar; --estado nao
chama o modelo; erro na chamada de chat (timeout, resposta malformada) vira ERRO limpo, nunca traceback
(revisao de 30/10: a chamada de chat nao tinha try/except, diferente do /health que ja tinha)."""
import json
import sys
import types
import urllib.error

import pytest


class _RespostaFalsa:
    """Fake minimo de http.client.HTTPResponse: context manager com .read()."""

    def __init__(self, corpo: dict):
        self._dados = json.dumps(corpo).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._dados


def _fake_adb_ok(cmd, **kw):
    return types.SimpleNamespace(stdout="SM-A125M", stderr="", returncode=0)


def test_aborta_se_celular_nao_encontrado(importa_script, monkeypatch):
    mod = importa_script("ia-celular.py")

    def fake_run(cmd, **kw):
        return types.SimpleNamespace(stdout="", stderr="no devices", returncode=1)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["ia-celular.py", "oi"])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "ABORTADO" in str(exc.value)


def test_aborta_limpo_se_ia_nao_esta_no_ar(importa_script, monkeypatch):
    mod = importa_script("ia-celular.py")
    monkeypatch.setattr(mod.subprocess, "run", _fake_adb_ok)

    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("conexao recusada")

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(sys, "argv", ["ia-celular.py", "oi"])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "nao esta no ar" in str(exc.value)


def test_estado_nao_chama_chat_completions(importa_script, monkeypatch, capsys):
    mod = importa_script("ia-celular.py")
    monkeypatch.setattr(mod.subprocess, "run", _fake_adb_ok)
    chamadas = []

    def fake_urlopen(req, timeout=None):
        chamadas.append(req.full_url)
        if "/health" in req.full_url:
            return _RespostaFalsa({"status": "ok"})
        raise AssertionError(f"--estado nao deveria chamar: {req.full_url!r}")

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(sys, "argv", ["ia-celular.py", "--estado"])

    mod.main()

    assert "no ar" in capsys.readouterr().out
    assert all("chat/completions" not in c for c in chamadas)


def test_pergunta_normal_imprime_a_resposta(importa_script, monkeypatch, capsys):
    mod = importa_script("ia-celular.py")
    monkeypatch.setattr(mod.subprocess, "run", _fake_adb_ok)

    def fake_urlopen(req, timeout=None):
        if "/health" in req.full_url:
            return _RespostaFalsa({"status": "ok"})
        corpo = json.loads(req.data.decode("utf-8"))
        assert corpo["messages"][-1]["content"] == "qual a capital da franca"
        return _RespostaFalsa({"choices": [{"message": {"content": "  Paris  "}}]})

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(sys, "argv", ["ia-celular.py", "qual", "a", "capital", "da", "franca"])

    mod.main()

    assert capsys.readouterr().out.strip() == "Paris"


def test_erro_na_chamada_de_chat_vira_mensagem_limpa_nao_traceback(importa_script, monkeypatch):
    """O bug de 30/10: so o /health tinha try/except; um timeout ou JSON sem 'choices' na
    chamada de chat de verdade vazava como traceback em vez de ABORTADO/ERRO limpo."""
    mod = importa_script("ia-celular.py")
    monkeypatch.setattr(mod.subprocess, "run", _fake_adb_ok)

    def fake_urlopen(req, timeout=None):
        if "/health" in req.full_url:
            return _RespostaFalsa({"status": "ok"})
        raise TimeoutError("modelo nao respondeu em 180s")

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(sys, "argv", ["ia-celular.py", "pergunta", "demorada"])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "ERRO" in str(exc.value) and "TimeoutError" in str(exc.value)
