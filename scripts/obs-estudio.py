#!/usr/bin/env python3
"""Monta o estudio do OBS para esta maquina (Ryzen 5 5600G sem placa dedicada, monitor 1440x900 a 60 Hz). Regra do Rafael: fluido acima de bonito.

  python scripts/obs-estudio.py             simulacao: mostra o que faria
  python scripts/obs-estudio.py --aplicar   guarda copia do OBS atual, grava perfil e cenas e cria os atalhos
  python scripts/obs-estudio.py desfazer    volta o OBS ao perfil e as cenas de antes (os arquivos do estudio ficam)
  python scripts/obs-estudio.py relatorio   le o registro do OBS: quantos quadros a ultima gravacao perdeu
  python scripts/obs-estudio.py provar      grava 20 s da tela pelo atalho Ctrl+F9, mede, apaga o video e fecha

Perfil "Gravar Jogos": 1440x900 a 60 fps, sem reescala, H.264 no chip da AMD em modo velocidade, 4 faixas de audio.
Colecao "Estudio": 6 cenas com atalhos. Webcam em chamada e por webcam-celular.py, com perfil proprio.
Nao apaga nada do OBS do Rafael. Decisoes e limites: memoria/OBS-ESTUDIO.md.
"""
import argparse
import ctypes
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import zipfile

OBS = pathlib.Path(r"C:\Program Files\obs-studio\bin\64bit\obs64.exe")
PERFIL = "Gravar Jogos"
PERFIL_DIR = "Gravar_Jogos"
COLECAO = "Estudio"
COLECAO_ARQ = "Estudio.json"
LARGURA, ALTURA, FPS = 1440, 900, 60
BITRATE = 25000  # kbps: 11 GB por hora, sobra para acao a 1440x900; o chip nao trabalha mais por causa disso
PASTA_VIDEOS = pathlib.Path(os.environ.get("USERPROFILE", "")) / "Videos" / "Estudio" / "Jogos"
LIMITE_PERDA = 1.0  # % de quadros perdidos a partir do qual a gravacao nao esta fluida
BRILHO_PRETO = 20  # numa escala de 16 (preto) a 235: o video vazio de 04/11 mediu 16
JANELA_WEBCAM = "Webcam do celular:SDL_app:scrcpy.exe"


class Erro(Exception):
    pass


def pasta_obs():
    return pathlib.Path(os.environ["APPDATA"]) / "obs-studio"


def perfil_ini(videos=None):
    videos = (videos or PASTA_VIDEOS).as_posix()
    return f"""[General]
Name={PERFIL}

[Video]
BaseCX={LARGURA}
BaseCY={ALTURA}
OutputCX={LARGURA}
OutputCY={ALTURA}
FPSType=0
FPSCommon={FPS}
ScaleType=bilinear
ColorFormat=NV12
ColorSpace=709
ColorRange=Partial
SdrWhiteLevel=300
HdrNominalPeakLevel=1000

[Audio]
SampleRate=48000
ChannelSetup=Stereo
MonitoringDeviceId=default

[Output]
Mode=Advanced
FilenameFormatting=%CCYY-%MM-%DD %hh-%mm-%ss Jogo
DelayEnable=false
Reconnect=true

[AdvOut]
RecType=Standard
RecFilePath={videos}
RecFormat2=hybrid_mp4
RecEncoder=h264_texture_amf
RecAudioEncoder=ffmpeg_aac
RecUseRescale=false
RecTracks=15
Encoder=h264_texture_amf
AudioEncoder=ffmpeg_aac
TrackIndex=1
Track1Bitrate=192
Track2Bitrate=192
Track3Bitrate=192
Track4Bitrate=192
Track1Name=Tudo
Track2Name=Jogo
Track3Name=Microfone
Track4Name=Chamada

[Hotkeys]
OBSBasic.StartRecording={{"bindings":[{{"control":true,"key":"OBS_KEY_F9"}}]}}
OBSBasic.StopRecording={{"bindings":[{{"control":true,"key":"OBS_KEY_F9"}}]}}
"""


