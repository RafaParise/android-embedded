#!/usr/bin/env python3
"""Usa a camera do A12 como webcam do PC, com ou sem cabo: scrcpy (camera direta, sem app no celular) + camera virtual do OBS.

  Dois cliques em scripts\\webcam-celular.cmd. No Teams, Meet ou Zoom: "OBS Virtual Camera".
  Escolhe sozinho o caminho: cabo, senao Wi-Fi local, senao Tailscale. Sem fio funciona ate reiniciar o celular;
  depois disso, ligue o cabo uma vez e rode de novo.
  python scripts/webcam-celular.py ligar [--frontal] [--sem-fio] [--tamanho 1280x720] [--fps 30]
  python scripts/webcam-celular.py provar [--sem-fio]   liga, mede pela camera virtual (com a lanterna, sem olhar a imagem) e desliga
  python scripts/webcam-celular.py fechar-sem-fio       fecha a porta de rede do adb no celular (precisa do cabo)

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


def args_scrcpy(serial="", frontal=False, tamanho="1280x720", fps=30, lanterna=False, tipo="cabo"):
    largura, altura = tamanho.split("x")
    a = ["scrcpy"] + (["-s", serial] if serial else []) + ["--video-source=camera", f"--camera-facing={'front' if frontal else 'back'}", f"--camera-size={tamanho}",
         f"--camera-fps={fps}", f"--video-bit-rate={BITRATE[tipo]}", "--no-audio", f"--window-title={TITULO}", f"--window-width={largura}", f"--window-height={altura}", "--window-borderless"]
    if tipo != "cabo":
        a.append("--video-buffer=50")  # folga pequena contra oscilacao da rede
    return a + ["--camera-torch"] if lanterna else a


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
            {"id": "scene", "versioned_id": "scene", "name": "Celular", "enabled": True,
             "settings": {"id_counter": 1, "custom_size": False, "items": [{
                 "name": "Janela scrcpy", "id": 1, "visible": True, "locked": False, "rot": 0.0, "align": 5, "scale_filter": "disable",
                 "pos": {"x": 0.0, "y": 0.0}, "scale": {"x": 1.0, "y": 1.0}, "bounds_type": 2, "bounds_align": 0,
                 "bounds": {"x": 1280.0, "y": 720.0}}]}},
        ],
    }


PERFIL = ("[General]\nName=" + NOME + "\n\n[Video]\nBaseCX=1280\nBaseCY=720\nOutputCX=1280\nOutputCY=720\nFPSType=0\nFPSCommon=30\n"
          "ColorFormat=NV12\nColorSpace=709\nColorRange=Partial\n\n[Audio]\nSampleRate=48000\nChannelSetup=Stereo\n")


def prepara_obs(base=None):
    """Grava so os arquivos deste script; os do Rafael ficam como estao."""
    base = base or pasta_obs()
    cenas = base / "basic" / "scenes"
    perfil = base / "basic" / "profiles" / ARQ
    cenas.mkdir(parents=True, exist_ok=True)
    perfil.mkdir(parents=True, exist_ok=True)
    (cenas / f"{ARQ}.json").write_text(json.dumps(colecao(), ensure_ascii=False, indent=1), encoding="utf-8")
    (perfil / "basic.ini").write_text(PERFIL, encoding="utf-8")


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


def imagem_real(medida):
    return medida["quadros"] >= 5 and medida["brilho"] >= BRILHO_MINIMO_LANTERNA


def liga(frontal, tamanho, fps, provar, so_rede):
    confere(tamanho)
    so_camera = obs_aberto()
    if so_camera and provar:
        raise Erro("feche o OBS antes da prova")
    ini = pasta_obs() / "user.ini"
    antes = le_escolha(ini)
    serial, tipo = escolhe_rota(so_rede)
    if not so_camera:
        prepara_obs()
    sc = subprocess.Popen(args_scrcpy(serial, frontal, tamanho, fps, provar, tipo), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    obs = None
    try:
        time.sleep(4)
        if sc.poll() is not None:
            raise Erro("o scrcpy fechou ao abrir a camera: feche o Open Camera ou outro app que esteja usando a camera e tente de novo")
        tela(serial, "apagar")  # poupa bateria; keyevent 223 bloqueava em 15 s
        if so_camera:
            print("\nCamera ligada: ela aparece nas cenas de webcam do OBS que esta aberto.")
        else:
            obs = subprocess.Popen(args_obs(), cwd=str(OBS_PADRAO.parent), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(8)
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
        tela(serial, "acender")
        desconecta(serial)


def fecha_sem_fio():
    usb = serial_usb(roda(["adb", "devices"]).stdout)
    if not usb:
        raise Erro("ligue o cabo para fechar a porta (ou reinicie o celular, que tambem fecha)")
    roda(["adb", "-s", usb, "usb"], 20)
    print("Porta de rede do adb fechada. Para o sem fio voltar, rode a webcam uma vez com o cabo.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Celular como webcam do PC")
    ap.add_argument("modo", nargs="?", default="ligar", choices=["ligar", "provar", "fechar-sem-fio"])
    ap.add_argument("--frontal", action="store_true")
    ap.add_argument("--sem-fio", action="store_true", help="usa a rede mesmo com o cabo ligado")
    ap.add_argument("--tamanho", default="1280x720")
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args(argv)
    try:
        if a.modo == "fechar-sem-fio":
            return fecha_sem_fio()
        return liga(a.frontal, a.tamanho, a.fps, a.modo == "provar", a.sem_fio)
    except Erro as e:
        print("NAO LIGOU:", e)
        return 2
    except subprocess.TimeoutExpired:
        print("NAO LIGOU: o celular parou de responder. Confira o cabo ou a rede e tente de novo.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
