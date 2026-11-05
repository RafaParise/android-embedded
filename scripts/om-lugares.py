#!/usr/bin/env python3
"""Lugares no Organic Maps do A12: valida, importa (listas KML OCULTAS) e mede o custo (abertura a frio e memoria).

Pedido do Rafael, 31/10: achar lojas, escolas e servicos pelo NOME no Organic Maps, "como o Maps". Fatos medidos no aparelho
(Organic Maps 2026.09.29, 31/10; memoria/DECISOES.md):
  - a barra de busca PRINCIPAL so acha o mapa (OpenStreetMap), NAO acha favoritos importados;
  - o botao Buscar DENTRO da lista (Marcadores -> lista -> Buscar) acha pelo nome, e a pagina do lugar tem "ROTA DE/PARA";
  - <visibility>0</visibility> no <Document> importa a lista OCULTA (sem pinos no mapa; botao "Mostrar");
  - importar por file:// falha; o que funciona e content://media/external/file/<id> com --grant-read-uri-permission;
  - com 12.516 favoritos em 3 listas: abertura a frio 417 a 481 ms e PSS total de 304454 KB (297 MiB; o meminfo fala em KB).

  python scripts/om-lugares.py importar ARQ.kml [ARQ.kml ...]            SIMULACAO: valida o arquivo e mostra o plano (nao toca o aparelho)
  python scripts/om-lugares.py importar ARQ.kml [...] --aplicar          copia para /sdcard/Download e abre no Organic Maps, um por vez
  python scripts/om-lugares.py limpar-copias ARQ.kml [...] --aplicar     apaga a COPIA em /sdcard/Download (a lista importada fica no app)
  python scripts/om-lugares.py medir                                     abre o Organic Maps a frio 3x e le a memoria (FECHA o app antes)

Limites honestos: o script nao consegue ver dentro do Organic Maps (os dados ficam na area privada dele, sem root), entao NAO
confirma que a lista apareceu: confira em Marcadores. Um KML grande demora a importar: use --espera maior. Para apagar uma lista
importada, use o menu da lista no proprio app (Apagar). O texto vem de bases abertas (OpenStreetMap, INEP, Overture Maps): pode haver
lugar fechado ou com coordenada aproximada.
"""
import codecs
import argparse
import pathlib
import re
import statistics
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

PACOTE = "app.organicmaps"
ATIVIDADE = "app.organicmaps/.SplashActivity"
PASTA_CELULAR = "/sdcard/Download"
CAMINHO_MEDIA = "/storage/emulated/0/Download"
MIME_KML = "application/vnd.google-earth.kml+xml"
BRASIL = (-75.0, -35.0, -30.0, 6.0)  # lon_min, lat_min, lon_max, lat_max (folga de proposito)
APPS_EM_USO = ("app.organicmaps", "net.sourceforge.opencamera")  # dashcam: nao fechar no meio de uma gravacao
LIMITE_VISIVEL = 2000  # lista sem <visibility>0</visibility> com mais lugares que isso enche o mapa de pinos
REFERENCIA = "referencia de 31/10 com 12.516 lugares: abertura a frio 417 a 481 ms, PSS total 304454 KB (297 MiB)"
RE_NOME_KML = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.kml")


def sh(cmd, timeout=120):
    r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).replace("\r", "").strip()


