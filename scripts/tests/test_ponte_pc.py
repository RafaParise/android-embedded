"""Testes de scripts/ponte-pc.py (servidor MCP + REST do PC para o Qwen do celular).

Cobrem: so ler o que foi liberado (CLAUDE.md, memoria/, scripts/), nunca fora, nunca segredo, planilha, MAPAO, binario nem atalho;
entrega so como arquivo NOVO em saida (nunca sobrescreve, nunca no projeto); token; limites; protocolo MCP; nada de traceback ou
caminho do PC nas respostas. O servidor sobe em 127.0.0.1 numa porta livre; nenhum teste toca rede de verdade nem o PC do Rafael.
"""
import http.client
import inspect
import json
import os
import re
import threading
import types

import pytest

TOKEN = "t0ken-de-teste-" + "x" * 30
SEGREDO_FALSO = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"  # montado em pedacos: a varredura de segredos le este arquivo


def _escreve(caminho, texto, binario=False):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if binario:
        caminho.write_bytes(texto)
    else:
        caminho.write_text(texto, encoding="utf-8", newline="\n")


@pytest.fixture
def mundo(tmp_path, importa_script):
    m = importa_script("ponte-pc.py")
    proj, base = tmp_path / "proj", tmp_path / "base"
    _escreve(proj / "CLAUDE.md", "# Projeto\nregra um\n")
    _escreve(proj / "memoria" / "ESTADO.md", "".join(f"linha {i}\n" for i in range(1, 11)))
    _escreve(proj / "memoria" / "LONGO.md", "".join(f"n{i}\n" for i in range(1, 501)))
    _escreve(proj / "memoria" / "GRANDE.md", "x" * (m.MAX_ARQUIVO_LEITURA + 10))
    _escreve(proj / "memoria" / "COM-SEGREDO.md", f"nota\nchave = {SEGREDO_FALSO}\n")
    _escreve(proj / "memoria" / "planilha.xlsx", b"PK\x03\x04", binario=True)
    _escreve(proj / "memoria" / "MAPAO_turma.md", "notas\n")
    _escreve(proj / "memoria" / "binario.md", b"abc\x00def", binario=True)
    _escreve(proj / "memoria" / "programa.exe", b"MZ", binario=True)
    _escreve(proj / "memoria" / "hermes-espelho" / "x.md", "espelho\n")
    _escreve(proj / "scripts" / "a.py", "def a():\n    return 1  # Zebra\n")
    _escreve(proj / "scripts" / "celular-kit" / "bin" / "ia", "#!/bin/bash\necho oi\n")
    _escreve(proj / "scripts" / "__pycache__" / "x.py", "cache\n")
    _escreve(proj / "diagnostico" / "x.md", "diag\n")
    _escreve(proj / "outra" / "x.md", "outra\n")
    _escreve(proj / ".git" / "config", "git\n")
    _escreve(base / "entrada" / "pedido-01.md", "Faca o resumo.\n")
    _escreve(base / "retorno" / "rev-01.md", "Veredito: COM CORRECOES\n")
    _escreve(base / "kit" / "skills" / "minha-skill" / "SKILL.md", "# minha skill\nfaca assim\n")
    (base / "kit" / "skills" / "vazia").mkdir(parents=True)
    _escreve(base / "kit" / "estrategias" / "politica.md", "# politica\n")
    ponte = m.Ponte(proj, base)
    return types.SimpleNamespace(m=m, ponte=ponte, proj=proj, base=base, tmp=tmp_path)


def erro(mundo, funcao, *args, **kw):
    with pytest.raises(mundo.m.ErroPonte) as e:
        funcao(*args, **kw)
    return e.value


def arvore(pasta):
    return sorted(str(p.relative_to(pasta)) for p in pasta.rglob("*"))


# ---------------------------------------------------------------- projeto: o que pode ser lido

def test_raiz_lista_so_claude_md_memoria_e_scripts(mundo):
    nomes = [i["nome"] for i in mundo.ponte.projeto_listar("")["itens"]]
    assert nomes == ["CLAUDE.md", "memoria", "scripts"], "diagnostico, outra e .git nao podem aparecer"


def test_pasta_memoria_esconde_espelho_planilha_mapao_e_ocultos(mundo):
    nomes = [i["nome"] for i in mundo.ponte.projeto_listar("memoria")["itens"]]
    assert "ESTADO.md" in nomes and "COM-SEGREDO.md" in nomes
    for proibido in ("hermes-espelho", "planilha.xlsx", "MAPAO_turma.md", "programa.exe"):
        assert proibido not in nomes
    assert [i["nome"] for i in mundo.ponte.projeto_listar("scripts")["itens"]] == ["celular-kit", "a.py"]


def test_leitura_em_fatias_com_total_de_linhas(mundo):
    r = mundo.ponte.projeto_ler("memoria/ESTADO.md", 2, 4)
    assert r["texto"] == "linha 2\nlinha 3\nlinha 4" and r["total_linhas"] == 10 and (r["inicio"], r["fim"]) == (2, 4)
    padrao = mundo.ponte.projeto_ler("memoria/ESTADO.md")
    assert (padrao["inicio"], padrao["fim"]) == (1, 10)


