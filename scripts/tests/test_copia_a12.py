"""copia-a12.py: decisoes do plano, filtros e travas. O adb nunca e aberto; a prova no aparelho e o 'conferir'."""
import hashlib
import io
import json
import tarfile

import pytest


@pytest.fixture
def m(importa_script):
    return importa_script("copia-a12.py")


def estado(**k):
    base = {
        "pacotes": {"ativos": ["a.fdroid", "b.play", "org.heliboard", "com.android.settings"], "desativados": ["sam.velho"], "no_sistema": ["a.fdroid", "b.play", "org.heliboard", "sam.velho", "sam.removido", "com.android.settings"], "terceiros": ["a.fdroid", "b.play", "org.heliboard"]},
        "instaladores": {"a.fdroid": "org.fdroid.fdroid", "b.play": "com.android.vending"},
        "permissoes": {"a.fdroid": ["android.permission.CAMERA"]},
        "papeis": {"android.app.role.SMS": ["org.fossify"]},
        "teclado": "org.heliboard/.Ime",
        "isentos_bateria": ["a.fdroid"],
        "ajustes": {},
    }
    base.update(k)
    return base


def test_filtro_tira_identificadores_e_nome_de_rede(m):
    texto = "android_id=abc\nbluetooth_name=Meu\nwifi_saved_state=x\nlast_ssid=casa\ndevice_name=A12\nwindow_animation_scale=0.0\nsem_chave\nbonded_device_mhsside=1\n"
    assert m.filtra_ajustes(texto) == {"window_animation_scale": "0.0"}


def test_permissoes_so_as_concedidas(m):
    d = "    runtime permissions:\n      android.permission.CAMERA: granted=true, flags=[]\n      android.permission.READ_SMS: granted=false, flags=[]\n"
    assert m.permissoes_concedidas(d) == ["android.permission.CAMERA"]


def test_instalador(m):
    assert m.instalador("  installerPackageName=org.fdroid.fdroid\n") == "org.fdroid.fdroid"
    assert m.instalador("  installerPackageName=null\n") == ""


@pytest.mark.parametrize("ruim", ["../fora.txt", "a/../../b", "/a//b", "a/./b"])
def test_nome_no_pc_recusa_sair_da_pasta(m, ruim):
    with pytest.raises(ValueError):
        m.nome_no_pc(ruim)


def test_nome_no_pc_aceito_pelo_windows(m):
    assert m.nome_no_pc('Dir: x/foto?.jpg ') == "Dir_ x/foto_.jpg"
    assert m.nome_no_pc("CON/nul.txt") == "_CON/_nul.txt"


def tar_com(*itens):
    b = io.BytesIO()
    with tarfile.open(fileobj=b, mode="w") as t:
        for nome, dado in itens:
            i = tarfile.TarInfo(nome)
            i.size = len(dado)
            t.addfile(i, io.BytesIO(dado))
    b.seek(0)
    return b


def test_extrai_grava_so_o_esperado_e_devolve_md5(m, tmp_path):
    f = m.extrai_tar(tar_com(("a/b.txt", b"oi"), ("nao/pedido.txt", b"x")), tmp_path, {"a/b.txt"})
    assert f == {"a/b.txt": ("a/b.txt", hashlib.md5(b"oi").hexdigest())}
    assert (tmp_path / "a" / "b.txt").read_bytes() == b"oi"
    assert not (tmp_path / "nao").exists()


def test_extrai_guarda_arquivo_oculto_com_o_ponto(m, tmp_path):
    f = m.extrai_tar(tar_com(("./.oculto/x", b"1")), tmp_path, {".oculto/x"})
    assert list(f) == [".oculto/x"]
    assert (tmp_path / ".oculto" / "x").exists()


