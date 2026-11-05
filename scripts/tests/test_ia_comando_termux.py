"""Testes do comando `ia` do Termux (scripts/celular-kit/bin/ia) e do guia que o traz para colar.

O script e bash puro: aqui ele roda de verdade, mas com curl, qwen, socat, llama-server, llama-cli, pkg e pkill FALSOS
(pasta so de testes, PATH so com os falsos e uns poucos utilitarios reais). Nada toca rede, celular ou processo real.
Os testes rodam no WSL (scripts/testes-py.ps1); sem bash eles sao pulados.
"""
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import time

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPT = RAIZ / "scripts" / "celular-kit" / "bin" / "ia"
GUIA = RAIZ / "memoria" / "GUIA-IA-NO-CELULAR.md"
BASH = next((p for p in ("/bin/bash", "/usr/bin/bash") if pathlib.Path(p).exists()), "/bin/bash")
pytestmark = pytest.mark.skipif(not pathlib.Path(BASH).exists(), reason="precisa de bash (os testes rodam no WSL)")
SIGKILL = getattr(signal, "SIGKILL", 9)

PC_IP = "100.64.0.1"
CHAVE = "chave-de-teste"

FALSO_CURL = r"""#!/bin/bash
echo "curl $*" >> "$FAKE_LOG"
url=""; quer_codigo=0; hdr=""; saida=""; cfg=0; pedido=""
while [ $# -gt 0 ]; do
  case "$1" in
    -w) quer_codigo=1; shift 2 ;;
    -H) hdr="$2"; shift 2 ;;
    -o) saida="$2"; shift 2 ;;
    -K) cfg=1; shift 2 ;;
    --data-binary) pedido="${2#@}"; shift 2 ;;
    -m|--connect-timeout|-d) shift 2 ;;
    http*) url="$1"; shift ;;
    *) shift ;;
  esac
done
[ $cfg = 1 ] && { cat > "$FAKE_ESTADO/curl-config.txt"; [ -n "$hdr" ] || hdr=$(cat "$FAKE_ESTADO/curl-config.txt"); }
if [ -n "$pedido" ]; then cat "$pedido" > "$FAKE_ESTADO/pedido.json"; stat -c '%a' "$pedido" > "$FAKE_ESTADO/pedido.modo"; fi
alvo="${url#http://}"; hp="${alvo%%/*}"; caminho="/${alvo#*/}"
if ! grep -qx "$hp" "$FAKE_MUNDO" 2>/dev/null; then [ $quer_codigo = 1 ] && printf '000'; exit 7; fi
codigo=200; corpo='{}'
chave_ok=chave-de-teste   # o OmniRoute do PC; a reserva (127.0.0.1:20129, ou a 20128 quando a ponte aponta para ela) so aceita a chave local
[ "$hp" = "127.0.0.1:20129" ] && chave_ok=chave-local-teste
[ "$hp" = "127.0.0.1:20128" ] && grep -qx "127.0.0.1:[0-9]*" "$FAKE_ESTADO/destino20128" 2>/dev/null && chave_ok=chave-local-teste
[ -n "${FAKE_RECUSA_LOCAL:-}" ] && [ "$hp" = "127.0.0.1:20128" ] && [ "$chave_ok" = chave-local-teste ] && chave_ok=ninguem-entra   # a ponte da reserva recusa a chave local
case "$caminho" in
  /v1/models*) case "$hdr" in *"Bearer $chave_ok"*) corpo='{"data":[]}' ;; *) codigo=401; corpo='{"error":"sem chave"}' ;; esac ;;
  /v1/chat/completions*)
    if grep -q "Bearer chave-de-teste" "$FAKE_ESTADO/curl-config.txt" 2>/dev/null; then
      corpo=$(cat "$FAKE_ESTADO/resposta.json" 2>/dev/null || echo '{}'); codigo=$(cat "$FAKE_ESTADO/resposta.cod" 2>/dev/null || echo 200)
    else codigo=401; corpo='{"error":{"message":"chave invalida"}}'; fi ;;
  /api/tags*) corpo='{"models":[{"name":"llama3.2-32k:latest"}]}' ;;
  /mcp*) [ -n "${FAKE_ACORDA:-}" ] && grep -q "Bearer token-de-teste" "$FAKE_ESTADO/curl-config.txt" 2>/dev/null && echo "$FAKE_ACORDA" >> "$FAKE_MUNDO" ;;   # a ponte do PC liga o OmniRoute dele
esac
[ "$saida" = /dev/null ] || printf '%s' "$corpo"
[ $quer_codigo = 1 ] && printf '%s' "$codigo"
exit 0
"""
FALSO_QWEN = r"""#!/bin/bash
echo "qwen cwd=$PWD args=$* chave=${OMNIROUTE_API_KEY:+definida} inicio=${OMNIROUTE_API_KEY:0:12}" >> "$FAKE_LOG"
exit "${FAKE_QWEN_RC:-0}"
"""
FALSO_SOCAT = r"""#!/bin/bash
echo "socat $*" >> "$FAKE_LOG"
echo $$ >> "$FAKE_ESTADO/socat.pids"
case "$1" in TCP-LISTEN:*) p="${1#TCP-LISTEN:}"; p="${p%%,*}"; echo "127.0.0.1:$p" >> "$FAKE_MUNDO"; [ "$p" = 20128 ] && echo "${2#TCP:}" > "$FAKE_ESTADO/destino20128" ;; esac
trap 'kill $S 2>/dev/null; exit 0' TERM
sleep 300 & S=$!
wait $S
"""
FALSO_NODE = r"""#!/bin/bash
echo "node $* DATA_DIR=$DATA_DIR HOST=$OMNIROUTE_SERVER_HOST MB=$OMNIROUTE_MEMORY_MB PWD=$PWD" >> "$FAKE_LOG"
[ -n "$FAKE_NODE_MORRE" ] && exit 1
echo $$ >> "$FAKE_ESTADO/node.pids"
porta=""; while [ $# -gt 0 ]; do [ "$1" = "--port" ] && porta="$2"; shift; done
echo "127.0.0.1:$porta" >> "$FAKE_MUNDO"
trap 'kill $S 2>/dev/null; exit 0' TERM
sleep 300 & S=$!
wait $S
"""
FALSO_LLAMA_SERVER = r"""#!/bin/bash
echo "llama-server $*" >> "$FAKE_LOG"
echo $$ >> "$FAKE_ESTADO/llama.pids"
echo "127.0.0.1:8080" >> "$FAKE_MUNDO"
trap 'kill $S 2>/dev/null; exit 0' TERM
sleep 300 & S=$!
wait $S
"""
FALSO_SIMPLES = r"""#!/bin/bash
echo "${0##*/} $*" >> "$FAKE_LOG"
exit "${FAKE_RC:-0}"
"""
UTILITARIOS = ("grep", "sed", "cut", "head", "seq", "mkdir", "sleep", "cat", "tr", "sort", "rmdir", "rm", "stat")
PYTHON3 = shutil.which("python3")  # o `ia qwen` monta e le o JSON com o python3 do Termux