def codificador():
    """H.264 no chip da AMD. 'speed' = menor atraso; sem quadros B = menos trabalho e arquivo facil de editar."""
    return {"rate_control": "VBR", "bitrate": BITRATE, "preset": "speed", "profile": "high", "keyint_sec": 2, "bf": 0}


def filtro(tipo, nome, **ajustes):
    return {"id": tipo, "versioned_id": tipo, "name": nome, "enabled": True, "settings": ajustes}


def escolhe_jbl(ativos):
    """ativos = [(tipo, nome, id)]. Canal Game para o jogo, canal Chat para chamada e microfone; sem o JBL, o padrao do Windows."""
    def acha(tipo, palavra):
        return next((i for t, n, i in ativos if t == tipo and "JBL" in n and palavra in n), "default")
    return {"jogo": acha("Render", "Game"), "chat": acha("Render", "Chat"), "mic": acha("Capture", "Chat")}


def dispositivos_ativos():
    """Le do registro do Windows as saidas e entradas de audio ligadas agora."""
    import winreg

    base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio"
    achados = []
    for tipo, prefixo in (("Render", "{0.0.0.00000000}."), ("Capture", "{0.0.1.00000000}.")):
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{tipo}") as k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                guid = winreg.EnumKey(k, i)
                with winreg.OpenKey(k, guid) as d:
                    estado = winreg.QueryValueEx(d, "DeviceState")[0]
                    if estado & 0xF != 1:
                        continue
                    with winreg.OpenKey(d, "Properties") as p:
                        nome = winreg.QueryValueEx(p, "{b3f8fa53-0004-438e-9003-51a46e139bfc},6")[0]
                achados.append((tipo, nome, prefixo + guid))
    return achados


def audio(disp=None):
    """Faixa 1 Tudo; 2 Jogo; 3 Microfone; 4 Chamada: na edicao da para mexer em cada uma separada."""
    disp = disp or {"jogo": "default", "chat": "default", "mic": "default"}
    atalho = {"libobs.mute": [{"control": True, "key": "OBS_KEY_F10"}], "libobs.unmute": [{"control": True, "key": "OBS_KEY_F10"}]}
    jogo = {"id": "wasapi_output_capture", "versioned_id": "wasapi_output_capture", "name": "Som do Jogo e do PC", "enabled": True, "muted": False,
            "mixers": 3, "volume": 1.0, "settings": {"device_id": disp["jogo"]},
            "filters": [filtro("limiter_filter", "Limitador", threshold=-1.5, release_time=60)]}
    chamada = {"id": "wasapi_output_capture", "versioned_id": "wasapi_output_capture", "name": "Som da Chamada", "enabled": True, "muted": False,
               "mixers": 9, "volume": 1.0, "settings": {"device_id": disp["chat"]},
               "filters": [filtro("limiter_filter", "Limitador", threshold=-1.5, release_time=60)]}
    mic = {"id": "wasapi_input_capture", "versioned_id": "wasapi_input_capture", "name": "Microfone", "enabled": True, "muted": False,
           "mixers": 5, "volume": 1.0, "settings": {"device_id": disp["mic"]}, "hotkeys": atalho,
           "filters": [filtro("noise_suppress_filter_v2", "1 Tirar Ruido", method="rnnoise"),
                       filtro("compressor_filter", "2 Igualar Voz", ratio=3.0, threshold=-18.0, attack_time=6, release_time=60, output_gain=0.0),
                       filtro("limiter_filter", "3 Limitador", threshold=-3.0, release_time=60)]}
    return jogo, chamada, mic


def item(nome, n, x=0.0, y=0.0, largura=LARGURA, altura=ALTURA, visivel=True):
    return {"name": nome, "id": n, "visible": visivel, "locked": False, "rot": 0.0, "align": 5, "bounds_align": 0, "bounds_type": 2,
            "pos": {"x": float(x), "y": float(y)}, "scale": {"x": 1.0, "y": 1.0}, "bounds": {"x": float(largura), "y": float(altura)}, "scale_filter": "disable"}


