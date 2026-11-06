"""Testes de scripts/webcam-celular.py: nao mexer na configuracao do OBS do Rafael e nao declarar imagem sem imagem."""
import json
import subprocess
import types

import pytest


@pytest.fixture
def wc(importa_script):
    return importa_script("webcam-celular.py")


def test_scrcpy_usa_camera_direta_sem_audio_e_titulo_certo(wc):
    a = wc.args_scrcpy()
    assert "--video-source=camera" in a and "--camera-facing=back" in a and "--camera-size=1280x720" in a
    assert "--window-width=1280" in a and "--window-height=720" in a  # cabe no monitor 1440x900, sem reduzir a imagem
    assert "--video-bit-rate=8M" in a and "--video-buffer=50" not in a
    assert "--no-audio" in a and f"--window-title={wc.TITULO}" in a and "--camera-torch" not in a
    assert "--camera-facing=front" in wc.args_scrcpy(frontal=True)
    assert "--camera-torch" in wc.args_scrcpy(lanterna=True)  # lanterna so na prova


def test_obs_abre_com_perfil_proprio_e_camera_virtual(wc):
    a = wc.args_obs()
    assert a[a.index("--profile") + 1] == wc.NOME and a[a.index("--collection") + 1] == wc.NOME
    assert "--startvirtualcam" in a


def test_colecao_captura_a_janela_pelo_titulo_e_ocupa_o_quadro(wc):
    c = json.loads(json.dumps(wc.colecao()))
    janela = next(s for s in c["sources"] if s["id"] == "window_capture")
    assert janela["settings"]["window"].startswith(wc.TITULO + ":") and janela["settings"]["priority"] == 1
    cena = next(s for s in c["sources"] if s["id"] == "scene")
    item = cena["settings"]["items"][0]
    assert item["name"] == janela["name"] and item["bounds"] == {"x": 1280.0, "y": 720.0} and item["bounds_type"] == 2
    assert c["current_scene"] == cena["name"]


def test_prepara_grava_so_arquivos_proprios_e_preserva_os_do_rafael(wc, tmp_path):
    dele = tmp_path / "basic" / "scenes" / "Sem_nome.json"
    dele.parent.mkdir(parents=True)
    dele.write_text("original", encoding="utf-8")
    perfil = tmp_path / "basic" / "profiles" / wc.ARQ / "basic.ini"
    wc.prepara_obs(tmp_path)
    assert dele.read_text(encoding="utf-8") == "original"
    assert (tmp_path / "basic" / "scenes" / f"{wc.ARQ}.json").exists() and perfil.exists()
    assert "BaseCX=1280" in perfil.read_text(encoding="utf-8") and "FPSCommon=30" in perfil.read_text(encoding="utf-8")


def test_devolve_so_as_quatro_chaves_e_mantem_o_resto_e_o_fim_de_linha(wc, tmp_path):
    ini = tmp_path / "user.ini"
    ini.write_bytes("﻿[Basic]\r\nProfile=Sem nome\r\nProfileDir=Sem_nome\r\nSceneCollection=Sem nome\r\nSceneCollectionFile=Sem_nome.json\r\nOutra=ação\r\n".encode())
    antes = wc.le_escolha(ini)
    assert antes["Profile"] == "Sem nome" and antes["SceneCollectionFile"] == "Sem_nome.json"
    original = ini.read_bytes()
    trocado = original.replace(b"Profile=Sem nome", b"Profile=Webcam Celular").replace(b"SceneCollection=Sem nome", b"SceneCollection=Webcam Celular")
    ini.write_bytes(trocado)
    wc.devolve_escolha(ini, antes)
    assert ini.read_bytes() == original


def test_sem_user_ini_nao_falha(wc, tmp_path):
    ini = tmp_path / "nao-existe.ini"
    assert wc.le_escolha(ini) == {}
    wc.devolve_escolha(ini, {})
    assert not ini.exists()


def test_medida_exige_quadros_e_brilho_para_declarar_imagem(wc):
    t = "Stream #0:0: Video: rawvideo, 1920x1080, 30 fps\n" + "lavfi.signalstats.YAVG=120.5\n" * 6
    m = wc.resume_medida(t)
    assert m == {"quadros": 6, "brilho": 120, "tamanho": "1920x1080"} and wc.imagem_real(m)
    assert not wc.imagem_real(wc.resume_medida("lavfi.signalstats.YAVG=16.0\n" * 40))  # preto: janela nao capturada
    assert not wc.imagem_real(wc.resume_medida("lavfi.signalstats.YAVG=130.0\n" * 2))  # quase nenhum quadro
    assert not wc.imagem_real(wc.resume_medida("nada"))


def falso(saidas):
    def run(args, **kw):
        return types.SimpleNamespace(returncode=0, stdout=saidas.get(args[0], ""), stderr="")
    return run