def test_leitura_nunca_passa_do_limite_de_linhas_nem_de_bytes(mundo):
    r = mundo.ponte.projeto_ler("memoria/LONGO.md", 1, 5000)
    assert r["fim"] == mundo.m.MAX_LINHAS and r["texto"].count("\n") == mundo.m.MAX_LINHAS - 1
    _escreve(mundo.proj / "memoria" / "LINHAGORDA.md", ("y" * 1000 + "\n") * 100)
    gorda = mundo.ponte.projeto_ler("memoria/LINHAGORDA.md", 1, 100)
    assert gorda["cortado_por_tamanho"] and len(gorda["texto"].encode()) <= mundo.m.MAX_BYTES_RESPOSTA


def test_script_sem_extensao_pode_ser_lido(mundo):
    assert "echo oi" in mundo.ponte.projeto_ler("scripts/celular-kit/bin/ia")["texto"]


@pytest.mark.parametrize("caminho", [
    "../CLAUDE.md", "memoria/../CLAUDE.md", "memoria\\..\\..\\x", "/etc/passwd", "C:\\Windows\\win.ini", "C:/Windows/win.ini", "~/x",
    "memoria//ESTADO.md/..", "memoria/ESTADO.md\x00.png", "memoria/ESTADO.md.", "memoria/ESTADO.md ", "memoria/CON.md", "memoria/nul",
    "memoria/AUX.txt", ".git/config", "memoria/.env", "memoria/ESTADO.md:stream", "memoria/*.md", "", "   ",
])
def test_caminhos_perigosos_sao_recusados_sem_ler_nada(mundo, caminho):
    e = erro(mundo, mundo.ponte.projeto_ler, caminho)
    assert e.status in (400, 403), (caminho, e.status)
    assert str(mundo.tmp) not in e.mensagem


@pytest.mark.parametrize("caminho,status", [
    ("diagnostico/x.md", 403), ("outra/x.md", 403), ("memoria/hermes-espelho/x.md", 403),
    ("memoria/HERMES-ESPELHO/AGENTS.md", 403), ("memoria/Hermes-Espelho/x.md", 403),  # o NTFS do PC nao distingue a caixa ("scripts/__pycache__/x.py", 400),
    ("memoria/planilha.xlsx", 403), ("memoria/MAPAO_turma.md", 403), ("memoria/binario.md", 415), ("memoria/programa.exe", 415),
    ("memoria/GRANDE.md", 413), ("memoria/COM-SEGREDO.md", 403), ("memoria/nao-existe.md", 404), ("memoria", 415),
])
def test_o_que_fica_de_fora_e_recusado_com_o_status_certo(mundo, caminho, status):
    e = erro(mundo, mundo.ponte.projeto_ler, caminho)
    assert e.status == status, (caminho, e.status, e.mensagem)
    assert SEGREDO_FALSO not in e.mensagem


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="sem link simbolico")
def test_atalho_para_fora_do_projeto_e_recusado_e_nao_aparece_na_lista(mundo):
    fora = mundo.tmp / "fora"
    _escreve(fora / "segredo.md", "so fora\n")
    try:
        os.symlink(fora / "segredo.md", mundo.proj / "memoria" / "atalho.md")
        os.symlink(fora, mundo.proj / "memoria" / "pasta-atalho", target_is_directory=True)
    except OSError:
        pytest.skip("sem permissao para link simbolico")
    assert erro(mundo, mundo.ponte.projeto_ler, "memoria/atalho.md").status == 403
    assert erro(mundo, mundo.ponte.projeto_ler, "memoria/pasta-atalho/segredo.md").status == 403
    nomes = [i["nome"] for i in mundo.ponte.projeto_listar("memoria")["itens"]]
    assert "atalho.md" not in nomes and "pasta-atalho" not in nomes
    assert not mundo.ponte.projeto_buscar("so fora")["achados"], "a busca nao pode seguir atalho"


def test_busca_acha_sem_distinguir_maiuscula_e_ignora_o_que_esta_fora(mundo):
    r = mundo.ponte.projeto_buscar("zebra")
    assert [(a["caminho"], a["linha"]) for a in r["achados"]] == [("scripts/a.py", 2)]
    assert mundo.ponte.projeto_buscar("regra um")["achados"][0]["caminho"] == "CLAUDE.md"
    for fora in ("espelho", "diag", SEGREDO_FALSO[-16:], "notas", "so fora"):  # o VALOR do segredo, nao o nome da variavel
        assert not mundo.ponte.projeto_buscar(fora)["achados"], fora
    _escreve(mundo.proj / "memoria" / "PERMITIDO.md", "nota liberada\n")
    caminhos = [a["caminho"] for a in mundo.ponte.projeto_buscar("nota")["achados"]]
    assert "memoria/PERMITIDO.md" in caminhos, "a busca funciona na pasta"
    assert "memoria/COM-SEGREDO.md" not in caminhos, "arquivo com segredo fica de fora, mesmo tendo a palavra"


def test_busca_limita_achados_e_recusa_termo_curto_ou_pasta_fora(mundo):
    _escreve(mundo.proj / "memoria" / "REPETE.md", "padrao\n" * 100)
    r = mundo.ponte.projeto_buscar("padrao", "memoria")
    assert len(r["achados"]) == mundo.m.MAX_ACHADOS and r["truncado"]
    assert erro(mundo, mundo.ponte.projeto_buscar, "a").status == 400
    assert erro(mundo, mundo.ponte.projeto_buscar, "x" * 200).status == 400
    assert erro(mundo, mundo.ponte.projeto_buscar, "padrao", "diagnostico").status == 403


