#!/usr/bin/env python3
"""Mensagens de status do Univo: uma logica so para o PC (Hermes) e o celular (Qwen Code e `ia qwen`). 18/11/2026.

Duas etapas, iguais nos dois lados:
  1) primeira(pedido): assim que o pedido sai, uma tirada ligada ao ASSUNTO dele (palavras-chave do catalogo,
     sem chamar modelo nenhum: microssegundos, nenhuma latencia a mais);
  2) proxima(): enquanto o modelo ou a ferramenta trabalham, frases do catalogo de rotacao, sem repetir ate
     esgotar o baralho e nunca a mesma duas vezes seguidas.

Fonte unica: frases-status.json (ao lado). Espelho em JavaScript: status_univo.cjs (mesma normalizacao e mesma
classificacao; o teste test_status_univo.py confere os dois com os mesmos pedidos).

Uso (linha de comando):
  python status_univo.py classificar "texto"        a categoria
  python status_univo.py primeira "texto"           a 1a frase (contextual)
  python status_univo.py proxima [-n 5]             frases da rotacao
  python status_univo.py validar                    confere o catalogo (tamanho, duplicadas, palavras); saida 1 se falhar
  python status_univo.py girar "texto"              spinner no terminal (stderr) ate receber SIGTERM/SIGINT; o `ia qwen` usa
  python status_univo.py qwen-frases                as frases de rotacao para o customWittyPhrases do Qwen Code (JSON)
  python status_univo.py hermes-skin                a skin "univo" do Hermes (YAML) com as mesmas frases
  python status_univo.py qwen-patch conferir|aplicar|desfazer [--pacote DIR]
                                                    liga a 1a frase contextual no Qwen Code instalado (Termux)
"""
from __future__ import annotations

import json
import os
import random
import re
import signal
import sys
import threading
import time
import unicodedata
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CATALOGO = AQUI / "frases-status.json"
_ACENTOS = re.compile("[̀-ͯ]")
_NAO_ALNUM = re.compile("[^a-z0-9]+")
CATEGORIAS_FIXAS = ("curto", "longo", "generico")
LIMITE_LONGO = 600   # caracteres: acima disso, sem palavra-chave, e "longo"
LIMITE_CURTO = 3     # palavras: ate isso, sem palavra-chave, e "curto"
TTL_PENDENTE = 120.0  # segundos: a 1a frase espera o spinner aparecer ate isso


def carregar(caminho: Path | str | None = None) -> dict:
    with open(caminho or CATALOGO, encoding="utf-8") as f:
        return json.load(f)


def normalizar(texto: str) -> str:
    """minusculas, sem acento, so letras e numeros separados por 1 espaco (igual ao normalizar do .cjs)."""
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    t = _ACENTOS.sub("", t)
    return _NAO_ALNUM.sub(" ", t).strip()


