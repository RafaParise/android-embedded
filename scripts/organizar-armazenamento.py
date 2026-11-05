#!/usr/bin/env python3
"""Organiza arquivos (fotos, downloads, midia) entre a memoria interna e o cartao PORTATIL
(exFAT) com seguranca. NUNCA usa armazenamento adotado nem move app: so copia arquivo comum,
confere com a MESMA tecnica de teste-gravacao.py (md5 antes e DEPOIS de forcar o cache a
descartar, lendo /system e /vendor) e so apaga a origem se as conferencias baterem 100% E o
Rafael tiver pedido o apagamento com --confirmo-apagar-origem.
Programas continuam na interna (decisao do projeto; nada aqui toca pacote nenhum).

  python scripts/organizar-armazenamento.py
      relatorio: tamanho das pastas de midia na interna e cartoes disponiveis

  python scripts/organizar-armazenamento.py --origem <pasta interna> --destino <pasta no cartao>
      simulacao: lista quantos arquivos seriam copiados, sem mexer em nada

  python scripts/organizar-armazenamento.py --origem <pasta interna> --destino <pasta no cartao> --aplicar
      copia de verdade (cp -rp: com as datas originais) e confere md5, tamanho e data com o cache descartado;
      a origem FICA (nada e apagado)

  ... --aplicar --confirmo-apagar-origem
      depois da conferencia 100%, apaga a origem (irreversivel: so com o "sim" do Rafael na mensagem do dia).
      Se o destino ja tem tudo igual (copia anterior), nao copia de novo: so confere e apaga.

Limites (recusados antes de qualquer comando que mude algo): a origem fica dentro de /storage/emulated/0/
(nunca a raiz, nunca Android/ = dados de app); o destino fica dentro de um cartao PORTATIL montado; caminhos
absolutos, sem '..', sem aspas nem barra invertida; destino que ja existe e nao bate com a origem nao e misturado.
Nao use o celular durante a organizacao: arquivo novo ou alterado na origem aborta a exclusao.
"""
import argparse
import posixpath
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

INTERNA = "/storage/emulated/0"
PASTAS_RELATORIO = ["DCIM", "Download", "Movies", "Pictures", "Music", "Documents"]
MARCA = "/data/local/tmp/.organizar-marca"  # arquivo-marca: o que ficar mais novo que ele durante a ultima leitura aborta a exclusao
TOLERANCIA_DATA = 2  # segundos (exFAT guarda a data com ate 2 s de granularidade)


def sh(cmd, timeout=120):
    try:
        r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        sys.exit(f"ABORTADO: o comando passou de {timeout} s e foi interrompido ({cmd[:80]}...). Confira a origem e o "
                 "destino (podem estar pela metade) antes de repetir; se o apagamento tinha comecado, a copia no cartao continua inteira.")
    return (r.stdout + r.stderr).replace("\r", "").strip()


def bateria_ok(minimo=3):
    b = sh("dumpsys battery")
    n = re.search(r"level:\s*(\d+)", b)
    s = re.search(r"status:\s*(\d+)", b)
    if not n or not s:
        sys.exit("ABORTADO: nao consegui ler a bateria (aparelho offline?)")
    nivel, status = int(n.group(1)), int(s.group(1))
    ligado = status in (2, 5)  # 2 = carregando, 5 = cheia
    print(f"bateria {nivel}% carregando={ligado}")
    if nivel < minimo or not ligado:
        sys.exit(f"ABORTADO: bateria abaixo de {minimo}% ou sem carregar")


def volumes():
    """sm list-volumes all -> [(id, estado, uuid)]. public: = PORTATIL, private: = ADOTADO."""
    linhas = [l.split() for l in sh("sm list-volumes all").splitlines()]
    return [(p[0], p[1], p[2] if len(p) > 2 else "") for p in linhas if len(p) >= 2]


def caminho_limpo(caminho):
    """Caminho absoluto, sem '..', sem aspas, barra invertida nem caractere de controle (ele vai entre aspas simples
    para o shell do aparelho). Devolve o caminho normalizado, sem barra no fim."""
    if not caminho.startswith("/") or ".." in caminho.split("/") or re.search(r"['\"\\\x00-\x1f]", caminho):
        sys.exit(f"ABORTADO: use caminho absoluto, sem '..', aspas nem barra invertida: {caminho!r}")
    return posixpath.normpath(caminho)