# ---------------------------------------------------------------- kit (skills e estrategias)

def test_kit_lista_skills_com_skill_md_e_estrategias(mundo):
    assert mundo.ponte.kit_listar("skills")["itens"] == [{"nome": "minha-skill", "tipo": "skill"}]
    assert mundo.ponte.kit_listar("estrategias")["itens"] == [{"nome": "politica", "tipo": "documento"}]
    assert "faca assim" in mundo.ponte.kit_ler("skills", "minha-skill")["texto"]
    assert "# politica" in mundo.ponte.kit_ler("estrategias", "politica")["texto"]


@pytest.mark.parametrize("tipo,nome,status", [
    ("outro", "x", 400), ("skills", "../x", 400), ("skills", "a/b", 400), ("skills", "..", 400), ("skills", "", 400),
    ("skills", "nao-existe", 404), ("skills", "vazia", 404), (None, "x", 400), ("skills", "minha-skill\n", 400),
])
def test_kit_recusa_tipo_e_nome_ruins(mundo, tipo, nome, status):
    assert erro(mundo, mundo.ponte.kit_ler, tipo, nome).status == status


def test_kit_bloqueia_segredo(mundo):
    _escreve(mundo.base / "kit" / "skills" / "ruim" / "SKILL.md", f"token = {SEGREDO_FALSO}\n")
    assert erro(mundo, mundo.ponte.kit_ler, "skills", "ruim").status == 403


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="sem link simbolico")
def test_kit_nao_segue_atalho_para_fora(mundo):
    _escreve(mundo.tmp / "fora" / "SKILL.md", "fora\n")
    try:
        os.symlink(mundo.tmp / "fora", mundo.base / "kit" / "skills" / "atalho", target_is_directory=True)
    except OSError:
        pytest.skip("sem permissao para link simbolico")
    assert erro(mundo, mundo.ponte.kit_ler, "skills", "atalho").status == 403
    assert "atalho" not in [i["nome"] for i in mundo.ponte.kit_listar("skills")["itens"]]


# ---------------------------------------------------------------- caixa de recados e entregas

def test_caixa_lista_e_le_entrada_e_retorno(mundo):
    itens = {(i["origem"], i["nome"]) for i in mundo.ponte.caixa_listar()["itens"]}
    assert itens == {("entrada", "pedido-01.md"), ("retorno", "rev-01.md")}
    assert "Faca o resumo" in mundo.ponte.caixa_ler("entrada", "pedido-01.md")["texto"]
    assert "COM CORRECOES" in mundo.ponte.caixa_ler("retorno", "rev-01.md")["texto"]


@pytest.mark.parametrize("origem,nome,status", [
    ("saida", "x.md", 400), ("entrada", "../retorno/rev-01.md", 400), ("entrada", "pedido-01.txt", 400), ("entrada", "nao.md", 404),
    ("entrada", "", 400), (None, "x.md", 400), ("entrada", "pedido-01.md\n", 400),
])
def test_caixa_recusa_origem_e_nome_ruins(mundo, origem, nome, status):
    assert erro(mundo, mundo.ponte.caixa_ler, origem, nome).status == status


def test_entrega_cria_arquivo_novo_marcado_nao_revisado_so_em_saida(mundo):
    antes = arvore(mundo.proj)
    r = mundo.ponte.entregar("plano-aula", "# Plano\nlinha\n", "100.1.2.3")
    gravado = mundo.base / "saida" / r["gravado"]
    assert gravado.is_file() and re.match(r"^\d{8}-\d{6}-plano-aula\.md$", r["gravado"])
    texto = gravado.read_text(encoding="utf-8")
    assert texto.startswith("Status: NAO REVISADO pelo Claude Code") and "100.1.2.3" in texto and texto.endswith("# Plano\nlinha\n")
    assert arvore(mundo.proj) == antes, "uma entrega nunca pode mexer no projeto"
    assert [p.name for p in (mundo.base / "saida").iterdir()] == [r["gravado"]]


def test_entrega_nunca_sobrescreve(mundo):
    p = mundo.m.Ponte(mundo.proj, mundo.base, relogio=lambda: 1_800_000_000)
    p.entregar("x", "primeira\n")
    assert erro(mundo, p.entregar, "x", "segunda\n").status == 409
    (arq,) = list((mundo.base / "saida").iterdir())
    assert "primeira" in arq.read_text(encoding="utf-8") and "segunda" not in arq.read_text(encoding="utf-8")


@pytest.mark.parametrize("nome", ["", ".oculto", "a b", "a/b", "a\\b", "..", "../x", "a:b", "x" * 80, "nome\n", "acao%", None, 5])
def test_entrega_recusa_nome_ruim(mundo, nome):
    assert erro(mundo, mundo.ponte.entregar, nome, "texto").status == 400
    assert not list((mundo.base / "saida").iterdir())


def test_entrega_tira_o_md_do_fim_do_nome(mundo):
    assert mundo.ponte.entregar("nota.MD", "t")["gravado"].endswith("-nota.md")


def test_entrega_recusa_texto_vazio_grande_nulo_e_segredo(mundo):
    for texto, status in (("", 400), ("   \n", 400), (None, 400), ("a" * (mundo.m.MAX_ENTREGA + 1), 413), ("a\0b", 400),
                          (f"minha chave {SEGREDO_FALSO}", 422), ("Authorization: Bearer " + "A" * 30, 422)):
        assert erro(mundo, mundo.ponte.entregar, "n", texto).status == status, texto
    assert not list((mundo.base / "saida").iterdir()), "recusou, entao nada pode ter sido gravado"


