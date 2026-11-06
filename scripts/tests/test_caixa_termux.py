"""Testes de ponta a ponta do `caixa` do Termux (scripts/celular-kit/bin/caixa) contra o SERVIDOR REAL (scripts/ponte-pc.py) em 127.0.0.1.

O `caixa` e bash puro e usa o curl de verdade (PATH so com o curl, um registrador de argumentos e poucos utilitarios): assim o protocolo
cliente-servidor e testado inteiro, sem rede de verdade e sem tocar o celular nem o PC do Rafael. Rodam no WSL (scripts/testes-py.ps1).
"""
import http.server
import pathlib
import subprocess
import threading
import types

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
CAIXA = RAIZ / "scripts" / "celular-kit" / "bin" / "caixa"
BASH = next((p for p in ("/bin/bash", "/usr/bin/bash") if pathlib.Path(p).exists()), "/bin/bash")
CURL_REAL = next((p for p in ("/usr/bin/curl", "/bin/curl") if pathlib.Path(p).exists()), None)
pytestmark = pytest.mark.skipif(not pathlib.Path(BASH).exists() or not CURL_REAL, reason="precisa de bash e curl (os testes rodam no WSL)")
TOKEN = "caixa-token-" + "z" * 40
SEGREDO_FALSO = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"  # montado em pedacos: a varredura de segredos le este arquivo
UTILITARIOS = ("grep", "sed", "cut", "head", "tail", "tr", "cat", "mkdir", "rm", "date", "ls", "sort", "sleep", "mv", "cp", "chmod", "python3")
PREFIXO_TERMUX = "/data/data/com.termux/files/usr"