class Ambiente:
    def __init__(self, base):
        self.base = base
        self.home = base / "home"
        self.fakebin = base / "fakebin"
        self.util = base / "util"
        self.estado = base / "estado"
        self.armazenamento = base / "storage"
        for d in (self.home / ".qwen", self.fakebin, self.util, self.estado, self.armazenamento):
            d.mkdir(parents=True)
        (self.home / ".qwen" / ".env").write_text(f"OMNIROUTE_API_KEY={CHAVE}\n", encoding="utf-8")
        (self.home / "modelos").mkdir()
        (self.home / "modelos" / "qwen.gguf").write_bytes(b"x")
        self.meminfo = self.estado / "meminfo"
        self.poe_memoria(2000)
        self.log = self.estado / "log.txt"
        self.mundo = self.estado / "mundo.txt"
        self.log.write_text("")
        self.mundo.write_text("")
        self.montagens = base / "estado" / "mounts"
        self.montagens.write_text("")
        self.gw_dir = base / "gw-pacote"      # onde o OmniRoute do celular estaria instalado (so existe depois de poe_gateway)
        self.dados = base / "gw-dados"        # ~/.omniroute do teste
        for nome, texto in (("curl", FALSO_CURL), ("qwen", FALSO_QWEN), ("socat", FALSO_SOCAT),
                            ("llama-server", FALSO_LLAMA_SERVER), ("llama-cli", FALSO_SIMPLES),
                            ("pkill", FALSO_SIMPLES), ("pkg", FALSO_SIMPLES), ("node", FALSO_NODE)):
            self.poe_falso(nome, texto)
        for nome in UTILITARIOS:
            real = next(p for p in (pathlib.Path("/usr/bin") / nome, pathlib.Path("/bin") / nome) if p.exists())
            (self.util / nome).symlink_to(real)
        if PYTHON3:
            (self.util / "python3").symlink_to(PYTHON3)

    def poe_resposta_do_modelo(self, corpo, codigo=200):
        """O que o OmniRoute falso devolve ao pedido de chat do `ia qwen` (dict vira JSON; texto vai como esta)."""
        (self.estado / "resposta.json").write_text(corpo if isinstance(corpo, str) else json.dumps(corpo), encoding="utf-8")
        (self.estado / "resposta.cod").write_text(str(codigo), encoding="utf-8")

    def pedido_ao_modelo(self):
        """O JSON que o `ia qwen` mandou ao OmniRoute falso (o curl falso o guarda)."""
        return json.loads((self.estado / "pedido.json").read_text(encoding="utf-8"))

    def poe_memoria(self, mb):
        """Escreve um /proc/meminfo falso no formato real (valores em kB) com `mb` MB de MemAvailable."""
        self.meminfo.write_text(f"MemTotal:        3805672 kB\nMemFree:          123456 kB\nMemAvailable:{mb * 1024:>10} kB\nBuffers:           10000 kB\n",
                                encoding="utf-8")

    def poe_modelo_grande(self):
        (self.home / "modelos" / "qwen2.5-1.5b.gguf").write_bytes(b"x")

    def poe_token(self):
        """O celular ja foi pareado: o token da ponte do PC esta em ~/.qwen/.env (valor de teste)."""
        with (self.home / ".qwen" / ".env").open("a", encoding="utf-8") as f:
            f.write("PONTE_PC_TOKEN=token-de-teste-" + "x" * 30 + "\n")

    def poe_gateway(self, pronto=True, chave=True):
        """O OmniRoute do celular instalado (pacote + chave local + arquivo `pronto`, que so existe depois do teste com provedor)."""
        (self.gw_dir / "bin").mkdir(parents=True, exist_ok=True)
        (self.gw_dir / "bin" / "omniroute.mjs").write_text("// falso\n", encoding="utf-8")
        self.dados.mkdir(parents=True, exist_ok=True)
        for nome, quer, texto in (("cliente-local.key", chave, "chave-local-teste\n"), ("pronto", pronto, "ok\n")):
            alvo = self.dados / nome
            if quer:
                alvo.write_text(texto, encoding="utf-8")
            elif alvo.exists():
                alvo.unlink()

    def reinicia(self):
        """Entre duas execucoes no mesmo teste: o ia anterior saiu, entao as portas dele fecharam (os falsos nao tiram a propria linha do mundo)."""
        self.log.write_text("")
        self.mundo.write_text("")
        destino = self.estado / "destino20128"
        if destino.exists():
            destino.unlink()

    def poe_falso(self, nome, texto):
        f = self.fakebin / nome
        f.write_text(texto, encoding="utf-8")
        f.chmod(0o755)

    def tira_falso(self, nome):
        (self.fakebin / nome).unlink()

    def no_ar(self, *hostports):
        with self.mundo.open("a", encoding="utf-8") as f:
            for hp in hostports:
                f.write(hp + "\n")

    def roda_com_a_pasta_atual_apagada(self, *args, timeout=40):
        """Reproduz o terminal aberto numa pasta que foi apagada (o $PWD fica velho), como no Termux do Rafael em 31/10."""
        pasta = self.base / "pasta apagada"
        pasta.mkdir()
        p = subprocess.Popen([BASH, "-c", 'cd "$1" && rmdir "$1" && shift && exec "$@"', "x", str(pasta), BASH, str(SCRIPT), *args],
                             cwd=str(self.home), env=self._env(), stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        saida, _ = p.communicate(timeout=timeout)
        return p.returncode, saida

    def _env(self, env_extra=None):
        env = {
            "PATH": f"{self.fakebin}:{self.util}",
            "HOME": str(self.home),
            "IA_RUN": str(self.estado / "run"),
            "IA_ARMAZENAMENTO": str(self.armazenamento),
            "IA_MONTAGENS": str(self.montagens),
            "IA_MEMINFO": str(self.meminfo),
            "IA_ESPERA": "0",
            "FAKE_LOG": str(self.log),
            "FAKE_MUNDO": str(self.mundo),
            "FAKE_ESTADO": str(self.estado),
            "IA_GW_DIR": str(self.gw_dir),
            "IA_GW_DADOS": str(self.dados),
        }
        env.update(env_extra or {})
        return env

    def roda(self, *args, cwd=None, env_extra=None, timeout=40, entrada=None):
        """`entrada` e o que chega pela entrada padrao (pipe); sem ela a entrada padrao e /dev/null, como num terminal sem nada colado."""
        p = subprocess.Popen([BASH, str(SCRIPT), *args], cwd=str(cwd or self.home), env=self._env(env_extra),
                             stdin=subprocess.DEVNULL if entrada is None else subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        saida, _ = p.communicate(input=entrada, timeout=timeout)
        return p.returncode, saida

    def chamadas(self, prefixo):
        return [l for l in self.log.read_text(encoding="utf-8").splitlines() if l.startswith(prefixo)]

    def pids(self, nome):
        f = self.estado / nome
        return [int(x) for x in f.read_text().split()] if f.exists() else []


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
    for nome in ("socat.pids", "llama.pids", "node.pids"):  # nenhum falso fica vivo depois do teste
        for pid in a.pids(nome):
            try:
                os.kill(pid, SIGKILL)
            except ProcessLookupError:
                pass


# ---------------------------------------------------------------- o arquivo em si

def test_sintaxe_do_bash_esta_correta():
    r = subprocess.Popen([BASH, "-n", str(SCRIPT)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    saida, _ = r.communicate(timeout=20)
    assert r.returncode == 0, saida


def test_script_e_ascii_e_sem_cr_para_colar_no_celular():
    dados = SCRIPT.read_bytes()
    assert b"\r" not in dados, "o script tem CR (CRLF): quebra no Termux"
    dados.decode("ascii")  # acento ou aspas curvas atrapalham a colagem no terminal


def test_guia_traz_exatamente_o_script_para_colar():
    guia = GUIA.read_text(encoding="utf-8")
    m = re.search(r"cat > ~/bin/ia <<'FIM_DO_IA'\n(.*?)\nFIM_DO_IA\n", guia, re.S)
    assert m, "o guia precisa ter o bloco `cat > ~/bin/ia <<'FIM_DO_IA' ... FIM_DO_IA`"
    assert m.group(1) == SCRIPT.read_text(encoding="ascii").rstrip("\n"), "o bloco do guia esta diferente do script: regenere o guia"


# ---------------------------------------------------------------- ajuda e status

def test_ajuda_lista_os_comandos_e_nao_abre_nada(amb):
    rc, saida = amb.roda("ajuda")
    assert rc == 0
    for comando in ("ia codigo", "ia pc", "ia chat", "ia local", "ia qwen", "ia status", "ia parar"):
        assert comando in saida
    assert not amb.chamadas("qwen")


def test_ajuda_mostra_o_cabecalho_inteiro_ate_a_ultima_linha(amb):
    """A ajuda imprime o bloco de comentarios do topo ate a linha em branco: uma linha nova no cabecalho nao pode empurrar outra para fora."""
    rc, saida = amb.roda("ajuda")
    assert rc == 0
    linhas_do_cabecalho = []
    for linha in SCRIPT.read_text(encoding="ascii").splitlines()[1:]:
        if not linha.startswith("#"):
            break
        linhas_do_cabecalho.append(re.sub(r"^# ?", "", linha))
    assert len(linhas_do_cabecalho) >= 14
    assert saida.splitlines() == linhas_do_cabecalho, "a ajuda tem que ser o cabecalho do script, linha por linha"
    assert "NUNCA mande nome, nota ou dado de aluno" in saida, "o aviso de privacidade do ia qwen tem que estar na ajuda geral"
    assert "IA_QWEN_MODELO" in saida.splitlines()[-1]


def test_status_sem_nada_ao_alcance_mostra_quatro_linhas_fora_e_nao_abre_o_qwen(amb):
    rc, saida = amb.roda("status")
    assert rc == 0
    assert saida.count("[--]") == 4 and saida.count("[ok]") == 1  # nuvem fora, PC fora, ponte sem token, 1,5B nao instalado; o 0,5B esta instalado
    assert "Nuvem (OmniRoute): fora" in saida and "modelo 0,5B" in saida and "modelo 1,5B nao instalado" in saida
    assert "Ponte do PC (projeto ao vivo, skills, caixa de recados): sem o token" in saida and "ponte-pc.ps1 -Parear" in saida
    assert not amb.chamadas("qwen") and not amb.chamadas("socat")


def test_token_vazio_nao_conta_como_pareado(amb):
    with (amb.home / ".qwen" / ".env").open("a", encoding="utf-8") as f:
        f.write("PONTE_PC_TOKEN=\n")
    amb.no_ar(f"{PC_IP}:20130")
    assert "sem o token" in amb.roda("status")[1]


def test_status_mostra_a_ponte_do_pc_sem_token_fora_e_pronta(amb):
    amb.poe_token()
    rc, saida = amb.roda("status")
    assert rc == 0 and "Ponte do PC: fora - PC desligado, sem login ou Tailscale desligada" in saida
    amb.no_ar(f"{PC_IP}:20130")
    rc, saida = amb.roda("status")
    assert rc == 0 and "[ok]  Ponte do PC (projeto ao vivo, skills, caixa de recados): pronta" in saida
    assert not amb.chamadas("socat") and not amb.chamadas("qwen"), "status so olha"
    assert any(f"{PC_IP}:20130/saude" in l for l in amb.chamadas("curl")), "a ponte e conferida pela rota /saude, que nao pede token"


def test_status_ve_a_nuvem_pela_tailscale_sem_abrir_ponte(amb):
    amb.no_ar(f"{PC_IP}:20128")
    rc, saida = amb.roda("status")
    assert rc == 0 and "pronta (pela Tailscale)" in saida
    assert not amb.chamadas("socat"), "status so olha: nunca abre ponte"


# ---------------------------------------------------------------- modos que abrem o Qwen

def test_nuvem_pela_ponte_local_abre_o_qwen_na_pasta_com_espaco(amb):
    amb.no_ar("127.0.0.1:20128")
    pasta = amb.armazenamento / "ABCD-1234" / "Projetos" / "Android Embeeded"
    pasta.mkdir(parents=True)
    rc, saida = amb.roda("codigo", str(pasta))
    assert rc == 0, saida
    (linha,) = amb.chamadas("qwen")
    assert f"cwd={pasta}" in linha and "args=--model codigo" in linha and "chave=definida" in linha
    assert not amb.chamadas("socat")


def test_nuvem_so_pela_tailscale_abre_ponte_e_fecha_ao_sair(amb):
    amb.no_ar(f"{PC_IP}:20128")
    rc, saida = amb.roda("codigo")
    assert rc == 0, saida
    (socat,) = amb.chamadas("socat")
    assert socat == f"socat TCP-LISTEN:20128,bind=127.0.0.1,fork,reuseaddr TCP:{PC_IP}:20128"
    log = amb.log.read_text(encoding="utf-8")
    assert log.index("socat TCP-LISTEN") < log.index("qwen cwd="), "a ponte tem que existir ANTES do Qwen abrir"
    assert "Cerebro: codigo (via Tailscale)" in saida
    (pid,) = amb.pids("socat.pids")
    assert espera_morrer(pid), "a ponte aberta pelo ia tem que fechar quando o ia sai"


def test_ia_manter_deixa_a_ponte_aberta(amb):
    amb.no_ar(f"{PC_IP}:20128")
    rc, _ = amb.roda("codigo", env_extra={"IA_MANTER": "1"})
    assert rc == 0
    (pid,) = amb.pids("socat.pids")
    assert vivo(pid)


def test_modo_nuvem_sem_chave_recusa_e_nao_abre_o_qwen(amb):
    (amb.home / ".qwen" / ".env").write_text("OUTRA=1\n", encoding="utf-8")
    amb.no_ar("127.0.0.1:20128")
    rc, saida = amb.roda("codigo")
    assert rc == 1 and "OMNIROUTE_API_KEY" in saida
    assert not amb.chamadas("qwen")


def test_nuvem_fora_do_ar_diz_o_que_conferir(amb):
    rc, saida = amb.roda("auditoria")
    assert rc == 1 and "ia status" in saida and "Tailscale" in saida
    assert not amb.chamadas("qwen")


def test_pc_pela_tailscale_abre_ponte_do_ollama_e_aquece_o_modelo(amb):
    amb.no_ar(f"{PC_IP}:11434")
    rc, saida = amb.roda("pc")
    assert rc == 0, saida
    (socat,) = amb.chamadas("socat")
    assert socat == f"socat TCP-LISTEN:11435,bind=127.0.0.1,fork,reuseaddr TCP:{PC_IP}:11434"
    assert any("api/generate" in l for l in amb.chamadas("curl"))
    (linha,) = amb.chamadas("qwen")
    assert "args=--model llama3.2-32k" in linha


def test_local_liga_o_llama_server_e_desliga_ao_sair(amb):
    rc, saida = amb.roda("local")
    assert rc == 0, saida
    assert "ia chat" in saida  # avisa que o Qwen Code com o modelo do celular e lento
    (llama,) = amb.chamadas("llama-server")
    assert "--host 127.0.0.1 --port 8080" in llama
    (linha,) = amb.chamadas("qwen")
    assert "args=--model qwen" in linha
    (pid,) = amb.pids("llama.pids")
    assert espera_morrer(pid)


def test_tudo_liga_nuvem_pc_e_modelo_do_celular_e_desliga_tudo_ao_sair(amb):
    amb.no_ar(f"{PC_IP}:20128", f"{PC_IP}:11434")
    rc, saida = amb.roda("tudo")
    assert rc == 0, saida
    assert "nuvem=1 pc=1 modelo-do-celular=1" in saida and "/model" in saida
    socats = amb.chamadas("socat")
    assert len(socats) == 2
    assert any("TCP-LISTEN:20128," in s and f"TCP:{PC_IP}:20128" in s for s in socats)
    assert any("TCP-LISTEN:11435," in s and f"TCP:{PC_IP}:11434" in s for s in socats)
    assert len(amb.chamadas("llama-server")) == 1
    (qwen,) = amb.chamadas("qwen")
    assert "args=--model codigo" in qwen
    pids = amb.pids("socat.pids") + amb.pids("llama.pids")
    assert len(pids) == 3 and all(espera_morrer(p) for p in pids), "tudo que o ia ligou tem que ser desligado ao sair"


def test_tudo_sem_nada_ao_alcance_recusa_sem_abrir_o_qwen(amb):
    (amb.home / "modelos" / "qwen.gguf").unlink()
    rc, saida = amb.roda("tudo")
    assert rc == 1 and "Nada ligou" in saida
    assert not amb.chamadas("qwen")


def test_argumentos_extras_vao_para_o_qwen(amb):
    amb.no_ar("127.0.0.1:20128")
    rc, _ = amb.roda("rapido", "-p", "diga oi")
    assert rc == 0
    (linha,) = amb.chamadas("qwen")
    assert "args=--model rapido --disable-mcp-server ponte-pc -p diga oi" in linha, "sem token, a ponte fica desligada; os argumentos do dono vem depois"


# ---------------------------------------------------------------- MCP: ponte do PC e busca na web so com modelo de nuvem

@pytest.mark.parametrize("modo", ["codigo", "auditoria", "rapido"])
def test_nuvem_com_token_e_ponte_no_ar_liga_o_mcp_e_avisa(amb, modo):
    amb.poe_token()
    amb.no_ar("127.0.0.1:20128", f"{PC_IP}:20130")
    rc, saida = amb.roda(modo)
    assert rc == 0, saida
    (linha,) = amb.chamadas("qwen")
    assert f"args=--model {modo} chave=" in linha, "nenhum --disable-mcp-server: ponte e busca ligadas"
    assert "Ponte do PC ligada" in saida and "caixa sincronizar" in saida


def test_nuvem_sem_token_ou_com_a_ponte_fora_desliga_so_a_ponte_e_nao_espera_por_ela(amb):
    amb.no_ar("127.0.0.1:20128", f"{PC_IP}:20130")
    amb.roda("codigo")  # ponte no ar, mas o celular ainda nao foi pareado (sem token)
    amb.poe_token()
    amb.mundo.write_text("127.0.0.1:20128\n")  # token certo, ponte fora do ar (PC desligado, Tailscale off)
    amb.roda("codigo")
    primeira, segunda = amb.chamadas("qwen")
    for linha in (primeira, segunda):
        assert "args=--model codigo --disable-mcp-server ponte-pc chave=" in linha and "exa" not in linha, linha


def test_ponte_url_do_ambiente_vale_para_o_ia_e_para_o_caixa(amb):
    amb.poe_token()
    amb.no_ar("127.0.0.1:20128", "10.9.8.7:7777")
    rc, saida = amb.roda("codigo", env_extra={"PONTE_URL": "http://10.9.8.7:7777"})
    assert rc == 0 and "Ponte do PC ligada" in saida
    assert any("10.9.8.7:7777/saude" in l for l in amb.chamadas("curl"))


def test_modelos_pequenos_nunca_levam_a_ponte_nem_a_busca_mesmo_com_tudo_no_ar(amb):
    amb.poe_token()
    amb.no_ar(f"{PC_IP}:20130", f"{PC_IP}:11434")
    rc, saida = amb.roda("pc")
    assert rc == 0 and "Ponte do PC ligada" not in saida, saida
    (linha_pc,) = amb.chamadas("qwen")  # conferido ANTES de zerar o log: o modo pc tambem nao leva a ponte nem a busca
    assert "--disable-mcp-server ponte-pc --disable-mcp-server exa" in linha_pc, linha_pc
    amb.roda("parar")
    amb.log.write_text("")
    amb.mundo.write_text(f"{PC_IP}:20130\n")
    rc, saida = amb.roda("local")
    assert rc == 0 and "Ponte do PC ligada" not in saida, saida  # a frase sai no stdout do ia, nao na linha do qwen falso
    (linha_local,) = amb.chamadas("qwen")
    assert "--disable-mcp-server ponte-pc --disable-mcp-server exa" in linha_local, linha_local


def test_tudo_com_nuvem_leva_a_ponte_e_sem_nuvem_nao(amb):
    amb.poe_token()
    amb.no_ar(f"{PC_IP}:20128", f"{PC_IP}:20130", f"{PC_IP}:11434")
    assert amb.roda("tudo")[0] == 0
    (linha,) = amb.chamadas("qwen")
    assert "--model codigo " in linha and "disable-mcp-server" not in linha
    amb.roda("parar")
    amb.log.write_text("")
    amb.mundo.write_text(f"{PC_IP}:20130\n{PC_IP}:11434\n")
    assert amb.roda("tudo")[0] == 0
    (linha,) = amb.chamadas("qwen")
    assert "--model llama3.2-32k " in linha and "--disable-mcp-server ponte-pc --disable-mcp-server exa" in linha


def test_com_a_ponte_no_ar_e_o_omniroute_fora_o_ia_pede_ao_pc_para_ligar(amb):
    amb.poe_token()
    amb.no_ar(f"{PC_IP}:20130")
    rc, saida = amb.roda("codigo", env_extra={"FAKE_ACORDA": f"{PC_IP}:20128"})
    assert rc == 0, saida
    pedido = [l for l in amb.chamadas("curl") if "/mcp" in l]
    assert len(pedido) == 1 and '"acao_pc"' in pedido[0] and '"ia-pc-ligar"' in pedido[0]
    assert "token-de-teste" not in pedido[0], "o token vai pela entrada padrao do curl, nunca na linha de comando"
    assert "pedindo ao PC" in saida and "--model codigo " in amb.chamadas("qwen")[0]


def test_ollama_fechado_o_ia_pede_ao_pc_para_abrir_so_na_tailnet(amb):
    amb.poe_token()
    amb.no_ar(f"{PC_IP}:20130")
    rc, saida = amb.roda("pc", env_extra={"FAKE_ACORDA": f"{PC_IP}:11434"})
    assert rc == 0, saida
    pedido = [l for l in amb.chamadas("curl") if "/mcp" in l]
    assert len(pedido) == 1 and '"ia-pc-ollama-abrir"' in pedido[0] and "token-de-teste" not in pedido[0]
    assert "--model llama3.2-32k" in amb.chamadas("qwen")[0]


def test_ia_sem_acordar_nao_chama_a_ponte_e_sem_token_tambem_nao(amb):
    amb.no_ar(f"{PC_IP}:20130")
    amb.roda("codigo", env_extra={"FAKE_ACORDA": f"{PC_IP}:20128"})
    assert not [l for l in amb.chamadas("curl") if "/mcp" in l], "sem token nao ha o que pedir"
    amb.poe_token()
    amb.log.write_text("")
    amb.roda("codigo", env_extra={"FAKE_ACORDA": f"{PC_IP}:20128", "IA_SEM_ACORDAR": "1"})
    assert not [l for l in amb.chamadas("curl") if "/mcp" in l]


def test_codigo_de_saida_do_qwen_e_repassado(amb):
    amb.no_ar("127.0.0.1:20128")
    rc, _ = amb.roda("codigo", env_extra={"FAKE_QWEN_RC": "3"})
    assert rc == 3


# ---------------------------------------------------------------- modo automatico

def test_auto_escolhe_a_nuvem_primeiro(amb):
    amb.no_ar("127.0.0.1:20128", "127.0.0.1:11435")
    rc, _ = amb.roda()
    assert rc == 0
    assert "args=--model codigo" in amb.chamadas("qwen")[0]


def test_auto_cai_para_o_pc_quando_a_nuvem_esta_fora(amb):
    amb.no_ar("127.0.0.1:11435")
    rc, _ = amb.roda()
    assert rc == 0
    assert "args=--model llama3.2-32k" in amb.chamadas("qwen")[0]


def test_auto_sem_nuvem_e_sem_pc_abre_a_conversa_do_celular_e_nao_o_qwen(amb):
    rc, saida = amb.roda()
    assert rc == 0
    assert "Nem a nuvem nem o PC responderam" in saida
    assert not amb.chamadas("qwen")
    (chat,) = amb.chamadas("llama-cli")
    assert "qwen.gguf" in chat and "-sys" in chat


def test_chat_sem_o_modelo_instalado_avisa(amb):
    (amb.home / "modelos" / "qwen.gguf").unlink()
    rc, saida = amb.roda("chat")
    assert rc == 1 and "Falta o modelo do celular" in saida


# ---------------------------------------------------------------- modelo do celular: modelo 0,5B x 1,5B (31/10)

def test_chat_usa_o_15b_quando_existe_e_ha_memoria(amb):
    amb.poe_modelo_grande()
    amb.poe_memoria(1500)
    rc, saida = amb.roda("chat")
    assert rc == 0, saida
    (chat,) = amb.chamadas("llama-cli")
    assert "qwen2.5-1.5b.gguf" in chat and "-sys" in chat
    assert "modelo 1,5B" in saida and "ia chat leve" in saida, "tem que avisar que e lento e dizer como pedir o rapido"


def test_chat_cai_para_o_05b_quando_falta_memoria_e_avisa(amb):
    amb.poe_modelo_grande()
    amb.poe_memoria(900)
    rc, saida = amb.roda("chat")
    assert rc == 0, saida
    (chat,) = amb.chamadas("llama-cli")
    assert "qwen.gguf" in chat and "1.5b" not in chat
    assert "Memoria livre: 900 MB" in saida and "modelo 0,5B" in saida


def test_limite_de_memoria_do_15b_e_exato_e_ajustavel(amb):
    amb.poe_modelo_grande()
    amb.poe_memoria(1300)
    amb.roda("chat")
    amb.poe_memoria(1299)
    amb.roda("chat")
    amb.poe_memoria(1000)
    amb.roda("chat", env_extra={"IA_MEM_MIN": "900"})
    c1, c2, c3 = amb.chamadas("llama-cli")
    assert "1.5b" in c1, "1300 MB e o minimo: tem que usar o 1,5B"
    assert "qwen.gguf" in c2, "1299 MB esta abaixo do minimo: tem que usar o 0,5B"
    assert "1.5b" in c3, "IA_MEM_MIN muda o minimo"


def test_chat_leve_forca_o_05b_mesmo_com_memoria_sobrando(amb):
    amb.poe_modelo_grande()
    amb.poe_memoria(3000)
    rc, saida = amb.roda("chat", "leve")
    assert rc == 0, saida
    (chat,) = amb.chamadas("llama-cli")
    assert "qwen.gguf" in chat and "1.5b" not in chat
    assert "A pasta nao existe" not in saida, "'leve' nao e pasta"


def test_leve_e_aceito_tambem_em_local_e_tudo_sem_virar_pasta(amb):
    for modo in ("local", "tudo"):
        amb.mundo.write_text("")  # o llama-server falso deixa "127.0.0.1:8080" no mundo mesmo depois de morrer
        rc, saida = amb.roda(modo, "leve")
        assert rc == 0 and "A pasta nao existe" not in saida, saida
        assert "qwen.gguf" in amb.chamadas("llama-server")[-1]


def test_chat_sem_o_15b_instalado_usa_o_05b_sem_reclamar(amb):
    amb.poe_memoria(3000)
    rc, saida = amb.roda("chat")
    assert rc == 0, saida
    assert "qwen.gguf" in amb.chamadas("llama-cli")[0]
    assert "Memoria livre" not in saida and "ia chat leve" not in saida


def test_sem_conseguir_ler_a_memoria_usa_o_05b(amb):
    amb.poe_modelo_grande()
    rc, saida = amb.roda("chat", env_extra={"IA_MEMINFO": str(amb.base / "nao-existe")})
    assert rc == 0, saida
    assert "qwen.gguf" in amb.chamadas("llama-cli")[0] and "Memoria livre: 0 MB" in saida


def test_so_o_15b_instalado_e_pouca_memoria_tenta_o_15b_mesmo_assim(amb):
    (amb.home / "modelos" / "qwen.gguf").unlink()
    amb.poe_modelo_grande()
    amb.poe_memoria(800)
    rc, saida = amb.roda("chat")
    assert rc == 0, saida
    assert "1.5b" in amb.chamadas("llama-cli")[0] and "mesmo assim" in saida


def test_ia_modelo_local_manda_em_qualquer_modo(amb):
    outro = amb.base / "meu-modelo.gguf"
    outro.write_bytes(b"x")
    amb.poe_modelo_grande()
    amb.poe_memoria(3000)
    env = {"IA_MODELO_LOCAL": str(outro)}
    amb.roda("chat", env_extra=env)
    amb.roda("local", env_extra=env)
    (chat,) = amb.chamadas("llama-cli")
    (servidor,) = amb.chamadas("llama-server")
    assert str(outro) in chat and str(outro) in servidor
    saida = amb.roda("status", env_extra=env)[1]
    assert "IA_MODELO_LOCAL" in saida and "modelo 1,5B" not in saida
    saida = amb.roda("chat", env_extra={"IA_MODELO_LOCAL": str(amb.base / "nao-existe.gguf")})[1]
    assert "Falta o modelo do celular" in saida


def test_qwen_code_local_e_tudo_usam_sempre_o_05b_mesmo_com_o_15b_e_memoria(amb):
    """O Qwen Code manda ~12 mil tokens de cara: a 5,9 t/s o 1,5B levaria ~35 min; o 0,5B (17,9 t/s) leva ~11 min."""
    amb.poe_modelo_grande()
    amb.poe_memoria(3000)
    assert amb.roda("local")[0] == 0
    (servidor,) = amb.chamadas("llama-server")
    assert "qwen.gguf" in servidor and "1.5b" not in servidor
    amb.roda("parar")
    amb.log.write_text("")
    amb.mundo.write_text("")  # o llama-server falso deixa "127.0.0.1:8080" no mundo mesmo depois de morrer
    assert amb.roda("tudo")[0] == 0
    (servidor,) = amb.chamadas("llama-server")
    assert "qwen.gguf" in servidor and "1.5b" not in servidor


def test_status_mostra_os_dois_modelos_e_a_memoria_livre(amb):
    amb.poe_modelo_grande()
    amb.poe_memoria(1450)
    rc, saida = amb.roda("status")
    assert rc == 0
    assert "modelo 0,5B" in saida and "modelo 1,5B" in saida and "memoria livre 1450 MB, pede 1300" in saida
    assert not amb.chamadas("llama-cli") and not amb.chamadas("llama-server"), "status so olha"


# ---------------------------------------------------------------- escolha da pasta

def _pasta_do_status(saida):
    (linha,) = [l for l in saida.splitlines() if "Pasta de trabalho:" in l]
    return linha.split("Pasta de trabalho:")[1].strip()


def test_pasta_prioridade_atual_depois_cartao_depois_copia_no_termux(amb):
    cartao = amb.armazenamento / "1A2B-3C4D" / "Projetos" / "Android Embeeded"
    copia = amb.home / "kit" / "projeto-android-embeeded"
    outra = amb.base / "outra pasta"
    copia.mkdir(parents=True)
    (copia / "CLAUDE.md").write_text("projeto", encoding="utf-8")
    outra.mkdir()
    assert _pasta_do_status(amb.roda("status")[1]) == str(copia), "so a copia do Termux existe"
    cartao.mkdir(parents=True)
    (cartao / "CLAUDE.md").write_text("projeto", encoding="utf-8")
    assert _pasta_do_status(amb.roda("status")[1]) == str(cartao), "o cartao SD vence a copia (UUID conhecido, mesmo sem /proc/mounts)"
    assert _pasta_do_status(amb.roda("status", cwd=outra)[1]) == str(outra), "estar numa pasta (fora da inicial) vence o cartao"


def test_cartao_com_outro_uuid_e_achado_pelo_proc_mounts(amb):
    """O Termux nao consegue listar /storage (Permission denied), mas /proc/mounts mostra o cartao: formatar muda o UUID."""
    novo = amb.armazenamento / "ABCD-1234" / "Projetos" / "Android Embeeded"
    novo.mkdir(parents=True)
    (novo / "CLAUDE.md").write_text("projeto", encoding="utf-8")
    amb.montagens.write_text(f"/dev/fuse {amb.armazenamento}/ABCD-1234 fuse rw 0 0\n/dev/block/dm-3 /data ext4 rw 0 0\n", encoding="utf-8")
    assert _pasta_do_status(amb.roda("status")[1]) == str(novo)


def test_ia_projeto_vence_o_cartao(amb):
    cartao = amb.armazenamento / "1A2B-3C4D" / "Projetos" / "Android Embeeded"
    cartao.mkdir(parents=True)
    (cartao / "CLAUDE.md").write_text("projeto", encoding="utf-8")
    meu = amb.base / "meu projeto"
    meu.mkdir()
    saida = amb.roda("status", env_extra={"IA_PROJETO": str(meu)})[1]
    assert _pasta_do_status(saida) == str(meu)


def test_pasta_do_cartao_so_com_esqueleto_de_pastas_e_ignorada_e_avisada(amb):
    """31/10: a copia do projeto no cartao SD tinha 406 pastas e NENHUM arquivo (a copia pelo cabo nao trouxe os arquivos)."""
    esqueleto = amb.armazenamento / "1A2B-3C4D" / "Projetos" / "Android Embeeded"
    (esqueleto / "memoria" / "nuvem").mkdir(parents=True)
    copia = amb.home / "kit" / "projeto-android-embeeded"
    copia.mkdir(parents=True)
    (copia / "CLAUDE.md").write_text("projeto", encoding="utf-8")
    saida = amb.roda("status")[1]
    assert _pasta_do_status(saida) == str(copia), "nao pode abrir o Qwen numa pasta sem arquivos"
    assert "so pastas vazias" in saida and str(esqueleto) in saida


def test_pasta_atual_apagada_com_o_terminal_aberto_nao_e_usada(amb):
    """31/10: o Termux do Rafael estava parado em /sdcard/Projetos/Android Embeeded, pasta que ele ja tinha apagado."""
    copia = amb.home / "kit" / "projeto-android-embeeded"
    copia.mkdir(parents=True)
    (copia / "CLAUDE.md").write_text("projeto", encoding="utf-8")
    rc, saida = amb.roda_com_a_pasta_atual_apagada("status")
    assert rc == 0, saida
    assert _pasta_do_status(saida) == str(copia), "um $PWD velho nao pode virar a pasta de trabalho"


def test_pasta_dada_como_primeiro_argumento_sem_modo(amb):
    amb.no_ar("127.0.0.1:20128")
    alvo = amb.base / "meu projeto"
    alvo.mkdir()
    rc, _ = amb.roda(str(alvo))
    assert rc == 0
    assert f"cwd={alvo}" in amb.chamadas("qwen")[0]


def test_pasta_que_nao_existe_e_recusada(amb):
    for alvo in (str(amb.base / "nao-existe"), "./sumiu", "pasta/que/nao/ha"):
        rc, saida = amb.roda("codigo", alvo)
        assert rc == 1 and "A pasta nao existe" in saida, alvo
        rc, saida = amb.roda(alvo)
        assert rc == 1 and "A pasta nao existe" in saida, alvo
    assert not amb.chamadas("qwen")


def test_texto_que_nao_e_modo_nem_pasta_vira_o_pedido_inicial_do_qwen(amb):
    amb.no_ar("127.0.0.1:20128")
    rc, saida = amb.roda("ligue o modo economia")
    assert rc == 0, saida
    (linha,) = amb.chamadas("qwen")
    assert "--model codigo " in linha and "-i ligue o modo economia chave=" in linha
    amb.log.write_text("")
    rc, _ = amb.roda("auditoria", "revise", "o", "script")
    linha = amb.chamadas("qwen")[0].rstrip()
    assert rc == 0 and "--model auditoria " in linha and "-i revise o script chave=" in linha
    amb.log.write_text("")
    rc, _ = amb.roda("codigo")
    assert rc == 0 and " -i " not in amb.chamadas("qwen")[0], "sem pedido, abre vazio"


def test_ia_perguntar_volta_a_pedir_licenca_so_nesta_vez(amb):
    amb.no_ar("127.0.0.1:20128")
    assert amb.roda("codigo")[0] == 0
    assert "--approval-mode" not in amb.chamadas("qwen")[0], "o modo sem perguntas vem do settings.json (tools.approvalMode)"
    amb.log.write_text("")
    assert amb.roda("codigo", env_extra={"IA_PERGUNTAR": "1"})[0] == 0
    assert "--approval-mode default" in amb.chamadas("qwen")[0]


# ---------------------------------------------------------------- parar

def test_parar_desliga_o_que_o_ia_abriu_mas_nunca_um_processo_estranho(amb):
    amb.no_ar(f"{PC_IP}:20128")
    amb.roda("codigo", env_extra={"IA_MANTER": "1"})  # deixa a ponte falsa viva e anotada
    (ponte,) = amb.pids("socat.pids")
    estranho = subprocess.Popen(["sleep", "60"], env={"PATH": "/usr/bin:/bin"})  # numero anotado, mas NAO e um socat
    try:
        with (amb.estado / "run" / "pids").open("a", encoding="utf-8") as f:
            f.write(f"{estranho.pid} socat\n")
        rc, saida = amb.roda("parar")
        assert rc == 0 and "Desligado" in saida
        assert espera_morrer(ponte), "a ponte do ia tinha que ser desligada"
        assert estranho.poll() is None, "o ia matou um processo que nao era dele (numero reaproveitado)"
        assert amb.chamadas("pkill")  # tambem manda parar o llama-server do celular
    finally:
        estranho.kill()
        estranho.wait()


def _qwen_aberto(amb):
    """Um 'Qwen Code' vivo: no celular o /proc mostra `node .../usr/bin/qwen --model codigo`; aqui `bash .../fakebin/qwen-aberto`."""
    falso = amb.fakebin / "qwen-aberto"
    falso.write_text("#!/bin/bash\nsleep 300\n", encoding="utf-8")
    falso.chmod(0o755)
    # PATH do ambiente de teste: o conftest esvazia o do pytest e, sem `sleep`, o falso morreria na hora
    return subprocess.Popen([BASH, str(falso)], env=amb._env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_parar_recusa_enquanto_ha_um_qwen_aberto_e_so_desliga_com_forca(amb):
    """31/10: o Rafael estava com o Qwen aberto no celular; um `ia parar` (ou o meu teste) teria derrubado a ponte da conversa dele."""
    amb.no_ar(f"{PC_IP}:20128")
    amb.roda("codigo", env_extra={"IA_MANTER": "1"})  # ponte viva e anotada
    (ponte,) = amb.pids("socat.pids")
    qwen = _qwen_aberto(amb)
    try:
        rc, saida = amb.roda("parar")
        assert rc == 1, saida
        assert "Matrix aberto" in saida and str(qwen.pid) in saida and "ia parar --forca" in saida, saida
        assert vivo(ponte), "ia parar derrubou a ponte de uma conversa que estava aberta"
        assert not amb.chamadas("pkill"), "recusou, entao nao pode ter mandado parar o llama-server"
        rc, saida = amb.roda("parar", "--forca")
        assert rc == 0 and "Desligado" in saida
        assert espera_morrer(ponte), "com --forca tinha que desligar mesmo assim"
        assert amb.chamadas("pkill")
    finally:
        qwen.kill()
        qwen.wait()


def test_ao_sair_o_ia_nao_derruba_a_ponte_que_outro_qwen_aberto_esta_usando(amb):
    """Duas sessoes do Termux: a que abriu a ponte sai primeiro e a outra (que so a reaproveitou) ainda conversa por ela."""
    amb.no_ar(f"{PC_IP}:20128")
    qwen = _qwen_aberto(amb)
    try:
        rc, saida = amb.roda("codigo")  # sem IA_MANTER: ao sair desligaria a ponte que abriu
        assert rc == 0, saida
        (ponte,) = amb.pids("socat.pids")
        assert vivo(ponte), "o ia derrubou a ponte enquanto outro Qwen estava aberto"
        assert "ia parar" in saida, "tem que avisar como desligar depois"
    finally:
        qwen.kill()
        qwen.wait()
    rc, saida = amb.roda("parar")
    assert rc == 0 and espera_morrer(ponte)


def test_a_sonda_da_nuvem_nunca_poe_a_chave_na_linha_de_comando_do_curl(amb):
    """/proc/<pid>/cmdline e legivel por qualquer processo do mesmo usuario: a chave vai pela entrada padrao (-K -)."""
    amb.no_ar(f"{PC_IP}:20128")
    rc, saida = amb.roda("codigo")
    assert rc == 0 and "Cerebro: codigo" in saida, saida
    log = amb.log.read_text(encoding="utf-8")
    assert "/v1/models" in log
    assert CHAVE not in log and "Authorization" not in log, "a chave foi para a linha de comando do curl"


def test_parar_sem_nenhum_qwen_aberto_desliga_normalmente(amb):
    amb.no_ar(f"{PC_IP}:20128")
    amb.roda("codigo", env_extra={"IA_MANTER": "1"})
    (ponte,) = amb.pids("socat.pids")
    rc, saida = amb.roda("parar")
    assert rc == 0 and "Desligado" in saida and espera_morrer(ponte)


# ---------------------------------------------------------------- ia qwen: o melhor Qwen gratis (27B) responde uma pergunta curta, sem o agente

precisa_python3 = pytest.mark.skipif(not PYTHON3, reason="o ia qwen usa o python3 (no Termux: pkg install python)")


def _resposta(texto, fim="stop"):
    return {"model": "qwen/qwen3.8-27b", "choices": [{"index": 0, "message": {"role": "assistant", "content": texto}, "finish_reason": fim}]}


def _pedidos_de_chat(amb):
    return [l for l in amb.chamadas("curl") if "/v1/chat/completions" in l]


def _o_que_foi_perguntado(amb):
    return amb.pedido_ao_modelo()["messages"][1]["content"]


@precisa_python3
def test_qwen_manda_a_pergunta_ao_modelo_27b_pela_tailscale_e_imprime_so_a_resposta(amb):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo(_resposta("Paris."))
    rc, saida = amb.roda("qwen", "Qual", "a", "capital", "da", "Franca?")
    assert (rc, saida) == (0, "Paris.\n")
    pedido = amb.pedido_ao_modelo()
    assert pedido["model"] == "groq/qwen/qwen3.8-27b"
    assert pedido["max_tokens"] == 1500
    assert [m["role"] for m in pedido["messages"]] == ["system", "user"]
    assert "portugues" in pedido["messages"][0]["content"]
    assert _o_que_foi_perguntado(amb) == "Qual a capital da Franca?"
    assert len(_pedidos_de_chat(amb)) == 1 and f"{PC_IP}:20128/v1/chat/completions" in _pedidos_de_chat(amb)[0]
    assert "Content-Type: application/json" in _pedidos_de_chat(amb)[0] and " -s " in _pedidos_de_chat(amb)[0], "JSON declarado e sem barra de progresso"
    assert not amb.chamadas("qwen") and not amb.chamadas("socat"), "o ia qwen nao abre o agente nem ponte nenhuma"


@precisa_python3
def test_qwen_usa_a_ponte_local_quando_ja_existe_uma(amb):
    amb.no_ar("127.0.0.1:20128")
    amb.poe_resposta_do_modelo(_resposta("ok"))
    rc, saida = amb.roda("qwen", "oi")
    assert (rc, saida) == (0, "ok\n")
    assert "127.0.0.1:20128/v1/chat/completions" in _pedidos_de_chat(amb)[0]


@precisa_python3
def test_qwen_vale_mesmo_com_uma_pasta_chamada_qwen_na_pasta_atual(amb):
    """`ia <pasta>` abre o Qwen Code naquela pasta: o modo `qwen` tem que ser decidido antes dessa regra."""
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo(_resposta("ok"))
    (amb.home / "qwen").mkdir()
    rc, saida = amb.roda("qwen", "oi")
    assert (rc, saida) == (0, "ok\n") and not amb.chamadas("qwen")


@precisa_python3
def test_qwen_a_chave_vai_pela_entrada_do_curl_e_nunca_na_linha_de_comando(amb):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo(_resposta("ok"))
    amb.roda("qwen", "oi")
    (chamada,) = _pedidos_de_chat(amb)
    assert CHAVE not in chamada and "Authorization" not in chamada, "a chave nao pode aparecer no ps"
    assert f"Bearer {CHAVE}" in (amb.estado / "curl-config.txt").read_text(encoding="utf-8")


@precisa_python3
def test_qwen_o_pedido_so_o_dono_le_e_nao_sobra_no_disco(amb):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo(_resposta("ok"))
    amb.roda("qwen", "uma pergunta particular")
    assert (amb.estado / "pedido.modo").read_text().strip() == "600"
    assert not (amb.estado / "run" / "qwen.req").exists()


@precisa_python3
def test_qwen_python_isolado_ignora_json_py_e_re_py_soltos_na_pasta_atual(amb):
    """`python3 -c` poe a pasta atual no caminho dos modulos: um json.py dentro de um projeto nao pode trocar o json do Python."""
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo(_resposta("ok"))
    pasta = amb.base / "projeto-com-modulos-soltos"
    pasta.mkdir()
    for nome in ("json.py", "re.py"):
        (pasta / nome).write_text(f"raise RuntimeError('{nome} da pasta foi carregado')\n", encoding="utf-8")
    rc, saida = amb.roda("qwen", "oi", cwd=pasta)
    assert (rc, saida) == (0, "ok\n"), saida


@precisa_python3
def test_qwen_entrada_padrao_sem_argumentos_vira_a_pergunta(amb):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo(_resposta("ok"))
    rc, _ = amb.roda("qwen", entrada="resuma: a, b e c\n\n")
    assert rc == 0 and _o_que_foi_perguntado(amb) == "resuma: a, b e c"


@precisa_python3
def test_qwen_traco_no_fim_junta_a_pergunta_com_a_entrada_padrao(amb):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo(_resposta("ok"))
    rc, _ = amb.roda("qwen", "Resuma", "isto:", "-", entrada="linha 1\nlinha 2\n")
    assert rc == 0 and _o_que_foi_perguntado(amb) == "Resuma isto:\n\nlinha 1\nlinha 2"


@precisa_python3
def test_qwen_traco_sozinho_le_so_a_entrada_padrao(amb):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo(_resposta("ok"))
    rc, _ = amb.roda("qwen", "-", entrada="so o texto")
    assert rc == 0 and _o_que_foi_perguntado(amb) == "so o texto"


@precisa_python3
def test_qwen_com_pergunta_nos_argumentos_nao_le_a_entrada_padrao_sem_o_traco(amb):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo(_resposta("ok"))
    rc, _ = amb.roda("qwen", "oi", entrada="isto nao deve ir")
    assert rc == 0 and _o_que_foi_perguntado(amb) == "oi"


@precisa_python3
def test_qwen_pergunta_com_aspas_cifrao_crase_barra_e_acento_chega_inteira(amb):
    pergunta = 'Qual \xe9 a "capital" de $HOME e `date` da Fran\xe7a? \\n fim'  # e-agudo e c-cedilha escritos por codigo: o arquivo fica ASCII
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo(_resposta("ok"))
    rc, _ = amb.roda("qwen", pergunta)
    assert rc == 0 and _o_que_foi_perguntado(amb) == pergunta


@precisa_python3
def test_qwen_modelo_pode_ser_trocado_pela_variavel_do_ambiente(amb):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo(_resposta("ok"))
    amb.roda("qwen", "oi", env_extra={"IA_QWEN_MODELO": "groq/outro-modelo"})
    assert amb.pedido_ao_modelo()["model"] == "groq/outro-modelo"


def test_qwen_sem_pergunta_mostra_o_uso_e_nao_chama_a_rede(amb):
    amb.no_ar(f"{PC_IP}:20128")
    rc, saida = amb.roda("qwen")
    assert rc == 1 and "Uso: ia qwen" in saida
    assert not amb.chamadas("curl")


def test_qwen_ajuda_curta_nao_chama_a_rede(amb):
    for opcao in ("-h", "--help"):
        rc, saida = amb.roda("qwen", opcao)
        assert rc == 0 and "Uso: ia qwen" in saida and 'cat arquivo | ia qwen "resuma isto" -' in saida
        assert "provedor externo" in saida and "dado de aluno" in saida, "o aviso de privacidade tem que estar na ajuda do comando"
    assert not amb.chamadas("curl")


@precisa_python3
def test_qwen_20000_caracteres_ainda_vao_e_20001_sao_recusados_antes_da_rede(amb):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo(_resposta("ok"))
    rc, saida = amb.roda("qwen", "x" * 20000)
    assert (rc, saida) == (0, "ok\n") and len(_o_que_foi_perguntado(amb)) == 20000
    antes = len(_pedidos_de_chat(amb))
    rc, saida = amb.roda("qwen", "x" * 20001)
    assert rc == 1 and "grande demais" in saida and "20001" in saida and "ia codigo" in saida
    assert len(_pedidos_de_chat(amb)) == antes, "texto grande demais nao pode ir ao servidor"


def test_qwen_sem_a_chave_do_omniroute_recusa_sem_chamar_a_rede(amb):
    (amb.home / ".qwen" / ".env").write_text("", encoding="utf-8")
    rc, saida = amb.roda("qwen", "oi")
    assert rc == 1 and "Falta a chave" in saida
    assert not amb.chamadas("curl")


def test_qwen_sem_python3_avisa_como_instalar_e_nao_chama_a_rede(amb):
    (amb.util / "python3").unlink(missing_ok=True)
    rc, saida = amb.roda("qwen", "oi")
    assert rc == 1 and "pkg install python" in saida
    assert not amb.chamadas("curl")


@precisa_python3
def test_qwen_com_o_pc_fora_do_ar_diz_o_que_conferir(amb):
    rc, saida = amb.roda("qwen", "oi")  # nenhuma porta no ar
    assert rc == 1 and "nao respondeu" in saida and "Tailscale" in saida
    assert not _pedidos_de_chat(amb)


@precisa_python3
def test_qwen_chave_que_o_omniroute_nao_aceita_nao_chega_a_pedir_o_chat(amb):
    amb.no_ar(f"{PC_IP}:20128")
    (amb.home / ".qwen" / ".env").write_text("OMNIROUTE_API_KEY=chave-velha\n", encoding="utf-8")
    rc, saida = amb.roda("qwen", "oi")
    assert rc == 1 and "chave" in saida
    assert not _pedidos_de_chat(amb)


@precisa_python3
@pytest.mark.parametrize("codigo, trecho", [
    (413, "Groq recusou"), (429, "Groq recusou"), (401, "recusou a chave"), (403, "recusou a chave"),
    (404, "nao existe"), (500, "HTTP 500: falha interna"), (502, "HTTP 502: falha interna"),
])
def test_qwen_erro_do_servidor_vira_frase_clara_e_saida_1(amb, codigo, trecho):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo({"error": {"message": "falha interna"}}, codigo)
    rc, saida = amb.roda("qwen", "oi")
    assert rc == 1 and trecho in saida, saida
    if codigo in (413, 429):
        assert "ia codigo" in saida


@precisa_python3
def test_qwen_mensagem_de_erro_do_servidor_sai_limpa_e_curta(amb):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo({"error": {"message": "falha\x1b[31m interna" + "y" * 500}}, 500)
    rc, saida = amb.roda("qwen", "oi")
    assert rc == 1 and "\x1b" not in saida and "HTTP 500: falha[31m interna" in saida, saida
    assert len(saida) < 220, "a mensagem do servidor e cortada em 160 caracteres"


@precisa_python3
@pytest.mark.parametrize("codigo", ["000", "abc"])
def test_qwen_sem_codigo_http_valido_diz_que_o_omniroute_nao_respondeu(amb, codigo):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo("", codigo)
    rc, saida = amb.roda("qwen", "oi")
    assert rc == 1 and "Sem resposta do OmniRoute" in saida, saida


@precisa_python3
@pytest.mark.parametrize("corpo", ['{"choices": [{"mess', "{}", '{"choices": []}', "[1, 2]", ""])
def test_qwen_resposta_200_cortada_ou_sem_choices_nao_imprime_lixo(amb, corpo):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo(corpo, 200)
    rc, saida = amb.roda("qwen", "oi")
    assert rc == 1 and "cortada ou sem texto" in saida, saida


@precisa_python3
@pytest.mark.parametrize("mensagem", [
    {"role": "assistant", "content": ""}, {"role": "assistant", "content": None}, {"role": "assistant"}, "texto solto",
    {"role": "assistant", "content": "<think>so pensei</think>"},
])
def test_qwen_resposta_sem_texto_diz_o_motivo(amb, mensagem):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo({"choices": [{"message": mensagem, "finish_reason": "length"}]})
    rc, saida = amb.roda("qwen", "oi")
    assert rc == 1 and "respondeu vazio" in saida and "length" in saida, saida


@precisa_python3
def test_qwen_tira_o_pensamento_e_os_caracteres_de_controle_da_resposta(amb):
    amb.no_ar(f"{PC_IP}:20128")
    amb.poe_resposta_do_modelo(_resposta("<think>vou pensar\ncom varias linhas</think>\n\x1b[31mvermelho\x07 bom" + chr(0x2028) + "dia" + chr(0x202E) + "x" + chr(0x200B) + "y" + chr(0x9B) + "z\nsegunda linha\tcom tab\r"))
    rc, saida = amb.roda("qwen", "oi")
    assert (rc, saida) == (0, "[31mvermelho bomdiaxyz\nsegunda linha\tcom tab\n")


# ---------------------------------------------------------------- tempo para conectar ao PC (o 1o pacote depois de um tempo parado leva 3 s ou mais)

def _sondas_de_rede(amb):
    return [l for l in amb.chamadas("curl") if "--connect-timeout" in l]


def test_sondagens_da_rede_esperam_ate_8_segundos_para_conectar(amb):
    """Medido em 31/10: o 1o pacote ao PC depois de 45 s parado leva 3,05 s para conectar; com o limite antigo de 3 s o `ia status` dizia 'tudo fora'."""
    amb.no_ar(f"{PC_IP}:20128", f"{PC_IP}:11434")
    rc, _ = amb.roda("status")
    assert rc == 0
    sondas = _sondas_de_rede(amb)
    assert len(sondas) >= 4, sondas  # nuvem (local e Tailscale) e Ollama (local e Tailscale)
    assert any("/api/tags" in l for l in sondas) and any("/v1/models" in l for l in sondas)
    for linha in sondas:
        assert "--connect-timeout 8 -m 12" in linha, linha


def test_ia_conecta_ajusta_o_tempo_e_valor_invalido_volta_ao_padrao(amb):
    amb.no_ar(f"{PC_IP}:20128")
    amb.roda("status", env_extra={"IA_CONECTA": "2"})
    sondas = _sondas_de_rede(amb)
    assert sondas and all("--connect-timeout 2 -m 6" in l for l in sondas), sondas
    for ruim in ("abc", "", "3s", "-1", "1.5"):
        amb.log.write_text("")
        amb.roda("status", env_extra={"IA_CONECTA": ruim})
        sondas = _sondas_de_rede(amb)
        assert sondas and all("--connect-timeout 8 -m 12" in l for l in sondas), (ruim, sondas)


# ---------------------------------------------------------------- reserva: o OmniRoute do proprio celular (01/11/2026)

def test_status_sem_a_reserva_instalada_nao_fala_dela(amb):
    rc, saida = amb.roda("status")
    assert rc == 0 and "OmniRoute do celular" not in saida


def test_status_com_a_reserva_instalada_mas_sem_provedor_diz_que_nao_e_usada(amb):
    amb.poe_gateway(pronto=False)
    rc, saida = amb.roda("status")
    assert rc == 0
    assert "[--]  OmniRoute do celular (reserva): instalado, mas sem provedor configurado" in saida
    assert not amb.chamadas("node") and not amb.chamadas("socat") and not amb.chamadas("qwen")


def test_status_com_a_reserva_pronta_so_olha_e_com_ela_ligada_diz_ligada(amb):
    amb.poe_gateway()
    rc, saida = amb.roda("status")
    assert rc == 0 and "[ok]  OmniRoute do celular (reserva): pronto; liga sozinho se o PC nao responder" in saida
    amb.no_ar("127.0.0.1:20129")
    rc, saida = amb.roda("status")
    assert rc == 0 and "[ok]  OmniRoute do celular (reserva): ligado em 127.0.0.1:20129" in saida
    assert not amb.chamadas("node") and not amb.chamadas("socat") and not amb.chamadas("qwen"), "status so olha"


def test_pc_fora_e_reserva_pronta_liga_o_omniroute_do_celular_poe_a_ponte_e_abre_o_qwen_com_a_chave_local(amb):
    amb.poe_gateway()
    rc, saida = amb.roda("codigo")
    assert rc == 0, saida
    (no,) = amb.chamadas("node")
    assert "bin/omniroute.mjs serve --port 20129 --no-open --no-tray --headless --no-recovery" in no
    assert f"DATA_DIR={amb.dados} HOST=127.0.0.1 MB=384 PWD={amb.gw_dir}" in no, "so em 127.0.0.1, dados no ~/.omniroute, heap de 384 MB, dentro da pasta do pacote"
    (socat,) = amb.chamadas("socat")
    assert socat == "socat TCP-LISTEN:20128,bind=127.0.0.1,fork,reuseaddr TCP:127.0.0.1:20129"
    (linha,) = amb.chamadas("qwen")
    assert "args=--model codigo" in linha and "inicio=chave-local-" in linha, "o Qwen tem que levar a chave LOCAL, nunca a do PC"
    assert "Cerebro: codigo (via OmniRoute do celular" in saida and "O PC nao respondeu" in saida
    log = amb.log.read_text(encoding="utf-8")
    assert log.index("node bin/omniroute.mjs") < log.index("socat TCP-LISTEN") < log.index("qwen cwd="), "servidor, depois ponte, depois o Qwen"
    aquece = "curl -s -K - -m 90 -o /dev/null http://127.0.0.1:20129/v1/models"
    assert aquece in log, "a 1a chamada fria (~8 s no A12) tem que ser feita com paciencia, antes da ponte"
    assert log.index("node bin/omniroute.mjs") < log.index(aquece) < log.index("socat TCP-LISTEN")
    assert "chave-local-teste" not in next(l for l in log.splitlines() if l.startswith("curl") and aquece in l), "a chave local vai pela entrada padrao do curl, nunca na linha de comando"
    assert "Bearer chave-local-teste" in (amb.estado / "curl-config.txt").read_text(encoding="utf-8")


def test_ao_sair_o_ia_desliga_o_omniroute_do_celular_e_a_ponte_dele(amb):
    amb.poe_gateway()
    rc, _ = amb.roda("codigo")
    assert rc == 0
    (pid_no,), (pid_ponte,) = amb.pids("node.pids"), amb.pids("socat.pids")
    assert espera_morrer(pid_no), "o OmniRoute do celular so vive enquanto o ia esta aberto"
    assert espera_morrer(pid_ponte)


def test_com_o_pc_no_ar_a_reserva_nunca_liga(amb):
    amb.poe_gateway()
    amb.no_ar(f"{PC_IP}:20128")
    rc, saida = amb.roda("codigo")
    assert rc == 0 and "via Tailscale" in saida
    assert "No such file" not in saida, "sem reserva ligada nao ha lista de processos para ler, e isso nao e erro"
    assert not amb.chamadas("node"), "com o PC respondendo, o celular nao gasta 400 MB"
    (linha,) = amb.chamadas("qwen")
    assert "inicio=chave-de-tes" in linha, "com o PC no ar o Qwen leva a chave do PC"


def test_reserva_sem_o_arquivo_pronto_ou_sem_a_chave_local_nunca_liga(amb):
    amb.poe_gateway(pronto=False)
    rc, saida = amb.roda("codigo")
    assert rc == 1 and "O OmniRoute do PC nao respondeu" in saida
    assert not amb.chamadas("node") and not amb.chamadas("socat") and not amb.chamadas("qwen")
    amb.poe_gateway(pronto=True, chave=False)
    rc, saida = amb.roda("codigo")
    assert rc == 1 and not amb.chamadas("node") and not amb.chamadas("qwen")
    (amb.dados / "cliente-local.key").write_text("", encoding="utf-8")   # arquivo vazio nao e chave
    rc, saida = amb.roda("codigo")
    assert rc == 1 and not amb.chamadas("node") and not amb.chamadas("qwen")
    assert "instalado, mas sem provedor configurado" in amb.roda("status")[1], "chave vazia: o status nao pode dizer que a reserva esta pronta"


def test_reserva_sem_o_node_avisa_e_nao_abre_o_qwen(amb):
    amb.poe_gateway()
    amb.tira_falso("node")
    rc, saida = amb.roda("codigo")
    assert rc == 1 and "Falta o node (pkg install nodejs)" in saida
    assert not amb.chamadas("qwen") and not amb.chamadas("socat")


def test_reserva_que_nao_sobe_no_auto_cai_para_o_ollama_do_pc_sem_levar_a_chave_local(amb):
    amb.poe_gateway()
    amb.no_ar(f"{PC_IP}:11434")
    rc, saida = amb.roda("auto", env_extra={"FAKE_NODE_MORRE": "1"})
    assert rc == 0 and "O OmniRoute do celular nao subiu" in saida, saida
    (linha,) = amb.chamadas("qwen")
    assert "args=--model llama3.2-32k" in linha and "inicio=chave-de-tes" in linha, "a chave local nao pode sobrar na variavel quando a reserva falha"


def test_com_o_pc_no_ar_mas_sem_como_abrir_a_ponte_a_reserva_nao_e_ligada_a_toa(amb):
    amb.poe_gateway()
    amb.no_ar(f"{PC_IP}:20128")
    amb.tira_falso("socat")
    rc, saida = amb.roda("codigo", env_extra={"FAKE_RC": "1"})   # o pkg falso falha: nao ha como instalar o socat
    assert rc == 1 and "Nao consegui instalar o socat" in saida and "O OmniRoute do PC nao respondeu" in saida
    assert not amb.chamadas("node") and not amb.chamadas("qwen"), "o PC respondeu; ligar a reserva so gastaria 400 MB sem ponte"


def test_segunda_execucao_com_a_reserva_e_a_ponte_deixadas_ligadas_reaproveita_as_duas(amb):
    amb.poe_gateway()
    rc, _ = amb.roda("codigo", env_extra={"IA_MANTER": "1"})
    assert rc == 0
    amb.log.write_text("")
    rc, saida = amb.roda("codigo", env_extra={"IA_MANTER": "1"})
    assert rc == 0, saida
    assert not amb.chamadas("node") and not amb.chamadas("socat"), "nada novo para ligar: servidor e ponte ja estao no ar"
    (linha,) = amb.chamadas("qwen")
    assert "inicio=chave-local-" in linha


def test_reserva_que_nao_sobe_diz_onde_olhar_e_nao_abre_o_qwen_nem_a_ponte(amb):
    amb.poe_gateway()
    rc, saida = amb.roda("codigo", env_extra={"FAKE_NODE_MORRE": "1"})
    assert rc == 1 and "O OmniRoute do celular nao subiu" in saida and "omniroute.log" in saida
    assert not amb.chamadas("qwen") and not amb.chamadas("socat")


def test_reserva_recusa_ligar_com_pouca_memoria_e_o_limite_e_exato(amb):
    amb.poe_gateway()
    amb.poe_memoria(799)
    rc, saida = amb.roda("codigo")
    assert rc == 1 and "Memoria livre: 799 MB (o OmniRoute do celular pede 800 MB)" in saida
    assert not amb.chamadas("node") and not amb.chamadas("qwen")
    amb.poe_memoria(800)
    rc, saida = amb.roda("codigo")
    assert rc == 0 and len(amb.chamadas("node")) == 1
    amb.reinicia()
    amb.poe_memoria(900)
    rc, saida = amb.roda("codigo", env_extra={"IA_GW_MEM_MIN": "1000"})
    assert rc == 1 and "pede 1000 MB" in saida and not amb.chamadas("node"), "IA_GW_MEM_MIN ajusta o limite"


def test_auto_com_o_pc_fora_usa_a_reserva_antes_do_ollama_e_da_conversa_do_celular(amb):
    amb.poe_gateway()
    amb.no_ar(f"{PC_IP}:11434")   # o Ollama do PC ate responderia, mas a reserva e melhor
    rc, saida = amb.roda("auto")
    assert rc == 0, saida
    (linha,) = amb.chamadas("qwen")
    assert "args=--model codigo" in linha and "inicio=chave-local-" in linha


def test_ia_manter_deixa_a_reserva_ligada_e_o_pc_de_volta_a_desliga_antes_da_ponte_dele(amb):
    amb.poe_gateway()
    rc, _ = amb.roda("codigo", env_extra={"IA_MANTER": "1"})
    assert rc == 0
    (pid_no,), (pid_ponte,) = amb.pids("node.pids"), amb.pids("socat.pids")
    assert vivo(pid_no) and vivo(pid_ponte), "IA_MANTER=1 deixa a reserva e a ponte dela ligadas"
    amb.no_ar(f"{PC_IP}:20128")   # o PC voltou
    amb.log.write_text("")
    rc, saida = amb.roda("codigo")
    assert rc == 0 and "via Tailscale" in saida, saida
    assert espera_morrer(pid_no) and espera_morrer(pid_ponte), "a reserva velha sai antes de abrir a ponte do PC"
    assert not amb.chamadas("node")
    (socat,) = amb.chamadas("socat")
    assert socat.endswith(f"TCP:{PC_IP}:20128")
    (linha,) = amb.chamadas("qwen")
    assert "inicio=chave-de-tes" in linha


def test_parar_desliga_tambem_a_reserva_que_o_ia_deixou_ligada(amb):
    amb.poe_gateway()
    amb.roda("codigo", env_extra={"IA_MANTER": "1"})
    (pid_no,), (pid_ponte,) = amb.pids("node.pids"), amb.pids("socat.pids")
    rc, saida = amb.roda("parar")
    assert rc == 0 and "Desligado" in saida and "OmniRoute do celular" in saida
    assert espera_morrer(pid_no) and espera_morrer(pid_ponte)


def test_a_porta_da_reserva_nunca_e_a_20128_e_valor_ruim_volta_ao_padrao(amb):
    amb.poe_gateway()
    for ruim in ("20128", "abc", "", "1.5", "-1"):
        amb.reinicia()
        rc, _ = amb.roda("codigo", env_extra={"IA_GW_PORTA": ruim})
        assert rc == 0, ruim
        (no,) = amb.chamadas("node")
        assert "--port 20129 " in no, (ruim, no)
    amb.reinicia()
    rc, _ = amb.roda("codigo", env_extra={"IA_GW_PORTA": "20555"})
    assert rc == 0 and "--port 20555 " in amb.chamadas("node")[0]
    assert amb.chamadas("socat")[0].endswith("TCP:127.0.0.1:20555")


def test_limite_de_memoria_do_node_da_reserva_e_ajustavel_e_valor_ruim_volta_ao_padrao(amb):
    amb.poe_gateway()
    rc, _ = amb.roda("codigo", env_extra={"IA_GW_MB": "256"})
    assert rc == 0 and "MB=256 " in amb.chamadas("node")[0]
    amb.reinicia()
    rc, _ = amb.roda("codigo", env_extra={"IA_GW_MB": "muito"})
    assert rc == 0 and "MB=384 " in amb.chamadas("node")[0]


def test_reserva_ligada_mas_recusada_pela_ponte_nao_deixa_a_chave_local_na_variavel(amb):
    amb.poe_gateway()
    amb.no_ar(f"{PC_IP}:11434")
    rc, saida = amb.roda("auto", env_extra={"FAKE_RECUSA_LOCAL": "1"})
    assert rc == 0, saida
    assert len(amb.chamadas("node")) == 1, "a reserva chegou a ligar"
    (linha,) = amb.chamadas("qwen")
    assert "args=--model llama3.2-32k" in linha and "inicio=chave-de-tes" in linha, linha


def test_reserva_que_morre_ao_subir_nao_faz_esperar_os_dois_minutos(amb):
    amb.poe_gateway()
    rc, saida = amb.roda("codigo", env_extra={"FAKE_NODE_MORRE": "1", "IA_ESPERA": "1"}, timeout=15)
    assert rc == 1 and "O OmniRoute do celular nao subiu" in saida
    assert not amb.chamadas("qwen") and not amb.chamadas("socat")


def test_reserva_com_o_servidor_ja_no_ar_nao_liga_outro_e_so_poe_a_ponte(amb):
    amb.poe_gateway()
    amb.no_ar("127.0.0.1:20129")
    rc, saida = amb.roda("codigo")
    assert rc == 0, saida
    assert not amb.chamadas("node") and len(amb.chamadas("socat")) == 1
    (linha,) = amb.chamadas("qwen")
    assert "inicio=chave-local-" in linha


def test_matrix_offline_percebe_a_volta_da_internet_e_reabre_completo_uma_vez(amb):
    # a conversa offline dura ~2 s; nesse meio tempo o Ollama do PC "volta" (entra no mundo falso)
    amb.poe_falso("llama-cli", '#!/bin/bash\necho "llama-cli $*" >> "$FAKE_LOG"\n'
                  f'echo "{PC_IP}:11434" >> "$FAKE_MUNDO"\nsleep 2\nexit 0\n')
    rc, saida = amb.roda(env_extra={"MATRIX": "1", "IA_VIGIA_REDE": "0.3"}, timeout=40)
    assert rc == 0, saida
    assert "A internet voltou" in saida and "Reabrindo o Matrix completo" in saida
    assert len(amb.chamadas("llama-cli")) == 1, "reabre uma vez so"
    assert "--model llama3.2-32k" in amb.chamadas("qwen")[0]


def test_sem_matrix_a_conversa_nao_vigia_a_rede(amb):
    rc, saida = amb.roda("chat", env_extra={"IA_VIGIA_REDE": "0.1"})
    assert rc == 0 and "A internet voltou" not in saida and "Reabrindo" not in saida
