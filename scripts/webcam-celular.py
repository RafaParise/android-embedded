#!/usr/bin/env python3
"""Usa a camera do A12 como webcam do PC, com ou sem cabo: scrcpy (camera direta, sem app no celular) + camera virtual do OBS.

  Dois cliques em scripts\\webcam-celular.cmd. No Teams, Meet ou Zoom: "OBS Virtual Camera".
  Escolhe sozinho o caminho: cabo, senao Wi-Fi local, senao Tailscale. Sem fio funciona ate reiniciar o celular;
  depois disso, ligue o cabo uma vez e rode de novo.
  python scripts/webcam-celular.py ligar [--frontal] [--sem-fio] [--tamanho 1280x720] [--fps 30]
  python scripts/webcam-celular.py provar [--sem-fio]   liga, mede pela camera virtual (com a lanterna, sem olhar a imagem) e desliga
  python scripts/webcam-celular.py fechar-sem-fio       fecha a porta de rede do adb no celular (precisa do cabo)
  De longe (acesso remoto, atalhos da area de trabalho ou o celular pela ponte), sem janela esperando Enter:
  python scripts/webcam-celular.py iniciar [--tela] [--som] [--gravar] [--frontal]   liga em segundo plano e volta
  python scripts/webcam-celular.py gravar | parar-gravacao | status | parar
  --tela = a TELA do celular (gravar ou transmitir o que aparece nele); --som = microfone (camera) ou som do aparelho (tela).
  A camera virtual do OBS liga SOZINHA, mesmo com o OBS do Estudio ja aberto (05/11: na aula ela estava desligada).
  Gravacoes: D:/Videos/Celular OBS (MP4 hibrido). Live: o destino e a chave ficam no OBS (obs-controle.py transmitir).

Com o OBS do Estudio ja aberto, so liga a camera: ela aparece nas cenas de webcam.
Por que 720p: cabe inteira no monitor de 1440x900, sem reduzir a imagem na captura, e e o que a maioria das chamadas envia.
A tela do celular apaga durante o uso (poupa bateria e calor; a camera continua) e acende no fim.
O audio da chamada continua no microfone do PC. Nao mexe na configuracao do OBS: usa perfil proprio e devolve o anterior.
Detalhe, medidas e limites: memoria/WEBCAM-E-RECUPERACAO.md. Saida: 0 = ok; 1 = sem imagem; 2 = nao deu para ligar.
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import time

TITULO = "Webcam do celular"
NOME = "Webcam Celular"
ARQ = "Webcam_Celular"
BRILHO_MINIMO_LANTERNA = 40  # no escuro total o sensor deu 18; com a lanterna, 132 (medido em 03/11)
OBS_PADRAO = pathlib.Path(r"C:\Program Files\obs-studio\bin\64bit\obs64.exe")
TAMANHOS_OK = {"1920x1080", "1440x1080", "1280x960", "1280x720", "960x720", "640x480"}  # 2560x1440 falhou no encoder do A12 em 03/11
IP_TAILSCALE = "100.64.0.2"
PORTA = 5555
# medido em 03/11, 720p: cabo 28,5 fps; Wi-Fi local 28,7; Tailscale 28,3
BITRATE = {"cabo": "8M", "wifi": "8M", "tailscale": "4M", "dados": "2M"}


class Erro(Exception):
    pass


def pasta_obs():
    return pathlib.Path(os.environ["APPDATA"]) / "obs-studio"


def args_scrcpy(serial="", frontal=False, tamanho="1280x720", fps=30, lanterna=False, tipo="cabo", fonte="camera", som=False):
    """fonte "camera" (webcam) ou "tela" (a TELA do celular, para gravar ou transmitir pelo OBS; sem controle pelo PC).
    som: microfone do celular (camera) ou o som do celular (tela) toca no PC e o OBS o pega pela janela do scrcpy."""
    largura, altura = tamanho.split("x")
    a = ["scrcpy"] + (["-s", serial] if serial else [])
    if fonte == "tela":
        a += ["--video-source=display", f"--max-size={max(int(largura), int(altura))}", f"--max-fps={fps}", "--no-control"]
    else:
        a += ["--video-source=camera", f"--camera-facing={'front' if frontal else 'back'}", f"--camera-size={tamanho}", f"--camera-fps={fps}"]
    a += [f"--video-bit-rate={BITRATE[tipo]}"]
    a += ([f"--audio-source={'output' if fonte == 'tela' else 'mic'}", "--audio-bit-rate=96K"] if som else ["--no-audio"])
    a += [f"--window-title={TITULO}", f"--window-width={largura}", f"--window-height={altura}", "--window-borderless"]
    if tipo != "cabo":
        a.append("--video-buffer=50")  # folga pequena contra oscilacao da rede
    return a + ["--camera-torch"] if lanterna and fonte == "camera" else a


def limpa_sentinela(base=None):
    """Com o OBS FECHADO, tira os marcadores de execucao que sobram quando ele cai ao sair (o OBS 32.1.2 deste PC cai ao
    fechar desde 03/11, sempre no mesmo ponto, depois de liberar tudo). Sobrando, a proxima abertura PARA na pergunta do
    "Modo Seguro" e a camera virtual nao liga (visto em 05/11 22:18). Devolve quantos tirou."""
    pasta = (base or pasta_obs()) / ".sentinel"
    n = 0
    for f in (pasta.glob("run_*") if pasta.is_dir() else []):
        try:
            f.unlink()
            n += 1
        except OSError:
            pass
    return n


def args_obs():
    return [str(OBS_PADRAO), "--profile", NOME, "--collection", NOME, "--startvirtualcam", "--minimize-to-tray",
            "--disable-updater", "--disable-shutdown-check"]


def colecao():
    """Colecao de cenas do OBS com uma so fonte: a janela do scrcpy, ajustada ao quadro."""
    return {
        "name": NOME, "current_scene": "Celular", "current_program_scene": "Celular", "scene_order": [{"name": "Celular"}],
        "sources": [
            {"id": "window_capture", "versioned_id": "window_capture", "name": "Janela scrcpy", "enabled": True,
             "settings": {"window": f"{TITULO}:SDL_app:scrcpy.exe", "method": 2, "priority": 1, "cursor": False, "client_area": True}},
            # som do celular (so com --som): o scrcpy toca no PC e o OBS pega so o audio DESSA janela, nada do resto do PC
            {"id": "wasapi_process_output_capture", "versioned_id": "wasapi_process_output_capture", "name": "Som do celular", "enabled": True,
             "settings": {"window": f"{TITULO}:SDL_app:scrcpy.exe", "priority": 2}},
            {"id": "scene", "versioned_id": "scene", "name": "Celular", "enabled": True,
             "settings": {"id_counter": 2, "custom_size": False, "items": [{
                 "name": "Janela scrcpy", "id": 1, "visible": True, "locked": False, "rot": 0.0, "align": 5, "scale_filter": "disable",
                 "pos": {"x": 0.0, "y": 0.0}, "scale": {"x": 1.0, "y": 1.0}, "bounds_type": 2, "bounds_align": 0,
                 "bounds": {"x": 1280.0, "y": 720.0}}, {
                 "name": "Som do celular", "id": 2, "visible": True, "locked": False, "rot": 0.0, "align": 5,
                 "pos": {"x": 0.0, "y": 0.0}, "scale": {"x": 1.0, "y": 1.0}, "bounds_type": 0, "bounds_align": 0,
                 "bounds": {"x": 0.0, "y": 0.0}}]}},
        ],
    }


def pasta_gravacoes():
    """D:\\Videos\\Celular OBS se o disco de dados existir; senao a pasta Videos do usuario."""
    d = pathlib.Path("D:/Vídeos")
    base = d if d.is_dir() else pathlib.Path(os.environ.get("USERPROFILE", str(pathlib.Path.home()))) / "Videos"
    return base / "Celular OBS"


def perfil_ini(pasta=None):
    pasta = str(pasta or pasta_gravacoes()).replace("\\", "/")
    # Gravacao: MP4 hibrido (nao corrompe se o PC desligar no meio, OBS 30.2+), na placa AMD (AMF), mesma qualidade da live
    return ("[General]\nName=" + NOME + "\n\n[Output]\nMode=Simple\nFilenameFormatting=Celular %CCYY-%MM-%DD %hh-%mm-%ss\n\n"
            "[SimpleOutput]\nFilePath=" + pasta + "\nRecFormat2=hybrid_mp4\nRecQuality=Stream\nStreamEncoder=amd\nVBitrate=4500\nABitrate=128\n\n"
            "[Video]\nBaseCX=1280\nBaseCY=720\nOutputCX=1280\nOutputCY=720\nFPSType=0\nFPSCommon=30\n"
            "ColorFormat=NV12\nColorSpace=709\nColorRange=Partial\n\n[Audio]\nSampleRate=48000\nChannelSetup=Stereo\n")


PERFIL = perfil_ini("C:/Users/Videos/Celular OBS")  # so para os testes antigos; o real sai de perfil_ini()


def prepara_obs(base=None):
    """Grava so os arquivos deste script; os do Rafael ficam como estao."""
    base = base or pasta_obs()
    cenas = base / "basic" / "scenes"
    perfil = base / "basic" / "profiles" / ARQ
    cenas.mkdir(parents=True, exist_ok=True)
    perfil.mkdir(parents=True, exist_ok=True)
    (cenas / f"{ARQ}.json").write_text(json.dumps(colecao(), ensure_ascii=False, indent=1), encoding="utf-8")
    (perfil / "basic.ini").write_text(perfil_ini(), encoding="utf-8")


# ---------------------------------------------------------------- OBS por comando (obs-controle.py) e permissoes do Windows
AQUI = pathlib.Path(__file__).resolve().parent
DIAG = AQUI.parent / "diagnostico"
PARAR = DIAG / "webcam-celular.parar"
ESTADO = DIAG / "webcam-celular.json"
LOG = DIAG / "webcam-celular.log"


def obsctl():
    import importlib.util
    spec = importlib.util.spec_from_file_location("obs_controle", AQUI / "obs-controle.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # type: ignore[union-attr]
    return m


def no_obs(acao, tentativas=1):
    """Roda acao(modulo, obs) no OBS aberto; devolve o texto ou None (OBS fechado, websocket desligado). Nunca derruba a webcam."""
    try:
        m = obsctl()
    except (OSError, SyntaxError):
        return None
    ultimo = None
    for i in range(tentativas):
        try:
            with m.Obs(tempo=5) as o:
                return acao(m, o)
        except (m.ErroObs, OSError, ValueError) as e:
            ultimo = e
            if i + 1 < tentativas:
                time.sleep(2)
    print(f"AVISO: nao falei com o OBS ({ultimo}).")
    return None


def prepara_camera_virtual(tentativas=1):
    """Camera virtual LIGADA e a cena no ar mostrando o celular (05/11: na aula ela estava desligada e o site so via o logo)."""
    def acao(m, o):
        cena, trocou = m.cena_com_webcam(o)
        cam = m.camera_virtual(o, True)
        return f"camera virtual {cam}; cena no ar: {cena}" + (" (troquei para ela)" if trocou else "")
    r = no_obs(acao, tentativas)
    if r:
        print(r)
    return r


def grava_no_obs(acao="iniciar"):
    def f(m, o):
        if acao == "iniciar":
            pasta = o.pede("GetRecordDirectory").get("recordDirectory", "")
            if not pasta or not pathlib.Path(pasta).is_dir():
                nova = pasta_gravacoes()
                nova.mkdir(parents=True, exist_ok=True)
                o.pede("SetRecordDirectory", {"recordDirectory": str(nova)})
                print(f"a pasta de gravacao do OBS nao existia; agora: {nova}")
        return m.gravar(o, acao)
    r = no_obs(f, 3)
    if r:
        print(r)
    return r


# ---------------------------------------------------------------- aviso na barra do celular (pedido do Rafael, 05/11)
SSH = pathlib.Path(r"C:\Program Files\Git\usr\bin\ssh.exe")
CHAVE_TERMUX = pathlib.Path(os.environ.get("USERPROFILE", str(pathlib.Path.home()))) / ".ssh" / "a12_termux"
PORTA_SSH_LOCAL = 8023  # a 8022 e do termux.ps1; esta e so do aviso
CEL = "/data/data/com.termux/files/home/bin/cel"


def texto_aviso(fonte, gravando=False, live=False):
    """(icone, titulo, texto) do aviso fixo. O icone da barra e um dos prontos do Android (o Termux:API nao aceita imagem propria)."""
    oque = "a TELA do celular" if fonte == "tela" else "a CAMERA do celular"
    if live:
        return "live_tv", "OBS do PC: AO VIVO", f"Transmitindo {oque}. Toque em Desligar para encerrar tudo."
    if gravando:
        return "fiber_manual_record", "OBS do PC: GRAVANDO", f"Gravando {oque} em D:/Videos/Celular OBS."
    if fonte == "tela":
        return "screen_share", "OBS do PC: tela do celular", "A tela vai para o OBS do PC (pronta para gravar ou transmitir)."
    return "videocam", "OBS do PC: camera do celular", "Camera virtual do PC ligada (aula, Meet, Teams)."


def comando_aviso(fonte, gravando=False, live=False, tirar=False):
    if tirar:
        return "timeout 20 termux-notification-remove obs-pc"
    icone, titulo, texto = texto_aviso(fonte, gravando, live)
    botoes = f"--button1 Desligar --button1-action '{CEL} obs desligar'"
    if gravando:
        botoes += f" --button2 'Parar gravacao' --button2-action '{CEL} obs parar-gravacao'"
    return (f"timeout 20 termux-notification --id obs-pc --ongoing --alert-once --priority high --icon {icone} "
            f"--title '{titulo}' --content '{texto}' {botoes}")


def aviso_celular(serial, fonte="camera", gravando=False, live=False, tirar=False):
    """Mostra (ou tira) o aviso fixo na barra do celular pelo SSH do Termux, pelo mesmo caminho do adb. Falhar nao derruba nada."""
    if not serial or not SSH.exists() or not CHAVE_TERMUX.exists():
        return False
    try:
        uid = re.search(r"userId=(\d+)", roda(["adb", "-s", serial, "shell", "dumpsys package com.termux | grep -m1 userId="], 20).stdout)
        if not uid:
            return False
        usuario = f"u0_a{int(uid.group(1)) - 10000}"
        roda(["adb", "-s", serial, "forward", f"tcp:{PORTA_SSH_LOCAL}", "tcp:8022"], 15)
        try:
            r = roda([str(SSH), "-i", str(CHAVE_TERMUX), "-p", str(PORTA_SSH_LOCAL), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
                      "-o", "ConnectTimeout=8", f"{usuario}@127.0.0.1", comando_aviso(fonte, gravando, live, tirar)], 40)
            return r.returncode == 0
        finally:
            roda(["adb", "-s", serial, "forward", "--remove", f"tcp:{PORTA_SSH_LOCAL}"], 15)
    except (subprocess.TimeoutExpired, OSError):
        return False


def atualiza_aviso(**mudou):
    """Para os comandos avulsos (gravar, parar-gravacao, live): atualiza o estado do modo de fundo e o aviso do celular."""
    try:
        e = json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    e.update(mudou)
    try:
        ESTADO.write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    aviso_celular(e.get("serial"), e.get("fonte", "camera"), e.get("gravando", False), e.get("live", False))


def permissoes_negadas():
    """Camera e captura de tela do Windows (o site da aula nao ve a camera nem compartilha a tela se estiverem em Negar)."""
    try:
        import winreg
    except ImportError:
        return []
    base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"
    neg = []
    for raiz, nome in ((winreg.HKEY_LOCAL_MACHINE, "HKLM"), (winreg.HKEY_CURRENT_USER, "HKCU")):
        for c in ("webcam", "graphicsCaptureProgrammatic", "graphicsCaptureWithoutBorder"):
            try:
                with winreg.OpenKey(raiz, f"{base}\\{c}") as k:
                    if winreg.QueryValueEx(k, "Value")[0] == "Deny":
                        neg.append(f"{nome}\\{c}")
            except OSError:
                pass
    return neg


def avisa_permissoes():
    neg = permissoes_negadas()
    if neg:
        print("AVISO: o Windows esta NEGANDO " + ", ".join(neg) + ": o site da aula fica sem camera ou sem compartilhar a tela.")
        print("       Conserte (como administrador): pwsh -File scripts\\pc-permissoes-aula.ps1 -Aplicar")


CHAVES = ("Profile", "ProfileDir", "SceneCollection", "SceneCollectionFile")


def le_escolha(ini):
    if not ini.exists():
        return {}
    t = ini.read_bytes().decode("utf-8-sig", "replace")
    return {k: m.group(1) for k in CHAVES if (m := re.search(rf"^{k}=(.*?)\r?$", t, re.M))}


def devolve_escolha(ini, antes):
    """Volta o OBS ao perfil e a colecao anteriores, sem tocar no resto do arquivo."""
    if not antes or not ini.exists():
        return
    t = ini.read_bytes().decode("utf-8", "surrogateescape")
    for k, v in antes.items():
        t = re.sub(rf"^{k}=.*?(\r?)$", lambda m, v=v, k=k: f"{k}={v}{m.group(1)}", t, flags=re.M)
    ini.write_bytes(t.encode("utf-8", "surrogateescape"))


def roda(args, timeout=60):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def tela(serial, modo):
    """Escurece ou acende sem bloquear (memoria/TELA-APAGADA.md). Falhar aqui nao derruba a webcam: e so para poupar bateria."""
    try:
        subprocess.run([sys.executable, "-B", str(pathlib.Path(__file__).resolve().parent / "tela-apagada.py"), modo], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45, env=dict(os.environ, ANDROID_SERIAL=serial))
    except (subprocess.TimeoutExpired, OSError):
        pass


def tenta(args, timeout=15):
    """Para o desligamento: a rede pode ter caido, e isso nao pode impedir o resto da limpeza."""
    try:
        roda(args, timeout)
    except (subprocess.TimeoutExpired, OSError):
        pass


def serial_usb(saida):
    """O aparelho do cabo: serial sem ':' (com ':' e conexao de rede)."""
    for linha in saida.splitlines():
        p = linha.split()
        if len(p) == 2 and p[1] == "device" and ":" not in p[0]:
            return p[0]
    return ""


def ip_wifi(saida_ip):
    m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", saida_ip)
    return m.group(1) if m else ""


def mesma_rede(ip, ips_pc):
    return bool(ip) and any(ip.rsplit(".", 1)[0] == p.rsplit(".", 1)[0] for p in ips_pc)


def ips_do_pc():
    try:
        return socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        return []


def conecta(alvo):
    return f"connected to {alvo}" in roda(["adb", "connect", alvo], 20).stdout


def desconecta(serial):
    """Dois aparelhos no adb quebrariam os outros scripts do projeto, que chamam 'adb' sem escolher."""
    if ":" in serial:
        tenta(["adb", "disconnect", serial])


def porta_aberta(usb):
    """Pergunta ao proprio celular: testar pela rede erra quando o Wi-Fi ou a Tailscale estao fora, e o tcpip reinicia o adb."""
    return roda(["adb", "-s", usb, "shell", "getprop service.adb.tcp.port"], 15).stdout.strip() == str(PORTA)


def abre_porta(usb):
    """Com o cabo: deixa o sem fio pronto ate reiniciar o celular. Quem entra precisa da chave deste PC, aceita no aparelho."""
    if porta_aberta(usb):
        return
    roda(["adb", "-s", usb, "tcpip", str(PORTA)], 20)
    time.sleep(4)
    print("Sem fio pronto: da proxima vez pode dispensar o cabo (vale ate reiniciar o celular).")


def rota_sem_fio():
    alvo = f"{IP_TAILSCALE}:{PORTA}"
    if not conecta(alvo):
        raise Erro("nao alcancei o celular: ligue o cabo uma vez (a porta fecha ao reiniciar) e confira a Tailscale nos dois aparelhos")
    wifi = ip_wifi(roda(["adb", "-s", alvo, "shell", "ip -4 addr show wlan0"], 20).stdout)
    if mesma_rede(wifi, ips_do_pc()):
        local = f"{wifi}:{PORTA}"
        desconecta(alvo)
        if conecta(local):
            print("Conexao: Wi-Fi local")
            return local, "wifi"
        conecta(alvo)
    if not wifi:
        print("AVISO: o celular esta nos DADOS MOVEIS. Gasta cerca de 900 MB por hora a 2 Mbit/s.")
        print("Conexao: Tailscale pelos dados moveis")
        return alvo, "dados"
    print("Conexao: Tailscale")
    return alvo, "tailscale"


def escolhe_rota(so_rede):
    usb = serial_usb(roda(["adb", "devices"]).stdout)
    if usb and not so_rede:
        abre_porta(usb)
        print("Conexao: cabo (melhor: tambem carrega o celular)")
        return usb, "cabo"
    return rota_sem_fio()


def confere(tamanho):
    if tamanho not in TAMANHOS_OK:
        raise Erro(f"tamanho {tamanho} nao testado neste aparelho; use um destes: {', '.join(sorted(TAMANHOS_OK))}")
    if not shutil.which("scrcpy"):
        raise Erro("scrcpy nao encontrado")
    if not OBS_PADRAO.exists():
        raise Erro(f"OBS nao encontrado em {OBS_PADRAO}")


def obs_aberto():
    return "obs64.exe" in roda(["tasklist", "/FI", "IMAGENAME eq obs64.exe", "/NH"]).stdout


def fecha_obs():
    roda(["taskkill", "/IM", "obs64.exe"])
    for _ in range(16):
        time.sleep(0.5)
        if not obs_aberto():
            return True
    roda(["taskkill", "/F", "/IM", "obs64.exe"])
    return False


def mede_camera_virtual(segundos=5):
    """Le a camera virtual como qualquer programa de chamada leria. So mede o brilho: a imagem nao e guardada nem vista."""
    r = roda(["ffmpeg", "-hide_banner", "-f", "dshow", "-i", "video=OBS Virtual Camera", "-t", str(segundos),
              "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG", "-f", "null", "-"], 60)
    return resume_medida(r.stdout + r.stderr)


def resume_medida(texto):
    vals = [float(v) for v in re.findall(r"YAVG=([\d.]+)", texto)]
    m = re.search(r"Video: .*?(\d{3,4})x(\d{3,4})", texto)
    return {"quadros": len(vals), "brilho": round(sum(vals) / len(vals)) if vals else 0, "tamanho": f"{m.group(1)}x{m.group(2)}" if m else "?"}


def faixas(texto, tolerancia=0.02):
    """Le a saida do cropdetect do ffmpeg: (esq, cima, dir, baixo) da tarja preta em pixels, ou None (sem tarja ou medida
    inconclusiva: imagem quase toda escura, como a camera de noite, nao e tarja)."""
    tam = re.search(r"Video: .*?(\d{3,4})x(\d{3,4})", texto)
    cortes = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", texto)
    if not tam or not cortes:
        return None
    W, H = int(tam.group(1)), int(tam.group(2))
    cw, ch, x, y = (int(v) for v in cortes[-1])
    if cw * ch < 0.5 * W * H:  # sobrou menos da metade: e escuridao, nao faixa
        return None
    m = (x, y, max(0, W - x - cw), max(0, H - y - ch))
    return m if (m[0] + m[2]) > tolerancia * W or (m[1] + m[3]) > tolerancia * H else None


def mede_faixas(entrada, segundos=3):
    """cropdetect em ~3 s da janela do scrcpy (gdigrab) ou da camera virtual (dshow); so mede, nada e gravado nem visto."""
    fonte = ["-f", "gdigrab", "-i", f"title={TITULO}"] if entrada == "janela" else ["-f", "dshow", "-i", "video=OBS Virtual Camera"]
    r = roda(["ffmpeg", "-hide_banner", *fonte, "-t", str(segundos), "-vf", "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"], 60)
    return faixas(r.stdout + r.stderr)


def corrige_faixas():
    """Verificacao pedida pelo Rafael (06/11: faixa preta com o celular de camera pelos dados): mede a tarja na janela do
    scrcpy, encaixa a fonte do celular na tela inteira do OBS cortando a tarja e confere a camera virtual depois."""
    m = mede_faixas("janela")
    r = no_obs(lambda mod, o: mod.encaixa(o, m), 2)
    if r is None:
        return None
    cena, tam, feitos = r
    print(f"OBS: {', '.join(feitos) or 'nenhuma fonte do celular'} na cena {cena} ocupando {tam[0]}x{tam[1]}"
          + (f"; tarja cortada {m}" if m else ""))
    depois = mede_faixas("camera")
    print("verificacao: camera virtual SEM faixa" if depois is None else f"ATENCAO: ainda ha faixa na camera virtual {depois} (celular em pe? deite-o)")
    return depois is None


def imagem_real(medida):
    return medida["quadros"] >= 5 and medida["brilho"] >= BRILHO_MINIMO_LANTERNA


def escreve_estado(**k):
    try:
        DIAG.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(json.dumps({**k, "pid": os.getpid(), "hora": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def espera_parar(sc):
    """Modo de fundo (acionado de longe): fica ate pedirem `parar` (arquivo PARAR) ou o scrcpy cair."""
    while sc.poll() is None and not PARAR.exists():
        time.sleep(1)
    if sc.poll() is not None and not PARAR.exists():
        print("o scrcpy caiu (rede ou celular): desligando tudo")


def liga(frontal, tamanho, fps, provar, so_rede, sem_espera=False, gravar=False, fonte="camera", som=False):
    confere(tamanho)
    avisa_permissoes()
    so_camera = obs_aberto()
    if so_camera and provar:
        raise Erro("feche o OBS antes da prova")
    ini = pasta_obs() / "user.ini"
    antes = le_escolha(ini)
    serial, tipo = escolhe_rota(so_rede)
    if not so_camera:
        prepara_obs()
        limpa_sentinela()
    if PARAR.exists():
        PARAR.unlink()
    sc = subprocess.Popen(args_scrcpy(serial, frontal, tamanho, fps, provar, tipo, fonte, som), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    obs = None
    gravando = False
    try:
        time.sleep(4)
        if sc.poll() is not None:
            raise Erro("o scrcpy fechou ao abrir a camera: feche o Open Camera ou outro app que esteja usando a camera e tente de novo")
        if fonte == "camera":
            tela(serial, "apagar")  # poupa bateria; keyevent 223 bloqueava em 15 s (na TELA nao: gravaria preto)
        if so_camera:
            print(f"\n{'Camera' if fonte == 'camera' else 'Tela do celular'} ligada no OBS que ja estava aberto.")
        else:
            # O obs64.exe esta marcado "executar como administrador" (para capturar jogos elevados): sem isto a ponte e o atalho,
            # que rodam sem elevacao, recebiam WinError 740. RunAsInvoker ignora a marca SO nesta abertura (camera, gravacao e live
            # nao precisam de administrador); a marca do Rafael continua para quando ele abre o OBS do jeito dele.
            obs = subprocess.Popen(args_obs(), cwd=str(OBS_PADRAO.parent), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   env={**os.environ, "__COMPAT_LAYER": "RunAsInvoker"})
            time.sleep(8)
        if not provar:
            prepara_camera_virtual(tentativas=4)
            time.sleep(2)  # a janela do scrcpy ja mostrando imagem
            corrige_faixas()  # 06/11: faixa preta pelos dados moveis; mede, corta a tarja, encaixa e confere
        if gravar:
            gravando = bool(grava_no_obs("iniciar"))
        if not provar:  # icone fixo na barra do celular enquanto estiver no OBS (some ao desligar)
            print("aviso na barra do celular: " + ("ligado" if aviso_celular(serial, fonte, gravando) else "nao deu (Termux fechado?)"))
        if sem_espera:
            escreve_estado(pronto=True, fonte=fonte, rota=tipo, gravando=gravando, live=False, obs_do_rafael=so_camera, serial=serial)
            print("PRONTO")
            sys.stdout.flush()
            espera_parar(sc)
            return 0
        if provar:
            m = mede_camera_virtual()
            print(f"camera virtual: {m['quadros']} quadros, {m['tamanho']}, brilho {m['brilho']} (com a lanterna)")
            if imagem_real(m):
                print("OK: a imagem do celular chega a camera virtual.")
                return 0
            print("SEM IMAGEM: a camera virtual nao esta recebendo a janela do scrcpy.")
            return 1
        if not so_camera:
            print('\nPronto: no programa da chamada escolha a camera "OBS Virtual Camera".')
        print("Deixe a janela do celular aberta (pode ficar atras das outras, nao minimize).")
        print("Quando acabar, volte aqui e aperte Enter para desligar.\n")
        input()
        return 0
    finally:
        # gravacao primeiro: fechar o OBS gravando abre uma pergunta na tela e o arquivo pode ficar sem o fim
        if gravando or (obs is not None and not provar):
            grava_no_obs("parar")
        # primeiro o que e do PC: com a rede fora, os comandos do celular demoram e nao podem deixar o OBS no perfil errado
        if obs is not None:
            try:
                fecha_obs()
            except subprocess.TimeoutExpired:
                tenta(["taskkill", "/F", "/IM", "obs64.exe"])
        if sc.poll() is None:
            sc.terminate()
        if not so_camera:
            devolve_escolha(ini, antes)
        if not provar:
            aviso_celular(serial, tirar=True)
        if fonte == "camera":
            tela(serial, "acender")
        desconecta(serial)
        if sem_espera:
            for f in (ESTADO, PARAR):
                try:
                    f.unlink()
                except OSError:
                    pass


def fecha_sem_fio():
    usb = serial_usb(roda(["adb", "devices"]).stdout)
    if not usb:
        raise Erro("ligue o cabo para fechar a porta (ou reinicie o celular, que tambem fecha)")
    roda(["adb", "-s", usb, "usb"], 20)
    print("Porta de rede do adb fechada. Para o sem fio voltar, rode a webcam uma vez com o cabo.")
    return 0


def em_fundo():
    """Dados do modo de fundo, se o processo ainda estiver vivo."""
    try:
        e = json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    vivo = str(e.get("pid", "")) in roda(["tasklist", "/FI", f"PID eq {e.get('pid')}", "/NH"]).stdout
    return e if vivo else None


def iniciar(a):
    """Liga em segundo plano (para o acesso remoto e para o celular pedir pela ponte) e volta assim que estiver pronto."""
    e = em_fundo()
    if e:
        print(f"Ja esta ligado ({e.get('fonte')}, desde {e.get('hora')}).")
        if a.gravar:
            grava_no_obs("iniciar")
        return 0
    DIAG.mkdir(parents=True, exist_ok=True)
    for f in (ESTADO, PARAR):
        if f.exists():
            f.unlink()
    args = [sys.executable, "-B", str(pathlib.Path(__file__).resolve()), "ligar", "--sem-espera", "--tamanho", a.tamanho, "--fps", str(a.fps)]
    args += [x for x, s in (("--frontal", a.frontal), ("--sem-fio", a.sem_fio), ("--gravar", a.gravar), ("--tela", a.tela), ("--som", a.som)) if s]
    log = open(LOG, "w", encoding="utf-8")
    flags = 0x00000008 | 0x00000200 | 0x08000000 if os.name == "nt" else 0  # DETACHED, NEW_GROUP, NO_WINDOW
    p = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=flags,
                         env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
    log.close()
    for _ in range(90):
        time.sleep(1)
        texto = LOG.read_text(encoding="utf-8", errors="replace") if LOG.exists() else ""
        if "PRONTO" in texto or p.poll() is not None:
            print(texto.replace("PRONTO", "").strip())
            if "PRONTO" in texto:
                print(f"\nLigado em segundo plano. Para desligar: webcam-celular.py parar")
                return 0
            return 2
    print("Ainda subindo depois de 90 s; confira com: webcam-celular.py status")
    return 1


def parar():
    e = em_fundo()
    if not e:
        # o processo pode ter morrido sem a limpeza (PC desligado, sessao encerrada): tira o aviso que ficou no celular
        lista = roda(["adb", "devices"]).stdout
        serial = serial_usb(lista) or next((s for s in (f"{IP_TAILSCALE}:{PORTA}",) if f"{s}\tdevice" in lista), "")
        if serial and aviso_celular(serial, tirar=True):
            print("Tirei o aviso que tinha ficado na barra do celular.")
        for f in (ESTADO, PARAR):
            if f.exists():
                f.unlink()
        print("Nada ligado em segundo plano.")
        return 0
    PARAR.write_text("parar", encoding="utf-8")
    for _ in range(60):
        time.sleep(1)
        if not em_fundo():
            print("Desligado (gravacao salva, OBS devolvido ao perfil anterior, tela do celular acesa).")
            return 0
    print("Nao desligou em 60 s; o processo segue no PC.")
    return 1


def status():
    e = em_fundo()
    print(f"Celular no OBS: {'LIGADO (' + str(e.get('fonte')) + ' pela rota ' + str(e.get('rota')) + ', desde ' + str(e.get('hora')) + ')' if e else 'desligado'}")
    if obs_aberto():
        r = no_obs(lambda m, o: m.status(o))
        if r:
            print(r)
    else:
        print("OBS fechado.")
    avisa_permissoes()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Celular (camera ou tela) no OBS do PC: webcam, gravacao e live, perto ou longe")
    ap.add_argument("modo", nargs="?", default="ligar",
                    choices=["ligar", "provar", "fechar-sem-fio", "iniciar", "parar", "status", "gravar", "parar-gravacao", "live", "parar-live", "verificar"])
    ap.add_argument("--frontal", action="store_true")
    ap.add_argument("--sem-fio", action="store_true", help="usa a rede mesmo com o cabo ligado")
    ap.add_argument("--tamanho", default="1280x720")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--tela", action="store_true", help="a TELA do celular em vez da camera")
    ap.add_argument("--som", action="store_true", help="leva o som do celular (microfone na camera, som do aparelho na tela)")
    ap.add_argument("--gravar", action="store_true", help="ja comeca gravando no PC")
    ap.add_argument("--sem-espera", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    try:
        if a.modo == "fechar-sem-fio":
            return fecha_sem_fio()
        if a.modo == "iniciar":
            return iniciar(a)
        if a.modo == "parar":
            return parar()
        if a.modo == "status":
            return status()
        if a.modo == "verificar":  # faixa preta na imagem: mede, corrige e confere (o celular ja no OBS)
            ok = corrige_faixas()
            return 0 if ok else (2 if ok is None else 1)
        if a.modo == "gravar":
            if em_fundo() or obs_aberto():
                if not em_fundo():
                    print("AVISO: o OBS esta aberto mas o celular nao esta ligado nele por este script; gravo o que estiver no ar.")
                if not grava_no_obs("iniciar"):
                    return 1
                atualiza_aviso(gravando=True)
                return 0
            a.gravar = True
            return iniciar(a)
        if a.modo == "parar-gravacao":
            if not grava_no_obs("parar"):
                return 1
            atualiza_aviso(gravando=False)
            return 0
        if a.modo in ("live", "parar-live"):
            liga_live = a.modo == "live"
            r = no_obs(lambda m, o: m.transmitir(o, "iniciar" if liga_live else "parar"))
            if not r:
                return 1
            print(r)
            atualiza_aviso(live=liga_live and ("iniciada" in r or "ja estava" in r))
            return 0
        return liga(a.frontal, a.tamanho, a.fps, a.modo == "provar", a.sem_fio, a.sem_espera, a.gravar, "tela" if a.tela else "camera", a.som)
    except Erro as e:
        print("NAO LIGOU:", e)
        return 2
    except subprocess.TimeoutExpired:
        print("NAO LIGOU: o celular parou de responder. Confira o cabo ou a rede e tente de novo.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
