"""Testes de scripts/obs-estudio.py: ajustes que garantem fluidez, nada do OBS do Rafael perdido e relatorio de perdas que nao mente."""
import configparser
import json
import zipfile

import pytest


@pytest.fixture
def oe(importa_script, monkeypatch):
    m = importa_script("obs-estudio.py")
    return m


def ini(oe, tmp_path):
    c = configparser.RawConfigParser()
    c.optionxform = str
    c.read_string(oe.perfil_ini(tmp_path))
    return c


def test_video_nativo_do_monitor_60_fps_sem_reescala_e_cor_padrao(oe, tmp_path):
    v = ini(oe, tmp_path)["Video"]
    assert (v["BaseCX"], v["BaseCY"]) == (v["OutputCX"], v["OutputCY"]) == ("1440", "900")
    assert v["FPSCommon"] == "60" and v["FPSType"] == "0"
    assert v["ColorFormat"] == "NV12" and v["ColorSpace"] == "709" and v["ColorRange"] == "Partial"


def test_gravacao_no_chip_da_amd_a_prova_de_queda_com_4_faixas(oe, tmp_path):
    a = ini(oe, tmp_path)["AdvOut"]
    assert a["RecEncoder"] == "h264_texture_amf" and a["RecFormat2"] == "hybrid_mp4" and a["RecTracks"] == "15" and a["RecUseRescale"] == "false"
    assert [a[f"Track{i}Name"] for i in (1, 2, 3, 4)] == ["Tudo", "Jogo", "Microfone", "Chamada"]


def test_codificador_prioriza_velocidade(oe):
    c = oe.codificador()
    assert c["preset"] == "speed" and c["bf"] == 0 and c["rate_control"] == "VBR" and c["bitrate"] == 25000 and c["keyint_sec"] == 2


def test_mesmo_atalho_liga_e_desliga_a_gravacao(oe, tmp_path):
    h = ini(oe, tmp_path)["Hotkeys"]
    assert h["OBSBasic.StartRecording"] == h["OBSBasic.StopRecording"]
    assert json.loads(h["OBSBasic.StartRecording"])["bindings"][0] == {"control": True, "key": "OBS_KEY_F9"}


def fontes(oe):
    return {s["name"]: s for s in oe.colecao("MON", "J:C:X.EXE")["sources"]}


def test_seis_cenas_em_ordem_com_atalhos_unicos(oe):
    c = oe.colecao()
    nomes = [s["name"] for s in c["scene_order"]]
    assert nomes == ["1 Jogo", "2 Jogo com Webcam", "3 Só Webcam", "4 Tela do PC", "5 Tela com Webcam", "6 Volto Já"]
    f = fontes(oe)
    teclas = [f[n]["hotkeys"]["OBSBasic.SelectScene"][0]["key"] for n in nomes]
    assert teclas == [f"OBS_KEY_{i}" for i in range(1, 7)]
    assert c["current_scene"] == "1 Jogo"


def test_todo_item_de_cena_aponta_para_fonte_existente_e_ids_unicos(oe):
    f = fontes(oe)
    for s in f.values():
        if s["id"] == "scene":
            itens = s["settings"]["items"]
            assert [i["id"] for i in itens] == list(range(1, len(itens) + 1))
            for i in itens:
                assert i["name"] in f, i["name"]


def test_webcam_em_miniatura_cabe_no_quadro(oe):
    f = fontes(oe)
    pip = next(i for i in f["2 Jogo com Webcam"]["settings"]["items"] if i["name"] == "Webcam do Celular")
    assert pip["pos"]["x"] + pip["bounds"]["x"] <= 1440 and pip["pos"]["y"] + pip["bounds"]["y"] <= 900 and pip["pos"]["x"] > 720


def test_captura_de_jogo_nao_limita_fps_nem_desenha_cursor(oe):
    f = fontes(oe)
    for n in ("Jogo em Tela Cheia", "Jogo em Janela (NFS U2)"):
        s = f[n]["settings"]
        assert s["limit_framerate"] is False and s["capture_cursor"] is False and s["anti_cheat_hook"] is True
    assert f["Jogo em Janela (NFS U2)"]["settings"]["window"] == "J:C:X.EXE"
    assert f["Tela do PC"]["settings"]["monitor_id"] == "MON"
    assert f["Webcam do Celular"]["settings"]["window"] == oe.JANELA_WEBCAM


