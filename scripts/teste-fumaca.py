#!/usr/bin/env python3
"""Teste de fumaca do Galaxy A12 pelo ADB. Abre os apps que importam (pula os desativados ou ausentes), confere o primeiro
plano e se algum processo caiu; abre paginas das Configuracoes (onde o UAD-ng avisa que pode cair) e mostra qual app
responde a camera, mapa e imagem. Nao altera configuracoes: so abre apps e volta para a tela inicial. Efeitos colaterais: apaga o logcat
(logcat -c) antes de cada app e de cada pagina, e --tempos fecha os apps medidos (am force-stop).

  python scripts/teste-fumaca.py            tudo
  python scripts/teste-fumaca.py --tempos   alem disso mede a abertura a frio (am start -W, mediana de 3)
"""
import argparse
import re
import statistics
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

L = "-c android.intent.category.LAUNCHER 1"
# (nome, trecho esperado no app em primeiro plano, comando que abre, pacote que precisa estar ativo)
APPS = [
    ("Telefone", "fossify.phone", "am start -a android.intent.action.DIAL", "org.fossify.phone"),
    ("Camera Samsung", "camera", "am start -a android.media.action.STILL_IMAGE_CAMERA", "com.sec.android.app.camera"),
    ("Configuracoes", "settings", "am start -a android.settings.SETTINGS", "com.android.settings"),
    ("Gov.br", "br.gov.meugovbr", f"monkey -p br.gov.meugovbr {L}", "br.gov.meugovbr"),
    ("SED", "br.gov.sp.educacao.sed.android", f"monkey -p br.gov.sp.educacao.sed.android {L}", "br.gov.sp.educacao.sed.android"),
    ("Sala do Futuro Prof.", "saladofuturo.professores", f"monkey -p br.gov.sp.educacao.saladofuturo.professores {L}",
     "br.gov.sp.educacao.saladofuturo.professores"),
    ("ARENA", "io.github.rafaparise.arena", f"monkey -p io.github.rafaparise.arena {L}", "io.github.rafaparise.arena"),
    ("Termux", "com.termux", f"monkey -p com.termux {L}", "com.termux"),
    ("Open Camera", "opencamera", f"monkey -p net.sourceforge.opencamera {L}", "net.sourceforge.opencamera"),
    ("Organic Maps", "organicmaps", f"monkey -p app.organicmaps {L}", "app.organicmaps"),
    ("Fossify Gallery", "fossify.gallery", f"monkey -p org.fossify.gallery {L}", "org.fossify.gallery"),
    ("Fossify Arquivos", "fossify.filemanager", f"monkey -p org.fossify.filemanager {L}", "org.fossify.filemanager"),
    ("VLC", "videolan", f"monkey -p org.videolan.vlc {L}", "org.videolan.vlc"),
    ("MJ PDF", "mudlej", f"monkey -p com.gitlab.mudlej.MjPdfReader {L}", "com.gitlab.mudlej.MjPdfReader"),
    ("F-Droid", "fdroid", f"monkey -p org.fdroid.fdroid {L}", "org.fdroid.fdroid"),
    ("Seal", "junkfood.seal", f"monkey -p com.junkfood.seal {L}", "com.junkfood.seal"),
    ("Fennec", "fennec", f"monkey -p org.mozilla.fennec_fdroid {L}", "org.mozilla.fennec_fdroid"),
    ("Thunderbird", "thunderbird", f"monkey -p net.thunderbird.android {L}", "net.thunderbird.android"),
    ("NewPipe", "newpipe", f"monkey -p org.schabi.newpipe {L}", "org.schabi.newpipe"),
    ("Mensagens", "fossify.messages", f"monkey -p org.fossify.messages {L}", "org.fossify.messages"),
    ("Agenda", "fossify.calendar", f"monkey -p org.fossify.calendar {L}", "org.fossify.calendar"),
    ("Notas", "fossify.notes", f"monkey -p org.fossify.notes {L}", "org.fossify.notes"),
    ("Relogio Fossify", "fossify.clock", f"monkey -p org.fossify.clock {L}", "org.fossify.clock"),
    ("Calculadora", "fossify.math", f"monkey -p org.fossify.math {L}", "org.fossify.math"),
    ("KDE Connect", "kdeconnect", f"monkey -p org.kde.kdeconnect_tp {L}", "org.kde.kdeconnect_tp"),
    ("aFreeRDP", "freerdp", f"monkey -p com.freerdp.afreerdp {L}", "com.freerdp.afreerdp"),
    ("LibreOffice", "documentfoundation", f"monkey -p org.documentfoundation.libreoffice {L}", "org.documentfoundation.libreoffice"),
    ("Relogio Samsung", "clockpackage", f"monkey -p com.sec.android.app.clockpackage {L}", "com.sec.android.app.clockpackage"),
]
PAGINAS = [  # paginas das Configuracoes: nao podem derrubar Configuracoes, Device Care nem SystemUI
    ("Bateria", "android.settings.BATTERY_SAVER_SETTINGS"),
    ("Armazenamento", "android.settings.INTERNAL_STORAGE_SETTINGS"),
    ("Apps", "android.settings.APPLICATION_SETTINGS"),
    ("Contas", "android.settings.SYNC_SETTINGS"),
    ("Teclados", "android.settings.INPUT_METHOD_SETTINGS"),
]
ESPERADO_SEM = {"Armazenamento": "com.sec.android.app.myfiles"}  # pagina que o UAD-ng avisa que cai sem esse pacote
NUCLEO = {"Telefone", "Configuracoes", "Gov.br", "SED", "ARENA", "Open Camera"}
TEMPOS = ["io.github.rafaparise.arena", "org.mozilla.fennec_fdroid", "com.android.settings", "br.gov.meugovbr"]
SISTEMA = ("settings", "lool", "systemui", "launcher", "telecom", "phone")


