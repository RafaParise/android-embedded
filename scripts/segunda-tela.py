#!/usr/bin/env python3
"""Segunda tela entre o PC e o A12 (pedido do Rafael, 05/11/2026), com cabo, Wi-Fi ou dados moveis.

  python scripts/segunda-tela.py celular [--leve]             o PC mostra e comanda a tela do celular (scrcpy). AUTOMATICO:
                                                              janela levada para a TV = tela cheia e SEM faixas (o celular
                                                              desenha na proporcao dela: wm size 720x1280 para 16:9); Alt+F
                                                              em qualquer monitor = idem; de volta ao monitor do PC em
                                                              janela = celular normal; fechar a janela = tudo normal
  python scripts/segunda-tela.py celular --preencher          igual, mas ja abre em tela cheia na TV (ou no monitor principal)
  python scripts/segunda-tela.py normal                       desfaz o --preencher se a janela do console foi fechada no X
  python scripts/segunda-tela.py extra [--app PACOTE] [--leve] o celular ganha uma TELA EXTRA, que aparece numa janela
                                                              do PC (scrcpy --new-display; padrao: Notas; o Fennec fica PRETO na tela virtual, conferido 05/11)
  python scripts/segunda-tela.py pc                           o celular vira MONITOR EXTRA do Windows (Sunshine no PC +
                                                              Moonlight no celular; instalar uma vez: segunda-tela-instalar.cmd)
  python scripts/segunda-tela.py status                       mostra o que esta pronto
  (sem argumento: menu)

Conexao: cabo, se estiver ligado; senao a Tailscale pela porta 5555 do adb (adb-remoto.py), que vale no Wi-Fi e nos dados
moveis. --leve = 2 Mbit/s, 1024 px e 30 quadros (para dados moveis: cerca de 15 MB por minuto [Palpite: conta pelo limite]).
Nunca usa --turn-screen-off (tela preta sem saida ao tirar o cabo: regra do CLAUDE.md).
"""
import ctypes
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import time

AQUI = pathlib.Path(__file__).resolve().parent
MARCA = AQUI.parent / "diagnostico" / "segunda-tela-preencher.marca"  # existe = a tela do celular esta em tamanho trocado
APP_PADRAO = "org.fossify.notes"
# Apps que desenham na tela virtual (conferido 05/11: as Notas sim; o Fennec/GeckoView fica com a janela preta).
APPS_EXTRA = [("Notas", "org.fossify.notes"), ("Arquivos", "org.fossify.filemanager"), ("Galeria", "org.fossify.gallery"),
              ("Termux", "com.termux"), ("VLC", "org.videolan.vlc"), ("Agenda", "org.fossify.calendar")]


def escolhe_app():
    for i, (nome, _) in enumerate(APPS_EXTRA, 1):
        print(" %d  %s" % (i, nome))
    try:
        op = input("Qual app abrir na tela extra? [1] ").strip() or "1"
    except EOFError:
        op = "1"
    return APPS_EXTRA[int(op) - 1][1] if op.isdigit() and 1 <= int(op) <= len(APPS_EXTRA) else APP_PADRAO
PC_IP = "100.64.0.1"
_executa = subprocess.run  # os testes trocam por um falso
_inicia = subprocess.Popen


