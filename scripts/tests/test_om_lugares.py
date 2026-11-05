"""Testes de scripts/om-lugares.py: validacao do KML, nomes seguros (o nome vai para o shell do aparelho), simulacao sem adb,
ordem exata dos comandos do --aplicar, travas (bateria, espaco, lista grande visivel), medicao e protecao do dashcam.
Nenhum teste toca o adb de verdade: subprocess.run e trocado por um aparelho falso e time.sleep vira nada."""
import types

import pytest

CABECA = '<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Lugares teste</name>'
RODAPE = "</Document></kml>"


def lugar(nome: "str | None" = "Loja A", coord="-46.33,-23.96,0"):
    nome_xml = f"<name>{nome}</name>" if nome is not None else ""
    return f"<Placemark>{nome_xml}<Point><coordinates>{coord}</coordinates></Point></Placemark>"


def grava(tmp_path, corpo, oculta=True, nome="lugares.kml"):
    texto = CABECA + ("<visibility>0</visibility>" if oculta else "") + corpo + RODAPE
    caminho = tmp_path / nome
    caminho.write_text(texto, encoding="utf-8")
    return caminho


class AdbFalso:
    """Aparelho de brinquedo: guarda cada comando e responde o que o Android responderia."""

    def __init__(self, bateria="level: 80\n  USB powered: true", livre_kb=50_000_000, ids_atrasados=0, id_arquivo=4242,
                 em_primeiro_plano="", tempos=(481, 418, 417), push_ok=True, meminfo=None, abre_app=True, inicio_app=None):
        self.chamadas = []
        self.bateria, self.livre_kb, self.ids_atrasados, self.id_arquivo = bateria, livre_kb, ids_atrasados, id_arquivo
        self.em_primeiro_plano, self.tempos, self.push_ok, self.abre_app = em_primeiro_plano, list(tempos), push_ok, abre_app
        self.meminfo = meminfo or ("  Native Heap   215966   215920        8       29   217188   222512   209913    12598\n"
                                   "           TOTAL PSS:   304454            TOTAL RSS:   365440       TOTAL SWAP PSS:      261\n")
        self.inicio_app = inicio_app

    def run(self, cmd, **kw):
        self.chamadas.append(cmd)
        if cmd[:2] == ["adb", "push"]:
            return types.SimpleNamespace(returncode=0 if self.push_ok else 1, stdout="1 file pushed" if self.push_ok else "", stderr="" if self.push_ok else "erro")
        c = cmd[2]
        saida = ""
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c.startswith("pm list packages"):
            saida = "package:app.organicmaps"
        elif c == "dumpsys battery":
            saida = self.bateria
        elif c.startswith("df -k"):
            saida = f"Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/fuse 60000000 10000000 {self.livre_kb} 17% /storage/emulated"
        elif c.startswith("content query"):
            if self.ids_atrasados > 0:
                self.ids_atrasados -= 1
                saida = "No result found."
            elif self.id_arquivo is None:
                saida = "No result found."
            else:
                saida = f"Row: 0 _id={self.id_arquivo}"
        elif c.startswith("[ -e "):
            saida = "SUMIU"
        elif c == "dumpsys activity activities":
            saida = self.em_primeiro_plano
        elif c.startswith("am start -W"):
            if self.abre_app and self.tempos:
                saida = f"Status: ok\nActivity: app.organicmaps/.SplashActivity\nTotalTime: {self.tempos.pop(0)}\nWaitTime: 500"
            else:
                saida = "Error type 3\nError: Activity class does not exist."
        elif c.startswith("dumpsys meminfo"):
            saida = self.meminfo
        elif c.startswith("am start --grant"):
            saida = self.inicio_app if self.inicio_app is not None else "Starting: Intent { act=android.intent.action.VIEW }"
        return types.SimpleNamespace(returncode=0, stdout=saida, stderr="")

    def comandos(self):
        return [c[2] if c[:2] == ["adb", "shell"] else " ".join(c) for c in self.chamadas]


@pytest.fixture
def om(importa_script, monkeypatch):
    mod = importa_script("om-lugares.py")
    esperas = []
    monkeypatch.setattr(mod.time, "sleep", lambda s: esperas.append(s))
    mod._esperas = esperas
    return mod


def com_adb(mod, monkeypatch, **kw):
    falso = AdbFalso(**kw)
    monkeypatch.setattr(mod.subprocess, "run", falso.run)
    return falso