def test_entrega_tem_limite_por_hora_e_a_hora_passa(mundo):
    agora = [1_800_000_000.0]
    p = mundo.m.Ponte(mundo.proj, mundo.base, relogio=lambda: agora[0])
    for i in range(mundo.m.MAX_ENTREGAS_POR_HORA):
        p.entregar(f"e{i}", "t")
    assert erro(mundo, p.entregar, "extra", "t").status == 429
    agora[0] += 3601
    assert p.entregar("depois", "t")["gravado"]


def test_pasta_de_saida_cheia_recusa(mundo, monkeypatch):
    monkeypatch.setattr(mundo.m, "MAX_ENTREGAS_NA_PASTA", 2)
    mundo.ponte.entregar("a", "t")
    mundo.ponte.entregar("b", "t")
    assert erro(mundo, mundo.ponte.entregar, "c", "t").status == 429


# ---------------------------------------------------------------- token, padroes e arquivo

def test_padroes_de_segredo_sao_os_mesmos_do_powershell(mundo):
    ps = (mundo.m.RAIZ_PROJETO / "scripts" / "padroes-segredo.ps1").read_text(encoding="utf-8")
    bloco = ps[ps.index("$script:PadroesSegredo = @("):ps.index("# Extensoes que nunca entram")]
    do_ps = [x.replace("''", "'") for x in re.findall(r"'((?:[^']|'')*)'", bloco)]
    assert do_ps and do_ps == mundo.m.PADROES_SEGREDO, "a copia em Python tem que ser a mesma lista de padroes-segredo.ps1"


def test_le_token_recusa_arquivo_ausente_ou_curto(mundo):
    with pytest.raises(SystemExit):
        mundo.m.le_token(mundo.tmp / "nao-existe")
    curto = mundo.tmp / "curto"
    curto.write_text("abc", encoding="utf-8")
    with pytest.raises(SystemExit):
        mundo.m.le_token(curto)
    bom = mundo.tmp / "bom"
    bom.write_text(TOKEN + "\n", encoding="utf-8")
    assert mundo.m.le_token(bom) == TOKEN


def test_servidor_so_escuta_em_127_0_0_1(mundo):
    srv = mundo.m.cria_servidor(mundo.ponte, TOKEN, 0)
    try:
        assert srv.server_address[0] == "127.0.0.1"
    finally:
        srv.server_close()
    fonte = inspect.getsource(mundo.m.principal)
    assert '"127.0.0.1"' in fonte and "0.0.0.0" not in fonte


# ---------------------------------------------------------------- HTTP (REST + MCP)

@pytest.fixture
def api(mundo):
    linhas = []
    srv = mundo.m.cria_servidor(mundo.ponte, TOKEN, 0, "127.0.0.1", linhas.append)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    porta = srv.server_address[1]

    def chama(metodo, caminho, corpo=None, token=TOKEN, cab=None):
        c = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
        h = dict(cab or {})
        if token is not None:
            h["Authorization"] = f"Bearer {token}"
        if isinstance(corpo, (dict, list)):
            corpo = json.dumps(corpo)
            h.setdefault("Content-Type", "application/json")
        if isinstance(corpo, str):
            corpo = corpo.encode("utf-8")
        c.request(metodo, caminho, body=corpo, headers=h)
        r = c.getresponse()
        dados = r.read()
        c.close()
        try:
            j = json.loads(dados) if dados else None
        except ValueError:
            j = None
        return r.status, j, dados, {k.lower(): v for k, v in r.getheaders()}

    yield types.SimpleNamespace(chama=chama, linhas=linhas, porta=porta, **vars(mundo))
    srv.shutdown()
    srv.server_close()


def mcp(api, metodo, params=None, mid=1, **kw):
    msg = {"jsonrpc": "2.0", "id": mid, "method": metodo}
    if params is not None:
        msg["params"] = params
    return api.chama("POST", "/mcp", msg, **kw)


def test_saude_nao_pede_token_e_o_resto_pede(api):
    s, j, _, _ = api.chama("GET", "/saude", token=None)
    assert s == 200 and j["ok"] is True
    for rota in ("/v1/projeto/listar", "/v1/caixa/listar", "/mcp"):
        assert api.chama("GET", rota, token=None)[0] == 401, rota
        assert api.chama("GET", rota, token="errado")[0] == 401, rota
    assert api.chama("GET", "/v1/projeto/listar", token=None, cab={"Authorization": TOKEN})[0] == 401, "sem a palavra Bearer"


def test_muitas_tentativas_com_token_errado_travam_por_um_minuto(api):
    for _ in range(api.m.FALHAS_AUTH_POR_MINUTO):
        assert api.chama("GET", "/v1/projeto/listar", token="errado")[0] == 401
    assert api.chama("GET", "/v1/projeto/listar", token="errado")[0] == 429
    assert api.chama("GET", "/v1/projeto/listar")[0] == 429, "ate o token certo espera: protege contra adivinhacao"