def remoto():
    spec = importlib.util.spec_from_file_location("adb_remoto", AQUI / "adb-remoto.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m._executa = _executa
    return m


def scrcpy():
    s = shutil.which("scrcpy")
    if s:
        return s
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    achados = sorted(base.glob("Genymobile.scrcpy_*/scrcpy-win64-*/scrcpy.exe"))
    return str(achados[-1]) if achados else None


def conecta():
    """(serial, solta_no_fim) ou (None, False)."""
    r = remoto()
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        codigo = r.garantir()
    modo = buf.getvalue().strip().splitlines()[0] if buf.getvalue().strip() else ""
    if codigo != 0:
        print(buf.getvalue().strip())
        return None, False
    if modo == "cabo":
        cabo = [s for s, e in r.aparelhos().items() if e == "device" and ":" not in s]
        return (cabo[0] if cabo else None), False
    return "%s:%d" % (r.ip_celular(), r.PORTA), modo == "tailscale-nova"


def tamanho_monitor():
    try:
        u = ctypes.windll.user32
        u.SetProcessDPIAware()
        return u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    except (AttributeError, OSError):
        return 1440, 900


_WIN = {}


def _win():
    """(user32, wintypes, INFO, DISP) no Windows; None fora dele (os testes rodam no Linux)."""
    if not _WIN:
        try:
            from ctypes import wintypes as wt
            u = ctypes.windll.user32
            u.SetProcessDPIAware()
        except (AttributeError, OSError, ImportError, ValueError):
            return None

        class INFO(ctypes.Structure):
            _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD),
                        ("szDevice", wt.WCHAR * 32)]

        class DISP(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("DeviceName", wt.WCHAR * 32), ("DeviceString", wt.WCHAR * 128),
                        ("StateFlags", wt.DWORD), ("DeviceID", wt.WCHAR * 128), ("DeviceKey", wt.WCHAR * 128)]

        u.FindWindowW.restype = wt.HWND
        u.MonitorFromWindow.restype = wt.HMONITOR
        u.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
        u.GetMonitorInfoW.argtypes = [wt.HMONITOR, ctypes.c_void_p]
        u.GetWindowRect.argtypes = [wt.HWND, ctypes.c_void_p]
        u.IsIconic.argtypes = [wt.HWND]
        u.SetForegroundWindow.argtypes = [wt.HWND]
        u.GetForegroundWindow.restype = wt.HWND
        _WIN.update(u=u, wt=wt, INFO=INFO, DISP=DISP)
    return _WIN["u"], _WIN["wt"], _WIN["INFO"], _WIN["DISP"]


def monitores():
    """Telas do Windows: [{nome, x, y, w, h, principal, tv, virtual}]. TV = monitor DEFAULT_MONITOR (a do Miracast);
    virtual = MTT1337 (o monitor do celular no Moonlight). Fora do Windows: []."""
    w = _win()
    if not w:
        return []
    u, wt, INFO, DISP = w
    lista = []

    def cada(hmon, _hdc, _ret, _p):
        i = INFO()
        i.cbSize = ctypes.sizeof(i)
        if u.GetMonitorInfoW(hmon, ctypes.byref(i)):
            ids = ""
            d = DISP()
            d.cb = ctypes.sizeof(d)
            j = 0
            while u.EnumDisplayDevicesW(i.szDevice, j, ctypes.byref(d), 0):
                ids += d.DeviceID.upper() + " "
                j += 1
            r = i.rcMonitor
            lista.append({"nome": i.szDevice, "x": r.left, "y": r.top, "w": r.right - r.left, "h": r.bottom - r.top,
                          "principal": bool(i.dwFlags & 1), "tv": "DEFAULT_MONITOR" in ids, "virtual": "MTT1337" in ids})
        return True

    proc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)(cada)
    u.EnumDisplayMonitors(None, None, proc, 0)
    return lista


def monitor_alvo(lista):
    """A TV sem fio, se estiver conectada; senao o monitor principal (nunca o virtual do celular)."""
    reais = [m for m in lista if not m["virtual"]]
    for m in reais:
        if m["tv"]:
            return m
    for m in reais:
        if m["principal"]:
            return m
    return reais[0] if reais else None


def tamanho_fisico(serial):
    """(lado curto, lado longo) da tela do celular, pelo `wm size` (A12: 720x1600)."""
    r = _executa(["adb", "-s", serial, "shell", "wm", "size"], capture_output=True, text=True)
    for linha in (r.stdout or "").splitlines():
        if linha.startswith("Physical size:"):
            a, b = (int(v) for v in linha.split(":")[1].strip().split("x"))
            return min(a, b), max(a, b)
    return None