def cena(nome, tecla, itens):
    return {"id": "scene", "versioned_id": "scene", "name": nome, "enabled": True, "hotkeys": {"OBSBasic.SelectScene": [{"control": True, "key": f"OBS_KEY_{tecla}"}]},
            "settings": {"id_counter": len(itens), "custom_size": False, "items": [dict(i, id=n + 1) for n, i in enumerate(itens)]}}


def fonte(tipo, nome, **ajustes):
    return {"id": tipo, "versioned_id": tipo, "name": nome, "enabled": True, "settings": ajustes}


def colecao(monitor_id="DUMMY", janela_jogo="NFS Underground 2:GameFrame:SPEED2.EXE", disp=None):
    jogo_tela = "Jogo em Tela Cheia"
    jogo_janela = "Jogo em Janela (NFS U2)"
    tela = "Tela do PC"
    cam = "Webcam do Celular"
    margem, pip_l, pip_a = 20, 360, 202
    pip = dict(x=LARGURA - pip_l - margem, y=ALTURA - pip_a - margem, largura=pip_l, altura=pip_a)
    jogos = [item(jogo_janela, 0), item(jogo_tela, 0)]
    fontes = [
        fonte("game_capture", jogo_tela, capture_mode="any_fullscreen", capture_cursor=False, capture_overlays=False, limit_framerate=False, anti_cheat_hook=True, allow_transparency=False),
        fonte("game_capture", jogo_janela, capture_mode="window", window=janela_jogo, priority=1, capture_cursor=False, capture_overlays=False, limit_framerate=False, anti_cheat_hook=True, allow_transparency=False),
        fonte("monitor_capture", tela, method=1, monitor_id=monitor_id, capture_cursor=True),
        fonte("window_capture", cam, window=JANELA_WEBCAM, method=2, priority=1, cursor=False, client_area=True),
        fonte("color_source_v3", "Fundo Escuro", color=4279901214, width=LARGURA, height=ALTURA),
        fonte("text_gdiplus_v3", "Texto Volto Ja", text="Volto já", color=4294967295, font={"face": "Segoe UI", "size": 96, "style": "Bold", "flags": 1}),
        cena("1 Jogo", 1, jogos),
        cena("2 Jogo com Webcam", 2, jogos + [item(cam, 0, **pip)]),
        cena("3 Só Webcam", 3, [item(cam, 0)]),
        cena("4 Tela do PC", 4, [item(tela, 0)]),
        cena("5 Tela com Webcam", 5, [item(tela, 0), item(cam, 0, **pip)]),
        cena("6 Volto Já", 6, [item("Fundo Escuro", 0), item("Texto Volto Ja", 0, x=500, y=380, largura=440, altura=140)]),
    ]
    jogo, chamada, mic = audio(disp)
    nomes = [s["name"] for s in fontes if s["id"] == "scene"]
    return {"name": COLECAO, "current_scene": nomes[0], "current_program_scene": nomes[0], "scene_order": [{"name": n} for n in nomes],
            "current_transition": "Cortar", "transition_duration": 0, "transitions": [], "quick_transitions": [], "groups": [],
            "DesktopAudioDevice1": jogo, "DesktopAudioDevice2": chamada, "AuxAudioDevice1": mic, "sources": fontes, "preview_locked": True, "scaling_enabled": False}


def do_obs_atual(base):
    """Aproveita o que o OBS do Rafael ja descobriu desta maquina: o monitor e a janela do NFS."""
    monitor, janela = "DUMMY", "NFS Underground 2:GameFrame:SPEED2.EXE"
    arq = base / "basic" / "scenes" / "Sem_nome.json"
    if arq.exists():
        try:
            d = json.loads(arq.read_text(encoding="utf-8-sig"))
        except ValueError:
            return monitor, janela
        for s in d.get("sources", []):
            if s.get("id") == "monitor_capture":
                monitor = s.get("settings", {}).get("monitor_id", monitor)
            if s.get("id") == "game_capture" and s.get("settings", {}).get("window"):
                janela = s["settings"]["window"]
    return monitor, janela


