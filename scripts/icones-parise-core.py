#!/usr/bin/env python3
"""Icones estilo parise-core (pedido do Rafael, 05/11/2026): todos os apps do A12 em pixel, verde puro sobre preto.

  python scripts/icones-parise-core.py exportar   o celular desenha o icone de cada app (app do papel rolante) e o PC copia
  python scripts/icones-parise-core.py gerar      faz a versao parise-core de cada um + uma folha de amostra (amostra.png)
  python scripts/icones-parise-core.py celular    manda os icones parise-core para Pictures/Icones-parise-core no celular
  python scripts/icones-parise-core.py tudo       os tres

Pasta: diagnostico/icones-parise-core/ (fora do git: os originais sao arte de terceiros).
Cores: so preto #000000, verde puro #00FF41, cinza #909090 e branco #FFFFFF (sem verde escuro: pedido do Rafael).
Como aplicar: a tela inicial da Samsung NAO aceita pacote de icones de terceiros [Provavel]; caminhos possiveis em
memoria/PLANO-PARISE-CORE.md (Theme Park do Good Lock, que pede conta Samsung, ou um launcher com pacote de icones).
"""
import pathlib
import subprocess
import sys
import time

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PASTA = RAIZ / "diagnostico" / "icones-parise-core"
ORIG, PARISE_CORE = PASTA / "originais", PASTA / "parise-core"
NO_CELULAR = "/sdcard/Android/data/br.embeeded.papel/files/icones"
DESTINO_CELULAR = "/sdcard/Pictures/Icones-parise-core"
PRETO, VERDE, CINZA, BRANCO = (0, 0, 0, 255), (0, 255, 65, 255), (144, 144, 144, 255), (255, 255, 255, 255)
GRADE, MIOLO, ESCALA = 32, 22, 6  # 32x32 pixels "grandes"; o desenho ocupa 22x22 no meio; 32*6 = 192 px
_executa = subprocess.run


def adb(*a, limite=120):
    p = _executa(["adb", *a], capture_output=True, text=True, timeout=limite)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def exportar():
    adb("shell", "rm -r " + NO_CELULAR + " 2>/dev/null; true")
    rc, s = adb("shell", "am broadcast -n br.embeeded.papel/.Icones")
    if rc != 0:
        print("Falhou o pedido ao celular: " + s[-200:])
        return 1
    for _ in range(30):
        time.sleep(1)
        rc, s = adb("shell", "ls " + NO_CELULAR + "/indice.tsv 2>/dev/null")
        if "indice.tsv" in s:
            break
    else:
        print("O celular nao terminou os icones em 30 s.")
        return 1
    ORIG.mkdir(parents=True, exist_ok=True)
    rc, s = adb("pull", NO_CELULAR + "/.", str(ORIG), limite=300)
    n = len(list(ORIG.glob("*.png")))
    print(f"{n} icones copiados do celular para {ORIG}")
    return 0 if n else 1