def forma_para(fisico, w, h):
    """Tamanho (em pe) que deixa a tela do celular na MESMA proporcao do monitor: o espelho deitado preenche a tela
    sem faixas. Mantem o lado curto (720) e encurta o longo: 1920x1080 (16:9) -> 720x1280. None = nada a mudar."""
    if not fisico or not w or not h:
        return None
    curto, longo = fisico
    novo = int(round(curto * max(w, h) / min(w, h) / 2.0)) * 2
    return None if novo >= longo else (curto, novo)


def volta_tamanho(serial):
    _executa(["adb", "-s", serial, "shell", "wm", "size", "reset"], capture_output=True, text=True)
    try:
        MARCA.unlink()
    except FileNotFoundError:
        pass
    print("Tela do celular de volta ao tamanho normal (720x1600).")


TITULO = "Celular (A12)"
INTERVALO = 1.0  # segundos entre as olhadas na janela (os testes poem 0)


def onde_esta(titulo):
    """Onde a janela do scrcpy esta: {hwnd, tv, virtual, cheia, w, h} do monitor dela; None se nao existe ou minimizada."""
    w = _win()
    if not w:
        return None
    u, wt, INFO, _ = w
    hwnd = u.FindWindowW(None, titulo)
    if not hwnd or u.IsIconic(hwnd):
        return None
    r = wt.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    i = INFO()
    i.cbSize = ctypes.sizeof(i)
    if not u.GetMonitorInfoW(u.MonitorFromWindow(hwnd, 2), ctypes.byref(i)):
        return None
    mr = i.rcMonitor
    mon = next((m for m in monitores() if m["nome"] == i.szDevice), {})
    return {"hwnd": hwnd, "tv": mon.get("tv", False), "virtual": mon.get("virtual", False),
            "cheia": (r.left, r.top, r.right, r.bottom) == (mr.left, mr.top, mr.right, mr.bottom),
            "w": mr.right - mr.left, "h": mr.bottom - mr.top}


def poe_tela_cheia(hwnd):
    """Alt+F na janela do scrcpy (o atalho de tela cheia dele). So aperta o F se a janela ficou mesmo em primeiro
    plano: senao o Alt+F iria para outro programa. Devolve True se mandou."""
    w = _win()
    if not w:
        return False
    u = w[0]
    u.keybd_event(0x12, 0, 0, 0)  # Alt apertado: o Windows deixa trazer a janela para frente
    try:
        u.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        if u.GetForegroundWindow() != hwnd:
            return False
        u.keybd_event(0x46, 0, 0, 0)
        u.keybd_event(0x46, 0, 2, 0)
        return True
    finally:
        u.keybd_event(0x12, 0, 2, 0)


def quer_tamanho(fisico, local):
    """Na TV ou em tela cheia em qualquer monitor: o celular na proporcao daquela tela. Janela comum no monitor do PC
    (ou no monitor virtual do proprio celular): tamanho normal (None)."""
    if not local or local["virtual"] or not (local["tv"] or local["cheia"]):
        return None
    return forma_para(fisico, local["w"], local["h"])


class Ajuste:
    """Guarda o tamanho que a tela do celular tem agora e so chama o adb quando muda."""

    def __init__(self, serial):
        self.serial, self.atual, self._fisico = serial, None, None

    @property
    def fisico(self):
        if self._fisico is None:
            self._fisico = tamanho_fisico(self.serial)
        return self._fisico

    def aplica(self, alvo):
        if alvo == self.atual:
            return
        if alvo:
            MARCA.parent.mkdir(exist_ok=True)
            MARCA.write_text("%dx%d\n" % alvo)
            _executa(["adb", "-s", self.serial, "shell", "wm", "size", "%dx%d" % alvo], capture_output=True, text=True)
            print("Celular desenhando em %dx%d (a proporcao da tela): deitado, preenche sem faixas;" % alvo)
            print("no proprio celular aparecem faixas enquanto isso.")
        else:
            volta_tamanho(self.serial)
        self.atual = alvo


