#!/usr/bin/env python3
"""Papel de parede rolante no A12 (pedido do Rafael, 05/11/2026), como nos Samsung antigos.

  python scripts/papel-rolante.py status                 mostra se esta ativo, a imagem e o deslocamento
  python scripts/papel-rolante.py aplicar [--imagem ARQ] [--paginas N]
                                                         instala o app (16 KB), manda a imagem e ativa; tudo sozinho
  python scripts/papel-rolante.py desfazer               volta ao papel de parede comum da Samsung
  python scripts/papel-rolante.py desloc                 so rele o deslocamento da tela inicial e entrega ao app
  python scripts/papel-rolante.py sincronia ligar|desligar|status
                                                         o papel segue a pagina EXATA da tela inicial (acessibilidade do
                                                         proprio app: so o aviso de rolagem da tela inicial, sem ler telas)

Em pe, a imagem larga ocupa a altura da tela e anda para o lado quando o dedo arrasta na tela inicial
(N "paginas" que encaixam; padrao 4). Deitado, a imagem aparece inteira, sem corte, com fundo desfocado nas bordas.

Por que um app proprio: a tela inicial da Samsung nao informa a rolagem ao papel de parede (medido em 05/11:
mLastWallpaperX fica em 0.5) e empurra o papel 321 px para cima (mLastWallpaperDisplayOffsetY=-321); o app
(scripts/celular-kit/papel, `compilar.ps1`) usa o toque e o deslocamento que este script le no dumpsys.
Imagem padrao: C:\\Users\\passo\\Pictures\\Papel-de-parede\\celular-2844x1600.png. Imagem estreita (em pe) nao rola: so preenche.
Tudo reversivel: `desfazer` volta ao papel comum (a imagem dele continua guardada pelo sistema).
"""
import argparse
import hashlib
import pathlib
import re
import subprocess
import sys
import tempfile

PACOTE = "br.embeeded.papel"
COMPONENTE = PACOTE + "/" + PACOTE + ".Papel"
PASTA = "/sdcard/Android/data/" + PACOTE + "/files"
APK = pathlib.Path(__file__).resolve().parent.parent / "diagnostico" / "papel.apk"  # fora do git (o sync recusa .apk)
COMPILAR = pathlib.Path(__file__).resolve().parent / "celular-kit" / "papel" / "compilar.ps1"
IMAGEM_PADRAO = pathlib.Path.home() / "Pictures" / "Papel-de-parede" / "celular-2844x1600.png"
ALTURA_MAX = 1600
_executa = subprocess.run  # os testes trocam por um falso


def adb(*args, limite=60):
    try:
        p = _executa(["adb", *args], capture_output=True, text=True, timeout=limite)
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def sh(comando, limite=60):
    return adb("shell", comando, limite=limite)


def no_cabo():
    rc, saida = adb("get-state")
    return rc == 0 and saida.strip() == "device"


def componente_atual():
    _, s = sh("dumpsys wallpaper | grep -m1 mWallpaperComponent")
    m = re.search(r"ComponentInfo\{([^}]+)\}", s)
    return m.group(1) if m else ""


def deslocamento():
    """(X, Y) que a tela inicial aplica ao papel; (0, 0) se nao houver."""
    _, s = sh("dumpsys window | grep -m1 mLastWallpaperDisplayOffset")
    m = re.search(r"OffsetX=(-?\d+)\s+\w*OffsetY=(-?\d+)", s)
    if not m:
        return 0, 0
    x, y = int(m.group(1)), int(m.group(2))
    limpa = lambda v: 0 if abs(v) > 2000 else v  # Integer.MIN_VALUE = sem valor
    return limpa(x), limpa(y)


def apk_instalado_sha():
    _, s = sh("pm path " + PACOTE)
    m = re.search(r"package:(\S+)", s)
    if not m:
        return None
    _, h = sh("sha256sum " + m.group(1))
    m2 = re.match(r"([0-9a-f]{64})", h.strip())
    return m2.group(1) if m2 else "?"


def instala():
    local = hashlib.sha256(APK.read_bytes()).hexdigest()
    if apk_instalado_sha() == local:
        return True, "app ja instalado (mesma versao)"
    rc, s = adb("install", "-r", str(APK), limite=180)
    if rc != 0 or "Success" not in s:
        if "INCOMPATIBLE" in s or "signatures do not match" in s.lower():
            adb("uninstall", PACOTE)
            rc, s = adb("install", str(APK), limite=180)
    ok = rc == 0 and "Success" in s
    return ok, ("app instalado" if ok else "falhou ao instalar: " + s[-200:])


def prepara_imagem(origem, destino):
    """JPEG com no maximo 1600 px de altura (a tela do A12); devolve (largura, altura)."""
    from PIL import Image

    with Image.open(origem) as im:
        im = im.convert("RGB")
        if im.height > ALTURA_MAX:
            im = im.resize((round(im.width * ALTURA_MAX / im.height), ALTURA_MAX), Image.LANCZOS)
        im.save(destino, "JPEG", quality=92, optimize=True)
        return im.size


def grava_desloc():
    x, y = deslocamento()
    sh("mkdir -p " + PASTA + " && echo '%d %d' > %s/desloc.txt" % (x, y, PASTA))
    return x, y


def ativa(acao="ativar"):
    rc, s = sh("CLASSPATH=$(pm path " + PACOTE + " | cut -d: -f2) app_process / " + PACOTE + ".Definir " + acao)
    return rc == 0 and s.strip().startswith("OK"), s.strip()


