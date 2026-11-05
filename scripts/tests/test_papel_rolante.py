"""Testes do papel-rolante.py com adb FALSO (nenhum aparelho e tocado)."""
import importlib.util
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "papel-rolante.py"
COMP = "br.embeeded.papel/br.embeeded.papel.Papel"


class R:
    def __init__(self, rc=0, out=""):
        self.returncode, self.stdout, self.stderr = rc, out, ""


@pytest.fixture
def m(tmp_path):
    spec = importlib.util.spec_from_file_location("papel_rolante", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    apk = tmp_path / "papel.apk"
    apk.write_bytes(b"apk falso")
    mod.APK = apk
    e = {"cabo": True, "comp": "com.android.systemui/com.android.systemui.ImageWallpaper", "instalado": None,
         "offset": "mLastWallpaperDisplayOffsetX=0 mLastWallpaperDisplayOffsetY=-321", "chamadas": [],
         "install_saida": "Success", "definir": "OK"}
    mod.estado = e

    def falso(cmd, **kw):
        e["chamadas"].append(cmd)
        a = cmd[1:]
        if a == ["get-state"]:
            return R(0 if e["cabo"] else 1, "device" if e["cabo"] else "")
        if a[0] == "install":
            if "Success" in e["install_saida"]:
                e["instalado"] = "novo"
            return R(0 if "Success" in e["install_saida"] else 1, e["install_saida"])
        if a[0] == "uninstall":
            e["instalado"] = None
            e["install_saida"] = "Success"
            return R(0, "Success")
        if a[0] == "push":
            return R(0, "1 file pushed")
        c = a[1] if a[0] == "shell" else ""
        if "mWallpaperComponent" in c:
            return R(0, "  mWallpaperComponent=ComponentInfo{%s}" % e["comp"])
        if "mLastWallpaperDisplayOffset" in c:
            return R(0, "  " + e["offset"])
        if c.startswith("pm path"):
            return R(0, "package:/data/app/x/base.apk" if e["instalado"] else "")
        if c.startswith("sha256sum"):
            return R(0, (e["instalado"] if len(e["instalado"] or "") == 64 else "0" * 64) + "  base.apk")
        if "Definir ativar" in c:
            if e["definir"] == "OK":
                e["comp"] = COMP
            return R(0, e["definir"] + " ativar via setWallpaperComponentChecked/3")
        if "Definir desfazer" in c:
            e["comp"] = "com.android.systemui/com.android.systemui.ImageWallpaper"
            return R(0, "OK desfazer")
        return R(0, "")
    mod._executa = falso
    mod.prepara_imagem = lambda o, d: (pathlib.Path(d).write_bytes(b"jpg"), (2844, 1600))[1]
    return mod


def shells(m):
    return [c[2] for c in m.estado["chamadas"] if c[1] == "shell"]


def test_sem_cabo_nao_faz_nada(m):
    m.estado["cabo"] = False
    assert m.main(["aplicar"]) == 2
    assert len(m.estado["chamadas"]) == 1


def test_aplicar_instala_envia_deslocamento_e_ativa(m, tmp_path, capsys):
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    assert m.main(["aplicar", "--imagem", str(img)]) == 0
    out = capsys.readouterr().out
    assert "ATIVO" in out and "0 -321" in out
    assert any("echo '0 -321' >" in c and c.endswith("/desloc.txt") for c in shells(m))
    assert any(c[1] == "push" and c[-1].endswith("/files/papel.jpg") for c in m.estado["chamadas"])
    assert m.estado["comp"] == COMP


def test_mesma_versao_nao_reinstala(m, tmp_path):
    import hashlib
    m.estado["instalado"] = hashlib.sha256(m.APK.read_bytes()).hexdigest()
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    assert m.main(["aplicar", "--imagem", str(img)]) == 0
    assert not [c for c in m.estado["chamadas"] if c[1] == "install"]


def test_assinatura_diferente_desinstala_e_instala(m, tmp_path):
    m.estado["install_saida"] = "Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE]"
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    assert m.main(["aplicar", "--imagem", str(img)]) == 0
    assert ["adb", "uninstall", "br.embeeded.papel"] in m.estado["chamadas"]


def test_so_desinstala_o_proprio_pacote(m, tmp_path):
    m.estado["install_saida"] = "Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE]"
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    m.main(["aplicar", "--imagem", str(img)])
    for c in m.estado["chamadas"]:
        if c[1] == "uninstall":
            assert c == ["adb", "uninstall", "br.embeeded.papel"]
        if c[1] == "shell":
            assert "pm uninstall" not in c[2] and "rm " not in c[2]


def test_falha_ao_ativar_avisa(m, tmp_path, capsys):
    m.estado["definir"] = "ERRO"
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    assert m.main(["aplicar", "--imagem", str(img)]) == 1
    assert "FALHOU" in capsys.readouterr().out


def test_imagem_inexistente(m, tmp_path):
    assert m.main(["aplicar", "--imagem", str(tmp_path / "nao.png")]) == 2
    assert not [c for c in m.estado["chamadas"] if c[1] in ("install", "push")]


def test_paginas_limitadas(m, tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    m.main(["aplicar", "--imagem", str(img), "--paginas", "50"])
    assert any(c.startswith("echo 9 >") and c.endswith("/paginas.txt") for c in shells(m))


def test_deslocamento_sem_valor_vira_zero(m):
    m.estado["offset"] = "mLastWallpaperDisplayOffsetX=-2147483648 mLastWallpaperDisplayOffsetY=-2147483648"
    assert m.deslocamento() == (0, 0)
    m.estado["offset"] = ""
    assert m.deslocamento() == (0, 0)


def test_desfazer_volta_ao_papel_comum(m, capsys):
    m.estado["comp"] = COMP
    assert m.main(["desfazer"]) == 0
    assert "Papel comum de volta" in capsys.readouterr().out


def test_status_inativo(m, capsys):
    assert m.main(["status"]) == 1
    assert "inativo" in capsys.readouterr().out


def test_imagem_estreita_avisa(m, tmp_path, capsys):
    m.prepara_imagem = lambda o, d: (720, 1600)
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    assert m.main(["aplicar", "--imagem", str(img)]) == 0
    assert "nao rola" in capsys.readouterr().out


@pytest.fixture
def ms(m):
    m.estado["acess"] = "com.freerdp.afreerdp/x.Teclado:org.kde.kdeconnect_tp/y.Kde"
    antigo = m._executa

    def falso(cmd, **kw):
        c = cmd[2] if len(cmd) > 2 and cmd[1] == "shell" else ""
        if c == "settings get secure enabled_accessibility_services":
            m.estado["chamadas"].append(cmd)
            return R(0, m.estado["acess"] or "null")
        if c.startswith("settings put secure enabled_accessibility_services "):
            m.estado["chamadas"].append(cmd)
            m.estado["acess"] = c.split(" ", 4)[4].strip("'")
            return R(0, "")
        if c == "settings delete secure enabled_accessibility_services":
            m.estado["chamadas"].append(cmd)
            m.estado["acess"] = ""
            return R(0, "")
        return antigo(cmd, **kw)
    m._executa = falso
    return m


def test_sincronia_liga_sem_tirar_os_outros(ms):
    assert ms.main(["sincronia", "ligar"]) == 0
    lista = ms.estado["acess"].split(":")
    assert lista[:2] == ["com.freerdp.afreerdp/x.Teclado", "org.kde.kdeconnect_tp/y.Kde"]
    assert lista[2] == "br.embeeded.papel/br.embeeded.papel.Sincronia"


def test_sincronia_ligar_duas_vezes_nao_duplica(ms):
    ms.main(["sincronia", "ligar"])
    ms.main(["sincronia", "ligar"])
    assert ms.estado["acess"].count("Sincronia") == 1


def test_sincronia_desliga_so_a_propria(ms):
    ms.main(["sincronia", "ligar"])
    assert ms.main(["sincronia", "desligar"]) == 0
    assert ms.estado["acess"] == "com.freerdp.afreerdp/x.Teclado:org.kde.kdeconnect_tp/y.Kde"


def test_sincronia_status_nao_muda_nada(ms):
    assert ms.main(["sincronia"]) == 1
    assert not [c for c in ms.estado["chamadas"] if c[1] == "shell" and "settings put" in c[2]]


def test_aplicar_tambem_poe_no_bloqueio(m, tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    assert m.main(["aplicar", "--imagem", str(img)]) == 0
    assert any("Definir bloqueio" in c for c in shells(m))