def prepara_confere(wc, monkeypatch, tmp_path, adb="L\tdevice\n", tasks="sem tarefas"):
    obs = tmp_path / "obs64.exe"
    obs.write_text("x")
    monkeypatch.setattr(wc, "OBS_PADRAO", obs)
    monkeypatch.setattr(wc.shutil, "which", lambda n: "scrcpy.exe")
    monkeypatch.setattr(subprocess, "run", falso({"adb": adb, "tasklist": tasks}))


def test_confere_passa_com_tudo_certo(wc, monkeypatch, tmp_path):
    prepara_confere(wc, monkeypatch, tmp_path)
    wc.confere("1920x1080")


@pytest.mark.parametrize("kw, tamanho, texto", [
    ({}, "2560x1440", "nao testado"),  # falhou no encoder do A12 em 03/11
])
def test_confere_recusa(wc, monkeypatch, tmp_path, kw, tamanho, texto):
    prepara_confere(wc, monkeypatch, tmp_path, **kw)
    with pytest.raises(wc.Erro, match=texto):
        wc.confere(tamanho)


def test_recusa_vira_saida_2_sem_abrir_nada(wc, monkeypatch, tmp_path, capsys):
    prepara_confere(wc, monkeypatch, tmp_path, adb="nada")  # sem cabo e sem rede
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("abriu programa depois de recusar"))
    assert wc.main(["ligar"]) == 2
    assert "ligue o cabo" in capsys.readouterr().out


def test_serial_do_cabo_ignora_conexao_de_rede(wc):
    assert wc.serial_usb("List of devices attached\nRQ8\tdevice\n100.1.1.1:5555\tdevice\n") == "RQ8"
    assert wc.serial_usb("List of devices attached\n100.1.1.1:5555\tdevice\n") == ""
    assert wc.serial_usb("List of devices attached\nRQ8\tunauthorized\n") == ""


def test_mesma_rede_escolhe_o_wifi_local(wc):
    assert wc.mesma_rede("192.168.1.4", ["172.20.0.1", "192.168.1.17"])
    assert not wc.mesma_rede("10.0.0.4", ["192.168.1.17"])
    assert not wc.mesma_rede("", ["192.168.1.17"])
    assert wc.ip_wifi("3: wlan0: <UP>\n    inet 192.168.1.4/24 brd") == "192.168.1.4"
    assert wc.ip_wifi("Device not found") == ""


@pytest.mark.parametrize("tipo, taxa, folga", [("cabo", "8M", False), ("wifi", "8M", True), ("tailscale", "4M", True), ("dados", "2M", True)])
def test_taxa_e_folga_por_caminho(wc, tipo, taxa, folga):
    a = wc.args_scrcpy("S", tipo=tipo)
    assert a[:3] == ["scrcpy", "-s", "S"] and f"--video-bit-rate={taxa}" in a and ("--video-buffer=50" in a) == folga


class Adb:
    def __init__(self, devices="", conecta=(), wifi="", porta=""):
        self.devices, self.conecta, self.wifi, self.porta, self.chamadas = devices, conecta, wifi, porta, []

    def __call__(self, args, **kw):
        self.chamadas.append(list(args))
        saida = ""
        if args[:2] == ["adb", "devices"]:
            saida = self.devices
        elif args[:2] == ["adb", "connect"]:
            saida = f"connected to {args[2]}" if args[2] in self.conecta else "failed"
        elif "ip -4 addr show wlan0" in args:
            saida = self.wifi
        elif "getprop service.adb.tcp.port" in args:
            saida = self.porta + "\r\n"
        return types.SimpleNamespace(returncode=0, stdout=saida, stderr="")


TS = "100.64.0.2:5555"


def test_rota_prefere_cabo_e_deixa_a_porta_pronta(wc, monkeypatch):
    a = Adb(devices="RQ8\tdevice\n", conecta=())
    monkeypatch.setattr(subprocess, "run", a)
    monkeypatch.setattr(wc.time, "sleep", lambda s: None)
    assert wc.escolhe_rota(False) == ("RQ8", "cabo")
    assert ["adb", "-s", "RQ8", "tcpip", "5555"] in a.chamadas


def test_rota_nao_reabre_porta_aberta_mesmo_com_a_rede_fora_e_nao_deixa_dois_aparelhos(wc, monkeypatch):
    a = Adb(devices="RQ8\tdevice\n", conecta=(), porta="5555")  # controles sufocando o Wi-Fi: a Tailscale nao responde, e o tcpip derrubaria o adb a toa
    monkeypatch.setattr(subprocess, "run", a)
    assert wc.escolhe_rota(False) == ("RQ8", "cabo")
    assert not any("tcpip" in c for c in a.chamadas)
    assert not any(c[:2] == ["adb", "connect"] for c in a.chamadas)