def confere_origem(origem):
    """So pasta da memoria INTERNA, nunca a raiz dela nem Android/ (dados de app, obb): o script apaga a origem."""
    partes = origem[len(INTERNA):].strip("/").split("/") if origem.startswith(INTERNA + "/") else []
    if not partes or not partes[0] or partes[0].lower() == "android":
        sys.exit(f"ABORTADO: origem {origem!r} nao permitida: use uma pasta DENTRO de {INTERNA}/ (DCIM, Download, "
                 "ARENA...), nunca a raiz dela nem Android/ (dados de app).")


def confere_destino_portatil(destino):
    """Aborta se o destino nao estiver claramente dentro de um cartao PORTATIL montado:
    nunca 'organizar' para dentro de armazenamento adotado (regra do projeto)."""
    portateis = [uuid for vid, estado, uuid in volumes()
                 if vid.startswith("public:") and estado == "mounted" and uuid not in ("", "null")]
    if not any(destino.startswith(f"/storage/{u}/") for u in portateis):
        sys.exit(f"ABORTADO: {destino!r} nao esta dentro de um cartao PORTATIL montado {portateis!r} (use uma "
                 "pasta DENTRO do cartao, nao a raiz dele). Nunca mover para armazenamento adotado.")


def relatorio():
    bases = [INTERNA + "/" + p for p in PASTAS_RELATORIO]
    saida = sh("du -sm " + " ".join(f"'{b}'" for b in bases) + " 2>/dev/null")
    linhas = [(int(m.group(1)), m.group(2)) for l in saida.splitlines() if (m := re.match(r"(\d+)\s+(.+)", l))]
    print("== Tamanho das pastas de midia na memoria interna (MB) ==")
    for mb, pasta in sorted(linhas, reverse=True):
        print(f"  {mb:>7} MB  {pasta}")
    print("\n== Cartoes disponiveis ==")
    for vid, estado, uuid in volumes():
        if vid.startswith(("public:", "private:")):
            tipo = "PORTATIL" if vid.startswith("public:") else "ADOTADO (nunca usar como destino)"
            local = f" | /storage/{uuid}" if uuid and uuid != "null" else ""
            print(f"  {vid} {tipo} | {estado}{local}")
    print("\nPara mover uma pasta: --origem <pasta interna> --destino <pasta no cartao portatil> [--aplicar]")


def hashes(caminho):
    """pasta -> {caminho relativo: md5}. Vazio se a pasta nao existir ou nao tiver arquivo."""
    saida = sh(f"find '{caminho}' -type f -exec md5sum {{}} +", timeout=1800)  # 6 GB lidos do cartao a 10 MB/s levam 10 min
    base = caminho.rstrip("/") + "/"
    out = {}
    for l in saida.splitlines():
        m = re.match(r"([0-9a-f]{32})\s+(.+)", l)
        if m and m.group(2).startswith(base):
            out[m.group(2)[len(base):]] = m.group(1)
    return out


def metadados(caminho):
    """pasta -> {caminho relativo: (tamanho em bytes, data de modificacao em segundos)}. O md5sum do toybox trata erro de
    leitura como fim de arquivo (copia truncada daria o mesmo md5 do trecho lido): o tamanho e a data fecham essa brecha."""
    saida = sh(f"find '{caminho}' -type f -printf '%s %T@ %P\\n'", timeout=1800)
    out = {}
    for l in saida.splitlines():
        m = re.match(r"(\d+) (\d+)(?:\.\d+)? (.+)", l)
        if m:
            out[m.group(3)] = (int(m.group(1)), int(m.group(2)))
    return out


def diferencas(antes_meta, depois_meta):
    """Arquivos que faltam ou diferem em tamanho ou data (alem de TOLERANCIA_DATA s)."""
    return {k: (v, depois_meta.get(k)) for k, v in antes_meta.items()
            if depois_meta.get(k) is None or depois_meta[k][0] != v[0] or abs(depois_meta[k][1] - v[1]) > TOLERANCIA_DATA}