def texto_do_pedido(obj) -> str:
    """O texto de um pedido em qualquer formato que os agentes usam: str, lista de partes, {"text": ...} ou {"content": ...}."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        for chave in ("text", "content", "prompt"):
            if chave in obj:
                return texto_do_pedido(obj[chave])
        return ""
    if isinstance(obj, (list, tuple)):
        return " ".join(p for p in (texto_do_pedido(x) for x in obj) if p)
    return ""


def _casa(texto_norm: str, palavra: str) -> bool:
    if palavra.endswith("*"):
        raiz = normalizar(palavra[:-1])
        return bool(raiz) and (" " + raiz) in (" " + texto_norm)
    p = normalizar(palavra)
    return bool(p) and (" " + p + " ") in (" " + texto_norm + " ")


def classificar(texto, catalogo: dict | None = None) -> str:
    """Categoria do pedido: mais pontos (palavras-chave casadas x peso da categoria; empate: a que vem antes no
    catalogo); sem nenhuma: 'longo' (> 600 caracteres), 'curto' (ate 3 palavras) ou 'generico'."""
    cat = catalogo or _catalogo_padrao()
    bruto = texto_do_pedido(texto)
    t = normalizar(bruto)
    melhor, pontos = None, 0
    for c in cat["contextual"]:
        n = sum(1 for p in c["palavras"] if _casa(t, p)) * int(c.get("peso", 1))
        if n > pontos:
            melhor, pontos = c["id"], n
    if melhor:
        return melhor
    if len(bruto.strip()) > LIMITE_LONGO:
        return "longo"
    if t and len(t.split()) <= LIMITE_CURTO:
        return "curto"
    return "generico"


def frases_da_categoria(cat_id: str, catalogo: dict | None = None) -> list[str]:
    cat = catalogo or _catalogo_padrao()
    if cat_id in CATEGORIAS_FIXAS:
        return list(cat[cat_id])
    for c in cat["contextual"]:
        if c["id"] == cat_id:
            return list(c["frases"])
    return list(cat["generico"])


_PADRAO = None


def _catalogo_padrao() -> dict:
    global _PADRAO
    if _PADRAO is None:
        _PADRAO = carregar()
    return _PADRAO


class Status:
    """Estado da selecao (seguro entre threads): ultima frase de cada categoria e o baralho da rotacao."""

    def __init__(self, catalogo: dict | None = None, rng: random.Random | None = None):
        self.cat = catalogo or _catalogo_padrao()
        self.rng = rng or random.Random()
        self.intervalo_s = float(self.cat.get("intervalo_s", 8))
        self._trava = threading.Lock()
        self._baralho: list[str] = []
        self._ultima = ""
        self._ultima_ctx: dict[str, str] = {}
        self._pendente: tuple[str, float] | None = None

    def primeira(self, texto) -> str:
        cat_id = classificar(texto, self.cat)
        opcoes = frases_da_categoria(cat_id, self.cat)
        with self._trava:
            antes = self._ultima_ctx.get(cat_id)
            escolha = [f for f in opcoes if f != antes] or opcoes
            frase = self.rng.choice(escolha)
            self._ultima_ctx[cat_id] = frase
            self._ultima = frase
        return frase

    def proxima(self) -> str:
        with self._trava:
            if not self._baralho:
                self._baralho = list(self.cat["rotacao"])
                self.rng.shuffle(self._baralho)
                if len(self._baralho) > 1 and self._baralho[-1] == self._ultima:
                    self._baralho.insert(0, self._baralho.pop())   # a de cima nao repete a ultima mostrada
            frase = self._baralho.pop()
            self._ultima = frase
        return frase

    # 1a frase guardada no envio do pedido e usada quando o spinner aparecer (Hermes e Qwen Code)
    def registrar_pedido(self, texto) -> str | None:
        bruto = texto_do_pedido(texto).strip()
        if not bruto or bruto[0] in "/!":   # comando de barra e modo shell nao sao pedido
            return None
        frase = self.primeira(bruto)
        with self._trava:
            self._pendente = (frase, time.monotonic())
        return frase

    def tomar_pendente(self) -> str | None:
        with self._trava:
            p, self._pendente = self._pendente, None
        if p and time.monotonic() - p[1] <= TTL_PENDENTE:
            return p[0]
        return None

    def primeira_ou_proxima(self) -> str:
        return self.tomar_pendente() or self.proxima()


def validar(cat: dict | None = None) -> list[str]:
    """Problemas do catalogo (lista vazia = ok)."""
    cat = cat or carregar()
    erros = []
    maximo = int(cat.get("max_caracteres", 44))
    vistos: dict[str, str] = {}
    ids = set()

    def frase_ok(f, onde):
        if not isinstance(f, str) or not f.strip():
            erros.append(f"{onde}: frase vazia")
            return
        if len(f) > maximo:
            erros.append(f"{onde}: {len(f)} > {maximo} caracteres: {f!r}")
        if f != f.strip() or f.endswith((".", "…")) or "\n" in f:
            erros.append(f"{onde}: sem ponto, reticencias, espaco ou quebra no fim: {f!r}")
        if f in vistos:
            erros.append(f"{onde}: repetida (ja em {vistos[f]}): {f!r}")
        vistos[f] = onde

    for c in cat.get("contextual", []):
        cid = c.get("id")
        if not cid or cid in ids or cid in CATEGORIAS_FIXAS:
            erros.append(f"categoria sem id ou repetida: {cid!r}")
        ids.add(cid)
        if not isinstance(c.get("peso", 1), int) or not 1 <= c.get("peso", 1) <= 9:
            erros.append(f"{cid}: peso inteiro de 1 a 9")
        if not c.get("palavras"):
            erros.append(f"{cid}: sem palavras-chave")
        for p in c.get("palavras", []):
            if p != p.lower() or normalizar(p.rstrip("*")) != p.rstrip("*").replace("-", " "):
                erros.append(f"{cid}: palavra-chave com maiuscula, acento ou simbolo: {p!r}")
        if len(c.get("frases", [])) < 2:
            erros.append(f"{cid}: precisa de 2 frases ou mais (para nao repetir)")
        for f in c.get("frases", []):
            frase_ok(f, cid)
    for chave in CATEGORIAS_FIXAS:
        if len(cat.get(chave, [])) < 2:
            erros.append(f"{chave}: precisa de 2 frases ou mais")
        for f in cat.get(chave, []):
            frase_ok(f, chave)
    if len(cat.get("rotacao", [])) < 30:
        erros.append("rotacao: o catalogo precisa de 30 frases ou mais")
    for f in cat.get("rotacao", []):
        frase_ok(f, "rotacao")
    if not 3 <= float(cat.get("intervalo_s", 0)) <= 30:
        erros.append("intervalo_s fora de 3 a 30 segundos")
    return erros


# ---------------------------------------------------------------- spinner de terminal (ia qwen no celular)
QUADROS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def girar(texto, saida=None, parar: threading.Event | None = None, maximo_s: float = 600.0, st: Status | None = None) -> int:
    """Desenha '⠋ frase…' numa linha, troca a frase a cada intervalo e apaga a linha ao parar.
    Para com o evento, SIGTERM/SIGINT, quando o processo pai morre (sem spinner orfao) ou em maximo_s."""
    saida = saida or sys.stderr
    parar = parar or threading.Event()
    st = st or Status()
    pai = os.getppid()
    frase, troca, i, t0 = st.primeira(texto), time.monotonic() + st.intervalo_s, 0, time.monotonic()
    try:
        while not parar.wait(0.12):
            agora = time.monotonic()
            if agora - t0 > maximo_s or (pai > 1 and os.getppid() != pai):
                break
            if agora >= troca:
                frase, troca = st.proxima(), agora + st.intervalo_s
            saida.write("\r\033[K" + QUADROS[i % len(QUADROS)] + " " + frase + "…")
            saida.flush()
            i += 1
    finally:
        try:
            saida.write("\r\033[K")
            saida.flush()
        except (OSError, ValueError):
            pass
    return 0


# ---------------------------------------------------------------- saidas para cada tela
def qwen_frases(cat: dict | None = None) -> list[str]:
    cat = cat or carregar()
    return [f + "…" for f in cat["rotacao"]]


ROSTOS_PENSANDO = ["[■_■]", "(¬_¬)", "(-_-)", "[o_o]", "(•_•)"]
ROSTOS_ESPERANDO = ["[■_■]", "(-_-)", "[>_<]", "(._.)"]


def hermes_skin(cat: dict | None = None) -> str:
    """Skin 'univo' do Hermes (so o spinner; cores herdadas da padrao). Strings JSON sao escalares YAML validos."""
    cat = cat or carregar()
    q = lambda s: json.dumps(s, ensure_ascii=False)   # noqa: E731
    linhas = ["# Gerada por status_univo.py hermes-skin (fonte: frases-status.json da casa-mae). Nao edite aqui.",
              "name: univo", "description: " + q("Univo: TARS + House + Alfred (frases de status do catalogo unico)"),
              "spinner:", "  thinking_faces: [" + ", ".join(q(r) for r in ROSTOS_PENSANDO) + "]",
              "  waiting_faces: [" + ", ".join(q(r) for r in ROSTOS_ESPERANDO) + "]", "  thinking_verbs:"]
    linhas += ["    - " + q(f) for f in cat["rotacao"]]
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------- patch do Qwen Code (1a frase contextual)
MARCA = "/*UNIVO-STATUS*/"
_CARREGA_JS = ('(globalThis.__univoStatus??=(()=>{try{const r=globalThis.require,p=r("node:path"),o=r("node:os");'
               'return r(p.join(o.homedir(),".qwen","univo-status","status_univo.cjs"))}catch(e){return false}})())||null')
CICLADOR_ANTES = ("const initialRandomIndex=Math.floor(Math.random()*loadingPhrases.length);"
                  "setCurrentLoadingPhrase(loadingPhrases[initialRandomIndex]);"
                  "phraseIntervalRef.current=setInterval(()=>{const randomIndex=Math.floor(Math.random()*loadingPhrases.length);"
                  "setCurrentLoadingPhrase(loadingPhrases[randomIndex])},PHRASE_CHANGE_INTERVAL_MS)")
CICLADOR_DEPOIS = (MARCA + "const __u=" + _CARREGA_JS + ";"
                   "const initialRandomIndex=Math.floor(Math.random()*loadingPhrases.length);"
                   "setCurrentLoadingPhrase(__u?__u.primeiraOuProxima():loadingPhrases[initialRandomIndex]);"
                   "phraseIntervalRef.current=setInterval(()=>{const randomIndex=Math.floor(Math.random()*loadingPhrases.length);"
                   "setCurrentLoadingPhrase(__u?__u.proxima():loadingPhrases[randomIndex])},__u?__u.intervaloMs:PHRASE_CHANGE_INTERVAL_MS)")
_ENVIO = re.compile(r'const submitQuery=\(0,import_react\d+\.useCallback\)\(async\(query,submitType="userQuery",prompt_id,metadata\)=>\{')
ENVIO_DEPOIS = MARCA + 'try{if(submitType==="userQuery"){const __u=' + _CARREGA_JS + ';__u&&__u.registrarPedido(query)}}catch(e){}'
SUFIXO_ORIGINAL = ".univo-orig"


def _pacote_qwen() -> Path:
    prefixo = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    return Path(prefixo) / "lib" / "node_modules" / "@qwen-code" / "qwen-code"


def _alvos_qwen(pacote: Path) -> tuple[Path | None, Path | None]:
    """(arquivo do ciclador de frases, arquivo do envio do pedido) pelo conteudo: o nome do pedaco muda a cada versao."""
    ciclador = envio = None
    for arq in sorted((pacote / "chunks").glob("*.js")):
        try:
            txt = arq.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if ciclador is None and ("var usePhraseCycler=" in txt) and (CICLADOR_ANTES in txt or CICLADOR_DEPOIS in txt):
            ciclador = arq
        if envio is None and (_ENVIO.search(txt) or (MARCA + 'try{if(submitType==="userQuery")') in txt):
            envio = arq
    return ciclador, envio


def qwen_patch(acao: str, pacote: Path | None = None, checar=None) -> tuple[int, str]:
    """conferir: 0 = ligado, 1 = desligado/parcial. aplicar: idempotente, guarda o original (.univo-orig) e confere a
    sintaxe com `node --check`; se algo falhar, devolve o original. desfazer: volta os originais."""
    pacote = Path(pacote) if pacote else _pacote_qwen()
    if not (pacote / "chunks").is_dir():
        return 1, f"Qwen Code nao encontrado em {pacote}"
    ciclador, envio = _alvos_qwen(pacote)
    if acao == "desfazer":
        voltou = []
        for arq in (pacote / "chunks").glob("*.js" + SUFIXO_ORIGINAL):
            destino = arq.with_name(arq.name[: -len(SUFIXO_ORIGINAL)])
            os.replace(arq, destino)
            voltou.append(destino.name)
        return 0, ("originais devolvidos: " + ", ".join(voltou)) if voltou else "nada a desfazer (sem patch)"
    if not ciclador or not envio:
        return 1, ("esta versao do Qwen Code mudou o codigo do spinner ou do envio (ciclador=%s, envio=%s): "
                   "fica so a rotacao do customWittyPhrases" % (bool(ciclador), bool(envio)))
    ligado = (MARCA + "const __u=" in ciclador.read_text(encoding="utf-8")
              and MARCA + 'try{if(submitType==="userQuery")' in envio.read_text(encoding="utf-8"))
    if acao == "conferir":
        return (0, "1a frase contextual ligada no Qwen Code") if ligado else (1, "1a frase contextual desligada")
    if acao != "aplicar":
        return 2, "acao: conferir, aplicar ou desfazer"
    if ligado:
        return 0, "ja estava ligado"
    novos = {}
    for arq in {ciclador, envio}:
        txt = novos.get(arq, arq.read_text(encoding="utf-8"))
        if arq == ciclador and MARCA + "const __u=" not in txt:
            txt = txt.replace(CICLADOR_ANTES, CICLADOR_DEPOIS, 1)
        if arq == envio and MARCA + "try{" not in txt:
            txt = _ENVIO.sub(lambda m: m.group(0) + ENVIO_DEPOIS, txt, count=1)
        novos[arq] = txt
    checar = checar or _node_check
    feitos = []
    try:
        for arq, txt in novos.items():
            tmp = arq.with_name(arq.stem + ".univo-novo.js")   # .js no fim: o node --check recusa outra extensao
            tmp.write_text(txt, encoding="utf-8")
            erro = checar(tmp)
            if erro:
                tmp.unlink(missing_ok=True)
                raise RuntimeError(f"{arq.name}: {erro}")
            orig = arq.with_name(arq.name + SUFIXO_ORIGINAL)
            if not orig.exists():
                orig.write_bytes(arq.read_bytes())
            os.replace(tmp, arq)
            feitos.append(arq)
    except Exception as e:  # noqa: BLE001 - volta tudo o que trocou
        for arq in feitos:
            orig = arq.with_name(arq.name + SUFIXO_ORIGINAL)
            if orig.exists():
                os.replace(orig, arq)
        return 1, f"patch nao aplicado (original mantido): {e}"
    return 0, "1a frase contextual ligada (%s)" % ", ".join(sorted(a.name for a in novos))


def _node_check(arq: Path) -> str:
    import subprocess
    try:
        p = subprocess.run(["node", "--check", str(arq)], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"node --check nao rodou: {e}"
    return "" if p.returncode == 0 else (p.stderr or p.stdout).strip()[-300:]


# ---------------------------------------------------------------- linha de comando
def principal(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="mensagens de status do Univo (PC e celular)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nome in ("classificar", "primeira", "girar"):
        sub.add_parser(nome).add_argument("texto", nargs="*")
    sub.add_parser("proxima").add_argument("-n", type=int, default=1)
    sub.add_parser("validar")
    sub.add_parser("qwen-frases")
    sub.add_parser("hermes-skin")
    qp = sub.add_parser("qwen-patch")
    qp.add_argument("acao", choices=("conferir", "aplicar", "desfazer"))
    qp.add_argument("--pacote")
    a = ap.parse_args(argv)
    if a.cmd == "classificar":
        print(classificar(" ".join(a.texto)))
    elif a.cmd == "primeira":
        print(Status().primeira(" ".join(a.texto)))
    elif a.cmd == "proxima":
        st = Status()
        for _ in range(max(1, a.n)):
            print(st.proxima())
    elif a.cmd == "validar":
        erros = validar()
        print("\n".join(erros) if erros else "catalogo ok")
        return 1 if erros else 0
    elif a.cmd == "qwen-frases":
        print(json.dumps(qwen_frases(), ensure_ascii=False))
    elif a.cmd == "hermes-skin":
        sys.stdout.write(hermes_skin())
    elif a.cmd == "girar":
        if not sys.stderr.isatty():
            return 0
        ev = threading.Event()
        for s in (signal.SIGTERM, signal.SIGINT, getattr(signal, "SIGHUP", None)):
            if s is not None:
                signal.signal(s, lambda *_: ev.set())
        return girar(" ".join(a.texto), parar=ev)
    elif a.cmd == "qwen-patch":
        cod, msg = qwen_patch(a.acao, a.pacote)
        print(msg)
        return cod
    return 0


if __name__ == "__main__":
    sys.exit(principal())