class FalsoProcesso:
    def poll(self):
        return None

    def terminate(self):
        pass


def test_rede_caida_no_fim_nao_deixa_o_obs_no_perfil_da_webcam(wc, monkeypatch, tmp_path):
    obs = tmp_path / "obs64.exe"
    obs.write_text("x")
    monkeypatch.setattr(wc, "OBS_PADRAO", obs)
    monkeypatch.setattr(wc.shutil, "which", lambda n: "scrcpy.exe")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    ini = tmp_path / "obs-studio" / "user.ini"
    ini.parent.mkdir()
    ini.write_text("Profile=Dele\nProfileDir=Dele\nSceneCollection=Dele\nSceneCollectionFile=Dele.json\n", encoding="utf-8")
    monkeypatch.setattr(wc, "escolhe_rota", lambda so_rede: (TS, "wifi"))
    monkeypatch.setattr(wc.time, "sleep", lambda s: None)
    monkeypatch.setattr("builtins.input", lambda: "")

    def popen(args, **k):
        if str(obs) in args[0]:
            ini.write_text("Profile=Webcam Celular\nProfileDir=Webcam_Celular\nSceneCollection=Webcam Celular\nSceneCollectionFile=Webcam_Celular.json\n", encoding="utf-8")
        return FalsoProcesso()

    fim = []

    def run(args, **k):
        if "acender" in args or args[:2] == ["adb", "disconnect"]:
            fim.append(ini.read_text(encoding="utf-8"))
            raise subprocess.TimeoutExpired(args, 15)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(subprocess, "run", run)
    assert wc.main(["ligar"]) == 0
    assert "Profile=Dele" in ini.read_text(encoding="utf-8")
    assert fim and all("Profile=Dele" in t for t in fim)  # devolveu ANTES de falar com o celular


def test_celular_que_para_de_responder_vira_saida_2(wc, monkeypatch, tmp_path, capsys):
    prepara_confere(wc, monkeypatch, tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    def run(args, **k):
        raise subprocess.TimeoutExpired(args, 20)

    monkeypatch.setattr(wc, "obs_aberto", lambda: False)
    monkeypatch.setattr(subprocess, "run", run)
    assert wc.main(["ligar"]) == 2
    assert "parou de responder" in capsys.readouterr().out


def test_sem_cabo_mesma_rede_usa_wifi_local_e_tira_a_tailscale(wc, monkeypatch):
    a = Adb(devices="", conecta=(TS, "192.168.1.4:5555"), wifi="inet 192.168.1.4/24")
    monkeypatch.setattr(subprocess, "run", a)
    monkeypatch.setattr(wc, "ips_do_pc", lambda: ["192.168.1.17"])
    assert wc.escolhe_rota(False) == ("192.168.1.4:5555", "wifi")
    assert ["adb", "disconnect", TS] in a.chamadas


def test_sem_cabo_fora_de_casa_usa_tailscale_e_avisa_dos_dados(wc, monkeypatch, capsys):
    a = Adb(conecta=(TS,), wifi="inet 10.0.0.9/24")
    monkeypatch.setattr(subprocess, "run", a)
    monkeypatch.setattr(wc, "ips_do_pc", lambda: ["192.168.1.17"])
    assert wc.escolhe_rota(False) == (TS, "tailscale")
    a.wifi = ""
    assert wc.escolhe_rota(False) == (TS, "dados")
    assert "DADOS MOVEIS" in capsys.readouterr().out


def test_sem_fio_forcado_ignora_o_cabo(wc, monkeypatch):
    a = Adb(devices="RQ8\tdevice\n", conecta=(TS,), wifi="")
    monkeypatch.setattr(subprocess, "run", a)
    assert wc.escolhe_rota(True)[1] == "dados"


def test_fechar_sem_fio_pede_o_cabo(wc, monkeypatch):
    a = Adb(devices="RQ8\tdevice\n")
    monkeypatch.setattr(subprocess, "run", a)
    assert wc.main(["fechar-sem-fio"]) == 0
    assert ["adb", "-s", "RQ8", "usb"] in a.chamadas
    monkeypatch.setattr(subprocess, "run", Adb(devices=""))
    assert wc.main(["fechar-sem-fio"]) == 2


# ---------------------------------------------------------------- 05/11: tela, som, aviso no celular, sentinela, fundo
def test_tela_usa_display_sem_controle_e_som_do_aparelho(wc):
    a = wc.args_scrcpy("S", tipo="dados", fonte="tela", som=True)
    assert "--video-source=display" in a and "--no-control" in a and "--audio-source=output" in a
    assert "--no-audio" not in a and not any(x.startswith("--camera") for x in a)
    c = wc.args_scrcpy("S", fonte="camera", som=True, lanterna=True)
    assert "--audio-source=mic" in c and "--camera-torch" in c
    assert "--camera-torch" not in wc.args_scrcpy("S", fonte="tela", lanterna=True)


@pytest.mark.parametrize("fonte,grav,live,icone,palavra", [
    ("camera", False, False, "videocam", "camera"), ("tela", False, False, "screen_share", "tela"),
    ("tela", True, False, "fiber_manual_record", "GRAVANDO"), ("camera", True, True, "live_tv", "AO VIVO")])
def test_aviso_muda_com_o_estado(wc, fonte, grav, live, icone, palavra):
    i, titulo, _ = wc.texto_aviso(fonte, grav, live)
    assert i == icone and palavra.lower() in titulo.lower()
    cmd = wc.comando_aviso(fonte, grav, live)
    assert cmd.startswith("timeout 20 termux-notification --id obs-pc --ongoing") and "obs desligar" in cmd
    assert ("parar-gravacao" in cmd) == grav
    assert "'" not in titulo and "'" not in wc.texto_aviso(fonte, grav, live)[2], "aspas simples quebrariam o comando"


def test_tirar_o_aviso(wc):
    assert wc.comando_aviso("camera", tirar=True) == "timeout 20 termux-notification-remove obs-pc"


def test_aviso_sem_ssh_nao_tenta_e_nao_quebra(wc, monkeypatch, tmp_path):
    monkeypatch.setattr(wc, "SSH", tmp_path / "nao-existe.exe")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("chamou programa sem ssh"))
    assert wc.aviso_celular("S", "camera") is False
    assert wc.aviso_celular("", "camera") is False


