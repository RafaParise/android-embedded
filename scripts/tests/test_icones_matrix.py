"""Testes do icones-matrix.py com imagens sinteticas (sem aparelho)."""
import importlib.util
import pathlib

import pytest

Image = pytest.importorskip("PIL.Image")
SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "icones-matrix.py"
PERMITIDAS = {(0, 0, 0, 255), (0, 255, 65, 255), (144, 144, 144, 255), (255, 255, 255, 255)}


@pytest.fixture
def m():
    spec = importlib.util.spec_from_file_location("icones_matrix", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _icone_fundo_branco_com_bola_verde(caminho):
    im = Image.new("RGBA", (192, 192), (255, 255, 255, 255))
    for y in range(192):
        for x in range(192):
            if (x - 96) ** 2 + (y - 96) ** 2 < 50 ** 2:
                im.putpixel((x, y), (37, 211, 102, 255))
    im.save(caminho)


def test_so_cores_permitidas_e_tamanho(m, tmp_path):
    a = tmp_path / "a.png"
    _icone_fundo_branco_com_bola_verde(a)
    r = m.matrix(a)
    assert r.size == (192, 192)
    assert set(r.getdata()) <= PERMITIDAS


def test_fundo_some_e_o_desenho_fica_verde(m, tmp_path):
    a = tmp_path / "a.png"
    _icone_fundo_branco_com_bola_verde(a)
    r = m.matrix(a)
    assert r.getpixel((96, 96)) == (0, 255, 65, 255)  # centro da bola
    assert r.getpixel((30, 96)) == (0, 0, 0, 255)  # fundo branco virou preto


def test_icone_recortado_transparente(m, tmp_path):
    a = tmp_path / "b.png"
    im = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
    for y in range(60, 132):
        for x in range(60, 132):
            im.putpixel((x, y), (200, 30, 30, 255))
    im.save(a)
    r = m.matrix(a)
    assert r.getpixel((96, 96)) == (0, 255, 65, 255) and r.getpixel((40, 40)) == (0, 0, 0, 255)
    assert set(r.getdata()) <= PERMITIDAS


def test_pixelado_em_blocos_de_6(m, tmp_path):
    a = tmp_path / "a.png"
    _icone_fundo_branco_com_bola_verde(a)
    r = m.matrix(a)
    for bx in range(0, 192, 6):
        bloco = {r.getpixel((bx + dx, 90 + dy)) for dx in range(6) for dy in range(6) if 90 + dy < 96}
        assert len(bloco) == 1