def test_faixas_de_audio_separam_jogo_e_microfone(oe):
    c = oe.colecao()
    jogo, chamada, mic = c["DesktopAudioDevice1"], c["DesktopAudioDevice2"], c["AuxAudioDevice1"]
    assert jogo["mixers"] == 3 and mic["mixers"] == 5 and chamada["mixers"] == 9  # faixa Tudo + a faixa propria de cada um
    assert jogo["settings"]["device_id"] == mic["settings"]["device_id"] == chamada["settings"]["device_id"] == "default"
    assert [x["id"] for x in mic["filters"]] == ["noise_suppress_filter_v2", "compressor_filter", "limiter_filter"]
    assert mic["filters"][0]["settings"]["method"] == "rnnoise"


ATIVOS = [("Render", "2 - SyncMaster", "H"), ("Render", "JBL Quantum810 Wireless Game", "G"), ("Render", "JBL Quantum810 Wireless Chat", "C"),
          ("Capture", "JBL Quantum810 Wireless Chat", "M"), ("Capture", "High Definition Audio Device", "X")]


def test_usa_canal_game_para_jogo_e_chat_para_chamada_e_microfone(oe):
    d = oe.escolhe_jbl(ATIVOS)
    assert d == {"jogo": "G", "chat": "C", "mic": "M"}
    c = oe.colecao(disp=d)
    assert c["DesktopAudioDevice1"]["settings"]["device_id"] == "G" and c["DesktopAudioDevice2"]["settings"]["device_id"] == "C"
    assert c["AuxAudioDevice1"]["settings"]["device_id"] == "M"


def test_sem_jbl_cai_no_padrao_do_windows(oe):
    assert oe.escolhe_jbl([("Render", "2 - SyncMaster", "H")]) == {"jogo": "default", "chat": "default", "mic": "default"}


def obs_falso(tmp_path):
    base = tmp_path / "obs"
    (base / "basic" / "scenes").mkdir(parents=True)
    (base / "basic" / "profiles" / "Sem_nome").mkdir(parents=True)
    (base / "basic" / "profiles" / "Sem_nome" / "basic.ini").write_text("dele", encoding="utf-8")
    dele = {"sources": [{"id": "monitor_capture", "settings": {"monitor_id": "SAM"}}, {"id": "game_capture", "settings": {"window": "W:C:E.EXE"}}]}
    (base / "basic" / "scenes" / "Sem_nome.json").write_text(json.dumps(dele), encoding="utf-8")
    (base / "global.ini").write_text("[General]\nProcessPriority=AboveNormal\n", encoding="utf-8")
    (base / "user.ini").write_bytes(b"[Basic]\r\nProfile=Sem nome\r\nProfileDir=Sem_nome\r\nSceneCollection=Sem nome\r\nSceneCollectionFile=Sem_nome.json\r\nOutra=1\r\n")
    return base


def test_aplicar_preserva_o_dele_guarda_copia_e_troca_so_as_escolhas(oe, tmp_path):
    base = obs_falso(tmp_path)
    original_cenas = (base / "basic" / "scenes" / "Sem_nome.json").read_bytes()
    oe.aplica(base, tmp_path / "videos")
    assert (base / "basic" / "scenes" / "Sem_nome.json").read_bytes() == original_cenas
    assert (base / "basic" / "profiles" / "Sem_nome" / "basic.ini").read_text(encoding="utf-8") == "dele"
    u = (base / "user.ini").read_bytes()
    assert b"Profile=Gravar Jogos\r\n" in u and b"SceneCollectionFile=Estudio.json\r\n" in u and b"Outra=1\r\n" in u
    with zipfile.ZipFile(base / "copia-antes-do-estudio.zip") as z:
        assert "user.ini" in z.namelist() and "basic/scenes/Sem_nome.json" in z.namelist()
    c = json.loads((base / "basic" / "scenes" / "Estudio.json").read_text(encoding="utf-8"))
    tela = next(s for s in c["sources"] if s["name"] == "Tela do PC")
    assert tela["settings"]["monitor_id"] == "SAM"  # o monitor que o OBS dele ja conhecia
    assert (tmp_path / "videos").is_dir()


def test_aplicar_duas_vezes_nao_estraga_o_desfazer_nem_a_copia(oe, tmp_path):
    base = obs_falso(tmp_path)
    oe.aplica(base, tmp_path / "videos")
    copia = (base / "copia-antes-do-estudio.zip").read_bytes()
    oe.aplica(base, tmp_path / "videos")
    assert (base / "copia-antes-do-estudio.zip").read_bytes() == copia
    oe.desfaz(base)
    u = (base / "user.ini").read_bytes()
    assert b"Profile=Sem nome\r\n" in u and b"SceneCollectionFile=Sem_nome.json\r\n" in u