CHAVES = ("Profile", "ProfileDir", "SceneCollection", "SceneCollectionFile")


def le_escolha(ini):
    if not ini.exists():
        return {}
    t = ini.read_bytes().decode("utf-8-sig", "replace")
    return {k: m.group(1) for k in CHAVES if (m := re.search(rf"^{k}=(.*?)\r?$", t, re.M))}


def grava_escolha(ini, valores):
    t = ini.read_bytes().decode("utf-8", "surrogateescape")
    for k, v in valores.items():
        t, n = re.subn(rf"^{k}=.*?(\r?)$", lambda m, k=k, v=v: f"{k}={v}{m.group(1)}", t, flags=re.M)
        if n == 0:
            raise Erro(f"nao achei {k} em {ini}")
    ini.write_bytes(t.encode("utf-8", "surrogateescape"))


def copia_de_seguranca(base):
    """Uma so vez, antes da primeira mudanca. Fica no OBS; a primeira copia e a que vale."""
    zipado = base / "copia-antes-do-estudio.zip"
    if zipado.exists():
        return zipado
    with zipfile.ZipFile(zipado, "w", zipfile.ZIP_DEFLATED) as z:
        for nome in ("user.ini", "global.ini"):
            if (base / nome).exists():
                z.write(base / nome, nome)
        for f in (base / "basic").rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(base).as_posix())
    return zipado


def aplica(base, videos=None, disp=None):
    base.mkdir(parents=True, exist_ok=True)
    (base / "basic" / "scenes").mkdir(parents=True, exist_ok=True)
    perfil = base / "basic" / "profiles" / PERFIL_DIR
    perfil.mkdir(parents=True, exist_ok=True)
    antes = le_escolha(base / "user.ini")
    if antes.get("Profile") not in (None, PERFIL):
        (base / "escolha-antes-do-estudio.json").write_text(json.dumps(antes, ensure_ascii=False), encoding="utf-8")
    copia_de_seguranca(base)
    monitor, janela = do_obs_atual(base)
    (base / "basic" / "scenes" / COLECAO_ARQ).write_text(json.dumps(colecao(monitor, janela, disp), ensure_ascii=False, indent=1), encoding="utf-8")
    (perfil / "basic.ini").write_text(perfil_ini(videos), encoding="utf-8", newline="\n")
    (perfil / "recordEncoder.json").write_text(json.dumps(codificador()), encoding="utf-8")
    (perfil / "streamEncoder.json").write_text(json.dumps(dict(codificador(), rate_control="CBR", bitrate=6000)), encoding="utf-8")
    (videos or PASTA_VIDEOS).mkdir(parents=True, exist_ok=True)
    if (base / "user.ini").exists():
        grava_escolha(base / "user.ini", {"Profile": PERFIL, "ProfileDir": PERFIL_DIR, "SceneCollection": COLECAO, "SceneCollectionFile": COLECAO_ARQ})


def desfaz(base):
    arq = base / "escolha-antes-do-estudio.json"
    if not arq.exists():
        raise Erro("nao ha escolha anterior guardada")
    grava_escolha(base / "user.ini", json.loads(arq.read_text(encoding="utf-8")))


