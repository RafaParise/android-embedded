"""Testes do comando `memoria` do celular (Python de verdade, getprop/cel/pm FALSOS) e do pacote que a ponte do PC entrega."""
import http.server
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import threading

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
MEMORIA = pathlib.Path(os.environ.get("MEMORIA_SCRIPT") or SCRIPTS / "celular-kit" / "bin" / "memoria")  # mutantes: so em copia
TOKEN = "t" * 43
CHAVE_FALSA = "nv" + "api-" + "Ab" * 12  # montada na hora: o varredor de segredos do sync nao distingue chave falsa


def _carrega_ponte():
    spec = importlib.util.spec_from_file_location("ponte_pc_memoria", SCRIPTS / "ponte-pc.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Cel:
    def __init__(self, tmp):
        self.tmp = tmp
        self.home = tmp / "home"
        self.bin = tmp / "bin"
        self.home.mkdir()
        self.bin.mkdir()
        self.dir = self.home / "kit" / "memoria"
        falsos = {
            "getprop": '#!/bin/bash\ncase "$1" in ro.product.model) echo SM-A125M ;; ro.build.version.release) echo 12 ;; esac\n',
            "cel": '#!/bin/bash\n[ "$1" = apps ] && printf "package:org.fossify.gallery\\npackage:com.termux\\n"\n',
            "pm": "#!/bin/bash\nexit 1\n",
        }
        for nome, texto in falsos.items():
            (self.bin / nome).write_text(texto)
            (self.bin / nome).chmod(0o755)

    def roda(self, *args, env_extra=None):
        env = {"HOME": str(self.home), "PATH": f"{self.bin}:/usr/bin:/bin", "LANG": "C.UTF-8", **(env_extra or {})}
        p = subprocess.Popen([sys.executable, str(MEMORIA), *args], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        saida, _ = p.communicate(timeout=60)
        return p.returncode, saida

    def topico(self, nome):
        return (self.dir / "topicos" / f"{nome}.md").read_text(encoding="utf-8")


@pytest.fixture
def cel(tmp_path):
    return Cel(tmp_path)


def test_lembrar_e_buscar(cel):
    rc, s = cel.roda("lembrar", "wifi", "O reinicio do Wi-Fi pelo cel leva uns 10 segundos")
    assert rc == 0 and "Guardado" in s
    rc, s = cel.roda("buscar", "reinicio wifi")
    assert rc == 0 and "wifi" in s and "10 segundos" in s
    assert "## Aprendido" in cel.topico("wifi") and "O reinicio do Wi-Fi" in cel.topico("wifi")
    assert cel.roda("lembrar", "wifi", "O reinicio do Wi-Fi pelo cel leva uns 10 segundos")[1].startswith("Ja estava")


@pytest.mark.parametrize("fato,motivo", [
    ("a senha do wifi e Casa12345", "senha"),
    ("chave " + CHAVE_FALSA, "chave"),
    ("o e-mail dele e fulano@exemplo.com", "e-mail"),
    ("CPF 123.456.789-09", "CPF"),
    ("nota do aluno no MAPAO", "aluno"),
])
def test_lembrar_recusa_dado_sensivel(cel, fato, motivo):
    rc, s = cel.roda("lembrar", "teste", fato)
    assert rc == 2 and "Recusado" in s and motivo.lower() in s.lower()
    assert not (cel.dir / "topicos" / "teste.md").exists()


def test_topico_invalido_e_pc_sao_recusados(cel):
    assert cel.roda("lembrar", "../fora", "x")[0] == 2
    assert cel.roda("lembrar", "Maiuscula", "x")[0] == 2
    rc, s = cel.roda("lembrar", "pc-estado", "x")
    assert rc == 2 and "pc-" in s


def test_esquecer_vai_para_a_lixeira_e_nunca_apaga(cel):
    cel.roda("lembrar", "tv", "a TV da sala aceita Miracast")
    cel.roda("lembrar", "tv", "a TV do quarto nao aceita")
    rc, s = cel.roda("esquecer", "tv", "quarto")
    assert rc == 0 and "lixeira" in s
    assert "quarto" not in cel.topico("tv") and "sala" in cel.topico("tv")
    assert "quarto" in (cel.dir / "lixeira" / "tv.md").read_text(encoding="utf-8")


def test_atualizar_gera_aparelho_e_apps_e_mantem_o_aprendido(cel):
    cel.roda("lembrar", "aparelho", "a bateria esquenta acima de 58 graus com carga maxima")
    rc, s = cel.roda("atualizar")
    assert rc == 0, s
    ap = cel.topico("aparelho")
    assert "SM-A125M" in ap and "58 graus" in ap, "o atualizar refaz o topo e guarda o aprendido"
    assert "org.fossify.gallery" in cel.topico("apps")
    assert cel.roda("buscar", "fossify")[1].count("apps") >= 1


class _PonteFalsa(http.server.BaseHTTPRequestHandler):
    pacote = {}

    def do_GET(self):
        if self.path != "/v1/memoria/pacote" or self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self.send_response(401)
            self.end_headers()
            return
        corpo = json.dumps(self.pacote).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *_):
        pass


@pytest.fixture
def ponte_falsa():
    srv = http.server.HTTPServer(("127.0.0.1", 0), _PonteFalsa)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()


def test_atualizar_pc_traz_os_documentos_e_troca_so_os_pc(cel, ponte_falsa):
    (cel.home / ".qwen").mkdir()
    (cel.home / ".qwen" / ".env").write_text(f"PONTE_PC_TOKEN={TOKEN}\n")
    url = f"http://127.0.0.1:{ponte_falsa.server_port}"
    _PonteFalsa.pacote = {"arquivos": {"pc-estado.md": "# Estado\nsaida pelo PC ligada", "pc-velho.md": "# velho",
                                       "fora.md": "nao comeca com pc-", "pc-chave.md": CHAVE_FALSA}}
    cel.roda("lembrar", "meu", "isto e do celular")
    rc, s = cel.roda("atualizar", "--pc", env_extra={"PONTE_URL": url})
    assert rc == 0, s
    tops = {p.stem for p in (cel.dir / "topicos").glob("*.md")}
    assert {"pc-estado", "pc-velho", "meu"} <= tops and "fora" not in tops and "pc-chave" not in tops
    _PonteFalsa.pacote = {"arquivos": {"pc-estado.md": "# Estado\nnovo"}}
    assert cel.roda("atualizar", "--pc", env_extra={"PONTE_URL": url})[0] == 0
    tops = {p.stem for p in (cel.dir / "topicos").glob("*.md")}
    assert "pc-velho" not in tops and (cel.dir / "lixeira" / "pc-velho.md").exists() and "meu" in tops
    assert "novo" in cel.topico("pc-estado")


def test_atualizar_pc_sem_token_ou_sem_pc_nao_estraga_nada(cel):
    cel.roda("lembrar", "meu", "fica")
    rc, s = cel.roda("atualizar", "--pc")
    assert rc == 2 and "PONTE_PC_TOKEN" in s
    (cel.home / ".qwen").mkdir()
    (cel.home / ".qwen" / ".env").write_text(f"PONTE_PC_TOKEN={TOKEN}\n")
    rc, s = cel.roda("atualizar", "--pc", env_extra={"PONTE_URL": "http://127.0.0.1:9"})
    assert rc == 3 and "nao respondeu" in s and "fica" in cel.topico("meu")


def test_status_e_topicos(cel):
    cel.roda("lembrar", "a", "um fato")
    assert "1 topicos" in cel.roda("status")[1]
    assert cel.roda("topicos")[1].startswith("a ")


# ---------------------------------------------------------------- lado do PC: o pacote

@pytest.fixture
def ponte(tmp_path):
    m = _carrega_ponte()
    proj = tmp_path / "proj"
    (proj / "memoria").mkdir(parents=True)
    (proj / "CLAUDE.md").write_text("# regras\nnunca abrir MAPAO\ncontato: alguem@exemplo.com\n", encoding="utf-8")
    (proj / "memoria" / "ESTADO.md").write_text("# estado\nok\n", encoding="utf-8")
    (proj / "memoria" / "DECISOES.md").write_text("chave sk-" + "a" * 40 + "\n", encoding="utf-8")
    projetos = tmp_path / "Projetos"
    for rel, texto in {"arena/README.md": "# ARENA\njogo", "kit/LEIA-ME.md": "# kit", "copia-kit/LEIA-ME.md": "# kit",
                       "notas-alunos/README.md": "# lista", "outro/MAPAO_2026.md": "x", "outro/notas.md": "nao e leia-me",
                       "x/y/README.md": "# fundo\nRA 123456789 linha de aluno\nresto"}.items():
        (projetos / rel).parent.mkdir(parents=True, exist_ok=True)
        (projetos / rel).write_text(texto, encoding="utf-8")
    p = m.Ponte(proj, tmp_path / "base")
    p.pasta_projetos = projetos
    p._executa = lambda cmd, **kw: type("R", (), {"stdout": ""})()  # sem git de verdade nos testes
    return p


def test_pacote_leva_a_lista_fechada_e_os_leia_me_sem_dado_sensivel(ponte):
    arq = ponte.memoria_pacote()["arquivos"]
    assert "pc-claude.md" in arq and "pc-estado.md" in arq
    assert "MAPAO" in arq["pc-claude.md"], "a regra que cita o MAPAO fica"
    assert "alguem@exemplo.com" not in arq["pc-claude.md"], "linha com e-mail sai"
    assert "pc-decisoes.md" not in arq, "documento com segredo nao vai"
    assert "pc-proj-arena.md" in arq and "pc-proj-x-y.md" in arq
    assert "123456789" not in arq["pc-proj-x-y.md"] and "resto" in arq["pc-proj-x-y.md"]
    assert not [k for k in arq if "aluno" in k or "mapao" in k.lower() or "notas" in k]
    assert sum(1 for v in arq.values() if v == "# kit") == 1, "mesmo LEIA-ME por atalho de pasta vai uma vez so"


def test_rota_do_pacote_exige_token(ponte):
    import http.client
    m = _carrega_ponte()
    srv = m.cria_servidor(ponte, TOKEN, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        def pede(cab):
            c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
            c.request("GET", "/v1/memoria/pacote", headers=cab)
            r = c.getresponse()
            return r.status, r.read()
        assert pede({})[0] == 401
        st, corpo = pede({"Authorization": f"Bearer {TOKEN}"})
        assert st == 200 and "pc-estado.md" in json.loads(corpo)["arquivos"]
    finally:
        srv.shutdown()


EVENTOS = "\n".join([
    '    time="2026-11-03 07:10:00" type=ACTIVITY_RESUMED package=org.fossify.messages class=X',
    '    time="2026-11-03 07:12:00" type=ACTIVITY_RESUMED package=com.sec.android.app.launcher class=X',
    '    time="2026-11-03 20:30:00" type=ACTIVITY_RESUMED package=com.termux class=X',
    '    time="2026-11-03 21:00:00" type=ACTIVITY_RESUMED package=com.termux class=X',
    '    time="2026-11-04 06:50:00" type=ACTIVITY_RESUMED package=org.fossify.messages class=X',
])


def test_rotina_guarda_historico_e_resume_por_periodo(cel):
    (cel.bin / "cel").write_text("#!/bin/bash\n[ \"$1\" = sh ] && cat \"$HOME/eventos.txt\"\n")
    (cel.home / "eventos.txt").write_text(EVENTOS)
    rc, s = cel.roda("rotina")
    assert rc == 0 and "Rotina atualizada" in s, s
    r = cel.topico("rotina")
    assert "noite: com.termux (2)" in r and "launcher" not in r, "o launcher nao e rotina"
    assert "2026-11-03: 07:10 a 21:00" in r
    (cel.home / "eventos.txt").write_text('    time="2026-11-05 13:00:00" type=ACTIVITY_RESUMED package=org.videolan.vlc class=X')
    cel.roda("rotina")
    r = cel.topico("rotina")
    assert "2026-11-03" in r and "2026-11-05" in r, "o historico fica mesmo depois que o Android esquece"


def test_cartao_sd_vira_topicos_sd_que_valem_offline(cel, tmp_path):
    cartao = tmp_path / "storage"
    for rel, texto in {"0A32/Projetos/ARENA/README.md": "# ARENA\njogo educativo\ncontato x@y.com",
                       "0A32/Projetos/notas-alunos/README.md": "# nao", "0A32/Projetos/Kit/sub/LEIA-ME.md": "# kit"}.items():
        (cartao / rel).parent.mkdir(parents=True, exist_ok=True)
        (cartao / rel).write_text(texto, encoding="utf-8")
    rc, s = cel.roda("atualizar", env_extra={"MEMORIA_CARTAO": str(cartao)})
    assert rc == 0, s
    tops = {p.stem for p in (cel.dir / "topicos").glob("*.md")}
    assert "sd-arena" in tops and "sd-kit-sub" in tops and not [t for t in tops if "aluno" in t]
    assert "x@y.com" not in cel.topico("sd-arena")
    assert "educativo" in cel.roda("buscar", "educativo")[1]


def test_resumo_cabe_no_modelo_do_celular(cel):
    cel.roda("atualizar")
    cel.roda("lembrar", "tv", "a TV da sala aceita Miracast")
    rc, s = cel.roda("resumo")
    assert rc == 0 and len(s) <= 1801 and "aparelho:" in s and "Miracast" in s


def test_pacote_traz_o_que_o_claude_fez(ponte):
    class R:
        stdout = "- 04/11 20:00 Matrix: memoria local\n- 04/11 19:00 chave sk-" + "a" * 40
    chamadas = []
    ponte._executa = lambda cmd, **kw: (chamadas.append(cmd), R())[1]
    arq = ponte.memoria_pacote()["arquivos"]
    assert "pc-claude-recente.md" not in arq, "log com segredo nao vai"
    R.stdout = "- 04/11 20:00 Matrix: memoria local"
    arq = ponte.memoria_pacote()["arquivos"]
    assert "Matrix: memoria local" in arq["pc-claude-recente.md"] and chamadas[0][:2] == ["git", "-C"]


def test_topico_nao_cresce_sem_fim_e_o_antigo_vai_para_a_lixeira(cel):
    env = {"MEMORIA_MAX_APRENDIDO": "3"}
    for i in range(5):
        assert cel.roda("lembrar", "rede", f"fato numero {i} sobre a rede", env_extra=env)[0] == 0
    t = cel.topico("rede")
    assert "fato numero 4" in t and "fato numero 2" in t and "fato numero 1" not in t
    lix = (cel.dir / "lixeira" / "rede.md").read_text(encoding="utf-8")
    assert "fato numero 0" in lix and "fato numero 1" in lix


def test_o_que_o_claude_fez_inclui_outros_projetos_com_git_menos_pasta_de_aluno(ponte):
    (ponte.pasta_projetos / "arena" / ".git").mkdir()
    (ponte.pasta_projetos / "notas-alunos" / ".git").mkdir(parents=True, exist_ok=True)
    vistos = []

    def falso(cmd, **kw):
        vistos.append(cmd[2])
        return type("R", (), {"stdout": f"- 04/11 10:00 commit em {pathlib.Path(cmd[2]).name}"})()
    ponte._executa = falso
    txt = ponte.memoria_pacote()["arquivos"]["pc-claude-recente.md"]
    assert "## arena" in txt and "commit em arena" in txt and "## Android Embeeded" in txt
    assert not [v for v in vistos if "alunos" in v]


# ---------------------------------------------------------------- 05/11: memoria no cartao SD e indice dos arquivos dos projetos
def _cartao(tmp):
    raiz = tmp / "storage"
    proj = raiz / "SD1" / "Projetos" / "jogo"
    (proj / "src").mkdir(parents=True)
    (proj / "src" / "fisica.py").write_text("def gravidade():\n    return 9.81  # aceleracao do quadricoptero\n", encoding="utf-8")
    (proj / "LEIA-ME.md").write_text("# Jogo\n\nUm jogo de nave com quadricoptero.\n", encoding="utf-8")
    (proj / "contato.txt").write_text("quadricoptero do professor\nfale com fulano@escola.com\n", encoding="utf-8")
    (proj / "segredo.py").write_text("CHAVE = '" + CHAVE_FALSA + "'  # quadricoptero\n", encoding="utf-8")
    (proj / "alunos").mkdir()
    (proj / "alunos" / "lista.txt").write_text("quadricoptero turma A\n", encoding="utf-8")
    (proj / "node_modules").mkdir()
    (proj / "node_modules" / "x.js").write_text("quadricoptero\n", encoding="utf-8")
    (proj / "foto.png").write_bytes(b"\x89PNG quadricoptero")
    return raiz, proj


def test_arquivos_do_cartao_entram_na_busca(cel, tmp_path):
    raiz, proj = _cartao(tmp_path)
    env = {"MEMORIA_CARTAO": str(raiz)}
    rc, s = cel.roda("arquivos", env_extra=env)
    assert rc == 0 and "4 no indice" in s, s  # fisica.py, LEIA-ME.md, contato.txt e segredo.py (este sem texto)
    rc, s = cel.roda("buscar", "quadricoptero", env_extra=env)
    assert "fisica.py" in s and "LEIA-ME.md" in s
    assert "alunos" not in s and "node_modules" not in s and "foto.png" not in s
    assert "fulano@" not in s and "segredo.py" not in s


def test_arquivos_incremental_e_some_quando_apagado(cel, tmp_path):
    raiz, proj = _cartao(tmp_path)
    env = {"MEMORIA_CARTAO": str(raiz)}
    cel.roda("arquivos", env_extra=env)
    rc, s = cel.roda("arquivos", env_extra=env)
    assert "(0 novos" in s
    (proj / "src" / "fisica.py").unlink()
    cel.roda("arquivos", env_extra=env)
    rc, s = cel.roda("buscar", "gravidade", env_extra=env)
    assert "fisica.py" not in s


def test_memoria_no_cartao_com_reserva_interna(cel, tmp_path):
    cel.roda("lembrar", "wifi", "fato antigo de wi-fi")
    sd = tmp_path / "sd" / "matrix-memoria"
    rc, s = cel.roda("cartao", "ligar", str(sd))
    assert rc == 0 and "conferidos" in s
    assert (sd / "topicos" / "wifi.md").exists()
    cel.roda("lembrar", "wifi", "fato novo guardado no cartao")
    assert "fato novo" in (sd / "topicos" / "wifi.md").read_text(encoding="utf-8")
    assert "fato novo" in cel.topico("wifi")  # a reserva interna acompanha
    rc, s = cel.roda("status")
    assert "cartao SD" in s
    sd.rename(tmp_path / "sd" / "fora")  # cartao tirado: usa a reserva, sem erro
    rc, s = cel.roda("buscar", "fato novo")
    assert rc == 0 and "guardado no cartao" in s
    rc, s = cel.roda("cartao", "status")
    assert "reserva interna" in s


def test_cartao_desligar_traz_de_volta(cel, tmp_path):
    sd = tmp_path / "sd" / "m"
    cel.roda("cartao", "ligar", str(sd))
    cel.roda("lembrar", "tela", "so no cartao antes de desligar")
    rc, s = cel.roda("cartao", "desligar")
    assert rc == 0 and "memoria interna" in s
    assert "so no cartao" in cel.topico("tela")
    assert not (cel.home / "kit" / "memoria-no-cartao").exists()


def test_arquivos_pula_bibliotecas_de_terceiros(cel, tmp_path):
    raiz, proj = _cartao(tmp_path)
    (proj / "Python314" / "Doc").mkdir(parents=True)
    (proj / "Python314" / "Doc" / "timeit.html").write_text("quadricoptero timer\n", encoding="utf-8")
    (proj / "scripts").mkdir()
    (proj / "scripts" / "util.py").write_text("# quadricoptero util\n", encoding="utf-8")
    env = {"MEMORIA_CARTAO": str(raiz)}
    cel.roda("arquivos", env_extra=env)
    rc, s = cel.roda("buscar", "quadricoptero", "-n", "20", env_extra=env)
    assert "timeit.html" not in s and "util.py" in s


def test_pacote_traz_o_blueprint_e_o_plano_do_projeto_matrix_celular(ponte):
    mc = ponte.pasta_projetos / "matrix-celular" / "memoria"
    mc.mkdir(parents=True)
    (mc / "BLUEPRINT-A12.md").write_text("# BLUEPRINT\nsem infravermelho\nconta: alguem@exemplo.com\n", encoding="utf-8")
    (mc / "PLANO.md").write_text("# plano do Matrix\n", encoding="utf-8")
    (mc / "OUTRO.md").write_text("# nao vai\n", encoding="utf-8")
    arq = ponte.memoria_pacote()["arquivos"]
    assert "sem infravermelho" in arq["pc-matrix-blueprint-a12.md"] and "alguem@" not in arq["pc-matrix-blueprint-a12.md"]
    assert "pc-matrix-plano.md" in arq and not [k for k in arq if "outro" in k]