def sh(cmd, timeout=60):
    r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def casa():
    sh("input keyevent KEYCODE_HOME")
    time.sleep(1)


def travado():
    sh("input keyevent KEYCODE_WAKEUP")
    sh("wm dismiss-keyguard")
    time.sleep(1.5)
    foco = sh("dumpsys window | grep -m1 mCurrentFocus")
    return any(x in foco for x in ("NotificationShade", "Keyguard", "StatusBar"))


def em_primeiro_plano():
    linha = sh("dumpsys activity activities | grep -m1 -E 'topResumedActivity|mResumedActivity'")
    m = re.search(r"u0 (\S+)", linha)
    return m.group(1) if m else linha[:80]


def processos_que_cairam():
    """Quedas Java ('Process: pkg') e nativas ('>>> pkg <<<' no tombstone, ex.: driver Vulkan do chip derrubando o app)."""
    log = sh("logcat -d -b crash | grep -E 'Process:|>>> '")
    return sorted(set(re.findall(r"Process:\s*([\w.]+)", log) + re.findall(r">>> ([\w.]+) <<<", log)))


def componente(pkg):
    saida = sh(f"cmd package resolve-activity --brief -a android.intent.action.MAIN "
               f"-c android.intent.category.LAUNCHER {pkg}")
    achados = [l.strip() for l in saida.splitlines() if "/" in l and " " not in l.strip()]
    return achados[-1] if achados else None


def tempo_frio(pkg, n=3):
    comp = componente(pkg)
    if not comp:
        return None
    ts = []
    for _ in range(n):
        sh(f"am force-stop {pkg}")
        time.sleep(1.5)
        m = re.search(r"TotalTime:\s*(\d+)", sh(f"am start -W -n {comp}"))
        if m:
            ts.append(int(m.group(1)))
        casa()
    return int(statistics.median(ts)) if ts else None