def test_extrai_nao_escapa_da_pasta(m, tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    f = m.extrai_tar(tar_com(("../fora.txt", b"x"), ("bom.txt", b"y")), base, {"../fora.txt", "bom.txt"})
    assert list(f) == ["bom.txt"]  # recusa o perigoso e segue com o resto
    assert not (tmp_path / "fora.txt").exists()


def test_barra_invertida_e_parte_do_nome(m):
    assert m.nome_no_pc("Android/data/app/\\.WL/log.txt") == "Android/data/app/_.WL/log.txt"


def agora_limpo():
    return {
        "pacotes": {"ativos": ["com.android.settings", "sam.velho", "sam.removido"], "desativados": [], "no_sistema": ["com.android.settings", "sam.velho", "sam.removido"], "terceiros": []},
        "permissoes": {}, "papeis": {}, "teclado": "sam/.Ime", "isentos_bateria": [],
    }


def test_plano_depois_do_firmware_original(m):
    lotes = {"R1": {"aplicavel": True, "pacotes": ["sam.velho", "sam.removido"]}, "NAO": {"aplicavel": False, "pacotes": ["sam.velho"]}}
    p = m.plano(estado(), agora_limpo(), lotes, [r"^com\.android\."])
    assert p["apps"] == ["a.fdroid", "b.play", "org.heliboard"]
    assert p["lotes"] == ["R1"]
    assert p["remover"] == ["sam.removido"]
    assert p["teclado"] == "org.heliboard/.Ime"
    assert p["papeis"] == {"android.app.role.SMS": ["org.fossify"]}
    assert p["isentos"] == ["a.fdroid"]


def test_plano_nada_a_fazer_quando_igual(m):
    e = estado()
    a = json.loads(json.dumps(e))
    assert not any(m.plano(e, a, {}, []).values())


def test_plano_nao_desativa_protegido_fora_de_lote(m):
    e = estado()
    e["pacotes"]["ativos"] = ["sam.velho", "sam.removido"]
    e["pacotes"]["desativados"] = ["com.android.settings", "sam.solto"]
    e["pacotes"]["no_sistema"] = ["com.android.settings", "sam.solto", "sam.velho", "sam.removido"]
    e["pacotes"]["terceiros"] = []
    a = agora_limpo()
    a["pacotes"]["ativos"] += ["sam.solto"]
    p = m.plano(e, a, {}, [r"^com\.android\."])
    assert p["desativar_fora_de_lote"] == ["sam.solto"]
    assert p["protegidos_fora_de_lote"] == ["com.android.settings"]


def test_plano_nunca_tira_app_instalado_depois_da_copia(m):
    e = estado()
    a = json.loads(json.dumps(e))
    a["pacotes"]["ativos"].append("novo.app")
    a["pacotes"]["terceiros"].append("novo.app")
    p = m.plano(e, a, {"R": {"aplicavel": True, "pacotes": ["novo.app"]}}, [])
    assert "novo.app" not in p["remover"] + p["desativar_fora_de_lote"]
    assert p["lotes"] == []


def test_plano_nao_reinstala_app_so_desativado(m):
    e = estado()
    a = json.loads(json.dumps(e))
    a["pacotes"]["ativos"].remove("a.fdroid")
    a["pacotes"]["desativados"].append("a.fdroid")
    assert m.plano(e, a, {}, [])["apps"] == []


def test_recusa_outro_aparelho(m, monkeypatch):
    monkeypatch.setattr(m, "sh", lambda c, timeout=600: "SM-G991B")
    with pytest.raises(SystemExit) as e:
        m.conferir_aparelho()
    assert "SM-A125M" in str(e.value)


def test_restaurar_sem_copia_recusa(m, monkeypatch, tmp_path):
    monkeypatch.setattr(m, "sh", lambda c, timeout=600: m.MODELO)
    with pytest.raises(SystemExit) as e:
        m.restaurar(tmp_path / "nada", False, set(m.ETAPAS))
    assert "nao ha copia" in str(e.value)


def test_simulacao_nao_muda_o_aparelho(m, monkeypatch, tmp_path):
    (tmp_path / "estado.json").write_text(json.dumps(estado()), encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "lotes-bloatware.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(m, "RAIZ", tmp_path)
    monkeypatch.setattr(m, "carrega_protegidos", lambda: [])
    comandos = []

    def falso_sh(c, timeout=600):
        comandos.append(c)
        return m.MODELO if "ro.product.model" in c else ""

    monkeypatch.setattr(m, "sh", falso_sh)
    monkeypatch.setattr(m, "fotografia", agora_limpo)
    monkeypatch.setattr(m, "adb", lambda *a, **k: pytest.fail(f"adb na simulacao: {a}"))
    monkeypatch.setattr(m, "script", lambda *a: pytest.fail(f"script na simulacao: {a}"))
    monkeypatch.setattr(m, "le_manifesto_celular", lambda: {})
    assert m.restaurar(tmp_path, False, set(m.ETAPAS)) == 3
    assert not [c for c in comandos if any(x in c for x in ("pm ", "cmd role add", "ime ", "settings put", "rm "))]


def test_simulacao_da_copia_nao_grava(m, monkeypatch, tmp_path):
    destino = tmp_path / "copia"
    monkeypatch.setattr(m, "sh", lambda c, timeout=600: m.MODELO if "ro.product.model" in c else "")
    monkeypatch.setattr(m, "fotografia", lambda: estado())
    monkeypatch.setattr(m, "le_manifesto_celular", lambda: {"a.txt": "0" * 32})
    assert m.copiar(destino, False) == 0
    assert not destino.exists()


def test_sem_espaco_nao_copia(m, monkeypatch, tmp_path):
    monkeypatch.setattr(m, "sh", lambda c, timeout=600: m.MODELO)
    monkeypatch.setattr(m.shutil, "disk_usage", lambda p: type("U", (), {"free": 1024})())
    with pytest.raises(SystemExit) as e:
        m.copiar(tmp_path / "c", True)
    assert "15 GB" in str(e.value)


def test_manifesto_le_nome_com_espaco_e_ignora_fora(m, monkeypatch):
    saida = f"{'a' * 32}  {m.ORIGEM}/Pasta X/foto 1.jpg\n{'b' * 32}  /outro/lugar\nlixo\n"
    monkeypatch.setattr(m, "sh", lambda c, timeout=600: saida)
    assert m.le_manifesto_celular() == {"Pasta X/foto 1.jpg": "a" * 32}


def test_termux_nao_leva_chaves(m):
    for x in (".omniroute", ".env", ".ssh", "*.gguf"):
        assert x in m.TERMUX_FORA
