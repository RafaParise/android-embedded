#!/usr/bin/env python3
"""Copia do projeto no cartao PORTATIL do A12, conferida por md5 com o cache descartado.

  python scripts/backup-cartao.py             simulacao: mostra o que faria, sem gravar nada
  python scripts/backup-cartao.py --aplicar   copia e confere (precisa do cabo, 3% de bateria e carregando)
  python scripts/backup-cartao.py --conferir  so confere a copia que esta no cartao, sem gravar

Destino: /storage/<cartao>/Backups/android-embeeded
  projeto/          arquivos da versao atual (os mesmos do GitHub)
  historico.bundle  historico do git; recuperar: git clone historico.bundle pasta
  MD5SUMS.txt       a lista conferida
  VERSAO.txt        so diz CONFERIDA depois de o md5 bater; se disser outra coisa, nao confie na copia

Envia so o que ja esta no GitHub: a varredura de segredos do sync passou por ali. O diagnostico/ e as chaves nao vao.
Nunca apaga nada no cartao: arquivo que saiu do projeto continua la e fica fora da conferencia.
Saida: 0 = conferida; 1 = copia com diferenca; 2 = nao deu para fazer. Detalhe em memoria/BACKUP-DRIVE.md.
"""
import argparse
import datetime
import hashlib
import pathlib
import re
import subprocess
import sys
import tarfile
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SUBPASTA = "Backups/android-embeeded"
BATERIA_MINIMA = 3


class Erro(Exception):
    pass


def roda(args, timeout=600):
    # cwd so existe para o git: o adb nao depende da pasta
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=str(RAIZ))
    except subprocess.TimeoutExpired:
        raise Erro(f"{args[0]} passou de {timeout} s e foi interrompido") from None
    if r.returncode != 0:
        raise Erro(f"{' '.join(args[:3])} falhou: {(r.stderr or r.stdout).strip()[:300]}")
    return r.stdout.replace("\r", "")


def sh(cmd, timeout=600):
    return roda(["adb", "shell", cmd], timeout)


def bateria_ok():
    b = sh("dumpsys battery")
    n, s = re.search(r"level:\s*(\d+)", b), re.search(r"status:\s*(\d+)", b)
    if not n or not s:
        raise Erro("nao consegui ler a bateria (aparelho offline?)")
    nivel, ligado = int(n.group(1)), int(s.group(1)) in (2, 5)
    if nivel < BATERIA_MINIMA or not ligado:
        raise Erro(f"bateria {nivel}%, carregando={ligado}: a regra pede {BATERIA_MINIMA}% e carregando")
    print(f"bateria {nivel}%, carregando")


def cartao_portatil(saida):
    """O UUID do unico cartao portatil montado. Adotado (private:) nunca entra: corrompeu gravacao em 28/10."""
    achados = []
    for linha in saida.splitlines():
        p = linha.split()
        if len(p) >= 3 and p[0].startswith("public:") and p[1] == "mounted":
            achados.append(p[2])
    if len(achados) != 1:
        raise Erro(f"esperava um cartao portatil montado e achei {len(achados)}")
    if not re.fullmatch(r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}", achados[0]):
        raise Erro(f"identificador de cartao inesperado: {achados[0]!r}")
    return achados[0]


def destino():
    return f"/storage/{cartao_portatil(sh('sm list-volumes all'))}/{SUBPASTA}"


def commit_enviado():
    """So o que ja esta no GitHub: a varredura do sync passou por ali."""
    head = roda(["git", "rev-parse", "HEAD"]).strip()
    origem = roda(["git", "rev-parse", "refs/remotes/origin/main"]).strip()
    if head != origem:
        raise Erro("HEAD diferente de origin/main: rode o sync antes, para a varredura de segredos passar por este commit")
    return head


def empacota(pasta):
    """Monta em pasta/ exatamente o que vai ao cartao, com os bytes do commit."""
    tar = pasta.parent / "projeto.tar"
    roda(["git", "archive", "--format=tar", "-o", str(tar), "HEAD"])
    with tarfile.open(tar) as t:
        t.extractall(pasta / "projeto", filter="data")
    tar.unlink()
    roda(["git", "bundle", "create", str(pasta / "historico.bundle"), "HEAD", "main"])