def vigia(ajuste, parar, ja_cheia=False):
    """Enquanto a janela esta aberta: chegou na TV = tela cheia (uma vez por chegada) e celular no formato dela;
    voltou ao monitor do PC em janela comum = celular normal."""
    while not parar.wait(INTERVALO):
        local = onde_esta(TITULO)
        if local is None:
            continue
        if local["tv"] and not local["cheia"] and not ja_cheia:
            ja_cheia = True
            if poe_tela_cheia(local["hwnd"]):
                continue  # na proxima olhada ela ja esta em tela cheia
            print("Para tela cheia: clique na janela do celular e aperte Alt+F.")
        if not local["tv"]:
            ja_cheia = False
        try:
            ajuste.aplica(quer_tamanho(ajuste.fisico, local))
        except OSError:
            pass  # adb caiu um instante: tenta de novo na proxima olhada


def roda_scrcpy(args, serial, soltar, ao_fim=None, durante=None):
    exe = scrcpy()
    if not exe:
        print("Falta o scrcpy no PC (winget install Genymobile.scrcpy).")
        if ao_fim:
            ao_fim()
        return 2
    print("Abrindo (feche a janela para terminar)... conexao: " + ("cabo" if ":" not in serial else "Tailscale " + serial))
    parar = threading.Event()
    t = None
    try:
        if durante:
            t = threading.Thread(target=durante, args=(parar,), daemon=True)
            t.start()
        return _executa([exe, "-s", serial, *args]).returncode
    finally:
        parar.set()
        if t:
            t.join(10)
        if ao_fim:
            ao_fim()  # antes de soltar a Tailscale: depois nao ha mais como falar com o celular
        if soltar:
            remoto().soltar()


def celular(leve, preencher=False):
    serial, soltar = conecta()
    if not serial:
        return 1
    args = ["--window-title=" + TITULO] + (["--stay-awake"] if ":" not in serial else [])
    if leve:
        args += ["--video-bit-rate=2M", "--max-size=1024", "--max-fps=30", "--no-audio"]
    if MARCA.exists():  # uma sessao anterior foi fechada sem desfazer (janela do console fechada no X)
        volta_tamanho(serial)
    ajuste = Ajuste(serial)
    if preencher:
        mon = monitor_alvo(monitores())
        if mon:
            print("Tela cheia em %s (%dx%d%s)." % (mon["nome"], mon["w"], mon["h"], ", a TV" if mon["tv"] else ""))
            args += ["--fullscreen", "--window-x=%d" % (mon["x"] + 40), "--window-y=%d" % (mon["y"] + 40)]
            ajuste.aplica(forma_para(ajuste.fisico, mon["w"], mon["h"]))
    print("Automatico: leve a janela para a TV (ou Alt+F em qualquer monitor) e a imagem preenche a tela; de volta ao")
    print("monitor do PC em janela, o celular volta ao normal. Ao fechar a janela, tudo volta ao normal.")

    def ao_fim():
        if ajuste.atual:
            ajuste.aplica(None)
    return roda_scrcpy(args, serial, soltar, ao_fim, lambda parar: vigia(ajuste, parar, preencher))


def normal():
    """Desfaz o preencher a mao (se a janela do console foi fechada no X e a tela do celular ficou menor)."""
    serial, soltar = conecta()
    if not serial:
        return 1
    try:
        volta_tamanho(serial)
    finally:
        if soltar:
            remoto().soltar()
    return 0