def quem_responde(args):
    saida = sh(f"cmd package resolve-activity --brief {args}")
    achados = [l.strip() for l in saida.splitlines() if "/" in l and " " not in l.strip()]
    return achados[-1] if achados else "(ninguem)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tempos", action="store_true")
    ap.add_argument("--rapido", action="store_true", help="so o nucleo (telefone, Configuracoes, Gov.br, SED, ARENA, camera) e as paginas")
    a = ap.parse_args()

    if "SM-A125" not in sh("getprop ro.product.model"):
        sys.exit("ABORTADO: aparelho nao encontrado ou inesperado")
    estado = sh("am get-started-user-state 0")
    if "UNLOCKED" not in estado:
        sys.exit(f"TRAVADO: o usuario 0 esta {estado!r}. Destrave o celular (PIN/biometria) e rode de novo.")
    if travado():
        sys.exit("TRAVADO: a tela de bloqueio esta ativa. Destrave o celular e rode de novo.")

    ativos = {l.split(":", 1)[1].strip() for l in sh("pm list packages -e").splitlines() if l.startswith("package:")}
    falhas, outros = 0, set()
    for nome, esperado, cmd, pkg in APPS:
        if pkg not in ativos:
            print(f"  pulado {nome:<22} ({pkg} desativado ou ausente)")
            continue
        if a.rapido and nome not in NUCLEO:
            continue
        sh("logcat -c")
        sh(cmd)
        time.sleep(7 if "organicmaps" in pkg else 4)  # o mapa so desenha (e, se o driver falhar, cai) depois de uns 4 s
        pp = em_primeiro_plano()
        procs = processos_que_cairam()
        proprios = [p for p in procs if esperado in p]
        outros.update(p for p in procs if p not in proprios)
        nota = ""
        if "permissioncontroller" in pp:
            nota = "  (pedindo permissao na 1a abertura)"
        elif "ResolverActivity" in pp:
            nota = "  (seletor: mais de um app responde)"
        ok = (esperado in pp or bool(nota)) and not proprios
        falhas += 0 if ok else 1
        print(f"  {'ok    ' if ok else 'FALHOU'} {nome:<22} {pp[:58]}"
              + (f"  CRASH={','.join(proprios)}" if proprios else "") + nota)
        casa()

    print("paginas das Configuracoes:")
    for nome, acao in PAGINAS:
        if nome in ESPERADO_SEM and ESPERADO_SEM[nome] not in ativos:
            print(f"  pulado {nome:<22} (esperado: {ESPERADO_SEM[nome]} desativado; a pagina nao abre sem ele)")
            continue
        sh("logcat -c")
        sh(f"am start -f 0x10008000 -a {acao}")  # NEW_TASK|CLEAR_TASK: nao reaproveitar a tela do teste anterior
        time.sleep(3)
        pp = em_primeiro_plano()
        caiu = [p for p in processos_que_cairam() if any(s in p for s in SISTEMA)]
        ok = not caiu and "/" in pp and "launcher" not in pp
        falhas += 0 if ok else 1
        print(f"  {'ok    ' if ok else 'FALHOU'} {nome:<22} {pp[:58]}" + (f"  CRASH={','.join(caiu)}" if caiu else ""))
        casa()

    print("quem responde:")
    print(f"  camera : {quem_responde('-a android.media.action.STILL_IMAGE_CAMERA')}")
    print(f"  mapa   : {quem_responde('-a android.intent.action.VIEW -d geo:-23.5,-46.6')}")
    print(f"  imagem : {quem_responde('-a android.intent.action.VIEW -t image/jpeg -d file:///sdcard/x.jpg')}")
    if outros:
        print("crashes de OUTROS processos durante o teste (nao reprovam o app aberto): " + ", ".join(sorted(outros)))
    if a.tempos:
        print("abertura a frio (ms, mediana de 3):")
        for pkg in TEMPOS:
            t = tempo_frio(pkg)
            print(f"  {pkg:<32} {t if t is not None else 'n/d'}")

    ime = sh("settings get secure default_input_method")
    print(f"teclado padrao: {ime} -> {'ativo' if ime.split('/')[0] in ativos else 'DESATIVADO!'}")
    mem = sh("grep -E 'MemAvailable|SwapFree' /proc/meminfo")
    kb = {k: int(v) // 1024 for k, v in re.findall(r"(\w+):\s+(\d+) kB", mem)}
    print(f"memoria: MemAvailable={kb.get('MemAvailable')} MB | SwapFree={kb.get('SwapFree')} MB")
    print("RESULTADO: " + ("tudo ok" if not falhas else f"{falhas} item(ns) com problema"))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
