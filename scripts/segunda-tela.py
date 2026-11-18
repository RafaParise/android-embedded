#!/usr/bin/env python3
"""Segunda tela entre o PC e o A12 (pedido do Rafael, 05/11/2026), com cabo, Wi-Fi ou dados moveis.

  python scripts/segunda-tela.py celular [--leve]             o PC mostra e comanda a tela do celular (scrcpy). AUTOMATICO: janela
                                                              levada para a TV sem fio (ou Alt+F em qualquer monitor) = tela cheia
                                                              SEM faixas: o celular passa a desenhar NA PROPORCAO DA TV (wm size
                                                              720x1280 para 16:9) e, enquanto isso, mostra faixas pretas em si; em
                                                              janela no monitor do PC, e ao fechar a janela, volta ao normal.
                                                              (12/11/2026: o A12 ficou em 720x960 sem voltar; agora o voltar e'
                                                              CONFERIDO pelo tamanho real, e toda abertura desfaz o que sobrou.)
  python scripts/segunda-tela.py celular --so-espelho         nunca mexe na tela do celular (na TV ficam faixas dos lados)
  python scripts/segunda-tela.py celular --preencher          ja abre em tela cheia na TV (ou no monitor principal), preenchida
  python scripts/segunda-tela.py normal                       confere a tela do celular e desfaz um tamanho forcado que sobrou
  python scripts/segunda-tela.py extra [--app PACOTE] [--leve] o celular ganha uma TELA EXTRA, que aparece numa janela
                                                              do PC (scrcpy --new-display; padrao: Notas; o Fennec fica PRETO na tela virtual, conferido 05/11)
  python scripts/segunda-tela.py pc                           o celular vira MONITOR EXTRA do Windows (Sunshine no PC +
                                                              Moonlight no celular; instalar uma vez: segunda-tela-instalar.cmd)
  python scripts/segunda-tela.py tv                           poe a TV sem fio do Windows no melhor modo 16:9 dela (a Miracast
                                                              entra em 1024x768, 4:3, e a TV fica com barras pretas; o espelho
                                                              e o status tambem fazem isso sozinhos)
  python scripts/segunda-tela.py vigia-tv [instalar|remover|estado]  o VIGIA: a cada 4 s, TV sem fio em modo DUPLICAR vira
                                                              ESTENDER e TV fora de 16:9 vai ao melhor 16:9 dela (tarefa do
                                                              Windows no logon; `instalar` ja liga agora)
  python scripts/segunda-tela.py status                       mostra o que esta pronto
  (sem argumento: menu)

Conexao: cabo, se estiver ligado; senao a Tailscale pela porta 5555 do adb (adb-remoto.py), que vale no Wi-Fi e nos dados
moveis. TROCA SOZINHA no meio (12/11/2026): tirou o cabo = segue sem fio; ligou o cabo = passa a ele (adb-remoto.Espelho). --leve = 2 Mbit/s, 1024 px e 30 quadros (para dados moveis: cerca de 15 MB por minuto [Palpite: conta pelo limite]).
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
ADB_ESPERA = 20  # segundos: o adb pela Tailscale pode travar; a vigia nunca pode ficar presa num `wm size`
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
def _roda_escondido(*a, **k):
    """subprocess.run sem abrir janela: a tarefa Vigia-TV-Sem-Fio roda no pythonw (sem console) e cada adb abria
    uma janela do Terminal por cima de tudo (14/11/2026)."""
    if os.name == "nt":
        k.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    return subprocess.run(*a, **k)


_executa = _roda_escondido  # os testes trocam por um falso
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
                          "principal": bool(i.dwFlags & 1), "tv": "DEFAULT_MONITOR" in ids, "virtual": "MTT1337" in ids,
                          "monitores": j})   # 2 = modo DUPLICAR (o monitor do PC e a TV no mesmo DISPLAY)
        return True

    proc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)(cada)
    u.EnumDisplayMonitors(None, None, proc, 0)
    return lista


class _DEVMODE(ctypes.Structure):
    _fields_ = [("dmDeviceName", ctypes.c_wchar * 32), ("dmSpecVersion", ctypes.c_ushort), ("dmDriverVersion", ctypes.c_ushort),
                ("dmSize", ctypes.c_ushort), ("dmDriverExtra", ctypes.c_ushort), ("dmFields", ctypes.c_uint),
                ("dmPositionX", ctypes.c_long), ("dmPositionY", ctypes.c_long), ("dmDisplayOrientation", ctypes.c_uint),
                ("dmDisplayFixedOutput", ctypes.c_uint), ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
                ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short), ("dmCollate", ctypes.c_short),
                ("dmFormName", ctypes.c_wchar * 32), ("dmLogPixels", ctypes.c_ushort), ("dmBitsPerPel", ctypes.c_uint),
                ("dmPelsWidth", ctypes.c_uint), ("dmPelsHeight", ctypes.c_uint), ("dmDisplayFlags", ctypes.c_uint),
                ("dmDisplayFrequency", ctypes.c_uint), ("dmICMMethod", ctypes.c_uint), ("dmICMIntent", ctypes.c_uint),
                ("dmMediaType", ctypes.c_uint), ("dmDitherType", ctypes.c_uint), ("dmReserved1", ctypes.c_uint),
                ("dmReserved2", ctypes.c_uint), ("dmPanningWidth", ctypes.c_uint), ("dmPanningHeight", ctypes.c_uint)]


def modos_da_tela(nome):
    """[(largura, altura, Hz)] que a tela aceita, e o modo atual, pelo EnumDisplaySettingsW. ([], None) fora do Windows."""
    if os.name != "nt":
        return [], None
    u = ctypes.windll.user32
    d = _DEVMODE()
    d.dmSize = ctypes.sizeof(d)
    atual = None
    if u.EnumDisplaySettingsW(nome, -1, ctypes.byref(d)):
        atual = (d.dmPelsWidth, d.dmPelsHeight, d.dmDisplayFrequency)
    modos, i = set(), 0
    while u.EnumDisplaySettingsW(nome, i, ctypes.byref(d)):
        modos.add((d.dmPelsWidth, d.dmPelsHeight, d.dmDisplayFrequency))
        i += 1
    return sorted(modos, reverse=True), atual


def e_16x9(w, h):
    return bool(w and h) and abs(w / h - 16 / 9) < 0.02


def melhor_modo_16x9(modos):
    """O maior modo 16:9 com 50 Hz ou mais (a TV de verdade: 1920x1080@60); None se a tela nao tem nenhum."""
    bons = [(w, h, hz) for w, h, hz in modos if e_16x9(w, h) and hz >= 50]
    return max(bons, key=lambda m: (m[0] * m[1], m[2])) if bons else None


def mudar_resolucao(nome, w, h, hz):
    """Troca a resolucao da tela, gravando no registro (o Windows lembra para esta TV). True se trocou."""
    if os.name != "nt":
        return False
    u = ctypes.windll.user32
    d = _DEVMODE()
    d.dmSize = ctypes.sizeof(d)
    if not u.EnumDisplaySettingsW(nome, -1, ctypes.byref(d)):
        return False
    d.dmPelsWidth, d.dmPelsHeight, d.dmDisplayFrequency = w, h, hz
    d.dmFields = 0x80000 | 0x100000 | 0x400000       # DM_PELSWIDTH | DM_PELSHEIGHT | DM_DISPLAYFREQUENCY
    return u.ChangeDisplaySettingsExW(nome, ctypes.byref(d), None, 1, None) == 0   # CDS_UPDATEREGISTRY; 0 = DISP_CHANGE_SUCCESSFUL


def ajustar_tvs(lista=None):
    """A TV sem fio (Miracast) entra em 1024x768 (4:3) e fica com barras pretas numa TV 16:9 (achado de 12/11/2026).
    Para cada TV do Windows que nao esteja em 16:9, poe o melhor modo 16:9 que ela aceita. Devolve [(nome, de, para, ok)]."""
    feitos = []
    for m in (monitores() if lista is None else lista):
        if not m["tv"] or e_16x9(m["w"], m["h"]):
            continue
        modos, atual = modos_da_tela(m["nome"])
        melhor = melhor_modo_16x9(modos)
        if not melhor:
            print("TV %s em %dx%d (nao e' 16:9) e nao oferece modo 16:9: fica como esta." % (m["nome"], m["w"], m["h"]))
            continue
        ok = mudar_resolucao(m["nome"], *melhor)
        print("TV %s: %dx%d -> %dx%d@%d Hz %s" % (m["nome"], m["w"], m["h"], melhor[0], melhor[1], melhor[2],
                                                 "(ajustada, sem barras pretas)" if ok else "NAO deu para ajustar (faca em Configuracoes > Tela)"))
        feitos.append((m["nome"], (m["w"], m["h"]), melhor, ok))
    return feitos


def tv_duplicada(lista):
    """A TV sem fio esta em modo DUPLICAR? No clone, o Windows mostra UM monitor que carrega o monitor do PC e a TV
    (DEFAULT_MONITOR) ao mesmo tempo, na resolucao comum (1024x768): barras pretas nos dois (visto em 12/11/2026)."""
    return any(m["tv"] and m["principal"] and m.get("monitores", 2) >= 2 for m in lista)


def estender_telas():
    """Troca o modo de projecao do Windows para ESTENDER (cada tela com a resolucao dela)."""
    if os.name != "nt":
        return False
    exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "DisplaySwitch.exe")
    try:
        _executa([exe, "/extend"], timeout=20)
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


VIGIA_TV_LOG = AQUI.parent / "diagnostico" / "vigia-tv.log"
TAREFA_VIGIA_TV = "Vigia-TV-Sem-Fio"


def _anota(texto):
    try:
        VIGIA_TV_LOG.parent.mkdir(exist_ok=True)
        if VIGIA_TV_LOG.exists() and VIGIA_TV_LOG.stat().st_size > 200_000:
            VIGIA_TV_LOG.write_text("", encoding="utf-8")
        with VIGIA_TV_LOG.open("a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + texto + "\n")
    except OSError:
        pass
    print(texto)


def vigia_tv_uma_volta(lista=None):
    """Uma olhada do vigia. Devolve o que fez: [] se nada."""
    lista = monitores() if lista is None else lista
    feitos = []
    if tv_duplicada(lista):
        ok = estender_telas()
        _anota("TV sem fio em modo DUPLICAR (barras pretas no monitor e na TV): " + ("passei para ESTENDER" if ok else "nao consegui estender (DisplaySwitch)"))
        feitos.append(("estender", ok))
        time.sleep(6)   # o Windows reorganiza as telas; a proxima volta ajusta a TV
        return feitos
    for nome, de, para, ok in ajustar_tvs(lista):
        _anota("TV %s: %dx%d -> %dx%d@%d %s" % (nome, de[0], de[1], para[0], para[1], para[2], "ok" if ok else "FALHOU"))
        feitos.append((nome, ok))
    return feitos


def vigia_tv(intervalo=4, voltas=None):
    """O laco do vigia (tarefa do Windows no logon). Parado nao gasta: so o EnumDisplayMonitors a cada 4 s."""
    _anota("vigia da TV sem fio ligado (a cada %d s)" % intervalo)
    n = 0
    while voltas is None or n < voltas:
        try:
            vigia_tv_uma_volta()
        except Exception as falha:  # noqa: BLE001 - o vigia nunca morre por uma volta ruim
            _anota("volta falhou: %s" % falha)
        n += 1
        time.sleep(intervalo)
    return 0


def vigia_tv_instalar():
    """Tarefa do Windows no logon do usuario (sem administrador): pythonw, sem janela. Ja liga agora."""
    python = pathlib.Path(sys.executable).with_name("pythonw.exe")
    if not python.exists():
        python = pathlib.Path(sys.executable)
    comando = '"%s" "%s" vigia-tv' % (python, pathlib.Path(__file__).resolve())
    r = _executa(["schtasks", "/Create", "/F", "/SC", "ONLOGON", "/TN", TAREFA_VIGIA_TV, "/TR", comando],
                 capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print("Nao consegui criar a tarefa: " + (r.stderr or r.stdout).strip())
        return 1
    _executa(["schtasks", "/Run", "/TN", TAREFA_VIGIA_TV], capture_output=True, text=True, errors="replace")
    print("Vigia da TV sem fio instalado (tarefa %s, no logon) e ligado agora. Registro: %s" % (TAREFA_VIGIA_TV, VIGIA_TV_LOG))
    return 0


def vigia_tv_remover():
    _executa(["schtasks", "/End", "/TN", TAREFA_VIGIA_TV], capture_output=True, text=True, errors="replace")
    r = _executa(["schtasks", "/Delete", "/F", "/TN", TAREFA_VIGIA_TV], capture_output=True, text=True, errors="replace")
    print("Vigia da TV sem fio removido." if r.returncode == 0 else "Tarefa nao existia.")
    return 0


def vigia_tv_estado():
    r = _executa(["schtasks", "/Query", "/TN", TAREFA_VIGIA_TV, "/FO", "LIST"], capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print("Vigia da TV sem fio: NAO instalado (python scripts/segunda-tela.py vigia-tv instalar)")
    else:
        estado = next((l.split(":", 1)[1].strip() for l in r.stdout.splitlines() if l.strip().startswith(("Status", "Estado"))), "?")
        print("Vigia da TV sem fio: tarefa %s, estado %s" % (TAREFA_VIGIA_TV, estado))
    if VIGIA_TV_LOG.exists():
        linhas = VIGIA_TV_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-3:]
        for l in linhas:
            print("  " + l)
    return 0


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


def tamanho_forcado(serial):
    """O 'Override size' que o celular esta usando agora (ex.: '720x960'), ou None se a tela esta no tamanho fisico."""
    try:
        r = _executa(["adb", "-s", serial, "shell", "wm", "size"], capture_output=True, text=True, timeout=ADB_ESPERA)
    except (OSError, subprocess.TimeoutExpired):
        return None
    for linha in (r.stdout or "").splitlines():
        if linha.startswith("Override size:"):
            return linha.split(":")[1].strip()
    return None


def volta_tamanho(serial):
    """`wm size reset` CONFERIDO: a marca so sai se o celular voltou mesmo ao tamanho fisico. Devolve True se voltou.
    (12/11/2026: antes o resultado era ignorado e a marca sumia com a tela ainda encolhida.)"""
    try:
        _executa(["adb", "-s", serial, "shell", "wm", "size", "reset"], capture_output=True, text=True, timeout=ADB_ESPERA)
    except (OSError, subprocess.TimeoutExpired):
        pass
    sobrou = tamanho_forcado(serial)
    if sobrou:
        print("ATENCAO: a tela do celular continua forcada em %s. Confira o cabo ou a Tailscale e rode: "
              "python scripts/segunda-tela.py normal" % sobrou)
        return False
    try:
        MARCA.unlink()
    except FileNotFoundError:
        pass
    print("Tela do celular no tamanho normal (720x1600).")
    return True


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
        self.trava = threading.Lock()   # a vigia e o fim da sessao nunca mexem no celular ao mesmo tempo

    @property
    def fisico(self):
        if self._fisico is None:
            self._fisico = tamanho_fisico(self.serial)
        return self._fisico

    def aplica(self, alvo):
        with self.trava:   # a vigia e o fim da sessao nunca mexem no celular ao mesmo tempo
            if alvo == self.atual:
                return
            if alvo:
                MARCA.parent.mkdir(exist_ok=True)
                MARCA.write_text("%dx%d\n" % alvo)   # a marca ANTES do adb: se o PC cair no meio, a proxima abertura desfaz
                r = _executa(["adb", "-s", self.serial, "shell", "wm", "size", "%dx%d" % alvo], capture_output=True,
                             text=True, timeout=ADB_ESPERA)
                if r.returncode != 0:
                    print("Nao consegui mudar o tamanho da tela do celular (%s)." % (r.stderr or r.stdout or "").strip())
                    return
                print("Celular desenhando em %dx%d (a proporcao da tela): deitado, preenche sem faixas;" % alvo)
                print("no proprio celular aparecem faixas enquanto isso (volta ao fechar a janela).")
            elif not volta_tamanho(self.serial):
                return   # continua "trocado": o fim da sessao e a proxima abertura tentam de novo
            self.atual = alvo


def vigia(ajuste, parar, ja_cheia=False, redimensiona=True):
    """Enquanto a janela esta aberta: chegou na TV = tela cheia (uma vez por chegada) e, com redimensiona (o padrao;
    --so-espelho desliga), o celular passa ao formato da tela e volta ao normal em janela comum no monitor do PC."""
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
        if not redimensiona:
            continue
        try:
            ajuste.aplica(quer_tamanho(ajuste.fisico, local))
        except (OSError, subprocess.TimeoutExpired):
            pass  # adb caiu um instante: tenta de novo na proxima olhada


def _escolhe_conexao():
    """(serial, tipo) da melhor conexao agora, sem imprimir as tentativas: cabo, senao a Tailscale (Wi-Fi ou dados)."""
    import io
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        serial, _ = conecta()
    if not serial:
        return None, None
    return serial, ("cabo" if ":" not in serial else "sem fio")


def roda_scrcpy(args, serial, soltar, ao_fim=None, durante=None, ao_trocar=None):
    """Abre o scrcpy e o mantem vivo trocando de conexao sozinho (12/11/2026, pedido do Rafael): comecou no cabo e
    o cabo saiu = segue pelo Wi-Fi ou pelos dados moveis (Tailscale); comecou sem fio e o cabo entrou = passa ao cabo."""
    exe = scrcpy()
    if not exe:
        print("Falta o scrcpy no PC (winget install Genymobile.scrcpy).")
        if ao_fim:
            ao_fim()
        return 2
    r = remoto()
    if ":" not in serial:
        r.garantir_porta(serial)   # com o cabo: a 5555 aberta antes, para tirar o cabo sem parar
    print("Abrindo (feche a janela para terminar)... conexao: " + ("cabo" if ":" not in serial else "Tailscale " + serial))
    print("Tirar ou ligar o cabo no meio troca a conexao sozinho (Wi-Fi ou dados moveis pela Tailscale).")
    base = [a for a in args if a != "--stay-awake"]

    def montar(s, tipo):
        return [exe, "-s", s, *(["--stay-awake"] if tipo == "cabo" else []), *base]

    parar = threading.Event()
    t = None
    esp = None
    try:
        if durante:
            t = threading.Thread(target=durante, args=(parar,), daemon=True)
            t.start()
        esp = r.Espelho(_escolhe_conexao, montar, serial, "cabo" if ":" not in serial else "sem fio", ao_trocar=ao_trocar,
                        iniciar=_inicia, cabo=r.tem_cabo, presentes=r.aparelhos)
        esp.start()
        rc = esp.wait()
        if esp.trocas and ":" in esp.serial:
            soltar = True   # terminou no sem fio que a troca abriu: solta no fim, como quando comeca sem fio
        return rc
    finally:
        if esp is not None:
            esp.terminate()
        parar.set()
        if t:
            t.join(10)
        if ao_fim:
            ao_fim()  # antes de soltar a Tailscale: depois nao ha mais como falar com o celular
        if soltar:
            remoto().soltar()


def celular(leve, preencher=False, so_espelho=False):
    serial, soltar = conecta()
    if not serial:
        return 1
    args = ["--window-title=" + TITULO] + (["--stay-awake"] if ":" not in serial else [])
    if leve:
        args += ["--video-bit-rate=2M", "--max-size=1024", "--max-fps=30", "--no-audio"]
    if MARCA.exists() or tamanho_forcado(serial):  # sessao anterior fechada sem desfazer (janela no X, PC caiu, adb caiu)
        volta_tamanho(serial)
    ajustar_tvs()   # a TV sem fio em 4:3 (1024x768) vira 16:9 antes de qualquer conta de proporcao
    ajuste = Ajuste(serial)
    if preencher:
        mon = monitor_alvo(monitores())
        if mon:
            print("Tela cheia em %s (%dx%d%s)." % (mon["nome"], mon["w"], mon["h"], ", a TV" if mon["tv"] else ""))
            args += ["--fullscreen", "--window-x=%d" % (mon["x"] + 40), "--window-y=%d" % (mon["y"] + 40)]
            ajuste.aplica(forma_para(ajuste.fisico, mon["w"], mon["h"]))
    if so_espelho:
        print("So espelho: leve a janela para a TV (ou Alt+F) para tela cheia. A tela do celular nao muda (faixas na TV).")
    else:
        print("Automatico: na TV (ou Alt+F) a imagem preenche a tela: o celular desenha na proporcao dela e fica com faixas")
        print("pretas enquanto isso; em janela no monitor do PC, e ao fechar a janela, ele volta ao normal (conferido).")

    def ao_fim():
        if ajuste.atual:
            ajuste.aplica(None)

    def ao_trocar(novo, _tipo):
        ajuste.serial = novo   # o tamanho forcado fica no celular; so o caminho para falar com ele mudou
    return roda_scrcpy(args, serial, soltar, ao_fim, lambda parar: vigia(ajuste, parar, preencher, not so_espelho), ao_trocar)


def normal():
    """Confere a tela do celular e desfaz um tamanho forcado que tenha sobrado (janela fechada no X, PC ou adb caido)."""
    serial, soltar = conecta()
    if not serial:
        return 1
    try:
        return 0 if volta_tamanho(serial) else 1
    finally:
        if soltar:
            remoto().soltar()


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
    for mon in monitores():
        if mon["tv"]:
            print("TV sem fio %s: %dx%d%s%s" % (mon["nome"], mon["w"], mon["h"], " DUPLICADA com o monitor" if mon.get("monitores", 1) >= 2 and mon["principal"] else "",
                                                 "" if e_16x9(mon["w"], mon["h"]) else " (NAO e' 16:9: barras pretas; ajusta com: python scripts/segunda-tela.py tv)"))
    vigia_tv_estado()
    serial = next((s for s, e in lista.items() if e == "device"), None)
    if serial:
        forcado = tamanho_forcado(serial)
        print("tela do celular: " + ("FORCADA em %s (desfaz: python scripts/segunda-tela.py normal)" % forcado if forcado
                                     else "tamanho normal"))
    return 0


def menu():
    print("== Segunda tela ==")
    print(" 1  Ver e comandar o celular no PC (na TV sem fio: tela cheia e sem faixas)")
    print(" 2  Tela EXTRA do celular numa janela do PC")
    print(" 3  Celular como MONITOR EXTRA do PC")
    print(" 4  Igual ao 1, versao leve (dados moveis)")
    print(" 5  Parar o monitor extra (Sunshine)")
    print(" 6  Igual ao 1, PREENCHENDO a TV (sem faixas na TV; o CELULAR fica com faixas pretas ate fechar)")
    print(" 7  Conferir a tela do celular e desfazer um tamanho forcado que tenha sobrado")
    print(" 8  Igual ao 1, mas SEM mexer na tela do celular (na TV ficam faixas dos lados)")
    print(" 9  Ajustar a TV sem fio do Windows para 16:9 (sem barras pretas)")
    print("10  Instalar o VIGIA da TV sem fio (ajusta sozinho toda vez que conectar)")
    print(" 0  Sair")
    try:
        op = input("Escolha: ").strip()
    except EOFError:
        return 0
    return {"1": lambda: celular(False), "2": lambda: extra(escolhe_app(), False), "3": pc, "4": lambda: celular(True),
            "5": pc_parar, "6": lambda: celular(False, True), "7": normal,
            "8": lambda: celular(False, False, True), "9": tv, "10": vigia_tv_instalar}.get(op, lambda: 0)()


def tv():
    """Ajusta a TV sem fio do Windows para 16:9 e mostra como ficou."""
    feitos = ajustar_tvs()
    tvs = [m for m in monitores() if m["tv"]]
    if not tvs:
        print("Nenhuma TV sem fio conectada ao Windows agora (Win+K para conectar).")
        return 1
    if not feitos:
        print("TV sem fio ja em 16:9: " + ", ".join("%s %dx%d" % (m["nome"], m["w"], m["h"]) for m in tvs))
    return 0 if all(ok for *_, ok in feitos) else 1


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
        return celular(leve, "--preencher" in args, "--so-espelho" in args)
    if cmd == "normal":
        return normal()
    if cmd == "tv":
        return tv()
    if cmd == "vigia-tv":
        acao = args[1] if len(args) > 1 else ""
        return {"instalar": vigia_tv_instalar, "remover": vigia_tv_remover, "estado": vigia_tv_estado}.get(acao, vigia_tv)()
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
