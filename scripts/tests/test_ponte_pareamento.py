"""Pareamento sem cabo e instalador do kit do celular (scripts/ponte-pc.py): codigo de uso unico, instalador de bash gerado no PC e execucao dele.

O instalador e executado de verdade (bash + python3 + curl do WSL) num HOME falso, com PREFIX de Termux; nada toca o celular nem o PC do Rafael.
Testa: uso unico (inclusive com pedidos ao mesmo tempo), validade, formato, limite de pendentes, codigo fora do log, token so no pareamento,
instalador fiel byte a byte, download cortado nao executa nada, nao sobrescreve sem copia, mescla settings.json sem perder nada, repetir e seguro.
"""
import hashlib
import http.client
import json
import os
import pathlib
import subprocess
import threading
import types

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
BASH = next((p for p in ("/bin/bash", "/usr/bin/bash") if pathlib.Path(p).exists()), "/bin/bash")
PY3 = next((p for p in ("/usr/bin/python3", "/bin/python3") if pathlib.Path(p).exists()), None)
CURL = next((p for p in ("/usr/bin/curl", "/bin/curl") if pathlib.Path(p).exists()), None)
pytestmark = pytest.mark.skipif(not pathlib.Path(BASH).exists() or not PY3 or not CURL, reason="precisa de bash, python3 e curl (os testes rodam no WSL)")
TOKEN = "a1b2c3d4" * 8  # 64 hex, como o do PC
URL = "http://100.64.0.1:20130"
PREFIXO_TERMUX = "/data/data/com.termux/files/usr"
SEGREDO_FALSO = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"  # montado em pedacos: a varredura de segredos le este arquivo
UTILITARIOS = ("grep", "sed", "cut", "head", "tr", "cat", "mkdir", "rm", "date", "ls", "sort", "sleep", "mv", "cp", "chmod", "stat", "md5sum")

# conteudo traicoeiro de proposito: aspas, crase, $, barra invertida, @@PLACEHOLDER@@, heredoc, acento
IA_FALSO = ("#!/data/data/com.termux/files/usr/bin/bash\n# ia falso\necho \"ia: $HOME\" 'aspas' `crase` \\barra @@VERSAO@@ $(cat) <<EOF\n"
            "linha com acento: ação\nEOF\nPONTE_FIM_IA\n")
CAIXA_FALSO = "#!/data/data/com.termux/files/usr/bin/bash\necho \"caixa falso: $1\"\n"
SAIDA_FALSO = "#!/data/data/com.termux/files/usr/bin/bash\necho \"saida falso: $1\" 'aspas' $HOME\n"
BOOT_FALSO = "#!/data/data/com.termux/files/usr/bin/bash\n# boot falso\nsshd\n"
QWEN_MD_FALSO = "# Instrucoes\n- fale em portugues: ação, coração\n- use `rg` e $VARIAVEL e \\n literal\n"


def _escreve(caminho, texto):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(texto.encode("utf-8"))


@pytest.fixture
def mundo(tmp_path, importa_script):
    m = importa_script("ponte-pc.py")
    proj, base = tmp_path / "proj", tmp_path / "base"
    kit = proj / "scripts" / "celular-kit"
    _escreve(kit / "bin" / "ia", IA_FALSO)
    _escreve(kit / "bin" / "caixa", CAIXA_FALSO)
    _escreve(kit / "bin" / "saida", SAIDA_FALSO)
    _escreve(kit / "bin" / "guarda", SAIDA_FALSO.replace("saida falso", "guarda falso"))
    _escreve(kit / "bin" / "cel", SAIDA_FALSO.replace("saida falso", "cel falso"))
    _escreve(kit / "bin" / "memoria", "#!/usr/bin/env python3\nprint('memoria falso')\n")
    _escreve(kit / "boot" / "iniciar-a12", BOOT_FALSO)
    _escreve(kit / "QWEN.md", QWEN_MD_FALSO)
    _escreve(proj / "CLAUDE.md", "# p\n")
    relogio = [1_000_000.0]
    ponte = m.Ponte(proj, base)
    pareamento = m.Pareamento(tmp_path / "pareamento", relogio=lambda: relogio[0])
    return types.SimpleNamespace(m=m, proj=proj, base=base, kit=kit, ponte=ponte, par=pareamento, relogio=relogio, tmp=tmp_path)


def erro(mundo, funcao, *args, **kw):
    with pytest.raises(mundo.m.ErroPonte) as e:
        funcao(*args, **kw)
    return e.value


# ------------------------------------------------------------------ codigos de pareamento (unidade)
def test_codigo_tem_12_letras_do_alfabeto_sem_confusao_e_so_o_hash_vai_ao_disco(mundo):
    cod = mundo.par.criar()
    assert len(cod) == 12 and set(cod) <= set(mundo.m.CODIGO_ALFABETO) and not set(cod) & set("01OI")
    assert len(set(mundo.m.CODIGO_ALFABETO)) == 32 and not set(mundo.m.CODIGO_ALFABETO) & set("01OI"), "o alfabeto tem 32 simbolos e nenhum parecido"
    arquivos = list(mundo.par.pasta.iterdir())
    assert len(arquivos) == 1 and arquivos[0].name == hashlib.sha256(cod.encode()).hexdigest() + ".json"
    assert cod not in arquivos[0].read_text(encoding="utf-8"), "o codigo em si nunca fica no disco"