def test_rest_le_lista_e_busca(api):
    s, j, _, cab = api.chama("GET", "/v1/projeto/ler?caminho=memoria/ESTADO.md&inicio=2&fim=3")
    assert s == 200 and j["texto"] == "linha 2\nlinha 3" and cab["cache-control"] == "no-store"
    assert [i["nome"] for i in api.chama("GET", "/v1/projeto/listar")[1]["itens"]] == ["CLAUDE.md", "memoria", "scripts"]
    assert api.chama("GET", "/v1/projeto/buscar?q=Zebra")[1]["achados"][0]["caminho"] == "scripts/a.py"
    assert api.chama("GET", "/v1/kit/listar?tipo=skills")[1]["itens"][0]["nome"] == "minha-skill"
    assert api.chama("GET", "/v1/kit/ler?tipo=skills&nome=minha-skill")[0] == 200
    assert api.chama("GET", "/v1/caixa/listar")[0] == 200
    assert api.chama("GET", "/v1/caixa/ler?origem=entrada&nome=pedido-01.md")[0] == 200


@pytest.mark.parametrize("url,status", [
    ("/v1/projeto/ler?caminho=%2e%2e%2fCLAUDE.md", 400), ("/v1/projeto/ler?caminho=memoria%2f..%2f..%2fx", 400),
    ("/v1/projeto/ler?caminho=memoria/ESTADO.md%00.png", 400), ("/v1/projeto/ler?caminho=diagnostico/x.md", 403),
    ("/v1/projeto/ler?caminho=memoria/COM-SEGREDO.md", 403), ("/v1/projeto/ler", 400), ("/v1/projeto/ler?caminho=memoria/ESTADO.md&inicio=abc", 400),
    ("/v1/inexistente", 404), ("/qualquer", 404), ("/v1/kit/ler?tipo=skills&nome=..", 400),
])
def test_rest_recusa_com_status_limpo_e_sem_vazar_caminho_do_pc(api, url, status):
    s, j, bruto, _ = api.chama("GET", url)
    assert s == status, (url, s, bruto)
    assert str(api.tmp).encode() not in bruto and b"Traceback" not in bruto and SEGREDO_FALSO.encode() not in bruto


def test_rest_texto_puro_para_o_caixa_do_celular(api):
    """O `caixa sincronizar` do Termux e bash puro: lista com TAB e le o recado inteiro, sem JSON."""
    _escreve(api.base / "entrada" / "com espaco.md", "nao deve aparecer\n")
    s, _, bruto, cab = api.chama("GET", "/v1/caixa/listar?formato=texto")
    assert s == 200 and cab["content-type"].startswith("text/plain")
    linhas = bruto.decode("utf-8").splitlines()
    assert sorted(l.split("\t")[:2] for l in linhas) == [["entrada", "pedido-01.md"], ["retorno", "rev-01.md"]], "nome com espaco fica de fora"
    assert all(len(l.split("\t")) == 4 for l in linhas)
    s, _, bruto, cab = api.chama("GET", "/v1/caixa/bruto?origem=entrada&nome=pedido-01.md")
    assert s == 200 and bruto == b"Faca o resumo.\n" and cab["content-type"].startswith("text/plain")
    s, _, bruto, _ = api.chama("GET", "/v1/projeto/bruto?caminho=memoria/ESTADO.md")
    assert s == 200 and bruto.decode("utf-8").splitlines()[0] == "linha 1" and len(bruto.splitlines()) == 10


@pytest.mark.parametrize("url,status", [
    ("/v1/caixa/bruto?origem=entrada&nome=com%20espaco.md", 400), ("/v1/caixa/bruto?origem=saida&nome=x.md", 400),
    ("/v1/caixa/bruto?origem=entrada&nome=..%2Fretorno%2Frev-01.md", 400), ("/v1/caixa/bruto?origem=entrada&nome=nao.md", 404),
    ("/v1/projeto/bruto?caminho=memoria/COM-SEGREDO.md", 403), ("/v1/projeto/bruto?caminho=diagnostico/x.md", 403),
    ("/v1/projeto/bruto?caminho=memoria/GRANDE.md", 413), ("/v1/projeto/bruto?caminho=../CLAUDE.md", 400),
])
def test_rest_texto_puro_tem_as_mesmas_travas_e_erro_em_json(api, url, status):
    s, j, bruto, cab = api.chama("GET", url)
    assert s == status and cab["content-type"].startswith("application/json") and "erro" in j
    assert SEGREDO_FALSO.encode() not in bruto and str(api.tmp).encode() not in bruto


def test_rest_entrega_por_put_cria_o_arquivo(api):
    s, j, _, _ = api.chama("PUT", "/v1/caixa/saida?nome=do-celular", "# oi do celular\nacento: ação\n")
    assert s == 200
    texto = (api.base / "saida" / j["gravado"]).read_text(encoding="utf-8")
    assert "ação" in texto and "NAO REVISADO" in texto
    assert api.chama("PUT", "/v1/caixa/saida?nome=../x", "t")[0] == 400
    assert api.chama("PUT", "/v1/caixa/saida?nome=ok", b"\xff\xfe\x00", )[0] == 400, "texto que nao e UTF-8"
    assert api.chama("PUT", "/v1/caixa/saida?nome=ok", "t", token="errado")[0] == 401
    assert len(list((api.base / "saida").iterdir())) == 1