def le_perdas(texto):
    """Da ULTIMA gravacao do registro: quadros perdidos por codificacao e por desenho."""
    trecho = texto[texto.rfind("==== Recording Start"):] if "==== Recording Start" in texto else texto
    # o OBS 32 so escreve as linhas de perda quando houve perda; "Total frames output" contra "Total drawn" fecha a conta
    feitos = re.search(r"Total frames output:\s*(\d+)", trecho)
    desenhados = re.search(r"Total drawn frames:\s*(\d+)", trecho)
    cod = re.search(r"skipped frames due to encoding lag:\s*(\d+)/(\d+)", trecho, re.I)
    des = re.search(r"lagged frames due to rendering lag/stalls:\s*(\d+)", trecho, re.I)
    if not cod and not (feitos and desenhados):
        return None
    total = int(desenhados.group(1)) if desenhados else int(cod.group(2))
    perdidos_cod = int(cod.group(1)) if cod else max(total - int(feitos.group(1)), 0)
    perdidos_des = int(des.group(1)) if des else 0
    pct = lambda n: 100.0 * n / max(total, 1)
    return {"codificacao": pct(perdidos_cod), "desenho": pct(perdidos_des), "quadros": total}


def veredito(p):
    if p is None:
        return "sem gravacao terminada no ultimo registro"
    base = f"{p['quadros']} quadros; perdidos: {p['codificacao']:.1f}% ao codificar, {p['desenho']:.1f}% ao desenhar"
    if p["codificacao"] > LIMITE_PERDA:
        return base + " -> o chip nao deu conta de codificar: veja 'Se engasgar' em memoria/OBS-ESTUDIO.md"
    if p["desenho"] > LIMITE_PERDA:
        return base + " -> o jogo ocupou o chip gráfico: limite o FPS do jogo ou baixe o gráfico dele"
    return base + " -> FLUIDO"


def ultimo_log(base):
    logs = sorted((base / "logs").glob("*.txt"), key=lambda f: f.stat().st_mtime)
    return logs[-1] if logs else None


def sem_imagem(brilhos):
    """Preto do comeco ao fim. Video de jogo com 0% de perda ainda pode estar vazio: em 04/11 o jogo parou pedindo o disco e o relatorio disse FLUIDO."""
    return bool(brilhos) and max(brilhos) <= BRILHO_PRETO