def empurra(local, remoto, timeout=900):
    r = subprocess.run(["adb", "push", str(local), remoto], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def nome_seguro(nome):
    """O nome vai para o shell do aparelho (push, content query, rm): so letras, numeros, ponto, hifen e sublinhado, terminando em .kml."""
    if not RE_NOME_KML.fullmatch(nome) or ".." in nome:
        sys.exit(f"ABORTADO: nome de arquivo invalido (so letras, numeros, ponto, hifen e sublinhado, terminando em .kml): {nome!r}")
    return nome


def recusa_doctype(caminho, bloco=1 << 20):
    """Recusa DOCTYPE/ENTITY em QUALQUER ponto do arquivo (nao so no inicio) e texto que nao e UTF-8/ASCII (UTF-16 escapa
    de uma busca por bytes). Le em blocos, com sobreposicao, sem carregar o arquivo inteiro."""
    cauda = b""
    primeiro = True
    with open(caminho, "rb") as f:
        while True:
            dados = f.read(bloco)
            if not dados:
                return
            if primeiro and dados.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
                raise ValueError("KML em UTF-16 (recusado: so UTF-8, para a trava de DOCTYPE/ENTITY valer)")
            primeiro = False
            if bytes(1) in dados:
                raise ValueError("byte nulo no KML (UTF-16 ou binario; recusado: so UTF-8)")
            janela = (cauda + dados).lower()
            if b"<!doctype" in janela or b"<!entity" in janela:
                raise ValueError("DOCTYPE/ENTITY no arquivo (recusado: expansao de entidades)")
            cauda = janela[-16:]


def valida_kml(caminho):
    """Le o KML sem carregar tudo na memoria. Devolve {lugares, sem_nome, sem_coordenada, fora_do_brasil, titulo, oculta, bytes}.
    Levanta ValueError se o arquivo nao serve (XML quebrado, DOCTYPE/ENTITY, nenhum lugar)."""
    caminho = pathlib.Path(caminho)
    recusa_doctype(caminho)
    info = {"lugares": 0, "sem_nome": 0, "sem_coordenada": 0, "fora_do_brasil": 0, "titulo": "", "oculta": False,
            "bytes": caminho.stat().st_size}
    pilha = []
    try:
        for evento, el in ET.iterparse(str(caminho), events=("start", "end")):
            tag = el.tag.rsplit("}", 1)[-1]
            if evento == "start":
                pilha.append(tag)
                continue
            pilha.pop()
            pai = pilha[-1] if pilha else ""
            if tag == "name" and pai == "Document" and not info["titulo"]:
                info["titulo"] = (el.text or "").strip()
            elif tag == "visibility" and pai == "Document":
                info["oculta"] = (el.text or "").strip() == "0"
            elif tag == "Placemark":
                info["lugares"] += 1
                if not (el.findtext("{*}name") or "").strip():
                    info["sem_nome"] += 1
                partes = (el.findtext(".//{*}coordinates") or "").strip().split(",")
                try:
                    lon, lat = float(partes[0]), float(partes[1])
                except (ValueError, IndexError):
                    info["sem_coordenada"] += 1
                else:
                    if not (BRASIL[0] <= lon <= BRASIL[2] and BRASIL[1] <= lat <= BRASIL[3]):
                        info["fora_do_brasil"] += 1
                el.clear()
    except ET.ParseError as erro:
        raise ValueError(f"XML quebrado: {erro}") from None
    if info["lugares"] == 0:
        raise ValueError("nenhum <Placemark> no arquivo")
    return info


def confere_aparelho(precisa_espaco_kb=0):
    """Aborta se nao for o A12, se o Organic Maps nao estiver instalado, se a bateria estiver abaixo de 3% sem carregar ou faltar espaco."""
    if "SM-A125" not in sh("getprop ro.product.model"):
        sys.exit("ABORTADO: aparelho nao encontrado ou inesperado")
    if f"package:{PACOTE}" not in sh(f"pm list packages {PACOTE}").split():
        sys.exit(f"ABORTADO: {PACOTE} (Organic Maps) nao esta instalado")
    bat = sh("dumpsys battery")
    nivel = re.search(r"level:\s*(\d+)", bat)
    carregando = re.search(r"(AC|USB|Wireless) powered:\s*true", bat)
    if not nivel or int(nivel.group(1)) < 3 or not carregando:
        sys.exit("ABORTADO: bateria abaixo de 3% ou fora do carregador (regra do projeto: 3% e carregando)")
    if precisa_espaco_kb:
        linhas = sh("df -k /sdcard").splitlines()
        try:
            livre = int(linhas[-1].split()[3])
        except (IndexError, ValueError):
            sys.exit("ABORTADO: nao consegui ler o espaco livre do /sdcard")
        if livre < precisa_espaco_kb:
            sys.exit(f"ABORTADO: falta espaco no /sdcard ({livre // 1024} MB livres, preciso de {precisa_espaco_kb // 1024} MB)")


def id_no_mediastore(nome, tentativas=15):
    """O MediaStore demora alguns segundos para indexar o arquivo recem-copiado: pergunta de novo ate achar o _id."""
    consulta = (f"content query --uri content://media/external/file --projection _id "
                f"--where \"_data='{CAMINHO_MEDIA}/{nome}'\"")
    for _ in range(tentativas):
        achou = re.search(r"\b_id=(\d+)", sh(consulta))
        if achou:
            return int(achou.group(1))
        time.sleep(1)
    return None


def importar(arquivos, aplicar, espera, visivel):
    caminhos = [pathlib.Path(a) for a in arquivos]
    total_kb = 0
    for c in caminhos:
        nome_seguro(c.name)
        if not c.is_file():
            sys.exit(f"ABORTADO: arquivo nao existe: {c}")
        try:
            info = valida_kml(c)
        except ValueError as erro:
            sys.exit(f"ABORTADO: {c.name}: {erro}")
        total_kb += info["bytes"] // 1024 + 1
        aviso = []
        if info["sem_nome"]:
            aviso.append(f"{info['sem_nome']} sem nome")
        if info["sem_coordenada"]:
            aviso.append(f"{info['sem_coordenada']} sem coordenada")
        if info["fora_do_brasil"]:
            aviso.append(f"{info['fora_do_brasil']} fora do Brasil")
        print(f"  {c.name}: {info['lugares']} lugares, {info['bytes'] / 1048576:.1f} MB, "
              f"{'oculta' if info['oculta'] else 'VISIVEL'}, titulo {info['titulo']!r}" + (" | AVISO: " + ", ".join(aviso) if aviso else ""))
        if not info["oculta"] and info["lugares"] > LIMITE_VISIVEL and not visivel:
            sys.exit(f"ABORTADO: {c.name} tem {info['lugares']} lugares sem <visibility>0</visibility>: o mapa ficaria cheio de pinos "
                     f"e pesado. Gere a lista oculta ou use --visivel se for isso mesmo.")
        if info["sem_coordenada"] or info["sem_nome"] == info["lugares"]:
            sys.exit(f"ABORTADO: {c.name} tem lugares sem coordenada ou todos sem nome: arquivo mal gerado")
    if not aplicar:
        print("SIMULACAO: nada foi copiado nem aberto. Use --aplicar (um arquivo por vez no app; "
              f"espera de {espera} s entre eles).")
        return 0

    confere_aparelho(precisa_espaco_kb=total_kb * 3)
    for i, c in enumerate(caminhos):
        remoto = f"{PASTA_CELULAR}/{c.name}"
        ok, saida = empurra(c, remoto)
        if not ok:
            print(f"  FALHOU ao copiar {c.name}: {saida[:200]}")
            return 1
        sh(f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://{remoto}")
        _id = id_no_mediastore(c.name)
        if _id is None:
            print(f"  FALHOU: o MediaStore nao indexou {c.name} (tente de novo; a copia ficou em {remoto})")
            return 1
        saida = sh(f"am start --grant-read-uri-permission -a android.intent.action.VIEW "
                   f"-d content://media/external/file/{_id} -t {MIME_KML} -p {PACOTE}")
        if "Error" in saida or "Exception" in saida:
            print(f"  FALHOU ao abrir {c.name} no Organic Maps: {saida[:200]}")
            return 1
        print(f"  aberto no Organic Maps: {c.name} (id {_id}). Confira em Marcadores se a lista apareceu.")
        if i < len(caminhos) - 1:
            time.sleep(espera)
    print("FEITO. Depois de conferir, apague as copias: om-lugares.py limpar-copias <nomes> --aplicar")
    return 0


def limpar_copias(nomes, aplicar):
    for n in nomes:
        nome_seguro(n)
    if not aplicar:
        for n in nomes:
            print(f"  apagaria {PASTA_CELULAR}/{n}")
        print("SIMULACAO: nada foi apagado. Use --aplicar.")
        return 0
    falhas = 0
    for n in nomes:
        remoto = f"{PASTA_CELULAR}/{n}"
        sh(f"rm -f {remoto}")
        sh(f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://{remoto}")
        if "SUMIU" in sh(f"[ -e {remoto} ] && echo AINDA_EXISTE || echo SUMIU"):
            print(f"  apagado: {remoto}")
        else:
            print(f"  FALHOU: {remoto} continua no aparelho (ou o adb nao respondeu)")
            falhas += 1
    return 1 if falhas else 0


def em_primeiro_plano():
    """Apps do dashcam que estao em primeiro plano agora (mResumedActivity / topResumedActivity)."""
    saida = sh("dumpsys activity activities", timeout=90)
    linhas = [ln for ln in saida.splitlines() if re.search(r"mResumedActivity|topResumedActivity|ResumedActivity:", ln)]
    return sorted({app for app in APPS_EM_USO for ln in linhas if f"{app}/" in ln})


def medir(forcar, vezes):
    if "SM-A125" not in sh("getprop ro.product.model"):
        sys.exit("ABORTADO: aparelho nao encontrado ou inesperado")
    ocupados = em_primeiro_plano()
    if ocupados and not forcar:
        sys.exit("ABORTADO: em primeiro plano agora (pode ser o dashcam gravando): " + ", ".join(ocupados)
                 + ". Medir FECHA o Organic Maps; use --forcar se tiver certeza.")
    tempos = []
    for _ in range(vezes):
        sh(f"am force-stop {PACOTE}")
        time.sleep(2)
        saida = sh(f"am start -W -n {ATIVIDADE}", timeout=60)
        m = re.search(r"TotalTime:\s*(\d+)", saida)
        if not m:
            print(f"  FALHOU: o Organic Maps nao abriu ({saida[:160]!r})")
            return 1
        tempos.append(int(m.group(1)))
        time.sleep(1)
    time.sleep(4)
    mem = sh(f"dumpsys meminfo {PACOTE}", timeout=60)
    pss = re.search(r"TOTAL PSS:\s*(\d+)", mem)
    nativo = re.search(r"^\s*Native Heap\s+(\d+)", mem, re.M)
    if not pss:
        print("  FALHOU: nao consegui ler a memoria (dumpsys meminfo)")
        return 1
    kb = int(pss.group(1))  # o dumpsys meminfo fala em KB (1024 bytes)
    linha = f"memoria do app: PSS total {kb} KB ({round(kb / 1024)} MiB)"
    if nativo:
        linha += f", Native Heap {int(nativo.group(1))} KB ({round(int(nativo.group(1)) / 1024)} MiB)"
    print(f"abertura a frio (ms): {' / '.join(map(str, tempos))}  (mediana {int(statistics.median(tempos))})")
    print(linha)
    print(REFERENCIA)
    return 0


def main():
    ap = argparse.ArgumentParser(description="Lugares no Organic Maps do A12 (importar listas KML ocultas e medir o custo).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("importar", help="valida e importa listas KML (simulacao sem --aplicar)")
    p.add_argument("arquivos", nargs="+")
    p.add_argument("--aplicar", action="store_true")
    p.add_argument("--espera", type=int, default=30, help="segundos entre um arquivo e o proximo (padrao 30)")
    p.add_argument("--visivel", action="store_true", help="aceita lista grande sem <visibility>0</visibility>")
    p = sub.add_parser("limpar-copias", help="apaga as copias dos KML em /sdcard/Download (simulacao sem --aplicar)")
    p.add_argument("nomes", nargs="+")
    p.add_argument("--aplicar", action="store_true")
    p = sub.add_parser("medir", help="abertura a frio e memoria do Organic Maps (fecha o app)")
    p.add_argument("--forcar", action="store_true", help="mede mesmo com o Organic Maps ou o Open Camera em primeiro plano")
    p.add_argument("--vezes", type=int, default=3)
    a = ap.parse_args()
    if a.cmd == "importar":
        if not 0 <= a.espera <= 600:
            sys.exit("ABORTADO: --espera entre 0 e 600 segundos")
        sys.exit(importar(a.arquivos, a.aplicar, a.espera, a.visivel))
    if a.cmd == "limpar-copias":
        if a.aplicar:
            confere_aparelho()
        sys.exit(limpar_copias(a.nomes, a.aplicar))
    if not 1 <= a.vezes <= 10:
        sys.exit("ABORTADO: --vezes entre 1 e 10")
    sys.exit(medir(a.forcar, a.vezes))


if __name__ == "__main__":
    main()