def forca_descarte_de_cache():
    print("  gravando o que estiver pendente (sync) e descartando o cache (lendo /system, /vendor, /product; igual ao teste-gravacao.py)...")
    sh("sync", timeout=600)  # pagina suja nao sai da RAM: sem o sync a leitura "fria" do destino poderia vir da memoria
    sh("find /system /vendor /product /system_ext -type f -size +512k -exec cat {} + > /dev/null 2>&1; echo feito",
       timeout=1800)


def confere_antes_de_apagar(origem, destino, antes):
    """Ultima barreira antes do rm -rf: a origem so tem arquivo comum e pasta, o md5sum viu TODOS os arquivos
    (nome estranho ou ilegivel some do md5sum e seria apagado sem conferencia), o cartao segue montado com os arquivos
    la e nada chegou ou mudou na origem desde a conferencia (nem DURANTE esta ultima leitura: marca de tempo)."""
    incomuns = sh(f"find '{origem}' ! -type f ! -type d")
    if incomuns:
        sys.exit("ABORTADO: a origem tem item que nao e arquivo comum nem pasta (link, socket...); nada apagado:\n  "
                 + "\n  ".join(incomuns.splitlines()[:5]))
    total = sh(f"find '{origem}' -type f | wc -l").strip()
    if total != str(len(antes)):
        sys.exit(f"ABORTADO: a origem tem {total} arquivo(s) e o md5sum conferiu {len(antes)} (nome estranho, arquivo "
                 "ilegivel ou arquivo novo); nada apagado.")
    confere_destino_portatil(destino)
    no_cartao = sh(f"find '{destino}' -type f | wc -l").strip()
    if not no_cartao.isdigit() or int(no_cartao) < len(antes):
        sys.exit(f"ABORTADO: o cartao tem {no_cartao} arquivo(s) em {destino} e eram esperados pelo menos {len(antes)} "
                 "(cartao ejetado ou erro de leitura?); nada apagado.")
    sh(f"touch '{MARCA}'")
    if hashes(origem) != antes:
        sys.exit("ABORTADO: a origem mudou durante a conferencia (arquivo novo ou alterado); nada apagado. "
                 "Nao use o celular durante a organizacao.")
    mudou = sh(f"find '{origem}' -newer '{MARCA}'")
    if mudou:
        sys.exit("ABORTADO: algo na origem foi criado ou alterado durante a ultima leitura; nada apagado:\n  "
                 + "\n  ".join(mudou.splitlines()[:5]))