# ---------------------------------------------------------------- validacao do KML

def test_valida_kml_conta_lugares_e_acha_defeitos(om, tmp_path):
    corpo = lugar() + lugar(None) + lugar("Sem coordenada", "abc,def") + lugar("Fora do Brasil", "10.5,50.2,0")
    info = om.valida_kml(grava(tmp_path, corpo))
    assert info["lugares"] == 4 and info["sem_nome"] == 1 and info["sem_coordenada"] == 1 and info["fora_do_brasil"] == 1
    assert info["oculta"] is True and info["titulo"] == "Lugares teste" and info["bytes"] > 0


def test_valida_kml_lista_visivel_nao_e_oculta(om, tmp_path):
    info = om.valida_kml(grava(tmp_path, lugar(), oculta=False))
    assert info["oculta"] is False and info["lugares"] == 1


def test_valida_kml_coordenada_trocada_conta_como_fora_do_brasil(om, tmp_path):
    """lat,lon trocados em Santos (-23.96,-46.33) viram lon=-23.96 (fora de -75..-30) e lat=-46.33 (fora de -35..6): a troca e pega."""
    info = om.valida_kml(grava(tmp_path, lugar("Troca", "-23.96,-46.33,0")))
    assert info["fora_do_brasil"] == 1


@pytest.mark.parametrize("texto,trecho", [
    ('<?xml version="1.0"?><!DOCTYPE kml [<!ENTITY a "b">]><kml><Document><Placemark/></Document></kml>', "DOCTYPE"),
    ('<?xml version="1.0"?><!ENTITY x "y"><kml/>', "DOCTYPE"),
    (CABECA + lugar() + "<Placemark>", "XML quebrado"),
    (CABECA + RODAPE, "nenhum"),
])
def test_valida_kml_recusa_arquivo_ruim(om, tmp_path, texto, trecho):
    p = tmp_path / "ruim.kml"
    p.write_text(texto, encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        om.valida_kml(p)
    assert trecho in str(exc.value)


def test_valida_kml_recusa_doctype_depois_de_comentario_longo(om, tmp_path):
    """A trava nao pode olhar so o inicio: um comentario de 20 KB empurra o DOCTYPE para alem dos primeiros bytes."""
    texto = ('<?xml version="1.0"?><!-- ' + "x" * 20000 + ' --><!DOCTYPE kml [<!ENTITY a "b">]>'
             + CABECA.split("\n", 1)[1] + lugar() + RODAPE)
    p = tmp_path / "longo.kml"
    p.write_text(texto, encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        om.valida_kml(p)
    assert "DOCTYPE" in str(exc.value)


def test_valida_kml_recusa_doctype_na_fronteira_de_dois_blocos(om, tmp_path, monkeypatch):
    texto = CABECA.split("\n", 1)[0] + "<!-- " + "y" * 90 + " --><!DOCTYPE kml>" + CABECA.split("\n", 1)[1] + lugar() + RODAPE
    p = tmp_path / "fronteira.kml"
    p.write_text(texto, encoding="utf-8")
    for bloco in range(40, 140, 7):  # o marcador cai em posicoes diferentes em relacao ao corte do bloco
        with pytest.raises(ValueError):
            om.recusa_doctype(p, bloco=bloco)


def test_valida_kml_recusa_utf16(om, tmp_path):
    p = tmp_path / "u16.kml"
    p.write_bytes((CABECA + lugar() + RODAPE).encode("utf-16"))
    with pytest.raises(ValueError) as exc:
        om.valida_kml(p)
    assert "UTF-16" in str(exc.value)


# ---------------------------------------------------------------- nomes seguros

@pytest.mark.parametrize("nome", ["a b.kml", "x;reboot.kml", "../x.kml", "x.txt", "x.kml.sh", "$(id).kml", "", ".kml", "x'y.kml", "a/b.kml", "x..y.kml"])
def test_nome_de_arquivo_perigoso_e_recusado(om, nome):
    with pytest.raises(SystemExit) as exc:
        om.nome_seguro(nome)
    assert "nome de arquivo invalido" in str(exc.value)


def test_nome_de_arquivo_comum_passa(om):
    assert om.nome_seguro("lugares-baixada_santista.v2.kml") == "lugares-baixada_santista.v2.kml"


def test_importar_recusa_nome_perigoso_antes_de_qualquer_adb(om, monkeypatch, tmp_path):
    def proibido(cmd, **kw):
        raise AssertionError(f"nao deveria chamar adb: {cmd!r}")
    monkeypatch.setattr(om.subprocess, "run", proibido)
    p = tmp_path / "x;reboot.kml"
    p.write_text(CABECA + lugar() + RODAPE, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        om.importar([str(p)], True, 0, False)
    assert "nome de arquivo invalido" in str(exc.value)


# ---------------------------------------------------------------- importar: simulacao e travas

def test_simulacao_nao_chama_adb_e_diz_simulacao(om, monkeypatch, tmp_path, capsys):
    def proibido(cmd, **kw):
        raise AssertionError(f"simulacao nao pode tocar o aparelho: {cmd!r}")
    monkeypatch.setattr(om.subprocess, "run", proibido)
    p = grava(tmp_path, lugar() + lugar("Loja B", "-46.4,-24.0,0"))
    assert om.importar([str(p)], False, 30, False) == 0
    saida = capsys.readouterr().out
    assert "2 lugares" in saida and "oculta" in saida and "SIMULACAO" in saida


def test_lista_grande_visivel_e_recusada_e_o_flag_libera(om, tmp_path):
    p = grava(tmp_path, lugar() * (om.LIMITE_VISIVEL + 1), oculta=False)
    with pytest.raises(SystemExit) as exc:
        om.importar([str(p)], False, 30, False)
    assert "pinos" in str(exc.value)
    assert om.importar([str(p)], False, 30, True) == 0


def test_arquivo_sem_coordenada_aborta(om, tmp_path):
    p = grava(tmp_path, lugar("A", "abc"))
    with pytest.raises(SystemExit) as exc:
        om.importar([str(p)], False, 30, False)
    assert "mal gerado" in str(exc.value)


def test_arquivo_que_nao_existe_aborta(om, tmp_path):
    with pytest.raises(SystemExit) as exc:
        om.importar([str(tmp_path / "nao-existe.kml")], False, 30, False)
    assert "nao existe" in str(exc.value)


# ---------------------------------------------------------------- importar --aplicar

def test_aplicar_sequencia_exata_de_comandos(om, monkeypatch, tmp_path):
    falso = com_adb(om, monkeypatch, ids_atrasados=2)
    p = grava(tmp_path, lugar())
    assert om.importar([str(p)], True, 30, False) == 0
    cmds = falso.comandos()
    iniciais = [c.split()[0] for c in cmds]
    ordem = ["getprop", "pm", "dumpsys", "df", "adb", "am", "content", "content", "content", "am"]
    assert iniciais == ordem, cmds
    assert cmds[4].startswith("adb push ") and cmds[4].endswith("/sdcard/Download/lugares.kml")
    assert cmds[5] == "am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Download/lugares.kml"
    assert "_data='/storage/emulated/0/Download/lugares.kml'" in cmds[6]
    assert cmds[-1] == ("am start --grant-read-uri-permission -a android.intent.action.VIEW "
                        "-d content://media/external/file/4242 -t application/vnd.google-earth.kml+xml -p app.organicmaps")
    assert om._esperas == [1, 1]  # o MediaStore demorou 2 consultas; nao ha espera depois do ultimo (nem do unico) arquivo


@pytest.mark.parametrize("bateria", [
    "level: 2\n  USB powered: true",
    "level: 80\n  AC powered: false\n  USB powered: false\n  Wireless powered: false",
    "",
])
def test_aplicar_aborta_com_bateria_baixa_ou_fora_do_carregador(om, monkeypatch, tmp_path, bateria):
    falso = com_adb(om, monkeypatch, bateria=bateria)
    p = grava(tmp_path, lugar())
    with pytest.raises(SystemExit) as exc:
        om.importar([str(p)], True, 30, False)
    assert "bateria" in str(exc.value)
    assert not any(c.startswith("adb push") for c in falso.comandos())


def test_aplicar_aceita_exatamente_3_por_cento_carregando(om, monkeypatch, tmp_path):
    """Regra do Rafael (29/10): o trabalho so para com 3%; com 3% e carregando segue."""
    falso = com_adb(om, monkeypatch, bateria="level: 3\n  AC powered: true")
    assert om.importar([str(grava(tmp_path, lugar()))], True, 30, False) == 0
    assert any(c.startswith("adb push") for c in falso.comandos())


def test_aplicar_aborta_sem_espaco(om, monkeypatch, tmp_path):
    falso = com_adb(om, monkeypatch, livre_kb=1)
    p = grava(tmp_path, lugar())
    with pytest.raises(SystemExit) as exc:
        om.importar([str(p)], True, 30, False)
    assert "espaco" in str(exc.value)
    assert not any(c.startswith("adb push") for c in falso.comandos())


def test_aplicar_aborta_se_o_aparelho_nao_for_o_a12(om, monkeypatch, tmp_path):
    falso = com_adb(om, monkeypatch)
    original = falso.run

    def outro_aparelho(cmd, **kw):
        if cmd[:3] == ["adb", "shell", "getprop ro.product.model"]:
            falso.chamadas.append(cmd)
            return types.SimpleNamespace(returncode=0, stdout="Pixel 7", stderr="")
        return original(cmd, **kw)
    monkeypatch.setattr(om.subprocess, "run", outro_aparelho)
    with pytest.raises(SystemExit) as exc:
        om.importar([str(grava(tmp_path, lugar()))], True, 30, False)
    assert "inesperado" in str(exc.value)
    assert not any(c.startswith("adb push") for c in falso.comandos())


def test_aplicar_falha_se_o_mediastore_nao_indexa(om, monkeypatch, tmp_path, capsys):
    falso = com_adb(om, monkeypatch, id_arquivo=None)
    p = grava(tmp_path, lugar())
    assert om.importar([str(p)], True, 30, False) == 1
    assert "nao indexou" in capsys.readouterr().out
    assert not any(c.startswith("am start --grant") for c in falso.comandos())


def test_aplicar_falha_se_o_push_falha(om, monkeypatch, tmp_path, capsys):
    falso = com_adb(om, monkeypatch, push_ok=False)
    assert om.importar([str(grava(tmp_path, lugar()))], True, 30, False) == 1
    assert "FALHOU ao copiar" in capsys.readouterr().out
    assert not any(c.startswith("am broadcast") for c in falso.comandos())


def test_aplicar_falha_se_o_organic_maps_recusa_o_arquivo(om, monkeypatch, tmp_path, capsys):
    com_adb(om, monkeypatch, inicio_app="Error: Activity not started, unable to resolve Intent")
    assert om.importar([str(grava(tmp_path, lugar()))], True, 30, False) == 1
    assert "FALHOU ao abrir" in capsys.readouterr().out


def test_aplicar_varios_arquivos_espera_so_entre_eles(om, monkeypatch, tmp_path):
    falso = com_adb(om, monkeypatch)
    a, b, c = (grava(tmp_path, lugar(), nome=f"lista{i}.kml") for i in range(3))
    assert om.importar([str(a), str(b), str(c)], True, 45, False) == 0
    assert om._esperas == [45, 45]
    assert sum(1 for x in falso.comandos() if x.startswith("am start --grant")) == 3


# ---------------------------------------------------------------- limpar-copias

def test_limpar_copias_simulacao_nao_apaga(om, monkeypatch, capsys):
    def proibido(cmd, **kw):
        raise AssertionError(f"simulacao nao pode tocar o aparelho: {cmd!r}")
    monkeypatch.setattr(om.subprocess, "run", proibido)
    assert om.limpar_copias(["a.kml", "b.kml"], False) == 0
    assert "SIMULACAO" in capsys.readouterr().out


def test_limpar_copias_aplicar_apaga_so_o_que_foi_pedido(om, monkeypatch):
    falso = com_adb(om, monkeypatch)
    assert om.limpar_copias(["a.kml"], True) == 0
    assert falso.comandos() == ["rm -f /sdcard/Download/a.kml",
                                "am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Download/a.kml",
                                "[ -e /sdcard/Download/a.kml ] && echo AINDA_EXISTE || echo SUMIU"]


def test_limpar_copias_nao_diz_apagado_se_o_arquivo_continua(om, monkeypatch, capsys):
    falso = com_adb(om, monkeypatch)
    original = falso.run

    def run(cmd, **kw):
        if cmd[:2] == ["adb", "shell"] and "[ -e" in cmd[2]:
            falso.chamadas.append(cmd)
            return types.SimpleNamespace(returncode=0, stdout="AINDA_EXISTE", stderr="")
        return original(cmd, **kw)

    monkeypatch.setattr(om.subprocess, "run", run)
    assert om.limpar_copias(["a.kml"], True) == 1
    saida = capsys.readouterr().out
    assert "FALHOU" in saida and "apagado:" not in saida


def test_limpar_copias_adb_mudo_tambem_e_falha(om, monkeypatch, capsys):
    com_adb(om, monkeypatch)
    monkeypatch.setattr(om.subprocess, "run", lambda cmd, **kw: types.SimpleNamespace(returncode=1, stdout="", stderr="error: closed"))
    assert om.limpar_copias(["a.kml"], True) == 1
    assert "apagado:" not in capsys.readouterr().out


def test_limpar_copias_recusa_nome_perigoso(om, monkeypatch):
    com_adb(om, monkeypatch)
    with pytest.raises(SystemExit):
        om.limpar_copias(["../../data/x.kml"], True)


# ---------------------------------------------------------------- medir

def test_medir_le_tempos_e_memoria(om, monkeypatch, capsys):
    falso = com_adb(om, monkeypatch)
    assert om.medir(False, 3) == 0
    saida = capsys.readouterr().out
    assert "481 / 418 / 417" in saida and "mediana 418" in saida
    assert "PSS total 304454 KB (297 MiB)" in saida and "Native Heap 215966 KB (211 MiB)" in saida
    cmds = falso.comandos()
    assert cmds.count("am force-stop app.organicmaps") == 3
    assert sum(1 for c in cmds if c.startswith("am start -W -n app.organicmaps/.SplashActivity")) == 3


def test_medir_aborta_com_o_dashcam_em_primeiro_plano_sem_forcar(om, monkeypatch):
    em_uso = ("  mResumedActivity: ActivityRecord{1 u0 app.organicmaps/.MwmActivity t12}\n"
              "  topResumedActivity=ActivityRecord{2 u0 net.sourceforge.opencamera/.MainActivity t13}\n")
    falso = com_adb(om, monkeypatch, em_primeiro_plano=em_uso)
    with pytest.raises(SystemExit) as exc:
        om.medir(False, 3)
    assert "app.organicmaps" in str(exc.value) and "net.sourceforge.opencamera" in str(exc.value)
    assert not any("force-stop" in c for c in falso.comandos())


def test_medir_com_forcar_mede_mesmo_com_o_app_aberto(om, monkeypatch):
    em_uso = "  mResumedActivity: ActivityRecord{1 u0 app.organicmaps/.MwmActivity t12}\n"
    falso = com_adb(om, monkeypatch, em_primeiro_plano=em_uso)
    assert om.medir(True, 1) == 0
    assert "am force-stop app.organicmaps" in falso.comandos()


def test_medir_nao_confunde_outro_app_com_o_dashcam(om, monkeypatch):
    outro = "  mResumedActivity: ActivityRecord{1 u0 com.android.settings/.Settings t9}\n"
    com_adb(om, monkeypatch, em_primeiro_plano=outro)
    assert om.medir(False, 1) == 0


def test_medir_falha_se_o_app_nao_abre(om, monkeypatch, capsys):
    com_adb(om, monkeypatch, abre_app=False)
    assert om.medir(False, 3) == 1
    assert "nao abriu" in capsys.readouterr().out


def test_medir_falha_se_nao_ler_a_memoria(om, monkeypatch, capsys):
    com_adb(om, monkeypatch, meminfo="No process found for: app.organicmaps")
    assert om.medir(False, 1) == 1
    assert "memoria" in capsys.readouterr().out


# ---------------------------------------------------------------- linha de comando

@pytest.mark.parametrize("args,trecho", [
    (["importar", "x.kml", "--espera", "601"], "--espera"),
    (["importar", "x.kml", "--espera", "-1"], "--espera"),
    (["medir", "--vezes", "0"], "--vezes"),
    (["medir", "--vezes", "11"], "--vezes"),
])
def test_main_valida_limites(om, monkeypatch, args, trecho):
    def proibido(cmd, **kw):
        raise AssertionError(f"nao deveria chamar adb: {cmd!r}")
    monkeypatch.setattr(om.subprocess, "run", proibido)
    monkeypatch.setattr("sys.argv", ["om-lugares.py"] + args)
    with pytest.raises(SystemExit) as exc:
        om.main()
    assert trecho in str(exc.value)


def test_main_importar_simulacao_sai_com_zero(om, monkeypatch, tmp_path):
    p = grava(tmp_path, lugar())
    monkeypatch.setattr("sys.argv", ["om-lugares.py", "importar", str(p)])
    with pytest.raises(SystemExit) as exc:
        om.main()
    assert exc.value.code == 0
