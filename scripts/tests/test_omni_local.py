"""omni-local (scripts/omniroute-celular/omni-local.sh): o ajudante que ativa a RESERVA do OmniRoute do celular com chaves de provedor.
O que mais importa aqui e o cuidado com a chave: ela vem so pela entrada padrao, nunca vai na linha de comando e nunca aparece na saida.
Roda no WSL com curl e node FALSOS (o python3 e de verdade); nada toca o celular, a rede ou o adb."""
import json
import os
import pathlib
import shutil
import signal
import subprocess
import time

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
PASTA = RAIZ / "scripts" / "omniroute-celular"
SCRIPT = PASTA / "omni-local.sh"
COMBOS = PASTA / "omni-local.combos.json"
BASH = next((p for p in ("/bin/bash", "/usr/bin/bash") if pathlib.Path(p).exists()), "/bin/bash")
pytestmark = pytest.mark.skipif(not pathlib.Path(BASH).exists() or not shutil.which("python3"), reason="precisa de bash e python3 (os testes rodam no WSL)")
SIGKILL = getattr(signal, "SIGKILL", 9)

# chaves FALSAS, curtas de proposito (o varredor de segredos do sync nao pode confundir com chave de verdade)
CHAVE_NVIDIA = "nvapi-FALSA123456789"
CHAVE_GEMINI = "AIzaFALSA12345678901"
CHAVE_GEMINI_NOVA = "AQ.FALSA123456789012345"   # formato novo do Google (01/11/2026): "AQ." + 50 caracteres; aqui curta de proposito
CHAVE_OPENROUTER = "sk-or-FALSA1234567890"
CHAVE_LOCAL = "chave-local-teste"
SENHA = "senha-teste"

FALSO_CURL = r"""#!/bin/bash
echo "curl $*" >> "$FAKE_LOG"
url=""; metodo=GET; saida=""; quer=0; cfg=0; stdin_corpo=0; jar_w=""; dados=""
while [ $# -gt 0 ]; do
  case "$1" in
    -X) metodo="$2"; shift 2 ;;
    -o) saida="$2"; shift 2 ;;
    -w) quer=1; shift 2 ;;
    -K) cfg=1; shift 2 ;;
    -c) jar_w="$2"; shift 2 ;;
    --data-binary) [ "$2" = "@-" ] && stdin_corpo=1; [ "$metodo" = GET ] && metodo=POST; shift 2 ;;   # como o curl de verdade: dados implicam POST
    -d) dados="$2"; metodo=POST; shift 2 ;;
    -H|-m|-b|--connect-timeout) shift 2 ;;
    http*) url="$1"; shift ;;
    *) shift ;;
  esac
done
n=$(cat "$FAKE_ESTADO/n" 2>/dev/null || echo 0); n=$((n + 1)); echo $n > "$FAKE_ESTADO/n"
alvo="${url#http://}"; caminho="/${alvo#*/}"
echo "REQ $n $metodo $caminho" >> "$FAKE_LOG"
[ $cfg = 1 ] && cat > "$FAKE_ESTADO/cfg-$n.txt"
[ $stdin_corpo = 1 ] && cat > "$FAKE_ESTADO/corpo-$n.txt"
[ -n "$dados" ] && printf '%s' "$dados" > "$FAKE_ESTADO/corpo-$n.txt"
if [ ! -e "$FAKE_ESTADO/no_ar" ]; then [ $quer = 1 ] && printf '000'; exit 7; fi
codigo=200; corpo='{}'
case "$metodo $caminho" in
  "POST /api/auth/login") [ -n "$jar_w" ] && echo cookie > "$jar_w"; [ -e "$FAKE_ESTADO/login-recusado" ] && codigo=401 ;;
  "GET /api/providers?limit=5000") corpo=$(cat "$FAKE_ESTADO/conexoes.json" 2>/dev/null || echo '{"connections":[]}') ;;
  "POST /api/providers") codigo=201; corpo='{"connection":{"id":"cid-novo"}}'; [ -e "$FAKE_ESTADO/provedor-erro.json" ] && { codigo=400; corpo=$(cat "$FAKE_ESTADO/provedor-erro.json"); } ;;
  "POST /api/providers/"*"/test") corpo=$(cat "$FAKE_ESTADO/teste.json" 2>/dev/null || echo '{"valid": true, "error": null}') ;;
  "GET /api/combos") corpo=$(cat "$FAKE_ESTADO/combos-atuais.json" 2>/dev/null || echo '[]') ;;
  "POST /api/combos") codigo=201 ;;
  "POST /v1/chat/completions") codigo=$(cat "$FAKE_ESTADO/chat.cod" 2>/dev/null || echo 200); corpo=$(cat "$FAKE_ESTADO/chat.json" 2>/dev/null || echo '{}') ;;
esac
chave_forca="$FAKE_ESTADO/forca-$(printf '%s' "$metodo $caminho" | tr ' /?' '___')"   # codigos HTTP forcados, um por chamada (o primeiro e consumido)
if [ -s "$chave_forca" ]; then codigo=$(head -1 "$chave_forca"); sed -i 1d "$chave_forca"; case "$codigo" in 2*) ;; *) corpo='{"error":"falha forcada"}' ;; esac; fi
[ -n "$saida" ] && [ "$saida" != /dev/null ] && printf '%s' "$corpo" > "$saida"
[ $quer = 1 ] && printf '%s' "$codigo"
exit 0
"""
FALSO_NODE = r"""#!/bin/bash
echo "node $* DATA_DIR=$DATA_DIR HOST=$OMNIROUTE_SERVER_HOST MB=$OMNIROUTE_MEMORY_MB PWD=$PWD" >> "$FAKE_LOG"
[ -n "$FAKE_NODE_MORRE" ] && exit 1
echo $$ > "$FAKE_ESTADO/node.pid"
: > "$FAKE_ESTADO/no_ar"
trap 'rm -f "$FAKE_ESTADO/no_ar"; kill $S 2>/dev/null; exit 0' TERM
sleep 300 & S=$!
wait $S
"""
UTILITARIOS = ("grep", "sed", "cut", "head", "seq", "mkdir", "sleep", "cat", "tr", "sort", "rm", "date", "dirname", "chmod", "stat")
PYTHON3 = shutil.which("python3")