def status():
    comp = componente_atual()
    ativo = comp == COMPONENTE
    _, img = sh("ls -l " + PASTA + "/papel.jpg 2>/dev/null")
    _, desl = sh("cat " + PASTA + "/desloc.txt 2>/dev/null")
    _, pag = sh("cat " + PASTA + "/paginas.txt 2>/dev/null")
    print("Papel rolante: " + ("ATIVO" if ativo else "inativo (papel atual: " + (comp or "?") + ")"))
    print("  imagem no celular: " + ("sim" if "papel.jpg" in img else "nao"))
    print("  deslocamento da tela inicial agora: %d %d (entregue ao app: %s)" % (*deslocamento(), desl.strip() or "nada"))
    print("  paginas: " + (pag.strip() or "4 (padrao)"))
    return 0 if ativo else 1


def aplicar(imagem, paginas):
    origem = pathlib.Path(imagem) if imagem else IMAGEM_PADRAO
    if not origem.is_file():
        print("Imagem nao encontrada: " + str(origem))
        return 2
    if not APK.is_file():
        print("0/4 compilando o app (primeira vez neste PC)...")
        try:
            _executa(["pwsh", "-NoProfile", "-File", str(COMPILAR)], capture_output=True, text=True, timeout=600)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if not APK.is_file():
            print("Falta o app compilado e a compilacao falhou: rode " + str(COMPILAR))
            return 2
    ok, msg = instala()
    print("1/4 " + msg)
    if not ok:
        return 1
    with tempfile.TemporaryDirectory() as t:
        jpg = pathlib.Path(t) / "papel.jpg"
        w, h = prepara_imagem(origem, jpg)
        sh("mkdir -p " + PASTA)
        rc, s = adb("push", str(jpg), PASTA + "/papel.jpg", limite=120)
        if rc != 0:
            print("falhou ao mandar a imagem: " + s[-200:])
            return 1
    aviso = "" if w * 1600 > h * 720 * 1.2 else " (imagem estreita: em pe ela so preenche, nao rola)"
    print("2/4 imagem %dx%d enviada%s" % (w, h, aviso))
    if paginas is not None:
        sh("echo %d > %s/paginas.txt" % (max(2, min(9, int(paginas))), PASTA))
    x, y = grava_desloc()
    print("3/4 deslocamento da tela inicial: %d %d" % (x, y))
    ok, s = ativa("ativar")
    comp = componente_atual()
    if not ok or comp != COMPONENTE:
        print("4/4 FALHOU ao ativar (" + s[-160:] + "); papel atual: " + comp)
        return 1
    print("4/4 papel rolante ATIVO. Desfazer: python scripts\\papel-rolante.py desfazer")
    # Tela de bloqueio: sem foto propria ela mostra o mesmo papel (a foto antiga continua na Galeria).
    okb, _ = ativa("bloqueio")
    print("    tela de bloqueio: " + ("o mesmo papel" if okb else "nao confirmado (a Samsung pode manter a foto dela)"))
    return 0


def desfazer():
    ok, s = ativa("desfazer")
    comp = componente_atual()
    voltou = comp != COMPONENTE
    print(("Papel comum de volta (" + comp + ")") if voltou else ("Nao voltou: " + s[-160:]))
    return 0 if voltou else 1


SINCRONIA = PACOTE + "/" + PACOTE + ".Sincronia"


def sincronia(acao):
    """Liga/desliga o servico de acessibilidade que faz o papel seguir a pagina exata da tela inicial.
    Mexe so no proprio item da lista enabled_accessibility_services; os outros servicos ficam como estao."""
    _, atual = sh("settings get secure enabled_accessibility_services")
    lista = [s for s in atual.strip().split(":") if s and s != "null"]
    tem = SINCRONIA in lista
    if acao == "ligar" and not tem:
        lista.append(SINCRONIA)
    elif acao == "desligar" and tem:
        lista = [s for s in lista if s != SINCRONIA]
    if acao in ("ligar", "desligar") and (SINCRONIA in lista) != tem:
        if lista:
            sh("settings put secure enabled_accessibility_services '" + ":".join(lista) + "'")
            sh("settings put secure accessibility_enabled 1")
        else:
            sh("settings delete secure enabled_accessibility_services")
    _, depois = sh("settings get secure enabled_accessibility_services")
    ligada = SINCRONIA in depois
    print("Seguir as paginas da tela inicial: " + ("LIGADO" if ligada else "desligado"))
    if acao == "ligar":
        return 0 if ligada else 1
    if acao == "desligar":
        return 0 if not ligada else 1
    return 0 if ligada else 1


def main(args):
    p = argparse.ArgumentParser(description="Papel de parede rolante no A12")
    p.add_argument("comando", nargs="?", default="status", choices=["status", "aplicar", "desfazer", "desloc", "sincronia"])
    p.add_argument("acao", nargs="?", default="status", choices=["ligar", "desligar", "status"])
    p.add_argument("--imagem")
    p.add_argument("--paginas", type=int)
    a = p.parse_args(args)
    if not no_cabo():
        print("O celular nao esta no cabo (adb).")
        return 2
    if a.comando == "status":
        return status()
    if a.comando == "aplicar":
        return aplicar(a.imagem, a.paginas)
    if a.comando == "desfazer":
        return desfazer()
    if a.comando == "sincronia":
        return sincronia(a.acao)
    print("deslocamento entregue: %d %d" % grava_desloc())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