def test_codigos_sao_aleatorios(mundo):
    vistos = set()
    for _ in range(40):
        c = mundo.par.criar()
        vistos.add(c)
        assert mundo.par.consumir(c)  # libera a vaga (o maximo de pendentes e 5)
    assert len(vistos) == 40


def test_uso_unico_e_aceita_minusculas_tracos_e_espacos(mundo):
    cod = mundo.par.criar()
    digitado = " " + "-".join((cod[:4], cod[4:8], cod[8:])).lower() + " "
    assert mundo.par.valido(digitado) is True and mundo.par.valido(cod) is True, "olhar nao gasta"
    assert mundo.par.consumir(digitado) is True
    assert mundo.par.consumir(cod) is False and mundo.par.valido(cod) is False


def test_codigo_vencido_nao_serve_e_e_apagado(mundo):
    cod = mundo.par.criar(horas=1)
    mundo.relogio[0] += 3600 - 1
    assert mundo.par.valido(cod) is True
    mundo.relogio[0] += 2
    assert mundo.par.valido(cod) is False and mundo.par.consumir(cod) is False
    assert not list(mundo.par.pasta.glob("*.json")), "vencido e apagado ao ser tentado"


def test_normaliza_codigo_aceita_so_o_formato_certo(mundo):
    n = mundo.m.normaliza_codigo
    assert n("abcd-efgh-jkmn") == "ABCDEFGHJKMN" and n(" ABCDEFGHJKMN ") == "ABCDEFGHJKMN" and n("ab cd efgh jkmn") == "ABCDEFGHJKMN"
    for ruim in ("", "ABC", "ABCDEFGHJKM", "ABCDEFGHJKMNP", "A" * 41, "ABCDEFGHJKM0", "ABCDEFGHJKMO", "ABCDEFGHJKM1", "ABCDEFGHJKMI", "ABCDEFGHJKM!", None, 5, b"ABCDEFGHJKMN"):
        assert n(ruim) is None, repr(ruim)


def test_formato_ruim_nunca_vale(mundo):
    mundo.par.criar()
    for ruim in ("", None, 5, "ABC", "A" * 13, "A" * 41, "0OI1" * 3, "ABCD EFGH JKL!", "../" * 4, "AAAAAAAAAAAA"):
        assert mundo.par.valido(ruim) is False and mundo.par.consumir(ruim) is False, repr(ruim)


@pytest.mark.parametrize("horas", [0, -1, 73, 1000, True, None, "24", float("nan")])
def test_validade_fora_do_permitido_e_recusada(mundo, horas):
    assert erro(mundo, mundo.par.criar, horas).status == 400


def test_no_maximo_5_codigos_pendentes_e_vencidos_nao_contam(mundo):
    for _ in range(5):
        mundo.par.criar(horas=1)
    assert erro(mundo, mundo.par.criar).status == 429
    mundo.relogio[0] += 3601
    assert mundo.par.pendentes() == 0
    assert len(mundo.par.criar()) == 12