def test_desfazer_sem_ter_aplicado_nao_inventa(oe, tmp_path):
    with pytest.raises(oe.Erro):
        oe.desfaz(obs_falso(tmp_path))


LOG = """==== Recording Start ===============================================
Video stopped, number of skipped frames due to encoding lag: 12/1200 (1.0%%)
Number of lagged frames due to rendering lag/stalls: 0/1200 (0.0%%)
==== Recording Stop ================================================
==== Recording Start ===============================================
Video stopped, number of skipped frames due to encoding lag: %s/1200 (0.0%%)
Number of lagged frames due to rendering lag/stalls: %s/1200 (0.0%%)
==== Recording Stop ================================================
"""


@pytest.mark.parametrize("cod, des, texto", [(0, 0, "FLUIDO"), (120, 0, "codificar"), (0, 120, "desenhar")])
def test_le_a_ultima_gravacao_e_diz_a_causa(oe, cod, des, texto):
    p = oe.le_perdas(LOG % (cod, des))
    assert p["quadros"] == 1200 and p["codificacao"] == 100.0 * cod / 1200
    assert texto in oe.veredito(p)


def test_formato_real_do_obs_32_sem_linhas_de_perda(oe):
    t = "==== Recording Start ===\nOutput 'adv_file_output': Total frames output: 1214\nOutput 'adv_file_output': Total drawn frames: 1223\n==== Recording Stop ===\n"
    p = oe.le_perdas(t)
    assert p["quadros"] == 1223 and round(p["codificacao"], 1) == 0.7 and p["desenho"] == 0.0
    assert "FLUIDO" in oe.veredito(p)
    ruim = "==== Recording Start ===\nTotal frames output: 900\nTotal drawn frames: 1200\nNumber of lagged frames due to rendering lag/stalls: 60 (5.0%)\n"
    assert "codificar" in oe.veredito(oe.le_perdas(ruim))


def test_sem_gravacao_nao_diz_que_esta_fluido(oe):
    assert oe.le_perdas("nada") is None
    assert "FLUIDO" not in oe.veredito(None)


def test_preto_do_comeco_ao_fim_e_sem_imagem(oe):
    assert oe.sem_imagem([16.0, 16.0, 16.0])  # o video vazio de 04/11
    assert not oe.sem_imagem([16.0, 80.0, 16.0])  # uma cena escura de jogo nao e video vazio
    assert not oe.sem_imagem([46.0])
    assert not oe.sem_imagem([])  # sem medida nao acusa


def registro_fluido(tmp_path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "a.txt").write_text("==== Recording Start\nTotal frames output: 3600\nTotal drawn frames: 3600\n", encoding="utf-8")


def test_relatorio_nao_diz_tudo_certo_com_video_preto(oe, tmp_path, monkeypatch, capsys):
    registro_fluido(tmp_path)
    videos = tmp_path / "v"
    videos.mkdir()
    (videos / "jogo.mp4").write_bytes(b"x")
    monkeypatch.setattr(oe, "PASTA_VIDEOS", videos)
    monkeypatch.setattr(oe, "brilhos_do_video", lambda v: [16.0, 16.0])
    assert oe.relatorio(tmp_path) == 1
    assert "PRETO" in capsys.readouterr().out
    monkeypatch.setattr(oe, "brilhos_do_video", lambda v: [16.0, 90.0])
    assert oe.relatorio(tmp_path) == 0
    assert "PRETO" not in capsys.readouterr().out


def test_relatorio_sem_video_ou_sem_ffmpeg_segue_pelo_registro(oe, tmp_path, monkeypatch):
    registro_fluido(tmp_path)
    monkeypatch.setattr(oe, "PASTA_VIDEOS", tmp_path / "nao-existe")
    assert oe.relatorio(tmp_path) == 0
    videos = tmp_path / "v"
    videos.mkdir()
    (videos / "jogo.mp4").write_bytes(b"x")
    monkeypatch.setattr(oe, "PASTA_VIDEOS", videos)

    def sem_ffmpeg(v):
        raise OSError("ffmpeg")

    monkeypatch.setattr(oe, "brilhos_do_video", sem_ffmpeg)
    assert oe.relatorio(tmp_path) == 0


def test_simulacao_nao_grava(oe, tmp_path, monkeypatch):
    base = obs_falso(tmp_path)
    monkeypatch.setattr(oe, "pasta_obs", lambda: base)
    assert oe.main([]) == 0
    assert not (base / "copia-antes-do-estudio.zip").exists() and not (base / "basic" / "scenes" / "Estudio.json").exists()