def mover(origem, destino, aplicar, apagar):
    if "No such" in sh(f"ls -d '{origem}' 2>&1"):
        sys.exit(f"ABORTADO: origem nao existe: {origem}")
    confere_destino_portatil(destino)
    antes = hashes(origem)
    if not antes:
        sys.exit(f"ABORTADO: nenhum arquivo encontrado em {origem}")
    meta_antes = metadados(origem)
    if set(meta_antes) != set(antes):  # sem isto a conferencia de tamanho e data passaria sem conferir nada
        sys.exit(f"ABORTADO: nao consegui ler tamanho e data de todos os arquivos da origem ({len(meta_antes)} de {len(antes)}); "
                 "a conferencia de copia truncada nao valeria. Nada copiado nem apagado.")
    print(f"{len(antes)} arquivo(s) em {origem}")
    if not aplicar:
        print("SIMULACAO: nada foi copiado. Use --aplicar para copiar de verdade.")
        return

    bateria_ok()
    ja_la = "No such" not in sh(f"ls -d '{destino}' 2>&1")
    if ja_la:
        no_destino = hashes(destino)
        if any(no_destino.get(k) != v for k, v in antes.items()):
            dif = diferencas(meta_antes, metadados(destino))
            lista = "\n".join(f"  {k}: origem {v[0]} bytes, destino {d[0] if d else 'FALTA'}" for k, (v, d) in list(dif.items())[:10])
            sys.exit(f"ABORTADO: {destino} ja existe e NAO tem tudo igual a origem; nada foi copiado nem misturado.\n{lista}\n"
                     "O destino pode ter dados MAIS NOVOS que a origem (por exemplo saves de um jogo aberto a partir do cartao): "
                     "NAO o apague sem conferir. Traga de volta o que for mais novo, ou escolha um destino que nao exista.")
        print(f"{destino} ja tem tudo igual: nao copio de novo, so confiro.")
    else:
        pai = destino.rsplit("/", 1)[0]
        sh(f"mkdir -p '{pai}'")
        print(f"copiando para {destino}...")
        saida_cp = sh(f"cp -rp '{origem}' '{destino}'", timeout=1800)  # -p: o cp -r do toybox perde as datas originais
        if saida_cp:
            print("o cp respondeu (confira; a conferencia abaixo decide):\n  " + "\n  ".join(saida_cp.splitlines()[:5]))
        iguais_na_hora = hashes(destino) == antes
        print(f"logo apos copiar (pode vir do cache, nao prova nada): {'OK' if iguais_na_hora else 'DIFERENTE'}")

    forca_descarte_de_cache()
    origem_depois = hashes(origem)
    if origem_depois != antes:
        sys.exit("ABORTADO: a propria ORIGEM mudou de hash depois do descarte de cache -- nao seguro continuar. Nada apagado.")

    destino_depois = hashes(destino)
    faltando = {k: v for k, v in antes.items() if destino_depois.get(k) != v}
    if faltando:
        print(f"CORROMPIDO OU FALTANDO no destino depois do descarte de cache: {len(faltando)} arquivo(s)")
        for k in list(faltando)[:10]:
            print(f"  {k}")
        sys.exit("ABORTADO: origem NAO apagada. Copia incompleta ou corrompida.")
    dif = diferencas(meta_antes, metadados(destino))
    if dif:
        print(f"TAMANHO OU DATA DIFERENTE no destino: {len(dif)} arquivo(s)")
        for k, (v, d) in list(dif.items())[:10]:
            print(f"  {k}: origem {v[0]} bytes, destino {d[0] if d else 'FALTA'}")
        sys.exit("ABORTADO: origem NAO apagada. Copia truncada ou sem as datas originais.")

    print(f"confirmado: {len(antes)} arquivo(s) iguais na origem e no destino (md5, tamanho e data), com o cache descartado.")
    if not apagar:
        print(f"origem MANTIDA em {origem} (nada apagado). Para apagar so a origem, depois de olhar o destino, repita "
              "o mesmo comando com --confirmo-apagar-origem.")
        return
    confere_antes_de_apagar(origem, destino, antes)
    sh(f"rm -rf '{origem}'", timeout=1800)
    sh("sync", timeout=600)
    if "No such" not in sh(f"ls -d '{origem}' 2>&1"):
        sys.exit(f"ATENCAO: o rm nao terminou: {origem} ainda existe (pela metade?). A copia no cartao esta inteira; confira antes de repetir.")
    print(f"origem apagada: {origem}")


def main():
    ap = argparse.ArgumentParser(allow_abbrev=False)  # sem abreviacao: --conf nao pode valer como --confirmo-apagar-origem
    ap.add_argument("--origem")
    ap.add_argument("--destino")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--confirmo-apagar-origem", action="store_true", dest="apagar")
    a = ap.parse_args()
    if "SM-A125" not in sh("getprop ro.product.model"):
        sys.exit("ABORTADO: aparelho nao encontrado ou inesperado")
    if not a.origem and not a.destino:
        if a.aplicar or a.apagar:
            sys.exit("Use --origem e --destino com --aplicar (ou nenhum dos quatro, para o relatorio).")
        relatorio()
        return
    if not (a.origem and a.destino):
        sys.exit("Use --origem e --destino juntos (ou nenhum dos dois, para o relatorio).")
    if a.apagar and not a.aplicar:
        sys.exit("--confirmo-apagar-origem so vale junto com --aplicar.")
    origem, destino = caminho_limpo(a.origem), caminho_limpo(a.destino)
    confere_origem(origem)
    mover(origem, destino, a.aplicar, a.apagar)


if __name__ == "__main__":
    main()
