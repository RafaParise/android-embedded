#!/usr/bin/env python3
"""Olhos e mão no A12 com a TELA ESCURA (tela-apagada.py), pela depuração sem fio (14/11/2026).

Pedido do Rafael: "desligar a tela mas ainda continue em depuração Wi-Fi e que você ainda possa ver, mexer, operar".
Com a camada preta do tela-apagada.py a captura da tela sai preta (medido: 6 KB contra 561 KB), mas a árvore de
elementos do Android (uiautomator) continua inteira e o toque passa por baixo da camada. Então:

  python scripts/olhar-a12.py olhar                 o app em primeiro plano e os botões/textos visíveis, com posição
  python scripts/olhar-a12.py tocar "Favoritos"     toca no primeiro elemento cujo texto ou descrição contém isso
  python scripts/olhar-a12.py tocar 360 800         toca nas coordenadas
  python scripts/olhar-a12.py voltar | inicio       teclas Voltar e Início (nunca a de energia: ela bloqueia)
  python scripts/olhar-a12.py foto [arquivo.png]    a foto de verdade: acende, captura e escurece de novo (se estava escura)

Nada aqui usa keyevent 26 nem 223 (bloqueiam; regra de memoria/TELA-APAGADA.md). Textos de outros apps podem mostrar
conta ou contato: o que esta ferramenta imprime fica só no terminal, nunca em arquivo nem em memória.
"""
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

SERIE = os.environ.get("A12_SERIE", "192.168.1.4:5555")
AQUI = Path(__file__).resolve().parent
SEM_JANELA = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def adb(*args, texto=True, espera=30):
    r = subprocess.run(["adb", "-s", SERIE, *args], capture_output=True, text=texto, timeout=espera, **SEM_JANELA,
                       **({"encoding": "utf-8", "errors": "replace"} if texto else {}))
    return r.stdout


def elementos():
    """[(rótulo, x, y, clicável)] dos elementos visíveis, na ordem da tela; e o app em primeiro plano."""
    adb("shell", "uiautomator dump /data/local/tmp/olhar.xml >/dev/null 2>&1")
    bruto = adb("shell", "cat /data/local/tmp/olhar.xml")
    app = re.search(r"(?:mResumedActivity|topResumedActivity).*? ([\w.]+/[\w.$]+)",
                    adb("shell", "dumpsys activity activities | grep -m1 -E 'mResumedActivity|topResumedActivity'"))
    achados = []
    try:
        # Risco aceito (revisão automática de 14/11/2026 pediu defusedxml): o XML vem do próprio A12, pelo adb, e o
        # ElementTree do Python não busca entidade externa; defusedxml não é da biblioteca padrão.
        raiz = ET.fromstring(bruto[bruto.find("<?xml"):] if "<?xml" in bruto else bruto)
    except ET.ParseError:
        return [], app.group(1) if app else "?"
    for no in raiz.iter("node"):
        rotulo = (no.get("text") or "").strip() or (no.get("content-desc") or "").strip()
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", no.get("bounds", ""))
        if not rotulo or not m:
            continue
        x1, y1, x2, y2 = map(int, m.groups())
        if x2 <= x1 or y2 <= y1:
            continue
        achados.append((rotulo, (x1 + x2) // 2, (y1 + y2) // 2, no.get("clickable") == "true"))
    return achados, app.group(1) if app else "?"


def olhar():
    lista, app = elementos()
    print("Em primeiro plano: %s; %d elementos com texto" % (app, len(lista)))
    for rotulo, x, y, clicavel in lista[:80]:
        print("  %s %-60s (%d, %d)" % ("▸" if clicavel else " ", rotulo[:60].replace("\n", " "), x, y))
    return 0


def tocar(alvo):
    if len(alvo) == 2 and all(a.isdigit() for a in alvo):
        adb("shell", "input tap %s %s" % tuple(alvo))
        print("Toquei em (%s, %s)." % tuple(alvo))
        return 0
    procura = " ".join(alvo).lower()
    lista, _app = elementos()
    for rotulo, x, y, _clicavel in lista:
        if procura in rotulo.lower():
            adb("shell", "input tap %d %d" % (x, y))
            print("Toquei em \"%s\" (%d, %d)." % (rotulo[:60], x, y))
            return 0
    print("Não achei \"%s\" na tela. Rode 'olhar' para ver o que há." % procura)
    return 1


def foto(destino):
    escura = adb("shell", "dumpsys SurfaceFlinger 2>/dev/null | grep -c tela-preta").strip() not in ("", "0")
    tela = [sys.executable, str(AQUI / "tela-apagada.py")]
    if escura:
        subprocess.run(tela + ["acender"], capture_output=True, timeout=60, **SEM_JANELA)
    try:
        dados = adb("exec-out", "screencap", "-p", texto=False)
    finally:
        if escura:
            subprocess.run(tela + ["apagar"], capture_output=True, timeout=60, **SEM_JANELA)
    destino = Path(destino or os.path.join(tempfile.gettempdir(), "a12-foto.png"))
    destino.write_bytes(dados)
    print("Foto em %s (%d KB)%s." % (destino, len(dados) // 1024, "; a tela voltou a escurecer" if escura else ""))
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    acao, resto = argv[0], argv[1:]
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if acao == "olhar":
        return olhar()
    if acao == "tocar" and resto:
        return tocar(resto)
    if acao in ("voltar", "inicio"):
        adb("shell", "input keyevent %d" % (4 if acao == "voltar" else 3))
        return 0
    if acao == "foto":
        return foto(resto[0] if resto else None)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
