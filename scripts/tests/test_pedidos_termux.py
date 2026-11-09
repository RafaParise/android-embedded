"""Testes do `pedidos` (celular-kit/bin/pedidos): a fila dos pedidos do Rafael ao parise-core."""
import importlib.machinery
import importlib.util
import json
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "celular-kit" / "bin" / "pedidos"


@pytest.fixture
def pd(tmp_path, monkeypatch):
    monkeypatch.setenv("PEDIDOS_DIR", str(tmp_path))
    loader = importlib.machinery.SourceFileLoader("pedidos", str(SCRIPT))
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader("pedidos", loader))
    loader.exec_module(m)
    return m


def test_utf8_sem_crlf():
    t = SCRIPT.read_bytes()
    t.decode("utf-8")
    assert b"\r" not in t


def test_ordem_urgente_primeiro_e_um_fazendo_por_vez(pd, capsys):
    assert pd.main(["novo", "organizar", "fotos"]) == 0
    assert pd.main(["novo", "ligar", "a", "lanterna", "--urgente"]) == 0
    assert pd.main(["novo", "ver", "o", "wifi"]) == 0
    capsys.readouterr()
    assert pd.main([]) == 0
    linhas = capsys.readouterr().out.splitlines()
    assert "lanterna" in linhas[0] and "fotos" in linhas[1] and "wifi" in linhas[2]
    pd.main(["fazendo", "3"])
    pd.main(["fazendo", "1"])
    estados = {p["id"]: p["estado"] for p in json.loads((pd.ARQ).read_text(encoding="utf-8"))}
    assert estados == {1: "fazendo", 2: "aberto", 3: "aberto"}


def test_feito_e_largar_com_motivo(pd, capsys):
    pd.main(["novo", "a"])
    pd.main(["novo", "b"])
    assert pd.main(["feito", "1", "pronto"]) == 0
    assert pd.main(["largar", "2"]) == 2
    assert pd.main(["largar", "2", "precisa do Claude"]) == 0
    capsys.readouterr()
    assert pd.main([]) == 1 and "Nenhum" in capsys.readouterr().out
    assert pd.main(["todos"]) == 0 and "[feito]" in capsys.readouterr().out


@pytest.mark.parametrize("texto", ["senha: abc123456", "manda pra fulano@exemplo.com", "cpf 123.456.789-00", "notas dos alunos do 2A"])
def test_recusa_dado_sensivel(pd, texto):
    assert pd.main(["novo", texto]) == 3
    assert not pd.ARQ.exists()


def test_revisar_mostra_o_velho_e_o_em_andamento(pd, capsys):
    pd.grava([{"id": 1, "hora": "2020-01-01 10:00", "texto": "velho", "estado": "aberto", "urgente": False},
              {"id": 2, "hora": "2999-01-01 10:00", "texto": "novo", "estado": "aberto", "urgente": False}])
    assert pd.main(["revisar"]) == 0
    out = capsys.readouterr().out
    assert "velho" in out and "novo" not in out


def test_uso_errado(pd):
    assert pd.main(["feito", "x"]) == 2
    assert pd.main(["novo"]) == 2
    assert pd.main(["apagar-tudo"]) == 2