def brilhos_do_video(video):
    """Um quadro a cada 5 s. So o brilho medio: a imagem nao e guardada nem vista."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", "fps=1/5,signalstats,metadata=print:key=lavfi.signalstats.YAVG", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    return [float(v) for v in re.findall(r"YAVG=([\d.]+)", r.stdout + r.stderr)]


def ultimo_video(pasta=None):
    pasta = pasta or PASTA_VIDEOS
    videos = sorted((f for f in pasta.glob("*") if f.is_file()), key=lambda f: f.stat().st_mtime) if pasta.exists() else []
    return videos[-1] if videos else None


def relatorio(base):
    log = ultimo_log(base)
    if not log:
        raise Erro("o OBS ainda nao tem registro")
    p = le_perdas(log.read_text(encoding="utf-8", errors="replace"))
    print(veredito(p))
    ok = bool(p) and max(p["codificacao"], p["desenho"]) <= LIMITE_PERDA
    video = ultimo_video()
    if video:
        try:
            vals = brilhos_do_video(video)
        except (OSError, subprocess.TimeoutExpired):
            vals = []
        if sem_imagem(vals):
            print(f"ATENCAO: o video {video.name} esta PRETO do comeco ao fim. O jogo esta aparecendo na tela? Se estiver, use a cena 4 Tela do PC.")
            ok = False
    return 0 if ok else 1


def atalhos_area_de_trabalho(scripts):
    """Atalhos em nome claro: quem nao decora comando nao precisa de nenhum."""
    alvos = [
        ("Estudio - Gravar Jogos", str(OBS), f'--profile "{PERFIL}" --collection "{COLECAO}" --scene "1 Jogo" --minimize-to-tray --disable-updater', str(OBS.parent), str(OBS)),
        ("Estudio - Webcam do Celular", str(scripts / "webcam-celular.cmd"), "", str(scripts), str(OBS)),
        ("Recuperar Arquivos", str(scripts / "recuperar-arquivos.cmd"), "", str(scripts), r"C:\Windows\System32\imageres.dll,109"),
    ]
    js = json.dumps(alvos).replace("'", "''")
    ps = ("$w=New-Object -ComObject WScript.Shell;$d=[Environment]::GetFolderPath('Desktop');"
          f"foreach($a in (ConvertFrom-Json '{js}')){{$s=$w.CreateShortcut((Join-Path $d ($a[0]+'.lnk')));$s.TargetPath=$a[1];$s.Arguments=$a[2];$s.WorkingDirectory=$a[3];$s.IconLocation=$a[4];$s.Save()}}")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, errors="replace", timeout=60)
    if r.returncode != 0:
        raise Erro("nao criei os atalhos: " + r.stderr[:200])


def aperta_ctrl_f9():
    k = ctypes.windll.user32.keybd_event  # type: ignore[attr-defined]
    for v, f in ((0x11, 0), (0x78, 0), (0x78, 2), (0x11, 2)):
        k(v, 0, f, 0)
        time.sleep(0.08)


def aberto():
    return "obs64.exe" in subprocess.run(["tasklist", "/FI", "IMAGENAME eq obs64.exe", "/NH"], capture_output=True, text=True, errors="replace").stdout


def prova(base):
    if aberto():
        raise Erro("feche o OBS antes da prova")
    antes = set(PASTA_VIDEOS.glob("*"))
    obs = subprocess.Popen([str(OBS), "--profile", PERFIL, "--collection", COLECAO, "--scene", "4 Tela do PC", "--minimize-to-tray", "--disable-updater", "--disable-shutdown-check"], cwd=str(OBS.parent))
    time.sleep(10)
    aperta_ctrl_f9()
    time.sleep(20)
    aperta_ctrl_f9()
    time.sleep(6)
    novos = [f for f in PASTA_VIDEOS.glob("*") if f not in antes]
    subprocess.run(["taskkill", "/IM", "obs64.exe"], capture_output=True)
    try:
        obs.wait(15)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/F", "/IM", "obs64.exe"], capture_output=True)
    if not novos:
        print("SEM VIDEO: o atalho Ctrl+F9 nao comecou a gravacao.")
        return 1
    for f in novos:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,avg_frame_rate", "-of", "csv=p=0", str(f)], capture_output=True, text=True, errors="replace")
        print(f"{f.stat().st_size / 1024 / 1024:.0f} MB em 20 s:", " | ".join(r.stdout.split()))
        f.unlink()
    print("video da prova apagado; a imagem nao foi olhada")
    return relatorio(base)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Estudio do OBS")
    ap.add_argument("modo", nargs="?", default="montar", choices=["montar", "desfazer", "relatorio", "provar"])
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args(argv)
    base = pasta_obs()
    try:
        if a.modo == "relatorio":
            return relatorio(base)
        if a.modo == "provar":
            return prova(base)
        if a.modo == "desfazer":
            desfaz(base)
            print("OBS de volta ao perfil e as cenas de antes.")
            return 0
        print(f"Perfil {PERFIL}: {LARGURA}x{ALTURA} a {FPS} fps; colecao {COLECAO}: " + ", ".join(s["name"] for s in colecao()["scene_order"]))
        if not a.aplicar:
            print("Simulacao: nada foi gravado. Para montar: --aplicar")
            return 0
        if aberto():
            raise Erro("feche o OBS antes: ele regrava os arquivos ao sair")
        disp = escolhe_jbl(dispositivos_ativos())
        print("Audio:", "JBL (Game e Chat)" if "default" not in disp.values() else "padrao do Windows em parte: " + json.dumps(disp))
        aplica(base, disp=disp)
        atalhos_area_de_trabalho(pathlib.Path(__file__).resolve().parent)
        print("Pronto. Atalhos na area de trabalho. Copia do OBS anterior:", base / "copia-antes-do-estudio.zip")
        return 0
    except Erro as e:
        print("NAO FEITO:", e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