class Ambiente:
    def __init__(self, base):
        self.base = base
        self.home = base / "home"
        self.fakebin = base / "fakebin"
        self.util = base / "util"
        self.estado = base / "estado"
        self.gw_dir = base / "pacote"
        self.dados = base / "dados"
        for d in (self.home, self.fakebin, self.util, self.estado, self.gw_dir / "bin", self.dados):
            d.mkdir(parents=True)
        (self.gw_dir / "bin" / "omniroute.mjs").write_text("// falso\n", encoding="utf-8")
        (self.dados / ".env").write_text(f"INITIAL_PASSWORD={SENHA}\nREQUIRE_API_KEY=true\n", encoding="utf-8")
        (self.dados / "cliente-local.key").write_text(CHAVE_LOCAL + "\n", encoding="utf-8")
        self.log = self.estado / "log.txt"
        self.log.write_text("")
        for nome, texto in (("curl", FALSO_CURL), ("node", FALSO_NODE)):
            f = self.fakebin / nome
            f.write_text(texto, encoding="utf-8")
            f.chmod(0o755)
        for nome in UTILITARIOS:
            real = next(p for p in (pathlib.Path("/usr/bin") / nome, pathlib.Path("/bin") / nome) if p.exists())
            (self.util / nome).symlink_to(real)
        (self.util / "python3").symlink_to(PYTHON3)
        shutil.copy(COMBOS, self.base / "combos.json")
        self.liga_o_servidor()

    def forca(self, metodo, caminho, *codigos):
        """As proximas chamadas a METODO CAMINHO devolvem estes codigos HTTP (um por chamada; depois volta ao normal)."""
        nome = f"{metodo} {caminho}".replace(" ", "_").replace("/", "_").replace("?", "_")
        (self.estado / f"forca-{nome}").write_text("".join(f"{c}\n" for c in codigos), encoding="utf-8")

    def liga_o_servidor(self):
        (self.estado / "no_ar").write_text("")

    def desliga_o_servidor(self):
        f = self.estado / "no_ar"
        if f.exists():
            f.unlink()

    def conexoes(self, *provedores):
        (self.estado / "conexoes.json").write_text(json.dumps({"connections": [{"id": f"cid-{p}", "provider": p, "name": p} for p in provedores]}), encoding="utf-8")

    def _env(self, extra=None):
        env = {"PATH": f"{self.fakebin}:{self.util}", "HOME": str(self.home), "IA_RUN": str(self.estado / "run"), "IA_GW_DIR": str(self.gw_dir),
               "IA_GW_DADOS": str(self.dados), "IA_ESPERA": "0", "FAKE_LOG": str(self.log), "FAKE_ESTADO": str(self.estado)}
        env.update(extra or {})
        return env

    def roda(self, *args, entrada=None, extra=None, timeout=40):
        p = subprocess.Popen([BASH, str(SCRIPT), *args], cwd=str(self.home), env=self._env(extra),
                             stdin=subprocess.DEVNULL if entrada is None else subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        saida, _ = p.communicate(input=entrada, timeout=timeout)
        return p.returncode, saida

    def _reqs(self):
        for l in self.log.read_text(encoding="utf-8").splitlines():
            if l.startswith("REQ "):
                _, n, m, c = l.split(" ", 3)
                yield n, m, c

    def requisicoes(self, prefixo=""):
        """Lista "METODO CAMINHO" das requisicoes cujo CAMINHO comeca com `prefixo`."""
        return [f"{m} {c}" for _, m, c in self._reqs() if c.startswith(prefixo)]

    def corpos(self, metodo, caminho):
        """Os corpos JSON enviados (pela entrada padrao ou por -d do curl) a METODO CAMINHO."""
        achados = []
        for n, m, c in self._reqs():
            if m == metodo and c == caminho:
                f = self.estado / f"corpo-{n}.txt"
                if f.exists():
                    achados.append(json.loads(f.read_text(encoding="utf-8")))
        return achados

    def tudo_que_o_curl_viu(self):
        """Linha de comando de todos os curl + tudo que foi mandado pelas entradas (para procurar vazamento onde NAO deve haver chave)."""
        return self.log.read_text(encoding="utf-8")

    def pid_do_node(self):
        f = self.estado / "node.pid"
        return int(f.read_text()) if f.exists() else None


def vivo(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def espera_morrer(pid, segundos=5):
    fim = time.time() + segundos
    while time.time() < fim:
        if not vivo(pid):
            return True
        time.sleep(0.1)
    return not vivo(pid)


@pytest.fixture
def amb(tmp_path):
    a = Ambiente(tmp_path)
    yield a
    pid = a.pid_do_node()
    if pid:
        try:
            os.kill(pid, SIGKILL)
        except ProcessLookupError:
            pass


# ---------------------------------------------------------------- o arquivo em si

def test_sintaxe_do_bash_esta_correta():
    p = subprocess.Popen([BASH, "-n", str(SCRIPT)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    saida, _ = p.communicate(timeout=20)
    assert p.returncode == 0, saida


def test_script_e_ascii_e_sem_cr():
    dados = SCRIPT.read_bytes()
    assert b"\r" not in dados
    dados.decode("ascii")


def test_arquivo_de_combos_nao_tem_chave_nenhuma_e_cobre_os_tres_combos():
    combos = json.loads(COMBOS.read_text(encoding="utf-8"))
    assert [c["name"] for c in combos] == ["codigo", "auditoria", "rapido"]
    texto = COMBOS.read_text(encoding="utf-8").lower()
    for proibido in ("apikey", "api_key", "secret", "password", "token", "bearer"):
        assert proibido not in texto
    assert {m["providerId"] for c in combos for m in c["models"]} == {"nvidia", "gemini", "openrouter", "ddgw"}


def test_ajuda_lista_os_comandos(amb):
    rc, saida = amb.roda("ajuda")
    assert rc == 0
    assert "omni-local ligar | desligar | status" in saida
    for c in ("provedor", "combos", "testar", "pronto", "tirar", "apagar-combos"):
        assert f"omni-local {c}" in saida
    assert not amb.requisicoes()


# ---------------------------------------------------------------- provedor: o cuidado com a chave

@pytest.mark.parametrize("provedor,chave", [("nvidia", CHAVE_NVIDIA), ("gemini", CHAVE_GEMINI), ("gemini", CHAVE_GEMINI_NOVA), ("openrouter", CHAVE_OPENROUTER)])
def test_provedor_manda_a_chave_pela_entrada_padrao_cria_a_conexao_e_testa(amb, provedor, chave):
    rc, saida = amb.roda("provedor", provedor, entrada=chave + "\r\n")   # o PC manda com CRLF: o ajudante limpa
    assert rc == 0, saida
    (corpo,) = amb.corpos("POST", "/api/providers")
    assert corpo == {"provider": provedor, "name": f"celular-{provedor}", "apiKey": chave}
    assert amb.requisicoes("/api/providers/cid-novo/test") == ["POST /api/providers/cid-novo/test"], "depois de criar, o teste do OmniRoute tem que ser pedido"
    assert f"{provedor}: conexao criada; teste do OmniRoute: OK" in saida


@pytest.mark.parametrize("provedor,chave", [("nvidia", CHAVE_NVIDIA), ("gemini", CHAVE_GEMINI), ("gemini", CHAVE_GEMINI_NOVA), ("openrouter", CHAVE_OPENROUTER)])
def test_a_chave_nunca_vai_na_linha_de_comando_nem_na_saida(amb, provedor, chave):
    rc, saida = amb.roda("provedor", provedor, entrada=chave + "\n")
    assert rc == 0
    assert chave not in saida
    for linha in amb.tudo_que_o_curl_viu().splitlines():
        if linha.startswith("curl "):
            assert chave not in linha, "a chave apareceu na linha de comando do curl: " + linha[:80]
        assert SENHA not in linha, "a senha inicial do OmniRoute tambem so vai pela entrada padrao"
    assert amb.corpos("POST", "/api/providers")[0]["apiKey"] == chave, "a chave chegou ao OmniRoute pelo corpo da requisicao"


@pytest.mark.parametrize("entrada", [
    "chave-errada-1234567890\n",            # prefixo que nao e do provedor
    "nvapi-curta\n",                        # curta demais
    "nvapi-" + "A" * 300 + "\n",            # longa demais
    "nvapi-FALSA12345678901234$%\n",        # caractere estranho
    "\n", "",                               # vazia
    "AIzaFALSA12345678901\n",               # chave do Gemini no lugar da NVIDIA
])
def test_chave_com_formato_errado_e_recusada_sem_chamar_a_api(amb, entrada):
    rc, saida = amb.roda("provedor", "nvidia", entrada=entrada)
    assert rc == 2, saida
    assert "nada foi guardado" in saida
    assert not amb.requisicoes("/api/providers") and not amb.requisicoes("/api/auth"), "nem login nem conexao podem acontecer com chave de formato errado"
    assert not amb.requisicoes(), "nenhuma chamada de rede"


@pytest.mark.parametrize("provedor,entrada", [
    ("nvidia", CHAVE_GEMINI_NOVA + "\n"),                  # chave nova do Google no lugar da NVIDIA
    ("openrouter", CHAVE_GEMINI_NOVA + "\n"),              # ... e no lugar da OpenRouter
    ("gemini", CHAVE_NVIDIA + "\n"),                       # NVIDIA no lugar do Gemini
    ("gemini", CHAVE_OPENROUTER + "\n"),
    ("gemini", "AQxFALSA123456789012345\n"),               # "AQ" sem o ponto nao e o formato novo
    ("gemini", "aq.FALSA123456789012345\n"),               # minuscula nao vale
])
def test_formato_novo_do_gemini_so_vale_para_o_gemini(amb, provedor, entrada):
    rc, saida = amb.roda("provedor", provedor, entrada=entrada)
    assert rc == 2 and "nada foi guardado" in saida, saida
    assert not amb.requisicoes(), "chave de formato errado nao pode nem chamar a rede"


def test_mensagem_de_prefixo_do_gemini_cita_os_dois_formatos(amb):
    rc, saida = amb.roda("provedor", "gemini", entrada="qualquer-coisa-1234567890\n")
    assert rc == 2 and "AIza" in saida and "AQ." in saida, saida


def test_provedor_desconhecido_e_recusado(amb):
    rc, saida = amb.roda("provedor", "groq", entrada=CHAVE_NVIDIA + "\n")
    assert rc == 2 and "Provedor desconhecido" in saida and not amb.requisicoes()


def test_provedor_com_o_servidor_desligado_manda_rodar_ligar(amb):
    amb.desliga_o_servidor()
    rc, saida = amb.roda("provedor", "nvidia", entrada=CHAVE_NVIDIA + "\n")
    assert rc == 1 and "omni-local ligar" in saida
    assert not amb.requisicoes("/api/providers") and not amb.requisicoes("/api/auth/login")


def test_login_recusado_para_antes_de_mexer_nos_provedores(amb):
    (amb.estado / "login-recusado").write_text("")
    rc, saida = amb.roda("provedor", "nvidia", entrada=CHAVE_NVIDIA + "\n")
    assert rc == 1 and "Login recusado" in saida
    assert not amb.requisicoes("/api/providers")


def test_provedor_que_ja_existe_e_atualizado_com_patch_e_nao_duplicado(amb):
    amb.conexoes("nvidia")
    rc, saida = amb.roda("provedor", "nvidia", entrada=CHAVE_NVIDIA + "\n")
    assert rc == 0, saida
    reqs = amb.requisicoes()
    assert "PATCH /api/providers/cid-nvidia" in reqs and "POST /api/providers" not in reqs
    assert "conexao atualizada" in saida
    assert "POST /api/providers/cid-nvidia/test" in reqs
    (corpo,) = amb.corpos("PATCH", "/api/providers/cid-nvidia")
    assert corpo == {"apiKey": CHAVE_NVIDIA}


def test_conexao_recusada_pelo_omniroute_mostra_o_motivo_sem_a_chave(amb):
    (amb.estado / "provedor-erro.json").write_text(json.dumps({"error": f"chave invalida: {CHAVE_NVIDIA}"}), encoding="utf-8")
    rc, saida = amb.roda("provedor", "nvidia", entrada=CHAVE_NVIDIA + "\n")
    assert rc == 1 and "recusou a conexao de nvidia (HTTP 400)" in saida
    assert CHAVE_NVIDIA not in saida and "***" in saida
    assert not amb.requisicoes("/api/providers/cid-novo/test"), "conexao recusada nao chega ao teste"


def test_teste_que_falha_devolve_erro_e_o_eco_da_chave_nao_vaza(amb):
    eco = {"valid": False, "error": f"Invalid API key {CHAVE_NVIDIA}", "diagnosis": {"message": f"o provedor devolveu {CHAVE_NVIDIA} como invalida"}}
    (amb.estado / "teste.json").write_text(json.dumps(eco), encoding="utf-8")
    rc, saida = amb.roda("provedor", "nvidia", entrada=CHAVE_NVIDIA + "\n")
    assert rc == 1 and "FALHOU" in saida
    assert CHAVE_NVIDIA not in saida, "mesmo que o servidor devolva a chave no erro, ela nao pode ser impressa"
    assert "***" in saida


@pytest.mark.parametrize("teste", [{"valid": False}, {"success": False}, {"ok": False}, {"error": "x"}, {"valid": True, "error": "x"}, {}, {"qualquer": 1}])
def test_so_e_ok_quando_o_teste_do_omniroute_diz_que_e_valido(amb, teste):
    (amb.estado / "teste.json").write_text(json.dumps(teste), encoding="utf-8")
    rc, saida = amb.roda("provedor", "nvidia", entrada=CHAVE_NVIDIA + "\n")
    assert rc == 1 and "FALHOU" in saida


def test_teste_com_http_200_mas_corpo_que_nao_e_json_nao_e_ok(amb):
    (amb.estado / "teste.json").write_text("<html>rota mudou</html>", encoding="utf-8")
    rc, saida = amb.roda("provedor", "nvidia", entrada=CHAVE_NVIDIA + "\n")
    assert rc == 1 and "FALHOU" in saida


def test_tirar_que_falha_no_delete_nao_diz_que_apagou(amb):
    amb.conexoes("nvidia")
    amb.forca("DELETE", "/api/providers/cid-nvidia", 500)
    rc, saida = amb.roda("tirar", "nvidia")
    assert rc != 0 and "conexao apagada" not in saida and "NAO apagou" in saida, saida


def test_tirar_com_a_listagem_falhando_nao_diz_que_nao_havia_conexao(amb):
    amb.conexoes("nvidia")
    amb.forca("GET", "/api/providers?limit=5000", 500)
    rc, saida = amb.roda("tirar", "nvidia")
    assert rc != 0 and "nao havia conexao" not in saida and "listar as conexoes" in saida, saida
    assert not [r for r in amb.requisicoes() if r.startswith("DELETE")]


def test_provedor_com_a_listagem_falhando_nao_cria_conexao_duplicada(amb):
    amb.conexoes("nvidia")
    amb.forca("GET", "/api/providers?limit=5000", 500)
    rc, saida = amb.roda("provedor", "nvidia", entrada=CHAVE_NVIDIA + "\n")
    assert rc == 1 and "listar as conexoes" in saida, saida
    assert "POST /api/providers" not in amb.requisicoes() and CHAVE_NVIDIA not in saida


def test_tirar_apaga_todas_as_conexoes_do_provedor(amb):
    amb.conexoes("nvidia", "gemini", "nvidia")
    rc, saida = amb.roda("tirar", "nvidia")
    assert rc == 0
    assert saida.count("conexao apagada") == 2
    assert amb.requisicoes("/api/providers/").count("DELETE /api/providers/cid-nvidia") == 2
    assert not any("cid-gemini" in r for r in amb.requisicoes())


# ---------------------------------------------------------------- combos

def _combos_enviados(amb):
    return {c["name"]: c for c in amb.corpos("POST", "/api/combos")}


def test_combos_so_levam_modelos_dos_provedores_que_existem_aqui_e_sem_compressao(amb):
    amb.conexoes("nvidia")
    rc, saida = amb.roda("combos")
    assert rc == 0, saida
    enviados = _combos_enviados(amb)
    assert set(enviados) == {"codigo", "auditoria", "rapido"}
    for c in enviados.values():
        assert c["models"] and all(m["providerId"] == "nvidia" for m in c["models"])
        assert c["enabled"] is True and "compressionMode" not in c["config"] and c["config"]["maxRetries"] == 2
    assert [len(enviados[n]["models"]) for n in ("codigo", "auditoria", "rapido")] == [4, 5, 2]
    assert enviados["rapido"]["strategy"] == "p2c" and enviados["codigo"]["strategy"] == "priority"


def test_combos_com_os_tres_provedores_levam_tudo_menos_o_que_pede_navegador(amb):
    amb.conexoes("nvidia", "gemini", "openrouter")
    rc, _ = amb.roda("combos")
    assert rc == 0
    enviados = _combos_enviados(amb)
    assert [len(enviados[n]["models"]) for n in ("codigo", "auditoria", "rapido")] == [7, 7, 6]   # o ddgw (DuckDuckGo) do rapido nao entra
    assert not any(m["providerId"] == "ddgw" for c in enviados.values() for m in c["models"])


def test_combo_sem_nenhum_modelo_dos_provedores_daqui_e_pulado_e_dito(amb):
    amb.conexoes("gemini")   # so o rapido tem modelo do gemini; codigo tem 1, auditoria nenhum
    rc, saida = amb.roda("combos")
    assert rc == 0
    enviados = _combos_enviados(amb)
    assert "auditoria" not in enviados and set(enviados) == {"codigo", "rapido"}
    assert "combo auditoria sem modelo dos provedores daqui" in saida


def test_combos_que_ja_existem_sao_apagados_antes_de_recriar(amb):
    amb.conexoes("nvidia")
    (amb.estado / "combos-atuais.json").write_text(json.dumps([{"id": "id-velho", "name": "codigo"}, {"id": "id-outro", "name": "aulas"}]), encoding="utf-8")
    rc, _ = amb.roda("combos")
    assert rc == 0
    assert amb.requisicoes("/api/combos/") == ["DELETE /api/combos/id-velho"], "so o combo que sera recriado e apagado (e o 'aulas' nao e do ajudante)"


def test_combo_recusado_na_criacao_devolve_o_combo_antigo_e_sai_com_erro(amb):
    amb.conexoes("nvidia")
    antigo = {"id": "id-velho", "name": "codigo", "strategy": "priority", "enabled": True, "models": [{"providerId": "nvidia", "model": "antigo"}], "createdAt": "2026-01-01"}
    (amb.estado / "combos-atuais.json").write_text(json.dumps([antigo]), encoding="utf-8")
    amb.forca("POST", "/api/combos", 500)   # a 1a criacao (codigo) e recusada; a recriacao do antigo passa
    rc, saida = amb.roda("combos")
    assert rc != 0 and "combo codigo: recusado" in saida and "combo codigo: restaurado" in saida, saida
    codigos = [c for c in amb.corpos("POST", "/api/combos") if c["name"] == "codigo"]
    assert len(codigos) == 2 and codigos[1]["models"] == antigo["models"], "o combo antigo tem que ser recriado"
    assert "id" not in codigos[1] and "createdAt" not in codigos[1]


def test_combo_que_nao_pode_ser_apagado_nao_e_recriado_e_sai_com_erro(amb):
    amb.conexoes("nvidia")
    (amb.estado / "combos-atuais.json").write_text(json.dumps([{"id": "id-velho", "name": "codigo"}]), encoding="utf-8")
    amb.forca("DELETE", "/api/combos/id-velho", 500)
    rc, saida = amb.roda("combos")
    assert rc != 0 and "combo codigo: nao apagou" in saida, saida
    assert "codigo" not in _combos_enviados(amb) and {"auditoria", "rapido"} <= set(_combos_enviados(amb))


def test_combos_sem_nenhum_provedor_manda_configurar_primeiro(amb):
    rc, saida = amb.roda("combos")
    assert rc == 1 and "Nenhum provedor configurado" in saida
    assert not [r for r in amb.requisicoes() if r.startswith(("POST /api/combos", "POST /api/providers"))] and not _combos_enviados(amb)


def test_apagar_combos_so_apaga_os_tres(amb):
    (amb.estado / "combos-atuais.json").write_text(json.dumps([{"id": "a1", "name": "codigo"}, {"id": "a2", "name": "aulas"}, {"id": "a3", "name": "rapido"}]), encoding="utf-8")
    rc, _ = amb.roda("apagar-combos")
    assert rc == 0
    assert sorted(amb.requisicoes("/api/combos/")) == ["DELETE /api/combos/a1", "DELETE /api/combos/a3"]


# ---------------------------------------------------------------- testar e pronto

def _chat(amb, texto="ok", cod=200, modelo="nvidia/modelo-x"):
    (amb.estado / "chat.cod").write_text(str(cod), encoding="utf-8")
    corpo = {"model": modelo, "choices": [{"message": {"content": texto}}]} if cod == 200 else {"error": {"message": f"falhou {CHAVE_LOCAL}"}}
    (amb.estado / "chat.json").write_text(json.dumps(corpo), encoding="utf-8")


def test_testar_ok_mostra_o_modelo_que_respondeu_e_leva_a_chave_local_pela_entrada_padrao(amb):
    _chat(amb)
    rc, saida = amb.roda("testar", "codigo")
    assert rc == 0, saida
    assert "OK codigo" in saida and "nvidia/modelo-x" in saida
    (corpo,) = amb.corpos("POST", "/v1/chat/completions")   # o -d do curl
    assert corpo["model"] == "codigo" and corpo["max_tokens"] >= 200
    cfgs = [p.read_text(encoding="utf-8") for p in amb.estado.glob("cfg-*.txt")]
    assert any("Authorization: Bearer " + CHAVE_LOCAL in c for c in cfgs)
    assert CHAVE_LOCAL not in "\n".join(l for l in amb.tudo_que_o_curl_viu().splitlines() if l.startswith("curl ")), "a chave local nao pode estar na linha de comando"


def test_testar_sem_argumento_testa_os_tres_combos(amb):
    _chat(amb)
    rc, saida = amb.roda("testar")
    assert rc == 0 and [n for n in ("codigo", "auditoria", "rapido") if f"OK {n}" in saida] == ["codigo", "auditoria", "rapido"]


def test_testar_com_falha_devolve_1_e_o_eco_da_chave_nao_vaza(amb):
    _chat(amb, cod=503)
    rc, saida = amb.roda("testar", "codigo")
    assert rc == 1 and "FALHOU codigo (HTTP 503)" in saida
    assert CHAVE_LOCAL not in saida


def test_testar_resposta_vazia_nao_conta_como_ok(amb):
    _chat(amb, texto="   ")
    rc, saida = amb.roda("testar", "codigo")
    assert rc == 1 and "FALHOU" in saida


def test_testar_sem_a_chave_local_ou_com_servidor_desligado(amb):
    amb.desliga_o_servidor()
    rc, saida = amb.roda("testar", "codigo")
    assert rc == 1 and "omni-local ligar" in saida
    amb.liga_o_servidor()
    (amb.dados / "cliente-local.key").unlink()
    rc, saida = amb.roda("testar", "codigo")
    assert rc == 1 and "Sem a chave local" in saida


def test_pronto_so_cria_o_arquivo_depois_que_o_combo_codigo_respondeu(amb):
    _chat(amb, cod=503)
    rc, saida = amb.roda("pronto")
    assert rc == 1 and "NAO criado" in saida and not (amb.dados / "pronto").exists()
    _chat(amb)
    rc, saida = amb.roda("pronto")
    assert rc == 0 and (amb.dados / "pronto").exists()
    assert (amb.dados / "pronto").stat().st_mode & 0o777 == 0o600


def test_pronto_que_falha_apaga_o_arquivo_que_ja_existia(amb):
    (amb.dados / "pronto").write_text("")
    _chat(amb, cod=503)
    rc, saida = amb.roda("pronto")
    assert rc == 1 and not (amb.dados / "pronto").exists(), "reserva que nao responde nao pode continuar marcada como pronta"
    assert "desligada" in saida


# ---------------------------------------------------------------- ligar e desligar

def test_ligar_sobe_o_node_so_em_127_0_0_1_sem_painel_e_desligar_para(amb):
    amb.desliga_o_servidor()
    rc, saida = amb.roda("ligar")
    assert rc == 0, saida
    linhas = [l for l in amb.log.read_text(encoding="utf-8").splitlines() if l.startswith("node ")]
    assert len(linhas) == 1
    assert "bin/omniroute.mjs serve --port 20129 --no-open --no-tray --headless --no-recovery" in linhas[0]
    assert f"DATA_DIR={amb.dados} HOST=127.0.0.1 MB=384 PWD={amb.gw_dir}" in linhas[0]
    pid = amb.pid_do_node()
    assert pid and vivo(pid)
    rc, saida = amb.roda("desligar")
    assert rc == 0 and "desligado" in saida
    assert espera_morrer(pid)


def test_ligar_com_o_servidor_ja_no_ar_nao_liga_outro(amb):
    rc, saida = amb.roda("ligar")
    assert rc == 0 and "ja estava ligado" in saida
    assert not [l for l in amb.log.read_text(encoding="utf-8").splitlines() if l.startswith("node ")]


def test_ligar_com_servidor_que_morre_ao_subir_desiste_na_hora(amb):
    amb.desliga_o_servidor()
    rc, saida = amb.roda("ligar", extra={"FAKE_NODE_MORRE": "1", "IA_ESPERA": "1"}, timeout=15)
    assert rc == 1 and "morreu ao subir" in saida


def test_ligar_sem_o_pacote_instalado_avisa(amb):
    amb.desliga_o_servidor()
    (amb.gw_dir / "bin" / "omniroute.mjs").unlink()
    rc, saida = amb.roda("ligar")
    assert rc == 1 and "nao esta instalado" in saida


@pytest.mark.parametrize("ruim", ["20128", "abc", "", "1.5", "-1"])
def test_porta_nunca_e_a_20128_e_valor_ruim_volta_ao_padrao(amb, ruim):
    amb.desliga_o_servidor()
    rc, _ = amb.roda("ligar", extra={"IA_GW_PORTA": ruim})
    assert rc == 0
    (linha,) = [l for l in amb.log.read_text(encoding="utf-8").splitlines() if l.startswith("node ")]
    assert "--port 20129 " in linha


def test_status_mostra_instalado_ligado_pronto_provedores_e_combos(amb):
    amb.conexoes("nvidia", "gemini")
    (amb.estado / "combos-atuais.json").write_text(json.dumps([{"id": "1", "name": "rapido"}, {"id": "2", "name": "codigo"}]), encoding="utf-8")
    rc, saida = amb.roda("status")
    assert rc == 0
    assert "Instalado: sim | ligado: sim | pronto: NAO" in saida
    assert "Provedores: gemini nvidia" in saida and "Combos: codigo rapido" in saida
    assert SENHA not in saida and CHAVE_LOCAL not in saida