def extra(app, leve):
    serial, soltar = conecta()
    if not serial:
        return 1
    w, h = tamanho_monitor()
    w, h = min(w, 1920), min(h, 1080)
    args = ["--window-title=Tela extra do celular", "--new-display=%dx%d/160" % (w, h), "--start-app=" + (app or APP_PADRAO)]
    if leve:
        args += ["--video-bit-rate=2M", "--max-size=1024", "--max-fps=30", "--no-audio"]
    return roda_scrcpy(args, serial, soltar)


def sunshine_instalado():
    r = _executa(["sc", "query", "SunshineService"], capture_output=True, text=True)
    return r.returncode == 0, ("RUNNING" in (r.stdout or ""))


def pc():
    instalado, rodando = sunshine_instalado()
    if not instalado:
        print("O celular como monitor do PC precisa de 2 programas no PC (uma vez so, como administrador):")
        print("  clique com o botao direito em scripts\\segunda-tela-instalar.cmd > Executar como administrador.")
        return 2
    if not rodando:
        _executa(["sc", "start", "SunshineService"], capture_output=True, text=True)
    print("Sunshine ligado no PC. No celular: abra o Moonlight, toque no PC (ou + e digite " + PC_IP + ")")
    print("e escolha 'Monitor extra (celular)': o PC liga um monitor virtual de 1600x720 a DIREITA da tela e o celular o mostra;")
    print("arraste janelas para a direita. Ao sair do Moonlight o monitor virtual desliga sozinho (scripts\\monitor-virtual.ps1).")
    print("'Desktop' no Moonlight = espelhar a tela principal. Primeira vez: o Moonlight mostra um PIN; digite-o em https://localhost:47990/pin.")
    print("Ao terminar: python scripts\\segunda-tela.py pc-parar (o Sunshine fica parado e nao gasta nada).")
    return 0


def pc_parar():
    _executa(["sc", "stop", "SunshineService"], capture_output=True, text=True)
    print("Sunshine parado.")
    return 0


def status():
    print("scrcpy: " + (scrcpy() or "FALTA"))
    instalado, rodando = sunshine_instalado()
    print("Sunshine (monitor extra do PC): " + ("instalado, " + ("ligado" if rodando else "parado") if instalado else "nao instalado (segunda-tela-instalar.cmd)"))
    r = remoto()
    lista = r.aparelhos()
    print("cabo: " + ("sim" if any(e == "device" and ":" not in s for s, e in lista.items()) else "nao") + " | celular na Tailscale: " + r.ip_celular())
    return 0


def menu():
    print("== Segunda tela ==")
    print(" 1  Ver e comandar o celular no PC")
    print(" 2  Tela EXTRA do celular numa janela do PC")
    print(" 3  Celular como MONITOR EXTRA do PC")
    print(" 4  Igual ao 1, versao leve (dados moveis)")
    print(" 5  Parar o monitor extra (Sunshine)")
    print(" 6  Igual ao 1, PREENCHENDO a TV ou o monitor (tela cheia, sem faixas)")
    print(" 0  Sair")
    try:
        op = input("Escolha: ").strip()
    except EOFError:
        return 0
    return {"1": lambda: celular(False), "2": lambda: extra(escolhe_app(), False), "3": pc, "4": lambda: celular(True),
            "5": pc_parar, "6": lambda: celular(False, True)}.get(op, lambda: 0)()


def main(args):
    if not args:
        return menu()
    leve = "--leve" in args
    app = None
    if "--app" in args:
        i = args.index("--app")
        app = args[i + 1] if i + 1 < len(args) else None
        if not app or not all(c.isalnum() or c in "._" for c in app):
            print("--app precisa de um nome de pacote (ex.: org.mozilla.fennec_fdroid)")
            return 2
    cmd = args[0]
    if cmd == "celular":
        return celular(leve, "--preencher" in args)
    if cmd == "normal":
        return normal()
    if cmd == "extra":
        return extra(app, leve)
    if cmd == "pc":
        return pc()
    if cmd == "pc-parar":
        return pc_parar()
    if cmd == "status":
        return status()
    print(__doc__.strip())
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