def test_corpo_grande_e_chunked_sao_recusados_antes_de_ler(api):
    s, j, _, _ = api.chama("PUT", "/v1/caixa/saida?nome=grande", "a" * (api.m.MAX_CORPO + 1))
    assert s == 413
    # o limite vale para QUALQUER rota (um JSON valido e enorme no /mcp tambem e recusado sem ser lido)
    enorme = '{"jsonrpc":"2.0","id":1,"method":"ping"}' + " " * (api.m.MAX_CORPO + 1)
    assert api.chama("POST", "/mcp", enorme)[0] == 413
    c = http.client.HTTPConnection("127.0.0.1", api.porta, timeout=10)
    c.putrequest("PUT", "/v1/caixa/saida?nome=chunk")
    c.putheader("Authorization", f"Bearer {TOKEN}")
    c.putheader("Transfer-Encoding", "chunked")
    c.endheaders()
    c.send(b"1\r\na\r\n0\r\n\r\n")
    assert c.getresponse().status == 411
    c.close()
    assert not list((api.base / "saida").iterdir())


def test_metodo_nao_permitido_e_erro_interno_nao_vazam(api, monkeypatch):
    assert api.chama("DELETE", "/v1/projeto/listar")[0] == 405
    assert api.chama("PUT", "/v1/projeto/listar", "x")[0] == 404
    monkeypatch.setattr(api.ponte, "projeto_listar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("C:\\Users\\passo\\segredo.txt")))
    s, j, bruto, _ = api.chama("GET", "/v1/projeto/listar")
    assert s == 500 and j == {"erro": "erro interno"} and b"passo" not in bruto


def test_log_registra_o_pedido_sem_token_e_sem_conteudo(api):
    api.chama("PUT", "/v1/caixa/saida?nome=log-teste", "CONTEUDO-DA-ENTREGA-XYZ")
    api.chama("GET", "/v1/projeto/ler?caminho=memoria/ESTADO.md")
    api.chama("GET", "/v1/projeto/listar", token="errado-123")
    tudo = "\n".join(api.linhas)
    assert "PUT /v1/caixa/saida" in tudo and "401" in tudo
    for proibido in (TOKEN, "errado-123", "CONTEUDO-DA-ENTREGA-XYZ", "ESTADO.md", "log-teste"):
        assert proibido not in tudo, f"o log nao pode conter {proibido!r}"


# ---------------------------------------------------------------- MCP

def test_mcp_initialize_negocia_versao_e_notificacao_volta_202(api):
    s, j, _, _ = mcp(api, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
    assert s == 200 and j["id"] == 1 and j["result"]["protocolVersion"] == "2025-03-26"
    assert j["result"]["serverInfo"]["name"] == "ponte-pc" and "tools" in j["result"]["capabilities"]
    assert mcp(api, "initialize", {"protocolVersion": "1999-01-01"})[1]["result"]["protocolVersion"] == "2025-06-18"
    s, _, bruto, _ = api.chama("POST", "/mcp", {"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert s == 202 and bruto == b""
    assert mcp(api, "ping")[1]["result"] == {}


def test_mcp_lista_as_10_ferramentas_com_esquema(api):
    ferramentas = mcp(api, "tools/list")[1]["result"]["tools"]
    assert [f["name"] for f in ferramentas] == ["projeto_listar", "projeto_ler", "projeto_buscar", "kit_listar", "kit_ler",
                                                 "caixa_listar", "caixa_ler", "entregar", "navegador_ler", "acao_pc"]
    for f in ferramentas:
        assert f["description"] and f["inputSchema"]["type"] == "object"
    for f in ferramentas:
        if f["name"].startswith("projeto_"):
            assert not {"grav", "escrev", "alter", "apag"} & {p[:5] for p in f["description"].lower().split()}, f"{f['name']} so le"
    entregar = next(f for f in ferramentas if f["name"] == "entregar")["description"].lower()
    assert "nunca altera o projeto" in entregar and "saida" in entregar and "nao revisado" in entregar


def test_mcp_chama_ferramentas_e_devolve_erro_como_resultado(api):
    r = mcp(api, "tools/call", {"name": "projeto_ler", "arguments": {"caminho": "memoria/ESTADO.md", "inicio": 1, "fim": 2}})[1]["result"]
    assert r["isError"] is False and json.loads(r["content"][0]["text"])["texto"] == "linha 1\nlinha 2"
    r = mcp(api, "tools/call", {"name": "projeto_ler", "arguments": {"caminho": "../x"}})[1]["result"]
    assert r["isError"] is True and "Erro 400" in r["content"][0]["text"] and str(api.tmp) not in r["content"][0]["text"]
    assert mcp(api, "tools/call", {"name": "nao-existe", "arguments": {}})[1]["result"]["isError"] is True
    assert mcp(api, "tools/call", {"name": "projeto_listar"})[1]["result"]["isError"] is False, "arguments e opcional"
    assert mcp(api, "tools/call", "texto-solto")[1]["result"]["isError"] is True


def test_mcp_entregar_grava_em_saida_e_recusa_segredo(api):
    r = mcp(api, "tools/call", {"name": "entregar", "arguments": {"nome": "via-mcp", "texto": "# pelo MCP\n"}})[1]["result"]
    assert r["isError"] is False
    nome = json.loads(r["content"][0]["text"])["gravado"]
    assert (api.base / "saida" / nome).is_file()
    r = mcp(api, "tools/call", {"name": "entregar", "arguments": {"nome": "ruim", "texto": f"token = {SEGREDO_FALSO}"}})[1]["result"]
    assert r["isError"] is True and "segredo" in r["content"][0]["text"]
    assert len(list((api.base / "saida").iterdir())) == 1


def test_mcp_erros_de_protocolo(api):
    assert mcp(api, "metodo/que/nao/existe")[1]["error"]["code"] == -32601
    assert api.chama("POST", "/mcp", "{nao e json")[0] == 400
    s, j, _, _ = api.chama("POST", "/mcp", [{"jsonrpc": "2.0", "id": 1, "method": "ping"}])
    assert s == 400 and j["error"]["code"] == -32600, "lote nao suportado"
    assert api.chama("POST", "/mcp", {"id": 1, "method": "ping"})[1]["error"]["code"] == -32600, "sem jsonrpc 2.0"
    s, _, _, cab = api.chama("GET", "/mcp")
    assert s == 405 and cab["allow"] == "POST", "sem fluxo SSE: o cliente MCP aceita o 405 e segue"
    assert api.chama("DELETE", "/mcp")[0] == 405
    assert mcp(api, "resources/list")[1]["result"] == {"resources": []}


# ---------------------------------------------------------------- navegador_ler (Qwen do celular)

def _ponte_com_navegador(importa_script, tmp_path, funcao, relogio=None):
    m = importa_script("ponte-pc.py")
    return m, m.Ponte(tmp_path / "proj", tmp_path / "base", relogio=relogio or (lambda: 1000.0), navegador=funcao)


def test_navegador_ler_devolve_a_pagina_e_marca_como_dado(importa_script, tmp_path):
    _, p = _ponte_com_navegador(importa_script, tmp_path, lambda u: {"url": u, "titulo": "T", "texto": "x", "truncado": False})
    r = p.chamar("navegador_ler", {"url": " https://a.com "})
    assert r["titulo"] == "T" and r["url"] == "https://a.com" and "nunca ordem" in r["aviso"]


@pytest.mark.parametrize("url", [None, "", "   ", 5])
def test_navegador_ler_sem_endereco_e_recusado(importa_script, tmp_path, url):
    m, p = _ponte_com_navegador(importa_script, tmp_path, lambda u: {})
    with pytest.raises(m.ErroPonte) as e:
        p.navegador_ler(url)
    assert e.value.status == 400


def test_navegador_ler_transforma_qualquer_erro_em_erro_da_ponte(importa_script, tmp_path):
    def explode(u):
        raise RuntimeError("x" * 500)
    m, p = _ponte_com_navegador(importa_script, tmp_path, explode)
    with pytest.raises(m.ErroPonte) as e:
        p.navegador_ler("https://a.com")
    assert e.value.status == 422 and len(e.value.mensagem) < 260


def test_navegador_ler_limita_por_minuto_e_libera_depois(importa_script, tmp_path):
    agora = [1000.0]
    m, p = _ponte_com_navegador(importa_script, tmp_path, lambda u: {"url": u}, relogio=lambda: agora[0])
    for _ in range(m.MAX_NAVEGADOR_POR_MINUTO):
        p.navegador_ler("https://a.com")
    with pytest.raises(m.ErroPonte) as e:
        p.navegador_ler("https://a.com")
    assert e.value.status == 429
    agora[0] += 61
    assert p.navegador_ler("https://a.com")["url"] == "https://a.com"


def test_navegador_padrao_recusa_endereco_interno_sem_abrir_nada(importa_script, tmp_path):
    """Sem falso: usa o navegador.py de verdade. A recusa acontece antes de procurar o Edge, entao roda em qualquer maquina."""
    m = importa_script("ponte-pc.py")
    p = m.Ponte(tmp_path / "proj", tmp_path / "base")
    for u in ("http://127.0.0.1:20128", "http://100.64.0.1:20130/saude", "http://192.168.0.1", "file:///etc/passwd"):
        with pytest.raises(m.ErroPonte) as e:
            p.navegador_ler(u)
        assert e.value.status == 422, u


# ---------------------------------------------------------------- acao_pc: lista fechada

class _Exec:
    def __init__(self, saida="ok", codigo=0, erro=None):
        self.cmds, self.saida, self.codigo, self.erro = [], saida, codigo, erro

    def __call__(self, cmd, **kw):
        self.cmds.append((cmd, kw))
        if self.erro:
            raise self.erro
        return types.SimpleNamespace(stdout=self.saida, stderr="", returncode=self.codigo)


def test_acao_pc_roda_comando_fixo_da_lista(mundo):
    ex = _Exec("Microfone: MUDO")
    mundo.ponte._executa = ex
    r = mundo.ponte.acao_pc("microfone-celular-mudo")
    (g, _), (cmd, kw) = ex.cmds  # 1o: adb-remoto garantir (cabo ou Tailscale); 2o: a acao
    assert g[-2:] == [str(mundo.proj / "scripts" / "adb-remoto.py"), "garantir"]
    assert cmd[-2:] == [str(mundo.proj / "scripts" / "microfone-bt.py"), "celular-mudo"] and cmd[1] == "-B"
    assert r["saida"] == "Microfone: MUDO" and r["codigo_de_saida"] == 0 and kw["timeout"] == mundo.m.MAX_ACAO_S
    assert "shell" not in kw and kw["stdin"] is not None


def test_acao_pc_sem_cabo_conecta_pela_tailscale_e_solta_no_fim(mundo):
    ex = _Exec("tailscale-nova")
    mundo.ponte._executa = ex
    mundo.ponte.acao_pc("microfone-celular-mudo")
    nomes = [c[-1] for c, _ in ex.cmds]
    assert nomes == ["garantir", "celular-mudo", "soltar"]


def test_acao_pc_com_cabo_nao_solta_nada(mundo):
    ex = _Exec("cabo")
    mundo.ponte._executa = ex
    mundo.ponte.acao_pc("microfone-celular-mudo")
    assert [c[-1] for c, _ in ex.cmds] == ["garantir", "celular-mudo"]


def test_acao_pc_da_ia_do_pc_nao_mexe_no_adb(mundo):
    ex = _Exec("ok")
    mundo.ponte._executa = ex
    mundo.ponte.acao_pc("ia-pc-status")
    assert not [c for c, _ in ex.cmds if "adb-remoto.py" in " ".join(c)]


@pytest.mark.parametrize("nome", [None, "", "rm", "microfone-status; calc", "../x", "Lista", "saida-ligar"])
def test_acao_pc_recusa_o_que_nao_esta_na_lista(mundo, nome):
    ex = _Exec()
    mundo.ponte._executa = ex
    erro(mundo, mundo.ponte.acao_pc, nome)
    assert ex.cmds == []


def test_acao_pc_lista_nao_roda_nada(mundo):
    ex = _Exec()
    mundo.ponte._executa = ex
    r = mundo.ponte.acao_pc("lista")
    assert "microfone-celular-mudo" in r["acoes"] and "lista" not in r["acoes"] and ex.cmds == []


def test_acao_pc_lista_nao_tem_nada_perigoso(mundo):
    for nome, (desc, script, *args) in mundo.m.ACOES_PC.items():
        if nome == "lista":
            continue
        assert (mundo.m.Path(mundo.m.__file__).parent / script).is_file(), script
        assert not {"--aplicar", "--remover", "remover", "apagar-tudo", "--confirmo-apagar-origem"} & set(args), nome
        assert script not in ("lote-pacotes.py", "sd-adotar.py", "omniroute-celular.ps1", "copia-a12.py", "reiniciar.py"), nome
        assert not (script == "vpn-celular.py" and "saida" in args), "saida pelo PC pode deixar o celular sem internet: fica com o `saida` do Termux"


def test_acao_pc_limite_por_minuto_e_uma_por_vez(mundo):
    mundo.ponte._executa = _Exec()
    for _ in range(mundo.m.MAX_ACOES_POR_MINUTO):
        mundo.ponte.acao_pc("saude")
    assert erro(mundo, mundo.ponte.acao_pc, "saude").status == 429
    mundo.ponte._acoes_recentes = []
    mundo.ponte._trava_acao.acquire()
    try:
        assert erro(mundo, mundo.ponte.acao_pc, "saude").status == 429
    finally:
        mundo.ponte._trava_acao.release()


def test_acao_pc_tempo_esgotado_e_saida_grande(mundo):
    import subprocess as sp
    mundo.ponte._executa = _Exec(erro=sp.TimeoutExpired("x", 1))
    assert erro(mundo, mundo.ponte.acao_pc, "auditoria").status == 504
    mundo.ponte._acoes_recentes = []
    mundo.ponte._executa = _Exec("a" * (mundo.m.MAX_SAIDA_ACAO + 500))
    r = mundo.ponte.acao_pc("auditoria")
    assert len(r["saida"]) <= mundo.m.MAX_SAIDA_ACAO + 30 and r["saida"].startswith("...")


def test_acao_pc_aparece_no_mcp_com_a_lista_no_enum(mundo):
    (f,) = [x for x in mundo.ponte.FERRAMENTAS if x["name"] == "acao_pc"]
    assert set(f["inputSchema"]["properties"]["nome"]["enum"]) == set(mundo.m.ACOES_PC)
    mundo.ponte._executa = _Exec("tudo ok")
    assert mundo.ponte.chamar("acao_pc", {"nome": "vpn-status"})["saida"] == "tudo ok"


def test_acao_pc_ps1_roda_pelo_pwsh(mundo):
    ex = _Exec("ok")
    mundo.ponte._executa = ex
    mundo.ponte.acao_pc("ia-pc-status")
    (cmd, _), = ex.cmds
    assert cmd[:3] == ["pwsh", "-NoProfile", "-File"] and cmd[3].endswith("ia-do-pc.ps1") and cmd[4:] == ["-SoVerificar"]


def test_acoes_do_obs_nao_mexem_no_adb_e_chamam_o_script_da_webcam(mundo):
    for nome in ("obs-camera-ligar", "obs-gravar-tela", "obs-desligar"):
        ex = _Exec("ok")
        mundo.ponte._executa = ex
        mundo.ponte.acao_pc(nome)
        assert not [c for c, _ in ex.cmds if "adb-remoto.py" in " ".join(c)], nome
        (cmd, _), = ex.cmds
        assert str(mundo.proj / "scripts" / "webcam-celular.py") in cmd


def test_acoes_do_obs_tem_lista_fechada_sem_argumento_livre(mundo):
    obs = {k: v for k, v in mundo.m.ACOES_PC.items() if k.startswith("obs-")}
    assert len(obs) == 11  # 06/11: obs-verificar (faixa preta)
    for k, (desc, script, *args) in obs.items():
        assert script == "webcam-celular.py" and desc
        assert all(a.startswith("--") or a in ("iniciar", "gravar", "parar", "parar-gravacao", "status", "live", "parar-live", "verificar") for a in args), k