@pytest.fixture
def cel(tmp_path, importa_script):
    m = importa_script("ponte-pc.py")
    proj, base = tmp_path / "proj", tmp_path / "base"
    (proj / "memoria").mkdir(parents=True)
    (proj / "CLAUDE.md").write_text("# p\n", encoding="utf-8")
    kit = proj / "scripts" / "celular-kit"  # o PC serve ao celular o kit REAL do repositorio
    (kit / "bin").mkdir(parents=True)
    (kit / "boot").mkdir()
    for rel in ("bin/ia", "bin/caixa", "bin/saida", "bin/guarda", "bin/cel", "bin/memoria", "bin/link", "bin/controle-tv", "boot/iniciar-a12", "QWEN.md"):
        (kit / rel).write_bytes((RAIZ / "scripts" / "celular-kit" / rel).read_bytes())
    ponte = m.Ponte(proj, base)
    (base / "entrada" / "pedido-01.md").write_text("Faca o resumo.\nacento: ação\n", encoding="utf-8")
    (base / "retorno" / "rev-01.md").write_text("Veredito: COM CORRECOES\n", encoding="utf-8")
    srv = m.cria_servidor(ponte, TOKEN, 0, "127.0.0.1")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    home, util, fakebin = tmp_path / "home", tmp_path / "util", tmp_path / "fakebin"
    for d in (home / ".qwen", util, fakebin):
        d.mkdir(parents=True)
    (home / ".qwen" / ".env").write_text(f"OMNIROUTE_API_KEY=outra-coisa\nPONTE_PC_TOKEN={TOKEN}\n", encoding="utf-8")
    for nome in UTILITARIOS:
        real = next(p for p in (pathlib.Path("/usr/bin") / nome, pathlib.Path("/bin") / nome) if p.exists())
        (util / nome).symlink_to(real)
    log = tmp_path / "curl-args.txt"
    curl = fakebin / "curl"  # registra os argumentos (para provar que o token nunca vai na linha de comando) e chama o curl de verdade
    curl.write_text(f'#!/bin/bash\necho "$*" >> "{log}"\nexec {CURL_REAL} "$@"\n', encoding="utf-8")
    curl.chmod(0o755)
    porta = srv.server_address[1]

    def roda(*args, entrada="", env_extra=None, url=None):
        env = {"PATH": f"{fakebin}:{util}", "HOME": str(home), "PREFIX": PREFIXO_TERMUX, "PONTE_URL": url or f"http://127.0.0.1:{porta}"}
        env.update(env_extra or {})
        p = subprocess.Popen([BASH, str(CAIXA), *args], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        saida, _ = p.communicate(entrada, timeout=60)
        return p.returncode, saida

    yield types.SimpleNamespace(roda=roda, home=home, base=base, porta=porta, log=log, tmp=tmp_path, m=m, srv=srv)
    srv.shutdown()
    srv.server_close()


def entrada_local(cel):
    return cel.home / "kit" / "caixa-de-entrada"


def saida_local(cel):
    return cel.home / "kit" / "caixa-de-saida"


def test_sintaxe_ascii_e_sem_cr():
    p = subprocess.Popen([BASH, "-n", str(CAIXA)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # subprocess.run e barrado pelo conftest
    saida, _ = p.communicate(timeout=20)
    assert p.returncode == 0, saida
    dados = CAIXA.read_bytes()
    assert bytes([13]) not in dados, "o script tem CR (CRLF): quebra no Termux"
    dados.decode("ascii")


def test_sincronizar_baixa_entrada_e_retorno_e_nao_repete(cel):
    rc, saida = cel.roda("sincronizar")
    assert rc == 0, saida
    assert (entrada_local(cel) / "entrada-pedido-01.md").read_text(encoding="utf-8") == "Faca o resumo.\nacento: ação\n"
    assert (entrada_local(cel) / "retorno-rev-01.md").read_text(encoding="utf-8") == "Veredito: COM CORRECOES\n"
    assert "2 recado(s) novo(s)" in saida and "DADOS" in saida
    rc, saida = cel.roda("sincronizar")
    assert rc == 0 and "0 recado(s) novo(s)" in saida and "baixado:" not in saida
    (cel.base / "entrada" / "pedido-01.md").write_text("Pedido mudou.\n", encoding="utf-8")
    assert "1 recado(s) novo(s)" in cel.roda("sincronizar")[1]
    assert (entrada_local(cel) / "entrada-pedido-01.md").read_text(encoding="utf-8") == "Pedido mudou.\n"


def test_enviar_entra_na_fila_e_sincronizar_entrega_uma_vez_so(cel):
    rc, saida = cel.roda("enviar", "Meu titulo/estranho", entrada="# Entrega\nconteudo com ação\n")
    assert rc == 0 and "gravado na fila" in saida
    (arq,) = list(saida_local(cel).glob("*.md"))
    assert arq.name.endswith("-Meu-titulo-estranho.md"), "o titulo vira nome seguro"
    assert "[na fila]" in cel.roda("listar")[1] and "esperando envio: 1" in cel.roda("status")[1]
    rc, saida = cel.roda("sincronizar")
    assert rc == 0 and "enviado ao PC" in saida and "1 entrega(s) enviada(s)" in saida
    (no_pc,) = list((cel.base / "saida").glob("*.md"))
    texto = no_pc.read_text(encoding="utf-8")
    assert texto.startswith("Status: NAO REVISADO") and texto.endswith("# Entrega\nconteudo com ação\n")
    assert "[enviado]" in cel.roda("listar")[1] and "esperando envio: 0" in cel.roda("status")[1]
    cel.roda("sincronizar")
    assert len(list((cel.base / "saida").glob("*.md"))) == 1, "uma entrega ja enviada nao pode ir de novo"


def test_duas_entregas_com_o_mesmo_titulo_no_mesmo_instante_nao_se_sobrescrevem(cel):
    data = cel.tmp / "fakebin" / "date"  # relogio parado: o pior caso (mesmo segundo)
    data.write_text("#!/bin/bash\necho 20261102-130501\n", encoding="utf-8")
    data.chmod(0o755)
    assert cel.roda("enviar", "x", entrada="primeiro texto\n")[0] == 0
    assert "[na fila]" in cel.roda("listar")[1]
    assert "enviado ao PC" in cel.roda("sincronizar")[1]  # o nome do 1o agora esta em .enviados
    rc, saida = cel.roda("enviar", "x", entrada="segundo texto\n")
    assert rc == 0, saida
    textos = sorted(a.read_text(encoding="utf-8") for a in saida_local(cel).glob("*.md"))
    assert textos == ["primeiro texto\n", "segundo texto\n"], "a 2a entrega nao pode apagar nem herdar o nome da 1a"
    assert "enviado ao PC" in cel.roda("sincronizar")[1]
    chegou = sorted(a.read_text(encoding="utf-8").splitlines()[-1] for a in (cel.base / "saida").glob("*.md"))
    assert chegou == ["primeiro texto", "segundo texto"], "a 2a entrega tem de chegar ao PC"


def test_entrega_com_segredo_e_recusada_uma_vez_e_o_segredo_nao_aparece(cel):
    cel.roda("enviar", "com-chave", entrada=f"minha chave: {SEGREDO_FALSO}\n")
    rc, saida = cel.roda("sincronizar")
    assert rc == 0 and "RECUSADO pelo PC (HTTP 422)" in saida and SEGREDO_FALSO not in saida
    assert not list((cel.base / "saida").glob("*.md")), "o PC nao pode ter gravado a entrega com segredo"
    assert "[recusado]" in cel.roda("listar")[1]
    assert "RECUSADO" not in cel.roda("sincronizar")[1], "nao tenta de novo a que o PC recusou"
    assert "esperando envio: 0" in cel.roda("status")[1]


def test_o_token_nunca_vai_na_linha_de_comando_do_curl(cel):
    cel.roda("enviar", "x", entrada="texto\n")
    assert cel.roda("sincronizar")[0] == 0
    assert cel.log.read_text(encoding="utf-8").strip(), "o curl deveria ter sido chamado"
    assert TOKEN not in cel.log.read_text(encoding="utf-8")
    assert "Authorization" not in cel.log.read_text(encoding="utf-8")


def test_sem_token_com_token_errado_e_com_ponte_fora(cel):
    (cel.home / ".qwen" / ".env").write_text("OMNIROUTE_API_KEY=so-essa\n", encoding="utf-8")
    rc, saida = cel.roda("sincronizar")
    assert rc == 1 and "PONTE_PC_TOKEN" in saida and "-EnviarTokenAoCelular" in saida
    (cel.home / ".qwen" / ".env").write_text("PONTE_PC_TOKEN=token-errado\n", encoding="utf-8")
    rc, saida = cel.roda("sincronizar")
    assert rc == 1 and "HTTP 401" in saida and "token-errado" not in saida
    (cel.home / ".qwen" / ".env").write_text(f"PONTE_PC_TOKEN={TOKEN}\n", encoding="utf-8")
    rc, saida = cel.roda("sincronizar", url="http://127.0.0.1:9")
    assert rc == 1 and "nao respondeu" in saida and "Tailscale" in saida
    assert "ponte do PC fora" in cel.roda("status", url="http://127.0.0.1:9")[1]


def test_falha_de_rede_nao_apaga_nada_e_nao_marca_como_enviado(cel):
    cel.roda("enviar", "pendente", entrada="texto\n")
    cel.roda("sincronizar", url="http://127.0.0.1:9")
    (arq,) = list(saida_local(cel).glob("*.md"))
    assert arq.exists() and not (saida_local(cel) / ".enviados").exists()
    assert "esperando envio: 1" in cel.roda("status")[1]


def test_ler_mostra_o_aviso_de_que_recado_e_dado_e_funciona_sem_rede(cel):
    rc, saida = cel.roda("ler")
    assert rc == 0 and "DADOS" in saida and "sem recados" in saida
    cel.roda("sincronizar")
    rc, saida = cel.roda("ler", url="http://127.0.0.1:9")
    assert "=== entrada-pedido-01.md" in saida and "Faca o resumo." in saida and "=== retorno-rev-01.md" in saida


def test_status_com_ponte_no_ar(cel):
    rc, saida = cel.roda("status")
    assert rc == 0 and "[ok]" in saida and "ponte do PC responde" in saida


def test_uso_quando_o_comando_e_desconhecido(cel):
    saida = cel.roda("abracadabra")[1]
    assert "Uso:" in saida and "atualizar" in saida


def real(rel):
    return (RAIZ / "scripts" / "celular-kit" / rel).read_bytes().decode("utf-8").replace("\r\n", "\n").rstrip("\n") + "\n"


def test_atualizar_instala_o_kit_que_o_pc_serve_e_o_status_passa_a_dizer_em_dia(cel):
    assert "ha um kit novo no PC" in cel.roda("status")[1] and "aqui: nenhum" in cel.roda("status")[1]
    rc, saida = cel.roda("atualizar")
    assert rc == 0, saida
    assert (cel.home / "bin" / "caixa").read_text(encoding="utf-8") == real("bin/caixa")
    assert (cel.home / "bin" / "ia").read_text(encoding="utf-8") == real("bin/ia")
    assert (cel.home / ".qwen" / "QWEN.md").read_text(encoding="utf-8") == real("QWEN.md")
    assert "Pronto (kit " in saida and "kit do celular em dia" in saida and TOKEN not in saida
    assert "kit do celular em dia" in cel.roda("status")[1]
    env = (cel.home / ".qwen" / ".env").read_text(encoding="utf-8")
    assert "OMNIROUTE_API_KEY=outra-coisa\n" in env and f"PONTE_PC_TOKEN={TOKEN}\n" in env and env.count("PONTE_PC_TOKEN=") == 1
    assert not list((cel.home / ".cache").glob("caixa-instalador.*")), "o instalador baixado nao fica no celular"


def test_atualizar_repassa_o_codigo_de_saida_do_instalador(cel):
    corpo = b"#!/data/data/com.termux/files/usr/bin/bash\nexit 3\nponte_instalar \"$@\" < /dev/null\n"  # passa nas conferencias e falha ao rodar
    srv = _servidor_falso(corpo)
    try:
        rc, saida = cel.roda("atualizar", url=f"http://127.0.0.1:{srv.server_address[1]}")
    finally:
        srv.shutdown()
        srv.server_close()
    assert rc == 3, saida


def test_atualizar_nunca_poe_o_token_na_linha_de_comando_do_curl(cel):
    assert cel.roda("atualizar")[0] == 0
    texto = cel.log.read_text(encoding="utf-8")
    assert "/v1/celular/instalador" in texto and TOKEN not in texto and "Authorization" not in texto


def test_atualizar_com_token_errado_ou_ponte_fora_nao_troca_nada(cel):
    (cel.home / ".qwen" / ".env").write_text("PONTE_PC_TOKEN=token-errado\n", encoding="utf-8")
    rc, saida = cel.roda("atualizar")
    assert rc == 1 and "HTTP 401" in saida and not (cel.home / "bin").exists()
    (cel.home / ".qwen" / ".env").write_text(f"PONTE_PC_TOKEN={TOKEN}\n", encoding="utf-8")
    rc, saida = cel.roda("atualizar", url="http://127.0.0.1:9")
    assert rc == 1 and "nao respondeu" in saida and not (cel.home / "bin").exists()


def _servidor_falso(corpo):
    """Responde 200 com `corpo` a qualquer GET (a pagina de login do Wi-Fi da escola, por exemplo)."""
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, format, *args):  # noqa: A002 - sem log no terminal dos testes
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_atualizar_recusa_resposta_que_nao_e_o_instalador_inteiro(cel):
    cabeca_certa = b"#!/data/data/com.termux/files/usr/bin/bash\n"
    rabo_certo = b"ponte_instalar \"$@\" < /dev/null\n"
    for corpo in (b"<html>entre com a senha do Wi-Fi</html>", b"#!/bin/bash\necho tomei conta\n", b"",
                  cabeca_certa + b"if then (\n" + rabo_certo,  # cabeca e rabo certos, erro de sintaxe no meio
                  b"#!/bin/bash\necho tomei conta\n" + rabo_certo,  # so a primeira linha esta errada (sintaxe e rabo certos)
                  cabeca_certa + b"echo tomei conta\n"):  # primeira linha e sintaxe certas, so o rabo esta errado
        srv = _servidor_falso(corpo)
        try:
            rc, saida = cel.roda("atualizar", url=f"http://127.0.0.1:{srv.server_address[1]}")
        finally:
            srv.shutdown()
            srv.server_close()
        assert rc == 1 and "nao parece o instalador" in saida, (corpo, saida)
        assert not (cel.home / "bin").exists(), "nada foi instalado"
    inteiro = cel.m.Ponte(cel.tmp / "proj", cel.tmp / "base").instalador(None, "http://100.64.0.1:20130").encode("utf-8")
    srv = _servidor_falso(inteiro[: len(inteiro) // 2])  # download cortado no meio
    try:
        rc, saida = cel.roda("atualizar", url=f"http://127.0.0.1:{srv.server_address[1]}")
    finally:
        srv.shutdown()
        srv.server_close()
    assert rc == 1 and "nao parece o instalador" in saida and not (cel.home / "bin").exists()


def test_tempo_para_conectar_e_largo_e_ajustavel_e_valor_invalido_volta_ao_padrao(cel):
    """Medido em 31/10: o 1o pacote ao PC depois de um tempo parado leva 3 s ou mais para conectar (Tailscale e Wi-Fi acordando);
    com o limite antigo de 5 s o `caixa atualizar` chegou a dizer que a ponte nao respondeu."""
    rc, _ = cel.roda("status")
    assert rc == 0
    linhas = cel.log.read_text().splitlines()
    assert linhas and all("--connect-timeout 10" in l for l in linhas), linhas
    assert any("/saude" in l and "-m 15" in l for l in linhas), linhas
    cel.log.write_text("")
    cel.roda("status", env_extra={"IA_CONECTA": "4"})
    linhas = cel.log.read_text().splitlines()
    assert linhas and all("--connect-timeout 4" in l for l in linhas) and any("/saude" in l and "-m 9" in l for l in linhas), linhas
    for ruim in ("abc", "", "3s", "-1", "1.5"):
        cel.log.write_text("")
        cel.roda("status", env_extra={"IA_CONECTA": ruim})
        linhas = cel.log.read_text().splitlines()
        assert linhas and all("--connect-timeout 10" in l for l in linhas), (ruim, linhas)


# ---------------------------------------------------------------- caixa pedido e caixa retrato (protocolo unico, 03/11)
PEDIDO_OK = (
    "# PEDIDO: busca do mapa\n\nStatus: NAO REVISADO\nDe: Qwen\n\n## Pedido do Rafael\nquero achar o terminal\n\n## Objetivo\nachar lugar pelo nome\n\n"
    "## Cadeia\n1. Hermes pesquisa\n2. Claude decide\n\n## Passos ou script proposto\nnenhum\n\n## Seguranca\nso leitura\n\n## Pronto quando\no lugar aparece\n\n## Nao verificado\nnada\n"
)
SECOES_OBRIGATORIAS = ["## Pedido do Rafael", "## Objetivo", "## Cadeia", "## Seguranca", "## Pronto quando", "## Nao verificado"]


def test_pedido_completo_vai_ao_pc_com_o_prefixo(cel):
    cod, saida = cel.roda("pedido", "busca do mapa", entrada=PEDIDO_OK)
    assert cod == 0, saida
    no_pc = list((cel.base / "saida").glob("*PEDIDO-busca-do-mapa*.md"))
    assert len(no_pc) == 1, saida
    assert "quero achar o terminal" in no_pc[0].read_text(encoding="utf-8")
    assert list(saida_local(cel).glob("*-PEDIDO-busca-do-mapa*.md"))


@pytest.mark.parametrize("secao", SECOES_OBRIGATORIAS)
def test_pedido_sem_uma_secao_e_recusado_e_nada_fica_na_fila(cel, secao):
    texto = "\n".join(l for l in PEDIDO_OK.split("\n") if l != secao)
    cod, saida = cel.roda("pedido", "faltando", entrada=texto)
    assert cod == 1, saida
    assert secao.lstrip("# ") in saida
    assert not saida_local(cel).exists() or not list(saida_local(cel).glob("*.md"))
    assert not list((cel.base / "saida").glob("*PEDIDO*"))


def test_pedido_vazio_e_recusado(cel):
    cod, saida = cel.roda("pedido", "vazio", entrada="")
    assert cod == 1, saida
    assert not list((cel.base / "saida").glob("*PEDIDO*"))


@pytest.mark.parametrize("sem,com", [("## Seguranca", "## Segurança"), ("## Nao verificado", "## Não verificado")])
def test_pedido_aceita_os_titulos_com_acento(cel, sem, com):
    cod, saida = cel.roda("pedido", "acentos", entrada=PEDIDO_OK.replace(sem, com))
    assert cod == 0, saida


def test_pedido_com_a_ponte_fora_fica_na_fila_e_nao_e_erro(cel):
    cod, saida = cel.roda("pedido", "sem rede", entrada=PEDIDO_OK, url="http://127.0.0.1:9", env_extra={"IA_CONECTA": "1"})
    assert cod == 0, saida
    assert "fila" in saida
    assert list(saida_local(cel).glob("*-PEDIDO-sem-rede*.md"))


def test_pedido_com_segredo_e_recusado_pelo_pc_e_o_segredo_nao_aparece(cel):
    cod, saida = cel.roda("pedido", "segredo", entrada=PEDIDO_OK + "chave " + SEGREDO_FALSO + "\n")
    assert SEGREDO_FALSO not in saida
    assert not list((cel.base / "saida").glob("*PEDIDO*"))


def test_modelo_mostra_todas_as_secoes_e_passa_no_proprio_filtro(cel):
    cod, modelo = cel.roda("modelo")
    assert cod == 0
    for secao in SECOES_OBRIGATORIAS:
        assert secao in modelo
    cod2, saida = cel.roda("pedido", "do modelo", entrada=modelo)
    assert cod2 == 0, saida


def test_retrato_baixa_o_claude_e_a_memoria_sem_as_subpastas(cel):
    proj = cel.tmp / "proj"
    (proj / "memoria" / "ESTADO.md").write_text("estado: ação\n", encoding="utf-8")
    (proj / "memoria" / "nuvem").mkdir()
    (proj / "memoria" / "nuvem" / "DIARIO.md").write_text("nao vem\n", encoding="utf-8")
    cod, saida = cel.roda("retrato")
    assert cod == 0, saida
    dest = cel.home / "kit" / "projeto-android-embeeded"
    assert (dest / "CLAUDE.md").read_text(encoding="utf-8") == "# p\n"
    assert (dest / "memoria" / "ESTADO.md").read_text(encoding="utf-8") == "estado: ação\n"
    assert not (dest / "memoria" / "nuvem").exists()
    assert (dest / ".retrato").read_text(encoding="utf-8").strip()
    assert "retrato" in cel.roda("status")[1]


def test_retrato_com_a_ponte_fora_nao_apaga_o_que_ja_existe(cel):
    dest = cel.home / "kit" / "projeto-android-embeeded" / "memoria"
    dest.mkdir(parents=True)
    (dest / "ESTADO.md").write_text("velho\n", encoding="utf-8")
    cod, _ = cel.roda("retrato", url="http://127.0.0.1:9", env_extra={"IA_CONECTA": "1"})
    assert cod == 1
    assert (dest / "ESTADO.md").read_text(encoding="utf-8") == "velho\n"


def test_retrato_nao_troca_arquivo_bom_quando_o_pc_recusa_um_deles(cel):
    proj = cel.tmp / "proj"
    (proj / "memoria" / "BOM.md").write_text("bom\n", encoding="utf-8")
    (proj / "memoria" / "RUIM.md").write_text("chave " + SEGREDO_FALSO + "\n", encoding="utf-8")
    dest = cel.home / "kit" / "projeto-android-embeeded" / "memoria"
    dest.mkdir(parents=True)
    (dest / "RUIM.md").write_text("copia antiga\n", encoding="utf-8")
    cod, saida = cel.roda("retrato")
    assert cod == 0, saida
    assert (dest / "BOM.md").read_text(encoding="utf-8") == "bom\n"
    assert (dest / "RUIM.md").read_text(encoding="utf-8") == "copia antiga\n"
    assert SEGREDO_FALSO not in saida


def test_uso_cita_pedido_modelo_e_retrato(cel):
    _, saida = cel.roda("xyz")
    for palavra in ("pedido", "modelo", "retrato"):
        assert palavra in saida