def manifesto(pasta):
    return {f.relative_to(pasta).as_posix(): hashlib.md5(f.read_bytes()).hexdigest()
            for f in sorted(pasta.rglob("*")) if f.is_file() and f.name not in ("MD5SUMS.txt", "VERSAO.txt")}


def le_md5(saida, base):
    prefixo = base.rstrip("/") + "/"
    lidos = {}
    for linha in saida.splitlines():
        m = re.match(r"([0-9a-f]{32})\s+(.+)", linha)
        if m and m.group(2).startswith(prefixo):
            lidos[m.group(2)[len(prefixo):]] = m.group(1)
    return lidos


def diferencas(esperado, lido):
    falta = [f"falta: {k}" for k in esperado if k not in lido]
    return falta + [f"diferente: {k}" for k in esperado if k in lido and lido[k] != esperado[k]]


def descarta_cache():
    """Logo depois de gravar, o dado sai do cache e a conferencia engana (28/10). Mesma tecnica do teste-gravacao.py."""
    print("descartando o cache (leva alguns minutos)...")
    sh("sync")
    sh("find /system /vendor /product /system_ext -type f -size +512k -exec cat {} + > /dev/null 2>&1; echo feito", 1800)


def le_do_cartao(base):
    return le_md5(sh(f"find '{base}' -type f -exec md5sum {{}} +", 1800), base)


def marca(base, texto):
    sh(f"echo '{texto}' > '{base}/VERSAO.txt'")


def relata(erros):
    print(f"COPIA COM DIFERENCA em {len(erros)} arquivo(s):")
    for e in erros[:20]:
        print(" ", e)


def aplica(simular):
    commit = commit_enviado()
    bateria_ok()
    base = destino()
    with tempfile.TemporaryDirectory() as tmp:
        pasta = pathlib.Path(tmp) / "pacote"
        pasta.mkdir()
        empacota(pasta)
        lista = manifesto(pasta)
        total = sum(f.stat().st_size for f in pasta.rglob("*") if f.is_file())
        print(f"versao {commit[:7]}: {len(lista)} arquivos, {total / 1024 / 1024:.1f} MB -> {base}")
        if simular:
            print("Simulacao: nada foi gravado. Para copiar: --aplicar")
            return 0
        (pasta / "MD5SUMS.txt").write_text("".join(f"{v}  {k}\n" for k, v in lista.items()), encoding="utf-8", newline="\n")
        sh(f"mkdir -p '{base}'")
        marca(base, "EM ANDAMENTO: nao confie nesta copia")
        roda(["adb", "push", str(pasta) + "/.", base], 1800)
    descarta_cache()
    erros = diferencas(lista, le_do_cartao(base))
    if erros:
        marca(base, f"FALHOU em {commit[:7]}: nao confie nesta copia")
        relata(erros)
        return 1
    quando = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    marca(base, f"CONFERIDA {commit} em {quando}")
    print(f"Copia conferida: {len(lista)} arquivos, md5 iguais com o cache descartado.")
    return 0


def confere():
    base = destino()
    lista = {k: v for v, k in re.findall(r"^([0-9a-f]{32})  (.+)$", sh(f"cat '{base}/MD5SUMS.txt' 2>/dev/null"), re.M)}
    if not lista:
        raise Erro(f"nao ha copia em {base}")
    descarta_cache()
    erros = diferencas(lista, le_do_cartao(base))
    if erros:
        relata(erros)
        return 1
    print(f"Conferida: {len(lista)} arquivos iguais a lista gravada no cartao.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Copia do projeto no cartao portatil do A12")
    grupo = ap.add_mutually_exclusive_group()
    grupo.add_argument("--aplicar", action="store_true", help="copia de verdade e confere")
    grupo.add_argument("--conferir", action="store_true", help="so confere a copia do cartao")
    a = ap.parse_args(argv)
    try:
        return confere() if a.conferir else aplica(not a.aplicar)
    except Erro as e:
        print("ABORTADO:", e)
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
