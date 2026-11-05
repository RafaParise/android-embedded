"""Publica a parte publica do projeto no GitHub (repositorio RafaParise/android-embedded).

Analogia: o repositorio privado e a cozinha (bancada suja, anotacoes, contas); o publico e a vitrine.
Este script e o garcom que leva so o prato pronto: copia uma LISTA PERMITIDA, troca os dados pessoais
por valores neutros, passa tudo por um detector de segredos e, se sobrar qualquer coisa, NAO publica.

Uso (pedido do Rafael, 05/11/2026; padrao do projeto: sem flag = simulacao):
  python scripts/publicar.py                    monta a previa em diagnostico/publico-previa e mostra o relatorio
  python scripts/publicar.py --aplicar          copia a previa para o clone publico, faz o commit e envia
  python scripts/publicar.py release            mostra o que entraria na versao (nada e criado)
  python scripts/publicar.py release --aplicar  cria a versao (tag vAAAA.MM.DD) com o pacote completo e o APK

Os dados pessoais e as trocas ficam em diagnostico/publicar-trocas.json (fora do git).
Sem esse arquivo o script recusa: nunca publica sem saber o que esconder.
"""
import argparse
import datetime
import fnmatch
import json
import pathlib
import re
import shutil
import subprocess
import sys
import zipfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
FONTE_PUBLICA = RAIZ / "memoria" / "publico"          # textos escritos para o publico (README, guias, AGENTS...); o sync so leva memoria/ e scripts/
PREVIA = RAIZ / "diagnostico" / "publico-previa"
TROCAS = RAIZ / "diagnostico" / "publicar-trocas.json"
CLONE = pathlib.Path(r"C:\Projetos\android-embedded")
REPO = "RafaParise/android-embedded"

# Scripts que sao da oficina do Rafael (memoria privada, Hermes, nuvem, contas dele) e nao servem a outra pessoa.
EXCLUIR_SCRIPTS = [
    "scripts/sync-memoria.ps1", "scripts/hermes-*.ps1", "scripts/nuvem-*",
    "scripts/teste-nuvem.ps1", "scripts/continuar-projeto.*",
    "scripts/reinstalar-nexus.*", "scripts/pc-rdp-senha.*", "scripts/qwen-agente-permitir.cmd",
    "scripts/termux-openpyxl-teste.py", "scripts/termux-pandoc-teste.sh",
    "scripts/celular-kit/papel/papel.apk.idsig", "scripts/celular-kit/tela/tela.dex",
    "scripts/tests/test_teste_nuvem*", "scripts/tests/test_sync*", "scripts/tests/test_hermes*",
]
# Documentos tecnicos da memoria que valem para qualquer A12 (o diario, ESTADO e DECISOES, nao vai).
DOCS_MEMORIA = [
    "RADAR-DESEMPENHO", "TELA-APAGADA", "VOZ-OFFLINE", "RECEITAS-ANDROID", "ANTIVIRUS", "CONTROLES-GAMESIR",
    "VPN-SEMPRE-ATIVA", "LINUX-A12", "COPIA-E-RESTAURAR", "WEBCAM-E-RECUPERACAO", "PLAY-PARA-FONTE",
    "GUIA-IA-NO-CELULAR", "QWEN-CELULAR", "OMNIROUTE-CELULAR", "PROTOCOLO-IAS", "ESPECIALISTA-A12",
    "LICOES-MATRIX", "PLANO-MATRIX", "INTEGRACAO-A12", "ADGUARD-PC", "OBS-ESTUDIO", "DISPOSITIVO",
    "ARMAZENAMENTO-EM-CAMADAS", "MAPAS-LUGARES", "AUDITORIA-SCRIPT", "DIVISAO-DE-TRABALHO",
]
AVISO_PRIVADO = """# {nome}

Este documento existe na copia de trabalho do projeto, mas fica so nela: tem o diario do dia a dia,
contas ou detalhes do aparelho do dono. Os outros documentos citam ele para quem trabalha na copia
privada; o que importa para usar o projeto esta nos guias (README e 1 a 6) e nos outros arquivos desta pasta.
"""
BINARIO_OK = {".png", ".gif", ".jpg", ".ico", ".jar"}
EMAIL_OK = {"noreply@anthropic.com", "voce@exemplo.com"}
EMAIL_DOMINIO_OK = ("@exemplo.com", "@example.com", "@users.noreply.github.com", "@raymondhill.net")  # uBlock0@raymondhill.net = ID publico da extensao
IP_OK = {"100.64.0.0", "100.64.0.1", "100.64.0.2", "100.100.100.100"}  # 100.64.0.0 = inicio da faixa 100.64.0.0/10
SEGREDOS = [
    r"ghp_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{30,}", r"gho_[A-Za-z0-9]{30,}", r"sk-or-v1-[a-f0-9]{40,}",
    r"sk-ant-[A-Za-z0-9_-]{30,}", r"sk-[A-Za-z0-9]{40,}", r"AIza[0-9A-Za-z_-]{35}", r"nvapi-[A-Za-z0-9_-]{40,}",
    r"AQ\.[A-Za-z0-9_-]{45,}", r"xox[abp]-[A-Za-z0-9-]{20,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"gsk_[A-Za-z0-9]{40,}", r"hf_[A-Za-z0-9]{30,}",
]


