#!/usr/bin/env python3
"""Segunda tela entre o PC e o A12 (pedido do Rafael, 05/11/2026), com cabo, Wi-Fi ou dados moveis.

  python scripts/segunda-tela.py celular [--leve]             o PC mostra e comanda a tela do celular (scrcpy)
  python scripts/segunda-tela.py extra [--app PACOTE] [--leve] o celular ganha uma TELA EXTRA, que aparece numa janela
                                                              do PC (scrcpy --new-display; padrao: navegador Fennec)
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

AQUI = pathlib.Path(__file__).resolve().parent
APP_PADRAO = "org.mozilla.fennec_fdroid"
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


def roda_scrcpy(args, serial, soltar):
    exe = scrcpy()
    if not exe:
        print("Falta o scrcpy no PC (winget install Genymobile.scrcpy).")
        return 2
    print("Abrindo (feche a janela para terminar)... conexao: " + ("cabo" if ":" not in serial else "Tailscale " + serial))
    try:
        return _executa([exe, "-s", serial, *args]).returncode
    finally:
        if soltar:
            remoto().soltar()


def celular(leve):
    serial, soltar = conecta()
    if not serial:
        return 1
    args = ["--window-title=Celular (A12)"] + (["--stay-awake"] if ":" not in serial else [])
    if leve:
        args += ["--video-bit-rate=2M", "--max-size=1024", "--max-fps=30", "--no-audio"]
    return roda_scrcpy(args, serial, soltar)


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
    print("Sunshine ligado no PC. No celular: abra o Moonlight, toque no PC (ou + e digite " + PC_IP + ") e escolha Desktop.")
    print("Primeira vez: o Moonlight mostra um PIN; digite-o em https://localhost:47990 > PIN (no PC).")
    print("Para ESTENDER a area de trabalho (e nao so espelhar): Windows > Configuracoes > Sistema > Tela > Estender estes video.")
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
    print(" 0  Sair")
    try:
        op = input("Escolha: ").strip()
    except EOFError:
        return 0
    return {"1": lambda: celular(False), "2": lambda: extra(None, False), "3": pc, "4": lambda: celular(True),
            "5": pc_parar}.get(op, lambda: 0)()


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
        return celular(leve)
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