def test_limpa_sentinela_tira_so_os_marcadores(wc, tmp_path):
    s = tmp_path / ".sentinel"
    s.mkdir()
    (s / "run_1").write_text("")
    (s / "run_2").write_text("")
    (s / "outro").write_text("")
    assert wc.limpa_sentinela(tmp_path) == 2
    assert [f.name for f in s.iterdir()] == ["outro"]
    assert wc.limpa_sentinela(tmp_path / "nao-tem") == 0


def test_perfil_grava_em_mp4_hibrido_na_pasta_dada(wc):
    ini = wc.perfil_ini("D:/X/Celular OBS")
    assert "FilePath=D:/X/Celular OBS" in ini and "RecFormat2=hybrid_mp4" in ini and "Mode=Simple" in ini


def test_colecao_tem_o_som_so_da_janela_do_scrcpy(wc):
    fontes = {s["name"]: s for s in wc.colecao()["sources"]}
    assert fontes["Som do celular"]["id"] == "wasapi_process_output_capture"
    assert "scrcpy.exe" in fontes["Som do celular"]["settings"]["window"]


def test_comandos_novos_sem_fundo_ligado(wc, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(wc, "ESTADO", tmp_path / "e.json")
    monkeypatch.setattr(wc, "PARAR", tmp_path / "p")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="List of devices attached\n", stderr=""))
    assert wc.main(["parar"]) == 0
    assert "Nada ligado" in capsys.readouterr().out


# ---- faixa preta (06/11): cropdetect diz onde esta a tarja; escuridao da camera NAO e tarja
def test_faixas_le_a_tarja_do_cropdetect(wc):
    texto = "Stream #0:0: Video: bmp, bgra, 1280x720\n[Parsed_cropdetect_0] x1:0 crop=1280:540:0:90\n... crop=1280:540:0:90"
    assert wc.faixas(texto) == (0, 90, 0, 90)


def test_faixas_sem_tarja_e_escuridao_dao_none(wc):
    assert wc.faixas("Video: bmp, 1280x720\n crop=1280:720:0:0") is None
    assert wc.faixas("Video: bmp, 1280x720\n crop=1276:718:2:0") is None  # menos de 2%: nao e faixa
    assert wc.faixas("Video: bmp, 1280x720\n crop=320:200:480:260") is None  # quase tudo escuro (noite): inconclusivo
    assert wc.faixas("nada") is None


def test_corrige_faixas_mede_encaixa_e_confere(wc, monkeypatch):
    medidas = iter([(0, 90, 0, 90), None])
    monkeypatch.setattr(wc, "mede_faixas", lambda entrada, segundos=3: next(medidas))
    pedidos = []
    monkeypatch.setattr(wc, "no_obs", lambda acao, tentativas=1: pedidos.append(tentativas) or ("Cena", (1280, 720), ["Janela scrcpy"]))
    assert wc.corrige_faixas() is True and pedidos


def test_corrige_faixas_com_obs_fechado(wc, monkeypatch):
    monkeypatch.setattr(wc, "mede_faixas", lambda entrada, segundos=3: None)
    monkeypatch.setattr(wc, "no_obs", lambda acao, tentativas=1: None)
    assert wc.corrige_faixas() is None