def fundo_da_borda(im):
    """Cor de fundo do icone = a mais comum num anel um pouco para dentro da borda (os icones da Samsung tem fundo
    arredondado com os cantos transparentes); None se o anel for transparente (icone recortado, sem fundo)."""
    w, h = im.size
    m1, m2 = int(w * 0.09), w - 1 - int(w * 0.09)
    borda = [im.getpixel((x, y)) for x in range(m1, m2 + 1) for y in (m1, m2)] + \
            [im.getpixel((x, y)) for y in range(m1, m2 + 1) for x in (m1, m2)]
    opacos = [p for p in borda if p[3] > 200]
    if len(opacos) < len(borda) * 0.6:
        return None
    contagem = {}
    for p in opacos:
        k = (p[0] // 24, p[1] // 24, p[2] // 24)
        contagem[k] = contagem.get(k, 0) + 1
    k = max(contagem, key=contagem.get)
    return tuple(min(255, v * 24 + 12) for v in k)


def parise_core(origem):
    """Um icone -> versao parise-core: o que difere do fundo vira verde; fino demais vira cinza; o resto, preto."""
    from PIL import Image

    im = Image.open(origem).convert("RGBA")
    fundo = fundo_da_borda(im)
    if fundo:  # icone de fundo cheio (o fundo some): olha so o miolo, onde fica o desenho
        m = int(im.size[0] * 0.16)
        im = im.crop((m, m, im.size[0] - m, im.size[1] - m))
    peq = im.resize((MIOLO, MIOLO), Image.BOX)
    saida = Image.new("RGBA", (GRADE, GRADE), PRETO)
    o = (GRADE - MIOLO) // 2
    for y in range(MIOLO):
        for x in range(MIOLO):
            r, g, b, a = peq.getpixel((x, y))
            if a < 90:
                continue
            if fundo:
                d = (abs(r - fundo[0]) + abs(g - fundo[1]) + abs(b - fundo[2])) / 765
                cor = VERDE if d > 0.18 else (CINZA if d > 0.09 else None)
            else:
                lum = (0.3 * r + 0.59 * g + 0.11 * b) / 255
                cor = VERDE if a > 170 else CINZA
                if lum > 0.92 and a > 170:
                    cor = BRANCO
            if cor:
                saida.putpixel((o + x, o + y), cor)
    # moldura de terminal: cinza com cantos cortados (pixel), e o cursor "_" verde no canto de baixo
    for i in range(2, GRADE - 2):
        for x, y in ((i, 0), (i, GRADE - 1), (0, i), (GRADE - 1, i)):
            saida.putpixel((x, y), CINZA)
    for x, y in ((1, 1), (GRADE - 2, 1), (1, GRADE - 2), (GRADE - 2, GRADE - 2)):
        saida.putpixel((x, y), CINZA)
    for x in range(GRADE - 6, GRADE - 3):
        saida.putpixel((x, GRADE - 3), VERDE)
    return saida.resize((GRADE * ESCALA, GRADE * ESCALA), Image.NEAREST)


def gerar():
    from PIL import Image

    arquivos = sorted(ORIG.glob("*.png"))
    if not arquivos:
        print("Sem originais: rode antes  python scripts\\icones-parise-core.py exportar")
        return 1
    PARISE_CORE.mkdir(parents=True, exist_ok=True)
    feitos = []
    for a in arquivos:
        m = parise_core(a)
        m.save(PARISE_CORE / a.name)
        feitos.append(m)
    col = 10
    lin = (len(feitos) + col - 1) // col
    folha = Image.new("RGBA", (col * 100, lin * 100), PRETO)
    for i, m in enumerate(feitos):
        folha.paste(m.resize((96, 96), Image.NEAREST), ((i % col) * 100 + 2, (i // col) * 100 + 2))
    folha.save(PASTA / "amostra.png")
    print(f"{len(feitos)} icones parise-core em {PARISE_CORE}; amostra: {PASTA / 'amostra.png'}")
    return 0


def celular():
    arquivos = sorted(PARISE_CORE.glob("*.png"))
    if not arquivos:
        print("Sem icones parise-core: rode antes  gerar")
        return 1
    adb("shell", "mkdir -p " + DESTINO_CELULAR)
    rc, s = adb("push", str(PARISE_CORE) + "/.", DESTINO_CELULAR, limite=300)
    print(f"{len(arquivos)} icones em {DESTINO_CELULAR} no celular" if rc == 0 else "falhou: " + s[-200:])
    return rc


def pacote():
    """Pacote de icones no formato ADW/Nova (appfilter.xml + PNG), que Lawnchair, Nova, Neo e outros launchers aceitam.
    Monta com as ferramentas oficiais ja baixadas (compilar.ps1 do papel) e assina com a mesma chave local."""
    import json
    import re
    import shutil
    sdk = pathlib.Path(r"C:\Projetos\ferramentas\android-sdk")
    dex = pathlib.Path(r"C:\Projetos\ferramentas\compilar-dex")
    aapt2, zipalign = sdk / "bt" / "android-14" / "aapt2.exe", sdk / "bt" / "android-14" / "zipalign.exe"
    apksigner, android_jar = sdk / "bt" / "android-14" / "lib" / "apksigner.jar", sdk / "plat" / "android-12" / "android.jar"
    java, chave, senha = dex / "jdk" / "bin" / "java.exe", sdk / "chave-papel.jks", sdk / "chave-papel.senha"
    for f in (aapt2, zipalign, apksigner, android_jar, java, chave, senha):
        if not f.exists():
            print("Falta " + str(f) + " (rode antes scripts\\celular-kit\\papel\\compilar.ps1)")
            return 2
    indice = ORIG / "indice.tsv"
    if not indice.exists() or not list(PARISE_CORE.glob("*.png")):
        print("Rode antes: exportar e gerar")
        return 1
    obra = PASTA / "pacote"
    if obra.exists():
        shutil.rmtree(obra)
    (obra / "res" / "drawable-nodpi").mkdir(parents=True)
    (obra / "res" / "xml").mkdir(parents=True)
    itens = []
    for linha in indice.read_text(encoding="utf-8").splitlines():
        partes = linha.split("\t")
        if len(partes) < 2 or not (PARISE_CORE / partes[1]).exists():
            continue
        comp, arq = partes[0], partes[1]
        nome = "m_" + re.sub(r"[^a-z0-9_]", "_", comp.lower())[:90]
        shutil.copyfile(PARISE_CORE / arq, obra / "res" / "drawable-nodpi" / (nome + ".png"))
        pacote_, atividade = comp.split("/", 1)
        itens.append((f"ComponentInfo{{{pacote_}/{atividade}}}", nome))
    filtro = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<resources>\n" + "".join(
        f"    <item component=\"{c}\" drawable=\"{d}\" />\n" for c, d in itens) + "</resources>\n"
    (obra / "res" / "xml" / "appfilter.xml").write_text(filtro, encoding="utf-8")
    (obra / "assets").mkdir()
    (obra / "assets" / "appfilter.xml").write_text(filtro, encoding="utf-8")
    acoes = ["org.adw.launcher.THEMES", "com.novalauncher.THEME", "com.gau.go.launcherex.theme", "com.fede.launcher.THEME_ICONPACK",
             "com.anddoes.launcher.THEME", "com.teslacoilsw.launcher.THEME", "org.adw.launcher.icons.ACTION_PICK_ICON"]
    filtros = "".join(f"            <intent-filter><action android:name=\"{a}\" /><category android:name=\"android.intent.category.DEFAULT\" /></intent-filter>\n" for a in acoes)
    (obra / "AndroidManifest.xml").write_text(f"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="br.embeeded.icones">
    <application android:label="Icones parise-core" android:icon="@drawable/{itens[0][1]}" android:hasCode="false" android:allowBackup="false">
        <activity android:name="android.app.Activity" android:exported="true">
{filtros}        </activity>
    </application>
</manifest>
""", encoding="utf-8")
    def roda(cmd):
        p = _executa([str(c) for c in cmd], capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            raise SystemExit("falhou: " + " ".join(map(str, cmd[:2])) + "\n" + (p.stdout or "") + (p.stderr or ""))
    roda([aapt2, "compile", "--dir", obra / "res", "-o", obra / "res.zip"])
    roda([aapt2, "link", "-o", obra / "cru.apk", "-I", android_jar, "--manifest", obra / "AndroidManifest.xml", "-A", obra / "assets",
          "--min-sdk-version", "26", "--target-sdk-version", "31", "--version-code", "1", "--version-name", "1.0", obra / "res.zip"])
    roda([zipalign, "-f", "4", obra / "cru.apk", obra / "alinhado.apk"])
    saida = PASTA / "icones-parise-core.apk"
    roda([java, "-jar", apksigner, "sign", "--ks", chave, "--ks-key-alias", "papel", "--ks-pass", "file:" + str(senha), "--out", saida, obra / "alinhado.apk"])
    print(f"Pacote de icones: {saida} ({saida.stat().st_size // 1024} KB, {len(itens)} apps). Instalar: adb install -r \"{saida}\"")
    (PASTA / "pacote.json").write_text(json.dumps({"apps": len(itens)}), encoding="utf-8")
    return 0


def main(args):
    cmd = args[0] if args else ""
    if cmd == "pacote":
        return pacote()
    if cmd == "exportar":
        return exportar()
    if cmd == "gerar":
        return gerar()
    if cmd == "celular":
        return celular()
    if cmd == "tudo":
        return exportar() or gerar() or celular()
    print(__doc__.strip())
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
