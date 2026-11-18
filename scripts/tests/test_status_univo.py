"""Mensagens de status do Univo (18/11/2026): catalogo unico em scripts/celular-kit/status/frases-status.json, logica em
status_univo.py (PC: plugin do Hermes; celular: `ia qwen` e o instalador) e o espelho status_univo.cjs (Qwen Code).
Os testes do espelho em JavaScript precisam do node (no Windows ha; no WSL sem node eles pulam).
"""
import importlib.util
import io
import json
import pathlib
import random
import shutil
import subprocess
import threading
import time

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
STATUS = RAIZ / "scripts" / "celular-kit" / "status"
NODE = shutil.which("node")   # resolvido antes do conftest esvaziar o PATH
precisa_node = pytest.mark.skipif(not NODE, reason="sem node nesta maquina (o espelho .cjs nao roda)")


def _mod():
    spec = importlib.util.spec_from_file_location("status_univo", STATUS / "status_univo.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


S = _mod()
CAT = S.carregar()

CASOS = {
    "libere a net da esxola por favor para mim": "filtro_escola",
    "como driblar o filtro da rede da escola": "filtro_escola",
    "ligar a lanterna": "celular",
    "Liga o Wi-Fi e abaixa o brilho": "celular",
    "o script deu erro no python": "erro",
    "meu código não funciona, dá traceback": "erro",
    "refatore a função de login em Java": "codigo",
    "revise este parágrafo": "revisar",
    "resuma este texto": "resumo",
    "escreva um e-mail para a coordenação": "texto",
    "monte o plano de aula da semana": "aula",
    "ligar o PC via LAN": "ligar_pc",
    "organize a pasta de downloads": "arquivos",
    "pesquise quem foi Alan Turing": "pesquisa",
    "me explica como funciona o DNS": "explicar",
    "traduza para o inglês": "traduzir",
    "calcule 15% de 230": "conta",
    "qual é melhor, java ou python?": "decidir",
    "sei lá, faz pra mim rapidinho": "preguica",
    "lembre que amanhã tem reunião": "memoria",
    "toca uma música no youtube": "midia",
    "telemetria do pc conectado": "telemetria",
    "oi": "saudacao",
    "Bom dia!": "saudacao",
    "obrigado": "agradecimento",
    "1": "curto",
    "e agora?": "curto",
    "": "generico",
    "preciso daquilo que conversamos ontem sobre o projeto": "generico",
    "x" * 700: "longo",
}


def test_catalogo_valido():
    assert S.validar(CAT) == []


def test_frases_cabem_na_tela_do_celular_com_reticencias():
    maximo = CAT["max_caracteres"]
    todas = CAT["rotacao"] + CAT["curto"] + CAT["longo"] + CAT["generico"] + [f for c in CAT["contextual"] for f in c["frases"]]
    assert maximo <= 44 and all(len(f) + 1 <= maximo + 1 for f in todas)
    assert all(len(f) <= maximo + 1 for f in S.qwen_frases(CAT))
    assert len(CAT["rotacao"]) >= 60   # catalogo extenso: ~8 minutos sem repetir com troca a cada 8 s


def test_validar_aponta_frase_longa_repetida_e_palavra_com_acento():
    ruim = json.loads(json.dumps(CAT))
    ruim["rotacao"].append("x" * 60)
    ruim["rotacao"].append(ruim["rotacao"][0])
    ruim["contextual"][0]["palavras"].append("Ação")
    ruim["contextual"][1]["frases"].append("termina com ponto.")
    erros = "\n".join(S.validar(ruim))
    assert "60 > 44" in erros and "repetida" in erros and "acento" in erros and "ponto" in erros


@pytest.mark.parametrize("texto,esperada", list(CASOS.items()))
def test_classifica_pelo_assunto(texto, esperada):
    assert S.classificar(texto, CAT) == esperada


def test_texto_do_pedido_aceita_partes_e_dicionarios():
    assert S.texto_do_pedido([{"text": "ligar"}, {"text": "a lanterna"}]) == "ligar a lanterna"
    assert S.texto_do_pedido({"content": [{"type": "text", "text": "oi"}]}) == "oi"
    assert S.classificar([{"text": "o script deu erro"}], CAT) == "erro"


def test_primeira_vem_da_categoria_e_nao_repete_em_seguida():
    st = S.Status(CAT, random.Random(1))
    opcoes = S.frases_da_categoria("erro", CAT)
    anteriores = [st.primeira("deu erro de novo") for _ in range(30)]
    assert all(f in opcoes for f in anteriores)
    assert all(a != b for a, b in zip(anteriores, anteriores[1:]))


def test_rotacao_percorre_o_baralho_inteiro_sem_repetir_seguidas():
    st = S.Status(CAT, random.Random(7))
    n = len(CAT["rotacao"])
    vistas = [st.proxima() for _ in range(n * 5)]
    assert all(a != b for a, b in zip(vistas, vistas[1:]))
    for k in range(5):
        assert sorted(vistas[k * n:(k + 1) * n]) == sorted(CAT["rotacao"])


def test_primeira_pendente_vale_uma_vez_e_expira(monkeypatch):
    st = S.Status(CAT, random.Random(3))
    assert st.registrar_pedido("/model") is None and st.registrar_pedido("!ls") is None
    f = st.registrar_pedido("o script deu erro")
    assert f in S.frases_da_categoria("erro", CAT)
    assert st.primeira_ou_proxima() == f
    assert st.primeira_ou_proxima() in CAT["rotacao"]
    agora = time.monotonic()
    st.registrar_pedido("resuma isto")
    monkeypatch.setattr(S.time, "monotonic", lambda: agora + S.TTL_PENDENTE + 1)
    assert st.tomar_pendente() is None


def test_girar_mostra_a_contextual_troca_e_apaga_a_linha_ao_parar():
    cat = json.loads(json.dumps(CAT))
    cat["intervalo_s"] = 0.2
    st = S.Status(cat, random.Random(5))
    saida, parar = io.StringIO(), threading.Event()
    t = threading.Thread(target=S.girar, args=("o script deu erro",), kwargs={"saida": saida, "parar": parar, "st": st})
    t.start()
    time.sleep(0.7)
    parar.set()
    t.join(2)
    assert not t.is_alive()   # o laco termina quando pedem para parar
    texto = saida.getvalue()
    assert any(f + "…" in texto for f in S.frases_da_categoria("erro", cat))
    assert any(f + "…" in texto for f in cat["rotacao"])
    assert texto.endswith("\r\033[K")   # a linha some: nada de spinner por cima da resposta


def test_girar_para_sozinho_no_tempo_maximo():
    saida = io.StringIO()
    t0 = time.monotonic()
    S.girar("oi", saida=saida, maximo_s=0.3)
    assert time.monotonic() - t0 < 2 and saida.getvalue().endswith("\r\033[K")


def test_skin_do_hermes_traz_as_mesmas_frases():
    yaml = pytest.importorskip("yaml")
    skin = yaml.safe_load(S.hermes_skin(CAT))
    assert skin["name"] == "univo" and skin["spinner"]["thinking_verbs"] == CAT["rotacao"]
    assert skin["spinner"]["thinking_faces"] and skin["spinner"]["waiting_faces"]


# ------------------------------------------------------------------ patch do Qwen Code (pacote falso)
CICLADOR_JS = ("var usePhraseCycler=__name((isActive,isWaiting,customPhrases)=>{const loadingPhrases=customPhrases;"
               "const phraseIntervalRef={current:null};function setCurrentLoadingPhrase(x){}if(isActive){"
               + S.CICLADOR_ANTES + "}},\"usePhraseCycler\");")
ENVIO_JS = ('const submitQuery=(0,import_react119.useCallback)(async(query,submitType="userQuery",prompt_id,metadata)=>{return 1});')


def _pacote(tmp_path, junto=False):
    chunks = tmp_path / "qwen" / "chunks"
    chunks.mkdir(parents=True)
    if junto:
        (chunks / "chunk-A.js").write_text(CICLADOR_JS + ENVIO_JS, encoding="utf-8")
    else:
        (chunks / "chunk-A.js").write_text(CICLADOR_JS, encoding="utf-8")
        (chunks / "startInteractiveUI-X.js").write_text(ENVIO_JS, encoding="utf-8")
    (chunks / "outro.js").write_text("var x=1;", encoding="utf-8")
    return tmp_path / "qwen"


@pytest.mark.parametrize("junto", [False, True])
def test_patch_aplica_uma_vez_confere_e_desfaz(tmp_path, junto):
    pac = _pacote(tmp_path, junto)
    antes = {p.name: p.read_text(encoding="utf-8") for p in (pac / "chunks").glob("*.js")}
    assert S.qwen_patch("conferir", pac)[0] == 1
    cod, msg = S.qwen_patch("aplicar", pac, checar=lambda arq: "")
    assert cod == 0, msg
    assert S.qwen_patch("conferir", pac)[0] == 0
    depois = {p.name: p.read_text(encoding="utf-8") for p in (pac / "chunks").glob("*.js")}
    assert S.qwen_patch("aplicar", pac, checar=lambda arq: "") == (0, "ja estava ligado")
    assert {p.name: p.read_text(encoding="utf-8") for p in (pac / "chunks").glob("*.js")} == depois   # idempotente
    junto_txt = "".join(depois.values())
    assert junto_txt.count(S.MARCA) == 2 and "registrarPedido(query)" in junto_txt and "primeiraOuProxima()" in junto_txt
    assert S.qwen_patch("desfazer", pac)[0] == 0
    assert {p.name: p.read_text(encoding="utf-8") for p in (pac / "chunks").glob("*.js")} == antes


def test_patch_com_erro_de_sintaxe_mantem_o_original(tmp_path):
    pac = _pacote(tmp_path)
    antes = {p.name: p.read_text(encoding="utf-8") for p in (pac / "chunks").glob("*.js")}
    erros = iter(["", "SyntaxError: x"])
    cod, msg = S.qwen_patch("aplicar", pac, checar=lambda arq: next(erros))
    assert cod == 1 and "original mantido" in msg
    assert {p.name: p.read_text(encoding="utf-8") for p in (pac / "chunks").glob("*.js")} == antes


def test_patch_em_versao_que_mudou_nao_mexe_em_nada(tmp_path):
    chunks = tmp_path / "q" / "chunks"
    chunks.mkdir(parents=True)
    (chunks / "a.js").write_text("var usePhraseCycler=1;", encoding="utf-8")
    cod, msg = S.qwen_patch("aplicar", tmp_path / "q", checar=lambda arq: "")
    assert cod == 1 and "customWittyPhrases" in msg
    assert (chunks / "a.js").read_text(encoding="utf-8") == "var usePhraseCycler=1;"


# ------------------------------------------------------------------ espelho em JavaScript
def _node(codigo, entrada=""):
    p = subprocess.Popen([str(NODE), "-e", codigo], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         cwd=str(STATUS), text=True, encoding="utf-8")
    out, err = p.communicate(entrada, timeout=60)
    assert p.returncode == 0, err
    return json.loads(out)


@precisa_node
def test_espelho_js_classifica_igual_ao_python():
    pedidos = list(CASOS) + ["Wi-Fi caiu, não funciona", "faça tudo", "Qual o melhor plano?", "ÁÉÍÓÚ ç ã õ", "por que?"]
    js = _node('const s=require("./status_univo.cjs");const c=s.carregar();let d="";process.stdin.on("data",x=>d+=x)'
               '.on("end",()=>{console.log(JSON.stringify(JSON.parse(d).map(t=>[s.normalizar(t),s.classificar(t,c)])))})',
               json.dumps(pedidos))
    assert js == [[S.normalizar(t), S.classificar(t, CAT)] for t in pedidos]


@precisa_node
def test_espelho_js_primeira_contextual_depois_rotacao():
    r = _node('const s=require("./status_univo.cjs");const a=s.registrarPedido("o script deu erro");'
              'const b=s.primeiraOuProxima();const c=[];for(let i=0;i<200;i++)c.push(s.proxima());'
              'console.log(JSON.stringify({a,b,c,i:s.intervaloMs,barra:s.registrarPedido("/help")}))')
    assert r["a"] in S.frases_da_categoria("erro", CAT) and r["b"] == r["a"] + "…"
    assert all(x[:-1] in CAT["rotacao"] and x.endswith("…") for x in r["c"])
    assert all(x != y for x, y in zip(r["c"], r["c"][1:]))
    assert r["i"] == CAT["intervalo_s"] * 1000 and r["barra"] is None


@precisa_node
def test_patch_gerado_e_javascript_valido(tmp_path):
    pac = _pacote(tmp_path, junto=True)
    cod, msg = S.qwen_patch("aplicar", pac, checar=lambda arq: "")
    assert cod == 0, msg
    p = subprocess.Popen([str(NODE), "--check", str(pac / "chunks" / "chunk-A.js")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    _, err = p.communicate(timeout=60)
    assert p.returncode == 0, err