def test_dois_pedidos_ao_mesmo_tempo_nunca_usam_o_codigo_duas_vezes(mundo):
    for _ in range(5):
        cod = mundo.par.criar()
        resultados, barreira = [], threading.Barrier(8)

        def tenta():
            barreira.wait()
            resultados.append(mundo.par.consumir(cod))

        ts = [threading.Thread(target=tenta) for _ in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert resultados.count(True) == 1, resultados


def test_arquivo_estranho_na_pasta_nao_quebra_nada(mundo):
    mundo.par.pasta.mkdir(parents=True, exist_ok=True)
    (mundo.par.pasta / "lixo.json").write_text("isto nao e json", encoding="utf-8")
    (mundo.par.pasta / "outro.json").write_text(json.dumps({"ate": "nunca"}), encoding="utf-8")
    assert mundo.par.pendentes() == 0, "arquivo ilegivel ou sem validade e varrido"
    assert len(mundo.par.criar()) == 12


# ------------------------------------------------------------------ o instalador gerado (texto)
def test_instalador_com_token_traz_o_token_uma_vez_e_o_de_atualizacao_nao(mundo):
    com, sem = mundo.ponte.instalador(TOKEN, URL), mundo.ponte.instalador(None, URL)
    assert com.count(TOKEN) == 1 and TOKEN not in sem
    assert com.startswith("#!/data/data/com.termux/files/usr/bin/bash\n") and sem.startswith(com.split("\n")[0])
    assert "PONTE_PC_TOKEN=%s" in com and "ja esta em ~/.qwen/.env (mantido)" in sem
    assert "\r" not in com and com.rstrip("\n").endswith('ponte_instalar "$@" < /dev/null')


def test_instalador_passa_no_bash_n_e_a_versao_confere(mundo):
    for texto in (mundo.ponte.instalador(TOKEN, URL), mundo.ponte.instalador(None, URL)):
        p = subprocess.Popen([BASH, "-n"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        saida, _ = p.communicate(texto, timeout=30)
        assert p.returncode == 0, saida
        assert mundo.ponte.kit_versao() in texto
    v = mundo.ponte.kit_versao()
    assert len(v) == 12 and set(v) <= set("0123456789abcdef") and v == mundo.ponte.kit_versao()


def test_versao_muda_quando_qualquer_arquivo_do_kit_muda(mundo):
    v0 = mundo.ponte.kit_versao()
    for rel in ("bin/ia", "bin/caixa", "bin/saida", "bin/guarda", "bin/cel", "bin/memoria", "boot/iniciar-a12", "QWEN.md"):
        arq = mundo.kit / rel
        antigo = arq.read_bytes()
        arq.write_bytes(antigo + b"# mudou\n")
        assert mundo.ponte.kit_versao() != v0, rel
        arq.write_bytes(antigo)
        assert mundo.ponte.kit_versao() == v0
    outro = pathlib.Path(mundo.kit / "bin" / "outro-comando")
    outro.write_text("#!/bin/bash\n", encoding="utf-8")
    assert mundo.ponte.kit_versao() == v0, "so os arquivos do instalador contam"


@pytest.mark.parametrize("token", ["", "curto", "x" * 31, "a'b" + "c" * 40, "a b" + "c" * 40, "a;rm" + "c" * 40, "a$(id)" + "c" * 40, "x" * 129, "ação" + "x" * 40])
def test_token_fora_do_formato_nunca_entra_no_script(mundo, token):
    assert erro(mundo, mundo.ponte.instalador, token, URL).status == 500


@pytest.mark.parametrize("url", ["ftp://x:1", "http://x", "http://x;id:20130", "http://x:20130/mcp", "http://a b:1", "https://x:20130", "http://x:20130'", "http://x:20130\n"])
def test_url_fora_do_formato_e_recusada(mundo, url):
    assert erro(mundo, mundo.ponte.instalador, None, url).status == 500


def test_kit_incompleto_estranho_ou_com_segredo_nao_gera_instalador(mundo):
    (mundo.kit / "bin" / "caixa").unlink()
    assert erro(mundo, mundo.ponte.instalador, TOKEN, URL).status == 503
    _escreve(mundo.kit / "bin" / "caixa", CAIXA_FALSO)
    _escreve(mundo.kit / "QWEN.md", "chave = " + SEGREDO_FALSO + "\n")
    assert erro(mundo, mundo.ponte.instalador, TOKEN, URL).status == 503
    mundo.kit.joinpath("QWEN.md").write_bytes(b"\xff\xfe nao e utf-8")
    assert erro(mundo, mundo.ponte.instalador, TOKEN, URL).status == 503
    mundo.kit.joinpath("QWEN.md").write_bytes(b"")
    assert erro(mundo, mundo.ponte.instalador, TOKEN, URL).status == 503
    mundo.kit.joinpath("QWEN.md").write_bytes(b"a\x00b")
    assert erro(mundo, mundo.ponte.instalador, TOKEN, URL).status == 503


def test_crlf_do_windows_vira_lf_no_instalador(mundo):
    mundo.kit.joinpath("bin", "ia").write_bytes(IA_FALSO.replace("\n", "\r\n").encode("utf-8"))
    assert "\r" not in mundo.ponte.instalador(TOKEN, URL)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="sem link simbolico")
def test_atalho_no_kit_do_celular_nao_e_seguido(mundo, tmp_path):
    fora = tmp_path / "fora.txt"
    fora.write_text("segredo do PC fora do kit\n", encoding="utf-8")
    (mundo.kit / "bin" / "caixa").unlink()
    (mundo.kit / "bin" / "caixa").symlink_to(fora)
    assert erro(mundo, mundo.ponte.instalador, TOKEN, URL).status == 503


# ------------------------------------------------------------------ HTTP
@pytest.fixture
def api(mundo):
    linhas = []
    srv = mundo.m.cria_servidor(mundo.ponte, TOKEN, 0, "127.0.0.1", linhas.append, mundo.par, URL)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    porta = srv.server_address[1]

    def chama(metodo, caminho, token=None, corpo=None):
        c = http.client.HTTPConnection("127.0.0.1", porta, timeout=15)
        h = {"Authorization": f"Bearer {token}"} if token else {}
        c.request(metodo, caminho, body=corpo, headers=h)
        r = c.getresponse()
        dados = r.read()
        c.close()
        return r.status, dados.decode("utf-8", errors="replace"), {k.lower(): v for k, v in r.getheaders()}

    yield types.SimpleNamespace(chama=chama, linhas=linhas, porta=porta, srv=srv, **vars(mundo))
    srv.shutdown()
    srv.server_close()


def test_pareamento_entrega_o_instalador_com_token_uma_unica_vez(api):
    cod = api.par.criar()
    s, corpo, cab = api.chama("GET", f"/p/{cod}")
    assert s == 200 and corpo.count(TOKEN) == 1 and corpo.startswith("#!/data/data/com.termux/files/usr/bin/bash")
    assert cab["content-type"].startswith("text/plain") and cab["cache-control"] == "no-store"
    s2, corpo2, _ = api.chama("GET", f"/p/{cod}")
    assert s2 == 404 and TOKEN not in corpo2 and "invalido, vencido ou ja usado" in corpo2


def test_codigo_errado_ou_vencido_e_igual_para_quem_tenta_adivinhar(api):
    cod = api.par.criar(horas=1)
    api.relogio[0] += 7200
    respostas = {api.chama("GET", f"/p/{c}")[1] for c in (cod, "AAAAAAAAAAAA", "curto", "x" * 50, "")}
    assert len(respostas) == 1, "o texto do erro nao pode distinguir vencido de inexistente"


def test_adivinhar_codigo_trava_por_um_minuto_ate_o_codigo_certo(api):
    cod = api.par.criar()
    for _ in range(api.m.FALHAS_AUTH_POR_MINUTO):
        assert api.chama("GET", "/p/BBBBBBBBBBBB")[0] == 404
    assert api.chama("GET", "/p/BBBBBBBBBBBB")[0] == 429
    assert api.chama("GET", f"/p/{cod}")[0] == 429, "ate o codigo certo espera"
    assert api.par.valido(cod) is True, "e o codigo certo nao foi gasto"


def test_codigo_nao_vai_para_o_log_nem_o_token(api):
    cod = api.par.criar()
    api.chama("GET", f"/p/{cod}")
    api.chama("GET", "/p/ZZZZZZZZZZZZ")
    log = "\n".join(api.linhas)
    assert "/p/***" in log and cod not in log and "ZZZZZZZZZZZZ" not in log and TOKEN not in log


def test_kit_incompleto_nao_gasta_o_codigo(api):
    cod = api.par.criar()
    api.kit.joinpath("bin", "caixa").unlink()
    s, corpo, _ = api.chama("GET", f"/p/{cod}")
    assert s == 503 and "incompleto" in corpo and "celular-kit" not in corpo and str(api.tmp) not in corpo
    _escreve(api.kit / "bin" / "caixa", CAIXA_FALSO)
    assert api.chama("GET", f"/p/{cod}")[0] == 200, "arrumado o kit, o mesmo codigo ainda serve"


def test_pareamento_so_responde_a_get_e_so_com_pareamento_configurado(api, mundo):
    cod = api.par.criar()
    assert api.chama("POST", f"/p/{cod}", corpo=b"x")[0] == 401
    assert api.chama("PUT", f"/p/{cod}", corpo=b"x")[0] == 401
    assert api.par.valido(cod) is True
    sem = mundo.m.cria_servidor(mundo.ponte, TOKEN, 0, "127.0.0.1", None, None, URL)
    threading.Thread(target=sem.serve_forever, daemon=True).start()
    try:
        c = http.client.HTTPConnection("127.0.0.1", sem.server_address[1], timeout=10)
        c.request("GET", f"/p/{cod}")
        assert c.getresponse().status == 404
    finally:
        sem.shutdown()
        sem.server_close()


def test_instalador_de_atualizacao_pede_token_e_nao_leva_o_token(api):
    assert api.chama("GET", "/v1/celular/instalador")[0] == 401
    s, corpo, cab = api.chama("GET", "/v1/celular/instalador", token=TOKEN)
    assert s == 200 and TOKEN not in corpo and corpo.startswith("#!/data/data/com.termux") and cab["content-type"].startswith("text/plain")
    s, corpo, _ = api.chama("GET", "/v1/celular/versao", token=TOKEN)
    j = json.loads(corpo)
    assert s == 200 and j["kit"] == api.ponte.kit_versao() and j["ponte"] == api.m.VERSAO
    assert api.chama("GET", "/v1/celular/versao")[0] == 401


def test_celular_nao_alcanca_arquivos_do_kit_por_nomes_de_instalador(api):
    for rota in ("/v1/celular/", "/v1/celular/ia", "/v1/celular/../projeto/listar", "/v1/celular/instalador/x"):
        assert api.chama("GET", rota, token=TOKEN)[0] in (404, 400), rota


# ------------------------------------------------------------------ o instalador EXECUTADO (bash de verdade, HOME falso)
class Celular:
    """Um 'Termux' falso: HOME proprio, PREFIX de Termux, PATH so com utilitarios e python3."""

    def __init__(self, tmp, url="http://127.0.0.1:9", com_python=True):
        self.home, util = tmp / "cel-home", tmp / "cel-util"
        self.home.mkdir(parents=True)
        util.mkdir()
        nomes = list(UTILITARIOS) + (["python3"] if com_python else []) + ["curl"]
        for nome in nomes:
            real = {"python3": PY3, "curl": CURL}.get(nome) or next(p for p in (f"/usr/bin/{nome}", f"/bin/{nome}") if pathlib.Path(p).exists())
            (util / nome).symlink_to(real)
        self.env = {"PATH": str(util), "HOME": str(self.home), "PREFIX": PREFIXO_TERMUX, "PONTE_URL": url}

    def roda(self, texto, como="arquivo", env_extra=None, remover_prefix=False):
        env = dict(self.env, **(env_extra or {}))
        if remover_prefix:
            env.pop("PREFIX")
        if como == "arquivo":
            alvo = self.home.parent / "instalar.sh"
            alvo.write_bytes(texto.encode("utf-8"))
            p = subprocess.Popen([BASH, str(alvo)], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            saida, _ = p.communicate(timeout=120)
        else:  # como o Rafael vai colar: curl ... | bash (o script chega pela ENTRADA PADRAO)
            p = subprocess.Popen([BASH], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            saida, _ = p.communicate(texto, timeout=120)
        return p.returncode, saida


@pytest.fixture
def cel(tmp_path):
    return Celular(tmp_path)


def ler(caminho):
    return pathlib.Path(caminho).read_bytes().decode("utf-8")


@pytest.mark.parametrize("como", ["arquivo", "pipe"])
def test_instalacao_inteira_num_celular_limpo(mundo, cel, como):
    rc, saida = cel.roda(mundo.ponte.instalador(TOKEN, URL), como)
    assert rc == 0, saida
    assert ler(cel.home / "bin" / "ia") == IA_FALSO and ler(cel.home / "bin" / "caixa") == CAIXA_FALSO, "ia e caixa chegam byte a byte"
    assert ler(cel.home / ".qwen" / "QWEN.md") == QWEN_MD_FALSO
    assert os.stat(cel.home / "bin" / "ia").st_mode & 0o777 == 0o755
    assert ler(cel.home / "bin" / "saida") == SAIDA_FALSO and os.stat(cel.home / "bin" / "saida").st_mode & 0o777 == 0o755
    assert ler(cel.home / ".termux" / "boot" / "iniciar-a12") == BOOT_FALSO and os.stat(cel.home / ".termux" / "boot" / "iniciar-a12").st_mode & 0o777 == 0o700
    assert not [p.name for p in (cel.home / ".termux" / "boot").iterdir() if p.name.startswith(".")], "nenhum temporario no boot"
    env = cel.home / ".qwen" / ".env"
    assert ler(env) == f"PONTE_PC_TOKEN={TOKEN}\n" and os.stat(env).st_mode & 0o777 == 0o600
    cfg = json.loads(ler(cel.home / ".qwen" / "settings.json"))
    ponte, exa = cfg["mcpServers"]["ponte-pc"], cfg["mcpServers"]["exa"]
    assert ponte["httpUrl"] == URL + "/mcp" and ponte["headers"] == {"Authorization": "Bearer $PONTE_PC_TOKEN"}
    assert ponte["trust"] is True and exa["trust"] is False and exa["httpUrl"] == "https://mcp.exa.ai/mcp"
    assert TOKEN not in json.dumps(cfg), "o token fica so no .env, nunca no settings.json"
    assert ler(cel.home / ".qwen" / "kit-versao").strip() == mundo.ponte.kit_versao()
    assert "Pronto (kit " in saida and TOKEN not in saida and "caixa falso: status" in saida
    assert not [p.name for p in (cel.home / "bin").iterdir() if p.name.startswith(".")], "nenhum arquivo temporario sobrou"
    assert not [p.name for p in (cel.home / ".qwen").iterdir() if p.name.endswith(".novo")]


def test_nao_sobrescreve_sem_guardar_copia_e_mantem_o_resto_do_settings(mundo, cel):
    (cel.home / "bin").mkdir()
    (cel.home / ".qwen").mkdir()
    (cel.home / "bin" / "ia").write_text("#!/bin/bash\necho ia antigo\n", encoding="utf-8")
    (cel.home / ".qwen" / "QWEN.md").write_text("instrucoes antigas\n", encoding="utf-8")
    (cel.home / ".qwen" / ".env").write_text("OMNIROUTE_API_KEY=chave-123\nPONTE_PC_TOKEN=antigo\nOUTRA=1\n", encoding="utf-8")
    antes = {"model": {"name": "codigo", "reasoningEffort": "max"}, "permissions": {"allow": ["Bash(ls *)", "Bash(git *)"]},
             "mcpServers": {"meu-servidor": {"command": "x"}, "exa": {"httpUrl": "https://velho", "trust": True}}}
    (cel.home / ".qwen" / "settings.json").write_text(json.dumps(antes), encoding="utf-8")
    rc, saida = cel.roda(mundo.ponte.instalador(TOKEN, URL))
    assert rc == 0, saida
    copias = cel.home / ".qwen" / "antes-da-ponte"
    assert ler(copias / "ia") == "#!/bin/bash\necho ia antigo\n" and ler(copias / "QWEN.md") == "instrucoes antigas\n"
    assert json.loads(ler(copias / "settings.json")) == antes
    cfg = json.loads(ler(cel.home / ".qwen" / "settings.json"))
    assert cfg["model"] == antes["model"], "nada do que e dele some"
    regras = cfg["permissions"]
    assert regras["allow"][:2] == ["Bash(ls *)", "Bash(git *)"], "as regras dele ficam, na frente"
    assert "Bash(cel *)" in regras["allow"] and "Bash(guarda *)" in regras["allow"], "o kit roda sem perguntar"
    assert "Bash(cel sh *)" in regras["ask"] and "Bash(saida ligar*)" in regras["ask"], "comando livre e o que corta a internet perguntam"
    assert "Bash(pkg upgrade*)" in regras["deny"] and "Bash(rm -rf *)" in regras["deny"] and "Bash(cel sh pm uninstall*)" in regras["deny"]
    assert "Bash(adb *)" in regras["deny"] and "Bash(cel sh pm disable*)" in regras["deny"] and "Bash(cel sh sm *)" in regras["deny"]
    assert "Bash(pkg *)" not in regras["deny"] and "Bash(memoria *)" in regras["allow"], "pkg install fica livre; so upgrade e remover travam"
    assert all(len(v) == len(set(v)) for v in regras.values()), "sem regra repetida"
    assert cfg["tools"]["approvalMode"] == "yolo", "pedido do Rafael: sem interromper"
    assert cfg["ui"]["theme"] == "Matrix" and cfg["ui"]["customThemes"]["Matrix"]["Background"] == "#000000"
    assert cfg["ui"]["customBannerTitle"] == "MATRIX" and "large" in cfg["ui"]["customAsciiArt"]
    assert (cel.home / "bin" / "matrix").exists() and "MATRIX=1 exec bash" in ler(cel.home / "bin" / "matrix")
    assert cfg["mcpServers"]["meu-servidor"] == {"command": "x"}, "servidor MCP dele fica"
    assert cfg["mcpServers"]["exa"]["httpUrl"] == "https://mcp.exa.ai/mcp" and cfg["mcpServers"]["exa"]["trust"] is False
    env = ler(cel.home / ".qwen" / ".env")
    assert "OMNIROUTE_API_KEY=chave-123\n" in env and "OUTRA=1\n" in env and "PONTE_PC_TOKEN=antigo" not in env
    assert env.count("PONTE_PC_TOKEN=") == 1 and env.endswith(f"PONTE_PC_TOKEN={TOKEN}\n")
    assert "chave-123" not in saida


def test_rodar_de_novo_e_seguro_e_a_copia_original_nao_e_trocada(mundo, cel):
    (cel.home / "bin").mkdir()
    (cel.home / "bin" / "ia").write_text("original dele\n", encoding="utf-8")
    assert cel.roda(mundo.ponte.instalador(TOKEN, URL))[0] == 0
    _escreve(mundo.kit / "bin" / "ia", IA_FALSO + "# versao 2\n")
    rc, saida = cel.roda(mundo.ponte.instalador(None, URL))  # atualizacao: sem token
    assert rc == 0 and "mantido" in saida, saida
    assert ler(cel.home / "bin" / "ia").endswith("# versao 2\n")
    assert ler(cel.home / ".qwen" / "antes-da-ponte" / "ia") == "original dele\n", "a copia guarda o ORIGINAL, nao a versao 1"
    assert ler(cel.home / ".qwen" / ".env") == f"PONTE_PC_TOKEN={TOKEN}\n"
    cfg = json.loads(ler(cel.home / ".qwen" / "settings.json"))
    assert list(cfg["mcpServers"]) == ["ponte-pc", "exa"]
    assert all(len(v) == len(set(v)) for v in cfg["permissions"].values()), "rodar de novo nao repete regra"
    assert ler(cel.home / ".bashrc").count("alias qwen=") == 1, "o atalho qwen entra uma vez so"
    assert "alias qwen='matrix'" in ler(cel.home / ".bashrc")
    cores = ler(cel.home / ".termux" / "colors.properties")
    assert cores.startswith("# matrix-kit v2") and "background=#000000" in cores and cores.count("# matrix-kit") == 1 and "#0F4D1F" not in cores
    assert (cel.home / "kit" / "scripts-qwen").is_dir()


def test_atualizacao_sem_token_no_celular_avisa_e_termina_com_aviso(mundo, cel):
    rc, saida = cel.roda(mundo.ponte.instalador(None, URL))
    assert rc == 1 and "sem PONTE_PC_TOKEN" in saida and "-Parear" in saida
    assert "Pronto" not in saida and "Terminei com avisos" in saida, "com aviso nao se diz Pronto"
    assert ler(cel.home / "bin" / "ia") == IA_FALSO, "o resto foi instalado mesmo assim"


def test_download_cortado_nao_executa_nada(mundo, cel):
    texto = mundo.ponte.instalador(TOKEN, URL)
    for corte in (len(texto) // 10, len(texto) // 2, len(texto) - 40):
        _, saida = cel.roda(texto[:corte], como="pipe")
        assert not (cel.home / "bin").exists() and not (cel.home / ".qwen").exists(), (corte, saida)
        assert "Pronto" not in saida and "[ok]" not in saida


def test_fora_do_termux_nao_instala_nada(mundo, cel):
    rc, saida = cel.roda(mundo.ponte.instalador(TOKEN, URL), remover_prefix=True)
    assert rc == 1 and "Termux" in saida and not (cel.home / "bin").exists() and not (cel.home / ".qwen").exists()


def test_sem_python_para_sem_instalar_nada(mundo, tmp_path):
    (tmp_path / "sp").mkdir()
    sem_python = Celular(tmp_path / "sp", com_python=False)
    rc, saida = sem_python.roda(mundo.ponte.instalador(TOKEN, URL))
    assert rc == 1 and "pkg install python" in saida and not (sem_python.home / "bin").exists()


def test_settings_que_nao_e_json_puro_fica_intacto_e_o_resto_instala(mundo, cel):
    (cel.home / ".qwen").mkdir()
    original = '{\n  // comentario do usuario\n  "model": {"name": "x"}\n}\n'
    (cel.home / ".qwen" / "settings.json").write_text(original, encoding="utf-8")
    rc, saida = cel.roda(mundo.ponte.instalador(TOKEN, URL))
    assert rc == 1 and "nao e um JSON puro" in saida and "nao mexi em ~/.qwen/settings.json" in saida
    assert ler(cel.home / ".qwen" / "settings.json") == original
    assert ler(cel.home / "bin" / "ia") == IA_FALSO and ler(cel.home / ".qwen" / ".env") == f"PONTE_PC_TOKEN={TOKEN}\n"


def test_instalacao_com_aviso_nao_grava_kit_versao(mundo, cel):
    """Com erro (settings.json que nao e JSON puro), o celular nao pode passar a dizer 'kit em dia'."""
    (cel.home / ".qwen").mkdir()
    (cel.home / ".qwen" / "settings.json").write_text("{ // comentario\n  }\n", encoding="utf-8")
    rc, saida = cel.roda(mundo.ponte.instalador(TOKEN, URL))
    assert rc == 1 and "Terminei com avisos" in saida, saida
    assert not (cel.home / ".qwen" / "kit-versao").exists()
    (cel.home / ".qwen" / "settings.json").unlink()
    rc, saida = cel.roda(mundo.ponte.instalador(TOKEN, URL))
    assert rc == 0, saida
    assert ler(cel.home / ".qwen" / "kit-versao").strip() == mundo.ponte.kit_versao(), "sem erro, a versao e gravada"


def test_boot_antigo_do_celular_ganha_copia_antes_de_ser_trocado(mundo, cel):
    (cel.home / ".termux" / "boot").mkdir(parents=True)
    (cel.home / ".termux" / "boot" / "iniciar-a12").write_text("#!/bin/bash\necho meu boot editado\n", encoding="utf-8")
    rc, saida = cel.roda(mundo.ponte.instalador(TOKEN, URL))
    assert rc == 0, saida
    assert ler(cel.home / ".qwen" / "antes-da-ponte" / "iniciar-a12") == "#!/bin/bash\necho meu boot editado\n"
    assert ler(cel.home / ".termux" / "boot" / "iniciar-a12") == BOOT_FALSO
    _escreve(mundo.kit / "boot" / "iniciar-a12", BOOT_FALSO + "# v2\n")
    assert cel.roda(mundo.ponte.instalador(None, URL))[0] == 0
    assert ler(cel.home / ".qwen" / "antes-da-ponte" / "iniciar-a12") == "#!/bin/bash\necho meu boot editado\n", "a copia guarda o ORIGINAL"


def test_gravacao_que_falha_no_celular_nao_troca_nada_nem_diz_ok(mundo, cel):
    """Armazenamento cheio: o cat falha. Antes, o arquivo vazio passava no bash -n e substituia o comando que funcionava."""
    (cel.home / "bin").mkdir()
    (cel.home / "bin" / "ia").write_text("#!/bin/bash\necho funciona\n", encoding="utf-8")
    util = pathlib.Path(cel.env["PATH"])
    (util / "cat").unlink()
    (util / "cat").write_text("#!/bin/bash\nexit 1\n", encoding="utf-8")
    (util / "cat").chmod(0o755)
    rc, saida = cel.roda(mundo.ponte.instalador(TOKEN, URL))
    assert rc == 1 and "[ok]" not in saida and "Pronto" not in saida, saida
    assert ler(cel.home / "bin" / "ia") == "#!/bin/bash\necho funciona\n"
    assert not (cel.home / ".qwen" / "kit-versao").exists() and not (cel.home / ".qwen" / "QWEN.md").exists()
    assert not [p.name for p in (cel.home / "bin").iterdir() if p.name.endswith(".novo")]


def test_arquivo_novo_com_erro_de_sintaxe_nao_substitui_o_comando_que_funciona(mundo, cel):
    (cel.home / "bin").mkdir()
    (cel.home / "bin" / "ia").write_text("#!/bin/bash\necho funciona\n", encoding="utf-8")
    _escreve(mundo.kit / "bin" / "ia", "#!/bin/bash\nif then fi (\n")
    rc, saida = cel.roda(mundo.ponte.instalador(TOKEN, URL))
    assert rc == 1 and "erro de sintaxe" in saida
    assert ler(cel.home / "bin" / "ia") == "#!/bin/bash\necho funciona\n"
    assert not (cel.home / ".qwen" / ".env").exists(), "nem o token foi gravado: nada pela metade"


def test_a_instalacao_real_do_repositorio_funciona_de_ponta_a_ponta(tmp_path, importa_script):
    """Com os arquivos REAIS do kit (ia, caixa, QWEN.md): instala, e o `caixa status` instalado fala com o servidor de verdade."""
    m = importa_script("ponte-pc.py")
    ponte = m.Ponte(RAIZ, tmp_path / "base")
    srv = m.cria_servidor(ponte, TOKEN, 0, "127.0.0.1", None, None, URL)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        (tmp_path / "real").mkdir()
        celular = Celular(tmp_path / "real", url=f"http://127.0.0.1:{srv.server_address[1]}")
        rc, saida = celular.roda(ponte.instalador(TOKEN, URL), como="pipe")
        assert rc == 0, saida
        kit = RAIZ / "scripts" / "celular-kit"
        for rel, destino in (("bin/ia", "bin/ia"), ("bin/caixa", "bin/caixa"), ("bin/saida", "bin/saida"), ("bin/guarda", "bin/guarda"), ("bin/cel", "bin/cel"), ("bin/memoria", "bin/memoria"), ("boot/iniciar-a12", ".termux/boot/iniciar-a12"), ("QWEN.md", ".qwen/QWEN.md")):
            esperado = (kit / rel).read_bytes().decode("utf-8").replace("\r\n", "\n").rstrip("\n") + "\n"
            assert ler(celular.home / destino) == esperado, rel
        assert "[ok]  ponte do PC responde" in saida and "Pronto (kit " in saida
    finally:
        srv.shutdown()
        srv.server_close()


def test_atalho_antigo_qwen_ia_vira_matrix_sem_perder_o_resto_do_bashrc(mundo, cel):
    (cel.home / ".bashrc").write_text("export EDITOR=nano\nalias qwen='ia'  # antigo\nalias ll='ls -l'\n", encoding="utf-8")
    rc, saida = cel.roda(mundo.ponte.instalador(TOKEN, URL))
    assert rc == 0, saida
    b = ler(cel.home / ".bashrc")
    assert "export EDITOR=nano" in b and "alias ll='ls -l'" in b
    assert b.count("alias qwen=") == 1 and "alias qwen='matrix'" in b and "alias qwen='ia'" not in b


def test_cores_antigas_do_termux_ganham_copia_antes_do_matrix(mundo, cel):
    (cel.home / ".termux").mkdir()
    (cel.home / ".termux" / "colors.properties").write_text("background=#101010\n", encoding="utf-8")
    assert cel.roda(mundo.ponte.instalador(TOKEN, URL))[0] == 0
    assert ler(cel.home / ".qwen" / "antes-da-ponte" / "colors.properties") == "background=#101010\n"
    assert "matrix-kit" in ler(cel.home / ".termux" / "colors.properties")


def test_cores_matrix_v1_viram_v2_sem_virar_copia_das_antigas(mundo, cel):
    (cel.home / ".termux").mkdir()
    (cel.home / ".termux" / "colors.properties").write_text("# matrix-kit: antigo\ncolor8=#0F4D1F\n", encoding="utf-8")
    assert cel.roda(mundo.ponte.instalador(TOKEN, URL))[0] == 0
    cores = ler(cel.home / ".termux" / "colors.properties")
    assert cores.startswith("# matrix-kit v2") and "#0F4D1F" not in cores
    assert not (cel.home / ".qwen" / "antes-da-ponte" / "colors.properties").exists(), "a v1 era do kit: nao vira 'cores antigas dele'"


def test_tema_matrix_so_verde_cinza_e_branco_e_frases_da_personalidade(mundo, cel):
    assert cel.roda(mundo.ponte.instalador(TOKEN, URL))[0] == 0
    ui = json.loads(ler(cel.home / ".qwen" / "settings.json"))["ui"]
    cores = {v.upper() for k, v in ui["customThemes"]["Matrix"].items() if isinstance(v, str) and v.startswith("#")}
    assert cores <= {"#000000", "#00FF41", "#FFFFFF", "#B0B0B0", "#909090", "#3A3A3A"}, cores
    frases = " ".join(ui["customWittyPhrases"])
    assert "Compilando a realidade" not in frases and len(ui["customWittyPhrases"]) >= 15 and "Qwen" not in frases
