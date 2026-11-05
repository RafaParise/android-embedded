#!/usr/bin/env python3
"""Copia local do Galaxy A12 e restauracao por cima do firmware original. Guia completo: memoria/COPIA-E-RESTAURAR.md.

NAO e imagem do aparelho: sem root as particoes nao abrem [medido em 04/11: dd da Permission denied], e o modo Download so aceita
firmware assinado. Celular que nem liga: primeiro o firmware original da Samsung (Smart Switch), depois este script.

  python scripts/copia-a12.py copiar              mostra o que copiaria (nao grava nada)
  python scripts/copia-a12.py copiar --aplicar    copia ou atualiza; so traz o que mudou; confere cada arquivo por md5
  python scripts/copia-a12.py copiar --aplicar --dados-apps    tambem o "adb backup" (toque no celular para confirmar)
  python scripts/copia-a12.py conferir            compara o celular com a copia (so leitura)
  python scripts/copia-a12.py restaurar           mostra o plano (nao muda nada)
  python scripts/copia-a12.py restaurar --aplicar [--so apps,papeis,lotes,permissoes,ajustes,arquivos,termux]

Fica fora do git e do Drive: C:\\Users\\passo\\Backups\\A12-copia (tem SMS, contatos e chamadas; o script nunca os imprime).
A restauracao nunca apaga arquivo do celular, nem app instalado fora da copia.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DESTINO = pathlib.Path(os.environ.get("A12_COPIA", str(pathlib.Path.home() / "Backups" / "A12-copia")))
MODELO = "SM-A125M"
ORIGEM = "/storage/emulated/0"
FOLGA_MINIMA = 15 * 1024**3
ETAPAS = ("apps", "papeis", "lotes", "permissoes", "ajustes", "arquivos", "termux")
PAPEIS = ("android.app.role.DIALER", "android.app.role.SMS", "android.app.role.BROWSER", "android.app.role.HOME", "android.app.role.ASSISTANT")
# Nome de rede, identificadores e dados de conta nao entram em arquivo (regras do CLAUDE.md).
AJUSTE_SENSIVEL = re.compile(r"ssid|wifi_saved|android_id|bluetooth_(name|address)|bluetooth_addr|bonded_device|device_name|token|session_id|account|password|credential|serial|imei|mhsside", re.I)
EXCLUIR = ("*/cache/*", "*/.thumbnails/*", "*/.Trash*", "*/code_cache/*", "*/termux-copia.tgz", "*/termux-pacotes.txt")
TERMUX_FORA = (".omniroute", ".env", ".ssh", ".cache", ".npm", "node_modules", "kit/projeto-android-embeeded", ".qwen/tmp", "*.gguf")
PESSOAIS = {"sms.txt": "content://sms", "contatos.txt": "content://contacts/phones", "chamadas.txt": "content://call_log/calls"}


def adb(*a, timeout=600):
    r = subprocess.run(["adb", *a], capture_output=True, timeout=timeout)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def sh(cmd, timeout=600):
    return adb("shell", cmd, timeout=timeout)[1].replace("\r\n", "\n")


def conferir_aparelho():
    modelo = sh("getprop ro.product.model").strip()
    if modelo != MODELO:
        sys.exit(f"ABORTADO: esperava {MODELO} com a depuracao USB ligada e autorizada; encontrei {modelo!r}.")


def bateria_ok(minimo=3):
    b = sh("dumpsys battery")
    n, s = re.search(r"level:\s*(\d+)", b), re.search(r"status:\s*(\d+)", b)
    if not n or not s or int(n.group(1)) < minimo or int(s.group(1)) not in (2, 5):
        sys.exit("ABORTADO: bateria abaixo de 3% ou sem carregar (regra do projeto).")


def lista_pacotes(flag):
    return sorted(l.split(":", 1)[1].strip() for l in sh(f"pm list packages {flag}").splitlines() if l.startswith("package:"))


def filtra_ajustes(texto):
    fora = {}
    for linha in texto.splitlines():
        if "=" not in linha:
            continue
        k, v = linha.split("=", 1)
        if not AJUSTE_SENSIVEL.search(k) and re.fullmatch(r"[\w.:-]+", k):
            fora[k] = v
    return fora


def permissoes_concedidas(texto):
    """Permissoes de tempo de execucao concedidas, lidas do 'dumpsys package <pacote>'."""
    return sorted(set(re.findall(r"^\s*([\w.]+): granted=true", texto, re.M)))


def instalador(texto):
    m = re.search(r"installerPackageName=([\w.]+)", texto)
    return m.group(1) if m and m.group(1) != "null" else ""


def nome_no_pc(rel):
    """Caminho do celular que o Windows aceita, sem sair da pasta da copia."""
    partes = []
    for p in rel.split("/"):  # no Android a barra invertida e letra comum do nome (medido: \.WL de um app)
        if p in ("", ".", ".."):
            raise ValueError(f"caminho perigoso: {rel!r}")
        limpo = re.sub(r'[<>:"|?*\\\x00-\x1f]', "_", p).rstrip(" .") or "_"
        if re.fullmatch(r"(?i)(con|prn|aux|nul|com\d|lpt\d)(\..*)?", limpo):
            limpo = "_" + limpo
        partes.append(limpo)
    return "/".join(partes)


def caminho_longo(p):
    p = str(pathlib.Path(p).absolute())
    return "\\\\?\\" + p if os.name == "nt" and not p.startswith("\\\\?\\") else p


def md5_arquivo(p):
    h = hashlib.md5()
    with open(caminho_longo(p), "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def le_json(p, padrao):
    p = pathlib.Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else padrao


def grava_json(p, dado):
    p = pathlib.Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dado, ensure_ascii=False, indent=1), encoding="utf-8")


def le_manifesto_celular():
    """{caminho relativo: md5} de tudo que a copia cobre na memoria interna. O cartao fica fora: e independente do sistema."""
    fora = " ".join(f"! -path '{x}'" for x in EXCLUIR)
    texto = sh(f"find {ORIGEM}/ -type f {fora} -print0 2>/dev/null | xargs -0 md5sum 2>/dev/null", timeout=3600)
    m = {}
    for linha in texto.splitlines():
        achou = re.match(r"^\\?([0-9a-f]{32})\s+(.+)$", linha)
        if achou and achou.group(2).startswith(ORIGEM + "/"):
            m[achou.group(2)[len(ORIGEM) + 1:]] = achou.group(1)
    return m


def fotografia():
    """Estado do aparelho sem arquivos: pacotes, papeis, permissoes, ajustes e isencoes de bateria."""
    terceiros, instaladores, permissoes = lista_pacotes("-3"), {}, {}
    for p in terceiros:
        d = sh(f"dumpsys package {p}", timeout=60)
        instaladores[p], permissoes[p] = instalador(d), permissoes_concedidas(d)
    return {
        "pacotes": {"ativos": lista_pacotes("-e"), "desativados": lista_pacotes("-d"), "no_sistema": lista_pacotes("-u"), "terceiros": terceiros},
        "instaladores": instaladores,
        "permissoes": permissoes,
        "papeis": {r: sorted(x.strip() for x in sh(f"cmd role get-role-holders {r}").split(";") if x.strip()) for r in PAPEIS},
        "teclado": sh("settings get secure default_input_method").strip(),
        "isentos_bateria": sorted(set(re.findall(r"^user,([\w.]+),", sh("dumpsys deviceidle whitelist"), re.M))),
        "ajustes": {t: filtra_ajustes(sh(f"settings list {t}")) for t in ("global", "secure", "system")},
    }


def copia_apks(dest, foto, aplicar):
    manifesto = le_json(dest / "apks.json", {})
    novos, falhas = 0, []
    for p in foto["pacotes"]["terceiros"]:
        caminhos = [l.split(":", 1)[1].strip() for l in sh(f"pm path {p}").splitlines() if l.startswith("package:")]
        esperado = {}
        for c in caminhos:
            m = sh(f"md5sum '{c}'").split()
            if m and re.fullmatch(r"[0-9a-f]{32}", m[0]):
                esperado[c.rsplit("/", 1)[1]] = m[0]
        pasta = dest / "apks" / p
        faltam = {a: h for a, h in esperado.items() if not (pasta / a).exists() or manifesto.get(p, {}).get(a) != h}
        if not faltam:
            continue
        novos += 1
        if not aplicar:
            continue
        pasta.mkdir(parents=True, exist_ok=True)
        for velho in pasta.iterdir():
            if velho.name not in esperado:
                velho.unlink()
        for c in caminhos:
            a = c.rsplit("/", 1)[1]
            if a in faltam:
                adb("pull", c, str(pasta / a))
                if not (pasta / a).exists() or md5_arquivo(pasta / a) != faltam[a]:
                    falhas.append(f"{p}/{a}")
        manifesto[p] = esperado
    if aplicar:
        grava_json(dest / "apks.json", manifesto)
    print(f"  apps: {len(foto['pacotes']['terceiros'])} de terceiros, {novos} a trazer" + (f", FALHAS: {falhas}" if falhas else ""))
    return falhas


def extrai_tar(fluxo, base, esperado):
    """Le o tar do celular e grava cada arquivo. Devolve {rel: (nome no pc, md5 lido)}; o caminho sai sempre dentro de base."""
    feitos = {}
    with tarfile.open(fileobj=fluxo, mode="r|") as t:
        for m in t:
            if not m.isfile():
                continue
            rel = m.name.removeprefix("./")  # lstrip comeria o ponto de .oculto e de ../fora
            if rel not in esperado:
                continue
            try:  # um nome ruim nao derruba a copia inteira: fica na lista do que faltou
                nome = nome_no_pc(rel)
                alvo = pathlib.Path(base) / nome
                os.makedirs(caminho_longo(alvo.parent), exist_ok=True)
                h = hashlib.md5()
                orig = t.extractfile(m)
                with open(caminho_longo(alvo), "wb") as f:
                    for bloco in iter(lambda: orig.read(1024 * 1024), b""):
                        h.update(bloco)
                        f.write(bloco)
            except (ValueError, OSError) as e:
                print(f"  AVISO: nao gravei um arquivo ({type(e).__name__})")
                continue
            feitos[rel] = (nome, h.hexdigest())
    return feitos


def traz_por_tar(lista, base, esperado):
    temp = "/data/local/tmp/copia-lista.txt"
    local = pathlib.Path(base).parent / "copia-lista.txt"
    local.write_bytes(("\n".join(lista) + "\n").encode("utf-8"))
    adb("push", str(local), temp)
    p = subprocess.Popen(["adb", "exec-out", f"tar -cf - -C {ORIGEM} -T {temp} 2>/dev/null"], stdout=subprocess.PIPE)
    try:
        return extrai_tar(p.stdout, base, esperado)
    finally:
        p.stdout.close()
        p.wait()
        sh(f"rm -f {temp}")
        local.unlink()


def copia_arquivos(dest, aplicar):
    atual = le_manifesto_celular()
    guardado = le_json(dest / "arquivos.json", {})
    faltam = sorted(r for r, h in atual.items() if guardado.get(r, {}).get("md5") != h)
    print(f"  arquivos da memoria interna: {len(atual)}, {len(faltam)} a trazer")
    if not aplicar or not faltam:
        return []
    base = dest / "arquivos"
    base.mkdir(parents=True, exist_ok=True)
    for _ in (1, 2):
        feitos = traz_por_tar(faltam, base, set(faltam))
        for rel, (nome, md5) in feitos.items():
            if md5 == atual[rel]:
                guardado[rel] = {"pc": nome, "md5": md5}
        grava_json(dest / "arquivos.json", guardado)
        faltam = [r for r in faltam if guardado.get(r, {}).get("md5") != atual[r]]
        if not faltam:
            break
        atual_de_novo = le_manifesto_celular()  # arquivo em uso muda durante a copia: compara com o valor novo na segunda volta
        atual = {**atual, **{r: atual_de_novo[r] for r in faltam if r in atual_de_novo}}
    for r in list(guardado):
        if r not in atual:
            del guardado[r]  # sumiu do celular: sai do plano; o arquivo fica na pasta da copia
    grava_json(dest / "arquivos.json", guardado)
    if faltam:
        print(f"  AVISO: {len(faltam)} arquivo(s) sem copia conferida (lista em arquivos-faltando.txt): em geral, em uso por um app")
        (dest / "arquivos-faltando.txt").write_text("\n".join(faltam), encoding="utf-8")
    return faltam


def copia_pessoais(dest):
    """SMS, contatos e chamadas: so para consulta. Nao ha como devolve-los pelo cabo sem root. Nada disso vai para a tela."""
    pasta = dest / "pessoais"
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, uri in PESSOAIS.items():
        (pasta / nome).write_text(sh(f"content query --uri {uri}", timeout=600), encoding="utf-8")
    print("  SMS, contatos e chamadas: guardados para consulta em pessoais\\")


def copia_termux(dest):
    fora = " ".join(f"--exclude='{x}'" for x in TERMUX_FORA)
    cmd = f"cd ~ && dpkg --get-selections > /sdcard/Download/termux-pacotes.txt; tar czf /sdcard/Download/termux-copia.tgz {fora} . ; echo fim=$?"
    r = subprocess.run(["pwsh", "-NoProfile", "-File", str(RAIZ / "scripts" / "termux.ps1"), "-Comando", cmd], capture_output=True, timeout=1800)
    adb("forward", "--remove", "tcp:8022")
    pasta = dest / "termux"
    pasta.mkdir(parents=True, exist_ok=True)
    ok = True
    for nome in ("termux-pacotes.txt", "termux-copia.tgz"):
        cod, _, _ = adb("pull", f"/sdcard/Download/{nome}", str(pasta / nome), timeout=1800)
        ok = ok and cod == 0
        sh(f"rm -f /sdcard/Download/{nome}")
    if not ok or b"fim=" not in r.stdout:
        print("  AVISO: nao consegui copiar o Termux (ele precisa estar aberto, com o SSH ligado).")
        return False
    print(f"  Termux: {(pasta / 'termux-copia.tgz').stat().st_size / 1024**2:.0f} MB, sem chaves nem modelos de IA")
    return True


def guarda_firmware(dest):
    pda = sh("getprop ro.build.PDA").strip()
    dados = {"modelo": sh("getprop ro.product.model").strip(), "firmware": pda, "regiao": sh("getprop ro.csc.sales_code").strip(),
             "android": sh("getprop ro.build.version.release").strip(), "serie": sh("getprop ro.serialno").strip(),
             "copia_em": datetime.datetime.now().isoformat(timespec="minutes")}
    grava_json(dest / "aparelho.json", dados)
    print(f"  firmware {pda}; numero de serie guardado em aparelho.json (o Smart Switch pede)")


def copiar(dest, aplicar, dados_apps=False):
    conferir_aparelho()
    print(("COPIANDO para " if aplicar else "SIMULACAO, nada sera gravado. Destino: ") + str(dest))
    dest.parent.mkdir(parents=True, exist_ok=True)
    if aplicar:
        livre = shutil.disk_usage(dest.parent).free
        if livre < FOLGA_MINIMA:
            sys.exit(f"ABORTADO: so {livre / 1024**3:.0f} GB livres; a copia pede ao menos 15 GB.")
        dest.mkdir(parents=True, exist_ok=True)
    foto = fotografia()
    falhas = copia_apks(dest, foto, aplicar)
    faltando = copia_arquivos(dest, aplicar)
    if not aplicar:
        print("Para copiar: python scripts/copia-a12.py copiar --aplicar")
        return 0
    grava_json(dest / "estado.json", foto)
    guarda_firmware(dest)
    copia_pessoais(dest)
    termux_ok = copia_termux(dest)
    if dados_apps:
        print("  Toque em 'Fazer backup' no celular, sem senha. Espero ate 10 minutos.")
        cod, _, erro = adb("backup", "-f", str(dest / "dados-apps.ab"), "-noapk", "-all", "-nosystem", "-noshared", timeout=3600)
        ab = dest / "dados-apps.ab"
        print(f"  dados de apps: {ab.stat().st_size / 1024**2:.0f} MB" if cod == 0 and ab.exists() else f"  AVISO: backup de dados falhou: {erro[:120]}")
    print(f"Pronta: {dest}. Faltou conferir: {len(falhas) + len(faltando)} arquivo(s). Termux: {'ok' if termux_ok else 'NAO copiado'}.")
    return 1 if falhas else 0


def carrega_protegidos():
    esp = importlib.util.spec_from_file_location("lote_pacotes", RAIZ / "scripts" / "lote-pacotes.py")
    m = importlib.util.module_from_spec(esp)
    esp.loader.exec_module(m)
    return m.PROTEGIDOS


def plano(estado, agora, lotes, protegidos):
    """Compara a copia com o aparelho. So decide; quem executa e restaurar()."""
    q = estado["pacotes"]
    a = agora["pacotes"]
    em_lote = {p for x in lotes.values() for p in x.get("pacotes", [])}
    ausentes_na_copia = [p for p in q["no_sistema"] if p not in q["ativos"] and p not in q["desativados"]]
    a_tirar = [p for p in a["ativos"] if p in q["desativados"] or p in ausentes_na_copia]
    lotes_a_rodar = [n for n, x in lotes.items() if x.get("aplicavel") and set(x.get("pacotes", [])) & set(a_tirar)]
    fora = [p for p in a_tirar if p not in em_lote]
    livres = [p for p in fora if not any(re.search(rx, p, re.I) for rx in protegidos)]
    return {
        "apps": sorted(p for p in q["terceiros"] if p not in a["ativos"] and p not in a["desativados"]),
        "papeis": {r: h for r, h in estado["papeis"].items() if h and sorted(h) != sorted(agora["papeis"].get(r, []))},
        "teclado": estado["teclado"] if estado["teclado"] != agora["teclado"] else "",
        "lotes": lotes_a_rodar,
        "remover": sorted(set(a_tirar + a["desativados"]) & set(ausentes_na_copia)),
        "desativar_fora_de_lote": sorted(livres),
        "protegidos_fora_de_lote": sorted(set(fora) - set(livres)),
        "reativar": sorted(p for p in q["ativos"] if p not in a["ativos"] and p not in q["terceiros"]),
        "permissoes": {p: sorted(set(v) - set(agora["permissoes"].get(p, []))) for p, v in estado["permissoes"].items() if set(v) - set(agora["permissoes"].get(p, []))},
        "isentos": sorted(set(estado["isentos_bateria"]) - set(agora["isentos_bateria"])),
    }


def resumo_plano(pl, n_arquivos):
    itens = [("apps a instalar", pl["apps"]), ("papeis padrao a devolver", list(pl["papeis"])), ("lotes a rodar de novo", pl["lotes"]),
             ("pacotes a remover", pl["remover"]), ("a desativar fora dos lotes", pl["desativar_fora_de_lote"]),
             ("protegidos: desativar so a mao", pl["protegidos_fora_de_lote"]), ("a reativar", pl["reativar"]),
             ("apps com permissao a devolver", list(pl["permissoes"])), ("isencoes de bateria", pl["isentos"])]
    total = n_arquivos + bool(pl["teclado"]) + sum(len(v) for _, v in itens)
    for nome, v in itens:
        if v:
            print(f"  {nome} ({len(v)}): " + ", ".join(v[:12]) + (" ..." if len(v) > 12 else ""))
    if pl["teclado"]:
        print("  teclado padrao a devolver")
    print(f"  arquivos a devolver: {n_arquivos}")
    return total


def instala_app(dest, p, instaladores):
    pasta = dest / "apks" / p
    apks = sorted(str(x) for x in pasta.glob("*.apk")) if pasta.exists() else []
    if not apks:
        return "sem APK na copia"
    orig = instaladores.get(p, "")
    saida = erro = ""
    for extra in ((["-i", orig],) if orig else ()) + ([],):
        cod, saida, erro = adb("install-multiple", "-r", *extra, *apks, timeout=900)
        if cod == 0 and "Success" in saida:
            return ""
    return (saida + erro).strip()[-120:]


def script(*a):
    return subprocess.run([sys.executable, "-B", str(RAIZ / "scripts" / a[0]), *a[1:]], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)


def arquivos_a_devolver(dest):
    guardado = le_json(dest / "arquivos.json", {})
    atual = le_manifesto_celular()
    return guardado, sorted(r for r, x in guardado.items() if atual.get(r) != x["md5"])


def restaurar(dest, aplicar, so):
    conferir_aparelho()
    estado = le_json(dest / "estado.json", None)
    if not estado:
        sys.exit(f"ABORTADO: nao ha copia em {dest}. Rode: python scripts/copia-a12.py copiar --aplicar")
    feito = le_json(dest / "aparelho.json", {})
    print(f"Copia de {feito.get('copia_em', '?')}, firmware {feito.get('firmware', '?')}; aparelho agora: {sh('getprop ro.build.PDA').strip()}")
    lotes = json.loads((RAIZ / "scripts" / "lotes-bloatware.json").read_text(encoding="utf-8"))
    pl = plano(estado, fotografia(), lotes, carrega_protegidos())
    guardado, devolver = arquivos_a_devolver(dest)
    total = resumo_plano(pl, len(devolver))
    if not aplicar:
        print(("Nada a fazer: o celular confere com a copia." if not total else f"{total} diferenca(s). Nada foi alterado.") + (" Para aplicar: restaurar --aplicar" if total else ""))
        return 0 if not total else 3
    bateria_ok()
    erros = []
    if "apps" in so:
        # o F-Droid primeiro: e o instalador de origem dos outros
        for p in sorted(pl["apps"], key=lambda x: x != "org.fdroid.fdroid"):
            e = instala_app(dest, p, estado["instaladores"])
            print(f"  app {p}: {'ok' if not e else 'FALHOU ' + e}")
            if e:
                erros.append(p)
    if "papeis" in so:
        # antes dos lotes: o substituto precisa estar no papel antes de o original sair
        for r, h in pl["papeis"].items():
            for x in h:
                sh(f"cmd role add-role-holder {r} {x}")
        if pl["teclado"]:
            sh(f"ime enable {pl['teclado']}")
            sh(f"ime set {pl['teclado']}")
    if "lotes" in so:
        for n in pl["lotes"]:
            r = script("lote-pacotes.py", n, "--aplicar")
            print(f"  lote {n}: saida {r.returncode}")
            if r.returncode:
                erros.append(f"lote {n}: {(r.stdout + r.stderr).strip()[-120:]}")
        for n in lotes:
            if lotes[n].get("aplicavel") and set(lotes[n].get("pacotes", [])) & set(pl["remover"]) and (lotes[n].get("remocao_autorizada") or lotes[n].get("substitutos")):
                script("lote-pacotes.py", n, "--remover")
        for p in pl["desativar_fora_de_lote"]:
            sh(f"pm disable-user --user 0 {p}")
        # lote pode desativar algo que voce reativou depois: a copia manda
        desativados_agora = set(lista_pacotes("-d"))
        ativos_agora = set(lista_pacotes("-e"))
        for p in estado["pacotes"]["ativos"]:
            if p in desativados_agora:
                sh(f"pm enable {p}")
            elif p not in ativos_agora and p not in estado["pacotes"]["terceiros"]:
                sh(f"cmd package install-existing {p}")
    if "permissoes" in so:
        for p, v in pl["permissoes"].items():
            for x in v:
                sh(f"pm grant {p} {x}")
        for p in pl["isentos"]:
            sh(f"dumpsys deviceidle whitelist +{p}")
    if "ajustes" in so:
        for s in (("ajustes-script.py", "--aplicar"), ("privacidade.py", "--aplicar"), ("tela-apagada.py", "iniciar")):
            r = script(*s)
            print(f"  {s[0]}: saida {r.returncode}")
            if r.returncode:
                erros.append(s[0])
    if "arquivos" in so:
        for r in devolver:
            cod, _, erro = adb("push", caminho_longo(dest / "arquivos" / guardado[r]["pc"]), f"{ORIGEM}/{r}")
            if cod:
                erros.append(f"arquivo {r}: {erro[:80]}")
        _, restam = arquivos_a_devolver(dest)
        print(f"  arquivos: {len(devolver)} enviados, {len(restam)} sem conferir (md5)")
        if restam:
            erros.append(f"{len(restam)} arquivos sem conferir")
    if "termux" in so and (dest / "termux" / "termux-copia.tgz").exists():
        adb("push", str(dest / "termux" / "termux-copia.tgz"), "/sdcard/Download/termux-copia.tgz")
        print("  Termux: pacote em Download. Depois de instalar: termux-setup-storage; cd ~; tar xzf ~/storage/downloads/termux-copia.tgz")
    print("Fim." if not erros else "Fim, com " + str(len(erros)) + " problema(s): " + "; ".join(erros[:6]))
    print("Com a sua mao: memoria/COPIA-E-RESTAURAR.md, parte 3.")
    return 1 if erros else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", choices=("copiar", "conferir", "restaurar"))
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--dados-apps", action="store_true")
    ap.add_argument("--so", default=",".join(ETAPAS))
    ap.add_argument("--destino", type=pathlib.Path, default=DESTINO)
    a = ap.parse_args()
    so = {x.strip() for x in a.so.split(",") if x.strip()}
    if so - set(ETAPAS):
        sys.exit("--so aceita: " + ",".join(ETAPAS))
    if a.comando == "copiar":
        return copiar(a.destino, a.aplicar, a.dados_apps)
    return restaurar(a.destino, a.comando == "restaurar" and a.aplicar, so)


if __name__ == "__main__":
    sys.exit(main())