def sh(cmd, cwd=None, entrada=None):
    r = subprocess.run(cmd, cwd=cwd, input=entrada, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def carrega_trocas():
    if not TROCAS.exists():
        sys.exit(f"RECUSADO: falta {TROCAS} (trocas e proibidos). Sem ele nada e publicado.")
    d = json.loads(TROCAS.read_text(encoding="utf-8"))
    trocas = sorted(d.get("trocas", {}).items(), key=lambda kv: -len(kv[0]))  # a mais longa primeiro
    return trocas, d.get("proibidos", [])


def lista_fontes():
    """Devolve {caminho_publico: caminho_de_origem} so com o que esta na lista permitida."""
    fontes = {}
    if FONTE_PUBLICA.exists():
        for p in FONTE_PUBLICA.rglob("*"):
            if p.is_file():
                fontes[p.relative_to(FONTE_PUBLICA).as_posix()] = p
    cod, saida = sh(["git", "ls-files", "scripts"], cwd=RAIZ)
    if cod:
        sys.exit("git ls-files falhou: " + saida)
    for rel in saida.splitlines():
        if rel and not any(fnmatch.fnmatch(rel, m) for m in EXCLUIR_SCRIPTS) and (RAIZ / rel).is_file():
            fontes[rel] = RAIZ / rel
    for nome in DOCS_MEMORIA:
        p = RAIZ / "memoria" / f"{nome}.md"
        if p.exists():
            fontes[f"memoria/{nome}.md"] = p
    return fontes


def transforma(texto, trocas):
    for velho, novo in trocas:
        texto = texto.replace(velho, novo)
    return texto


def achados(rel, texto, proibidos):
    """Tudo o que nao pode sair: proibidos, e-mails, IPs da Tailscale que nao sao os neutros e segredos."""
    ruins = []
    baixo = texto.lower()
    for p in proibidos:
        if p.lower() in baixo:
            ruins.append(f"proibido '{p[:4]}...'")
    # Nos testes, e-mails e IPs sao inventados de proposito (testam o mascaramento); os reais seguem nos proibidos.
    teste = rel.startswith("scripts/tests/")
    for m in re.finditer(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", texto):
        e = m.group(0).lower()
        if not teste and e not in EMAIL_OK and not e.endswith(EMAIL_DOMINIO_OK):
            ruins.append(f"e-mail {e[:3]}...@{e.split('@')[1]}")
    for m in re.finditer(r"\b100\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b", texto):
        ip = m.group(0)
        if not teste and 64 <= int(m.group(1)) <= 127 and ip not in IP_OK:
            ruins.append(f"IP da Tailscale {ip}")
    for padrao in SEGREDOS:
        for m in re.finditer(padrao, texto):
            corpo = m.group(0)
            if len(set(corpo[6:])) > 8:  # chave falsa de teste ("xxxx...", "0000...") passa; chave real nao
                ruins.append(f"segredo {corpo[:6]}...")
    return [f"{rel}: {r}" for r in ruins]


def monta_previa():
    trocas, proibidos = carrega_trocas()
    fontes = lista_fontes()
    if PREVIA.exists():
        shutil.rmtree(PREVIA)
    problemas, n_texto, n_bin = [], 0, 0
    for rel, origem in sorted(fontes.items()):
        destino = PREVIA / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        dados = origem.read_bytes()
        try:
            texto = dados.decode("utf-8")
        except UnicodeDecodeError:
            if origem.suffix.lower() not in BINARIO_OK:
                problemas.append(f"{rel}: binario fora da lista ({origem.suffix})")
                continue
            for p in proibidos:
                if p.encode("utf-8") in dados:
                    problemas.append(f"{rel}: proibido dentro do binario")
            destino.write_bytes(dados)
            n_bin += 1
            continue
        novo = transforma(texto, trocas)
        problemas += achados(rel, novo, proibidos)
        destino.write_bytes(novo.encode("utf-8"))
        n_texto += 1
    # Documento citado que fica na copia privada (diario, contas): um aviso neutro no lugar, para o link nao quebrar.
    citados = set()
    for md in list((PREVIA / "memoria").glob("*.md")) + [PREVIA / "scripts/celular-kit/QWEN.md"]:
        if md.exists():
            citados |= set(re.findall(r"`([A-Z][A-Z0-9-]+\.md)`", md.read_text(encoding="utf-8")))
    for nome in sorted(citados):
        if not (PREVIA / "memoria" / nome).exists() and not (PREVIA / nome).exists():
            rel = f"memoria/{nome}"
            (PREVIA / rel).write_text(AVISO_PRIVADO.format(nome=nome[:-3]), encoding="utf-8")
            fontes[rel] = None
            n_texto += 1
    return fontes, problemas, n_texto, n_bin


def espelha_no_clone(arquivos):
    if not (CLONE / ".git").exists():
        sys.exit(f"RECUSADO: o clone publico {CLONE} nao existe (gh repo clone {REPO} \"{CLONE}\").")
    cod, saida = sh(["git", "status", "--porcelain"], cwd=CLONE)
    if saida.strip():
        sys.exit("RECUSADO: o clone publico tem mudancas fora deste script:\n" + saida[:800])
    sh(["git", "pull", "--ff-only", "-q"], cwd=CLONE)
    _, rastreados = sh(["git", "ls-files"], cwd=CLONE)
    for rel in rastreados.splitlines():
        if rel and rel not in arquivos:
            sh(["git", "rm", "-q", "--", rel], cwd=CLONE)       # saiu da lista: sai da vitrine (fica no historico)
    for rel in arquivos:
        alvo = CLONE / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PREVIA / rel, alvo)
    for i in range(0, len(arquivos), 80):
        cod, saida = sh(["git", "add", "--"] + arquivos[i:i + 80], cwd=CLONE)
        if cod:
            sys.exit("git add falhou: " + saida[:400])


def publicar(aplicar):
    fontes, problemas, n_texto, n_bin = monta_previa()
    print(f"Previa: {len(fontes)} arquivos ({n_texto} de texto, {n_bin} imagens) em {PREVIA}")
    if problemas:
        print(f"PAROU: {len(problemas)} achado(s) que nao podem ir ao publico:")
        for p in problemas[:60]:
            print("  -", p)
        return 1
    print("Varredura limpa: sem dado pessoal, e-mail, IP da Tailscale nem segredo.")
    if not aplicar:
        print("Simulacao. Para enviar: python scripts/publicar.py --aplicar")
        return 0
    espelha_no_clone(sorted(fontes))
    _, mudou = sh(["git", "diff", "--cached", "--stat"], cwd=CLONE)
    if not mudou.strip():
        print("Nada mudou desde a ultima publicacao.")
        return 0
    _, ultimo = sh(["git", "log", "-1", "--format=%s"], cwd=RAIZ)
    msg = "Atualizacao: " + ultimo.strip()[:300] + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
    cod, saida = sh(["git", "commit", "-q", "-F", "-"], cwd=CLONE, entrada=msg)
    if cod:
        sys.exit("commit falhou: " + saida[:400])
    cod, saida = sh(["git", "push", "-q", "origin", "HEAD"], cwd=CLONE)
    print("Enviado ao GitHub publico." if cod == 0 else "push falhou: " + saida[:400])
    print(mudou.strip().splitlines()[-1])
    return cod


def versao_livre():
    base = datetime.date.today().strftime("%Y.%m.%d")
    _, tags = sh(["git", "tag", "--list", f"v{base}*"], cwd=CLONE)
    existentes = set(tags.split())
    if f"v{base}" not in existentes:
        return base
    n = 2
    while f"v{base}.{n}" in existentes:
        n += 1
    return f"{base}.{n}"


def release(aplicar):
    if not (CLONE / ".git").exists():
        sys.exit("Publique antes (python scripts/publicar.py --aplicar).")
    sh(["git", "fetch", "--tags", "-q"], cwd=CLONE)
    v = versao_livre()
    pasta = RAIZ / "diagnostico" / "release"
    apk = RAIZ / "diagnostico" / "papel.apk"
    dex = RAIZ / "scripts" / "celular-kit" / "tela" / "tela.dex"
    notas = CLONE / "NOVIDADES.md"
    print(f"Versao v{v}: pacote android-embedded-{v}.zip (o repositorio publicado + tela.dex) e papel-rolante-{v}.apk")
    for nome, p in (("APK do papel", apk), ("tela.dex", dex), ("NOVIDADES.md", notas)):
        print(f"  {'ok' if p.exists() else 'FALTA'}  {nome}")
    if not (apk.exists() and dex.exists() and notas.exists()):
        return 1
    if not aplicar:
        print("Simulacao. Para criar: python scripts/publicar.py release --aplicar")
        return 0
    if pasta.exists():
        shutil.rmtree(pasta)
    pasta.mkdir(parents=True)
    _, rastreados = sh(["git", "ls-files"], cwd=CLONE)
    pacote = pasta / f"android-embedded-{v}.zip"
    with zipfile.ZipFile(pacote, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in rastreados.splitlines():
            if rel and not rel.startswith(".github/"):
                z.write(CLONE / rel, f"android-embedded/{rel}")
        z.write(dex, "android-embedded/scripts/celular-kit/tela/tela.dex")
        z.write(apk, "android-embedded/binarios/papel-rolante.apk")
    apk_rel = pasta / f"papel-rolante-{v}.apk"
    shutil.copyfile(apk, apk_rel)
    texto = notas.read_text(encoding="utf-8")
    secao = texto.split("\n## ", 2)
    corpo = ("## " + secao[1]).strip() if len(secao) > 1 else texto
    (pasta / "notas.md").write_text(corpo + "\n", encoding="utf-8")
    titulo = f"Android Embedded {v}"
    cod, saida = sh(["gh", "release", "create", f"v{v}", str(pacote), str(apk_rel), "-R", REPO,
                     "--title", titulo, "--notes-file", str(pasta / "notas.md"), "--target", "main"])
    print(saida.strip()[-400:])
    return cod


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", nargs="?", default="publicar", choices=["publicar", "release"])
    ap.add_argument("--aplicar", action="store_true", help="executa de verdade (sem ela, so simula)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    return release(a.aplicar) if a.acao == "release" else publicar(a.aplicar)


if __name__ == "__main__":
    sys.exit(main())
