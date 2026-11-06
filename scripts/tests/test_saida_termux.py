"""Testes do `saida` do Termux (scripts/celular-kit/bin/saida): liga a saida de internet pelo PC e o GUARDA que a desliga sozinho quando o PC some.
O mundo e falso (curl, am e termux-wake-* de mentira, com o PC, o Wi-Fi e a saida como arquivos); o bash e os utilitarios sao de verdade (os testes rodam no WSL).
Nada toca o celular, a rede ou o adb."""
import os
import pathlib
import re
import signal
import subprocess
import time

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPT = RAIZ / "scripts" / "celular-kit" / "bin" / "saida"
BASH = next((p for p in ("/bin/bash", "/usr/bin/bash") if pathlib.Path(p).exists()), "/bin/bash")
pytestmark = pytest.mark.skipif(not pathlib.Path(BASH).exists(), reason="precisa de bash (os testes rodam no WSL)")
SIGKILL = getattr(signal, "SIGKILL", 9)

# O mundo falso: wifi_up = a rede de baixo funciona; pc_up = o PC esta ligado e na tailnet; exit_on = a saida pelo PC esta escolhida no app;
# exit_quebrada = a saida esta escolhida mas nao passa trafego (ex.: PC nao aprovado); sem_internet = a internet esta fora; portal = pagina de login (200 em vez de 204).
FALSO_CURL = r"""#!/bin/bash
echo "curl $*" >> "$FAKE_LOG"
url=""; quer=0
while [ $# -gt 0 ]; do
  case "$1" in
    -w) quer=1; shift 2 ;;
    -o|-m|--connect-timeout) shift 2 ;;
    http*) url="$1"; shift ;;
    *) shift ;;
  esac
done
E="$FAKE_ESTADO"
case "$url" in
  */saude)
    if [ -e "$E/wifi_up" ] && [ -e "$E/pc_up" ]; then exit "$(cat "$E/rc_pc" 2>/dev/null || echo 0)"; fi
    exit 28 ;;
esac
ok=0
if [ -e "$E/wifi_up" ] && [ ! -e "$E/sem_internet" ]; then
  if [ -e "$E/exit_on" ]; then [ -e "$E/pc_up" ] && [ ! -e "$E/exit_quebrada" ] && ok=1; else ok=1; fi
fi
if [ $ok = 1 ]; then cod=204; [ -e "$E/portal" ] && cod=200; else cod=000; fi
[ $quer = 1 ] && printf '%s' "$cod"
[ $ok = 1 ] && exit 0
exit 28
"""
FALSO_AM = r"""#!/bin/bash
echo "am $*" >> "$FAKE_LOG"
E="$FAKE_ESTADO"
if [ -e "$E/am_falha" ]; then echo "Error: Activity not started, unable to resolve Intent"; exit 255; fi
prev=""; nome=""
for a in "$@"; do
  if [ "$prev" = exitNode ]; then nome="$a"; fi
  prev="$a"
done
if [ -n "$nome" ]; then : > "$E/exit_on"; else rm -f "$E/exit_on"; fi
echo "Broadcast completed: result=0"
"""
UTILITARIOS = ("bash", "cat", "tr", "cut", "date", "wc", "tail", "mv", "rm", "mkdir", "chmod", "sleep", "readlink", "sed", "nohup")


class Ambiente:
    def __init__(self, base):
        self.home = base / "home"
        self.fakebin = base / "fakebin"
        self.util = base / "util"
        self.estado = base / "estado"
        self.run = base / "run"
        for d in (self.home, self.fakebin, self.util, self.estado, self.run):
            d.mkdir(parents=True)
        self.log = self.estado / "log.txt"
        self.log.write_text("")
        falsos = (("curl", FALSO_CURL), ("am", FALSO_AM),
                  # o hotspot e lido pelo python3 (getifaddrs); aqui ele so responde pelo arquivo "hotspot" do mundo falso
                  ("python3", '#!/bin/bash\necho python3 >> "$FAKE_LOG"\n[ -e "$FAKE_ESTADO/hotspot" ]\n'),
                  ("termux-wake-lock", '#!/bin/bash\necho wake-lock >> "$FAKE_LOG"\n'),
                  ("termux-wake-unlock", '#!/bin/bash\necho wake-unlock >> "$FAKE_LOG"\n'))
        for nome, texto in falsos:
            f = self.fakebin / nome
            f.write_text(texto, encoding="utf-8")
            f.chmod(0o755)
        for nome in UTILITARIOS:
            real = next(p for p in (pathlib.Path("/usr/bin") / nome, pathlib.Path("/bin") / nome) if p.exists())
            (self.util / nome).symlink_to(real)
        self.mundo(wifi=True, pc=True)

    def mundo(self, wifi=None, pc=None, exit_on=None, exit_quebrada=None, sem_internet=None, portal=None, am_falha=None, rc_pc=None,
              hotspot=None):
        for nome, v in (("wifi_up", wifi), ("pc_up", pc), ("exit_on", exit_on), ("exit_quebrada", exit_quebrada),
                        ("sem_internet", sem_internet), ("portal", portal), ("am_falha", am_falha), ("hotspot", hotspot)):
            if v is None:
                continue
            f = self.estado / nome
            if v:
                f.write_text("")
            elif f.exists():
                f.unlink()
        if rc_pc is not None:
            (self.estado / "rc_pc").write_text(str(rc_pc))

    def _env(self, extra=None):
        env = {"PATH": f"{self.fakebin}:{self.util}", "HOME": str(self.home), "SAIDA_RUN": str(self.run), "SAIDA_INTERVALO": "1",
               "SAIDA_ESPERA": "0", "SAIDA_PAUSA": "0", "SAIDA_TEMPO": "1", "FAKE_LOG": str(self.log), "FAKE_ESTADO": str(self.estado)}
        env.update(extra or {})
        return env

    def roda(self, *args, extra=None, timeout=40):
        p = subprocess.Popen([BASH, str(SCRIPT), *args], cwd=str(self.home), env=self._env(extra), stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        saida, _ = p.communicate(timeout=timeout)
        return p.returncode, saida

    def ciclos(self, n, extra=None):
        for _ in range(n):
            self.roda("ciclo", extra=extra)

    def am(self):
        """As intencoes que o app da Tailscale recebeu, em ordem: (nome da saida, rede local)."""
        achados = []
        for l in self.log.read_text(encoding="utf-8").splitlines():
            m = re.search(r"exitNode (.*?) --ez allowLanAccess (\w+)", l)
            if m:
                achados.append((m.group(1), m.group(2)))
        return achados

    def chamadas(self, quem):
        return [l for l in self.log.read_text(encoding="utf-8").splitlines() if l.startswith(quem)]

    def arq(self, nome):
        f = self.run / nome
        return f.read_text(encoding="utf-8").strip() if f.exists() else None

    def pede(self, lan="true"):
        (self.run / "desejada").write_text(lan + "\n", encoding="utf-8")

    def suspende(self):
        (self.run / "suspensa").write_text(str(int(time.time())) + "\n", encoding="utf-8")

    def pid_laco(self):
        p = self.arq("laco.pid")
        return int(p) if p and p.isdigit() else None

    def espera(self, condicao, segundos=15):
        fim = time.time() + segundos
        while time.time() < fim:
            if condicao():
                return True
            time.sleep(0.1)
        return condicao()


def vivo(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.fixture
def amb(tmp_path):
    a = Ambiente(tmp_path)
    yield a
    pid = a.pid_laco()
    if pid:
        try:
            os.kill(pid, SIGKILL)
        except ProcessLookupError:
            pass


# ---------------------------------------------------------------- o arquivo em si

def test_sintaxe_do_bash_esta_correta():
    p = subprocess.Popen([BASH, "-n", str(SCRIPT)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    saida, _ = p.communicate()
    assert p.returncode == 0, saida


def test_script_e_ascii_e_sem_cr():
    b = SCRIPT.read_bytes()
    assert b"\r" not in b
    b.decode("ascii")


def test_script_nao_mexe_em_ajustes_do_android_nem_usa_privilegio_nem_guarda_segredo():
    t = SCRIPT.read_text(encoding="ascii")
    codigo = "\n".join(l for l in t.splitlines() if not l.lstrip().startswith("#"))
    for proibido in ("settings put", "settings delete", "pm ", "su -c", "sudo", "rm -rf", "dumpsys", "svc ", "cmd "):
        assert proibido not in codigo, proibido
    assert len(re.findall(r"am broadcast", codigo)) == 1, "uma unica porta para o app da Tailscale"
    assert "com.tailscale.ipn/.IPNReceiver" in codigo and "USE_EXIT_NODE" in codigo
    for padrao in (r"nvapi-", r"AIza", r"sk-or-", r"Bearer\s", r"authkey", r"tskey-"):
        assert not re.search(padrao, t), padrao


def test_ajuda_lista_os_comandos_e_comando_desconhecido_da_erro(amb):
    rc, out = amb.roda("ajuda")
    assert rc == 0
    for c in ("saida ligar", "saida desligar", "saida status", "saida guarda", "saida vigilia", "saida log"):
        assert c in out, c
    rc, _ = amb.roda("zzz")
    assert rc == 2
    rc, _ = amb.roda()
    assert rc == 2
    assert amb.am() == []


# ---------------------------------------------------------------- ligar

def test_ligar_liga_a_saida_confere_e_deixa_o_guarda_vigiando(amb):
    rc, out = amb.roda("ligar")
    assert rc == 0, out
    assert amb.am() == [("rafaparise", "true")]
    assert amb.arq("desejada") == "true"
    pid = amb.pid_laco()
    assert pid and vivo(pid)
    assert not (amb.run / "vigilia").exists() and not amb.chamadas("wake-lock"), "vigilia gasta bateria: so se pedir"
    assert "LIGADA" in out


def test_ligar_sem_lan(amb):
    rc, out = amb.roda("ligar", "--sem-lan")
    assert rc == 0, out
    assert amb.am() == [("rafaparise", "false")]
    assert amb.arq("desejada") == "false"
    pid = amb.pid_laco()
    assert pid and vivo(pid)


def test_ligar_com_vigilia_segura_o_celular_e_avisa_da_bateria(amb):
    rc, out = amb.roda("ligar", "--vigilia")
    assert rc == 0, out
    assert (amb.run / "vigilia").exists() and amb.chamadas("wake-lock")
    assert "bateria" in out


def test_ligar_recusa_se_o_pc_nao_responde(amb):
    amb.mundo(pc=False)
    rc, out = amb.roda("ligar")
    assert rc == 1 and "nao respondeu" in out
    assert amb.am() == [] and amb.arq("desejada") is None and amb.pid_laco() is None


def test_ligar_recusa_se_o_celular_ja_esta_sem_internet(amb):
    amb.mundo(sem_internet=True)
    rc, out = amb.roda("ligar")
    assert rc == 1 and "sem internet" in out
    assert amb.am() == [] and amb.arq("desejada") is None


def test_ligar_desfaz_se_a_internet_nao_passa_pelo_pc(amb):
    amb.mundo(exit_quebrada=True)
    rc, out = amb.roda("ligar")
    assert rc == 1 and "DESFEITO" in out and "painel" in out
    assert amb.am() == [("rafaparise", "true"), ("", "true")]
    assert amb.arq("desejada") is None and amb.pid_laco() is None
    assert not (amb.estado / "exit_on").exists(), "a saida ficou escolhida no app"


def test_ligar_com_portal_cativo_nao_conta_como_internet(amb):
    amb.mundo(portal=True)
    rc, out = amb.roda("ligar")
    assert rc == 1 and amb.am() == []


def test_ligar_com_o_app_recusando_nao_marca_nada(amb):
    amb.mundo(am_falha=True)
    rc, out = amb.roda("ligar")
    assert rc == 1 and "nao aceitou" in out
    assert amb.arq("desejada") is None and amb.pid_laco() is None
    assert "Activity not started" in (amb.run / "saida.log").read_text(encoding="utf-8")


def test_ligar_duas_vezes_nao_cria_dois_guardas(amb):
    assert amb.roda("ligar")[0] == 0
    p1 = amb.pid_laco()
    assert amb.roda("ligar")[0] == 0
    assert amb.pid_laco() == p1 and vivo(p1)


def test_ligar_recusa_opcao_desconhecida(amb):
    rc, out = amb.roda("ligar", "--tudo")
    assert rc == 2 and amb.am() == []


# ---------------------------------------------------------------- desligar, guarda, vigilia

def test_desligar_desliga_a_saida_para_o_guarda_e_solta_a_vigilia(amb):
    assert amb.roda("ligar")[0] == 0
    pid = amb.pid_laco()
    amb.suspende()
    rc, out = amb.roda("desligar")
    assert rc == 0 and "DESLIGADA" in out
    assert amb.am()[-1] == ("", "true")
    assert amb.arq("desejada") is None and amb.arq("suspensa") is None
    assert amb.espera(lambda: not vivo(pid), 5)
    assert amb.chamadas("wake-unlock"), "desligar sempre solta a vigilia, mesmo a de antes"
    assert amb.pid_laco() is None


def test_desligar_sem_nada_ligado_e_inofensivo(amb):
    rc, out = amb.roda("desligar")
    assert rc == 0 and amb.am() == [("", "true")]


def test_desligar_com_o_app_recusando_avisa_mas_o_guarda_para(amb):
    assert amb.roda("ligar")[0] == 0
    amb.mundo(am_falha=True)
    rc, out = amb.roda("desligar")
    assert rc == 1 and "Exit node > None" in out
    assert amb.arq("desejada") is None and amb.pid_laco() is None


def test_desligar_nunca_mata_um_processo_que_nao_e_o_guarda(amb):
    real_sleep = next(p for p in ("/usr/bin/sleep", "/bin/sleep") if pathlib.Path(p).exists())
    outro = subprocess.Popen([real_sleep, "60"])
    try:
        (amb.run / "laco.pid").write_text(f"{outro.pid}\n")
        rc, out = amb.roda("desligar")
        assert rc == 0
        assert vivo(outro.pid) and outro.poll() is None, "o pid velho era de outro programa"
        rc, out = amb.roda("status")
        assert "Guarda: parado" in out
    finally:
        outro.kill()
        outro.wait()


def test_guarda_sobe_o_laco_so_se_a_saida_esta_pedida(amb):
    rc, out = amb.roda("guarda")
    assert rc == 1 and amb.pid_laco() is None
    amb.pede()
    rc, out = amb.roda("guarda")
    assert rc == 0
    pid = amb.pid_laco()
    assert pid and vivo(pid)
    assert amb.am() == [], "o guarda so vigia, nao liga nada por conta propria"


def test_vigilia_liga_e_desliga(amb):
    rc, out = amb.roda("vigilia", "ligar")
    assert rc == 0 and (amb.run / "vigilia").exists()
    rc, out = amb.roda("vigilia", "desligar")
    assert rc == 0 and not (amb.run / "vigilia").exists() and amb.chamadas("wake-unlock")
    assert amb.roda("vigilia", "talvez")[0] == 2


# ---------------------------------------------------------------- status e log

def test_status_sem_nada_pedido(amb):
    rc, out = amb.roda("status")
    assert rc == 0
    for t in ("nao pedida", "Guarda: parado", "desligada", "PC pela Tailscale: responde", "Internet agora: ok"):
        assert t in out, t


def test_status_com_a_saida_ligada(amb):
    assert amb.roda("ligar")[0] == 0
    rc, out = amb.roda("status")
    assert "PEDIDA" in out and "Guarda: rodando" in out and "Vigilia (celular acordado): desligada" in out
    assert amb.roda("vigilia", "ligar")[0] == 0
    assert "Vigilia (celular acordado): ligada" in amb.roda("status")[1]


def test_status_pedida_mas_sem_guarda_manda_rodar_guarda(amb):
    amb.pede()
    rc, out = amb.roda("status")
    assert "PEDIDA" in out and "PARADO" in out and "saida guarda" in out


def test_status_mostra_suspensa_pc_fora_e_sem_internet(amb):
    amb.pede()
    amb.suspende()
    amb.mundo(pc=False, sem_internet=True)
    rc, out = amb.roda("status")
    assert rc == 0 and "SUSPENSA" in out and "NAO responde" in out and "Internet agora: SEM" in out


def test_log_mostra_as_ultimas_linhas(amb):
    assert "(registro vazio)" in amb.roda("log")[1]
    (amb.run / "saida.log").write_text("".join(f"linha {i}\n" for i in range(30)), encoding="utf-8")
    rc, out = amb.roda("log", "3")
    assert out.splitlines() == ["linha 27", "linha 28", "linha 29"]
    assert len(amb.roda("log")[1].splitlines()) == 15
    assert len(amb.roda("log", "abc")[1].splitlines()) == 15


def test_log_roda_quando_passa_de_300_linhas(amb):
    (amb.run / "saida.log").write_text("".join(f"velha {i}\n" for i in range(305)), encoding="utf-8")
    assert amb.roda("desligar")[0] == 0
    linhas = (amb.run / "saida.log").read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 150 and "desligada" in linhas[-1] and linhas[0].startswith("velha 156")


# ---------------------------------------------------------------- o ciclo do guarda

def test_ciclo_sem_a_saida_pedida_nao_faz_nada(amb):
    amb.mundo(exit_on=True, pc=False)
    amb.ciclos(3)
    assert amb.am() == [] and not amb.chamadas("curl")


def test_ciclo_com_internet_ok_nao_faz_nada(amb):
    amb.pede()
    amb.mundo(exit_on=True)
    amb.ciclos(3)
    assert amb.am() == [] and amb.arq("falhas") == "0" and amb.arq("suspensa") is None


def test_uma_falha_so_conta_e_a_segunda_suspende_a_saida(amb):
    amb.pede()
    amb.mundo(exit_on=True, pc=False)
    amb.ciclos(1)
    assert amb.am() == [] and amb.arq("falhas") == "1" and amb.arq("suspensa") is None
    amb.ciclos(1)
    assert amb.am() == [("", "true")] and amb.arq("suspensa").isdigit()
    assert "SUSPENSA" in (amb.run / "saida.log").read_text(encoding="utf-8")
    assert not (amb.estado / "exit_on").exists()
    rc, out = amb.roda("ciclo")
    assert len(amb.am()) == 1, "suspensa e PC fora: nao manda nada de novo"


def test_falha_isolada_seguida_de_sucesso_zera_a_conta(amb):
    amb.pede()
    amb.mundo(exit_on=True, sem_internet=True)
    amb.ciclos(1)
    amb.mundo(sem_internet=False)
    amb.ciclos(1)
    amb.mundo(sem_internet=True)
    amb.ciclos(1)
    assert amb.am() == [] and amb.arq("suspensa") is None and amb.arq("falhas") == "1"


def test_o_numero_de_falhas_e_configuravel(amb):
    amb.pede()
    amb.mundo(exit_on=True, pc=False)
    amb.ciclos(2, extra={"SAIDA_FALHAS": "4"})
    assert amb.am() == []
    amb.ciclos(2, extra={"SAIDA_FALHAS": "4"})
    assert amb.am() == [("", "true")]


def test_o_guarda_mantem_a_rede_local_como_estava_ao_suspender_e_religar(amb):
    amb.pede("false")
    amb.mundo(exit_on=True, pc=False)
    amb.ciclos(2)
    amb.mundo(pc=True)
    amb.ciclos(2)
    assert amb.am() == [("", "false"), ("rafaparise", "false")]


def test_portal_cativo_conta_como_sem_internet(amb):
    amb.pede()
    amb.mundo(exit_on=True, portal=True)
    amb.ciclos(2)
    assert amb.am() == [("", "true")]


def test_suspensa_com_o_pc_fora_nao_religa(amb):
    amb.pede()
    amb.suspende()
    amb.mundo(pc=False)
    amb.ciclos(4)
    assert amb.am() == [] and amb.arq("oks") == "0" and amb.arq("suspensa") is not None


def test_pc_que_volta_so_e_religado_depois_de_oks_respostas_seguidas(amb):
    amb.pede()
    amb.suspende()
    amb.ciclos(1)
    assert amb.am() == [] and amb.arq("oks") == "1"
    amb.ciclos(1)
    assert amb.am() == [("rafaparise", "true")]
    assert amb.arq("suspensa") is None and (amb.estado / "exit_on").exists()
    assert "RELIGADA" in (amb.run / "saida.log").read_text(encoding="utf-8")


def test_pc_que_some_de_novo_no_meio_zera_a_contagem(amb):
    amb.pede()
    amb.suspende()
    amb.ciclos(1)
    amb.mundo(pc=False)
    amb.ciclos(1)
    amb.mundo(pc=True)
    amb.ciclos(1)
    assert amb.am() == [] and amb.arq("oks") == "1"


@pytest.mark.parametrize("rc", [0, 22, 52, 56])
def test_pc_responde_mesmo_com_a_ponte_parada(amb, rc):
    amb.pede()
    amb.suspende()
    amb.mundo(rc_pc=rc)
    amb.ciclos(2)
    assert amb.am() == [("rafaparise", "true")], rc


@pytest.mark.parametrize("rc", [6, 7, 28, 35])
def test_pc_nao_responde_com_outros_codigos_do_curl(amb, rc):
    amb.pede()
    amb.suspende()
    amb.mundo(rc_pc=rc)
    amb.ciclos(3)
    assert amb.am() == [], rc


def test_pc_responde_mas_a_internet_nao_passa_desfaz_e_espera_cada_vez_mais(amb):
    amb.pede()
    amb.suspende()
    amb.mundo(exit_quebrada=True)
    amb.ciclos(2)
    assert amb.am() == [("rafaparise", "true"), ("", "true")]
    assert amb.arq("suspensa") is not None and amb.arq("espera") == "30"
    assert int(amb.arq("proxima")) > time.time() + 20
    amb.ciclos(3)
    assert len(amb.am()) == 2, "dentro da espera nao tenta de novo"
    (amb.run / "proxima").write_text("0\n")
    amb.ciclos(2)
    assert len(amb.am()) == 4 and amb.arq("espera") == "60"
    (amb.run / "proxima").write_text("0\n")
    amb.ciclos(2)
    assert amb.arq("espera") == "120"
    assert "nao passou" in (amb.run / "saida.log").read_text(encoding="utf-8")


def test_a_espera_para_de_crescer_no_maximo(amb):
    amb.pede()
    amb.suspende()
    amb.mundo(exit_quebrada=True)
    (amb.run / "espera").write_text("600\n")
    amb.ciclos(2, extra={"SAIDA_ESPERA_MAX": "900"})
    assert amb.arq("espera") == "900"
    (amb.run / "proxima").write_text("0\n")
    amb.ciclos(2, extra={"SAIDA_ESPERA_MAX": "900"})
    assert amb.arq("espera") == "900"


def test_depois_de_religar_com_sucesso_a_espera_volta_ao_comeco(amb):
    amb.pede()
    amb.suspende()
    (amb.run / "espera").write_text("240\n")
    (amb.run / "proxima").write_text("0\n")
    amb.ciclos(2)
    assert amb.arq("suspensa") is None and amb.arq("espera") is None and amb.arq("proxima") is None


def test_o_guarda_nao_religa_o_que_voce_desligou(amb):
    amb.pede()
    amb.mundo(exit_on=True, pc=False)
    amb.ciclos(2)
    assert amb.roda("desligar")[0] == 0
    n = len(amb.am())
    amb.mundo(pc=True)
    amb.ciclos(4)
    assert len(amb.am()) == n and not (amb.estado / "exit_on").exists()


def test_se_o_app_recusar_ao_suspender_nao_marca_suspensa_e_tenta_de_novo(amb):
    amb.pede()
    amb.mundo(exit_on=True, pc=False, am_falha=True)
    amb.ciclos(3)
    assert amb.arq("suspensa") is None
    amb.mundo(am_falha=False)
    amb.ciclos(1)
    assert amb.arq("suspensa") is not None


def test_se_o_app_recusar_ao_religar_continua_suspensa(amb):
    amb.pede()
    amb.suspende()
    amb.mundo(am_falha=True)
    amb.ciclos(2)
    assert amb.arq("suspensa") is not None and amb.arq("espera") == "30"


# ---------------------------------------------------------------- configuracao

@pytest.mark.parametrize("nome", ["pc rafa", "pc;reboot", "$(id)", "a'b", 'a"b', "a`b`", "x" * 64, "a/b", "a&b", "a|b", "a>b"])
def test_nome_do_pc_invalido_e_recusado_antes_de_qualquer_coisa(amb, nome):
    rc, out = amb.roda("ligar", extra={"SAIDA_NO": nome})
    assert rc == 2 and amb.am() == [] and not amb.chamadas("curl")


def test_nome_do_pc_configuravel(amb):
    rc, out = amb.roda("ligar", extra={"SAIDA_NO": "outro-pc.1"})
    assert rc == 0, out
    assert amb.am() == [("outro-pc.1", "true")]


@pytest.mark.parametrize("var,valor", [("SAIDA_PC_IP", "1.2.3.4;x"), ("SAIDA_PC_IP", "$(x)"), ("SAIDA_PORTA", "80a"), ("SAIDA_PORTA", "$(x)")])
def test_ip_e_porta_invalidos_sao_recusados(amb, var, valor):
    rc, out = amb.roda("ligar", extra={var: valor})
    assert rc == 2 and amb.am() == []


@pytest.mark.parametrize("var", ["SAIDA_PC_IP", "SAIDA_PORTA"])
def test_ip_e_porta_vazios_caem_no_padrao(amb, var):
    amb.roda("status", extra={var: ""})
    assert any("http://100.64.0.1:20130/saude" in l for l in amb.chamadas("curl"))


def test_ligar_com_o_guarda_de_pe_prende_e_solta_a_vigilia(amb):
    assert amb.roda("ligar")[0] == 0
    assert not amb.chamadas("wake-lock")
    assert amb.roda("ligar", "--vigilia")[0] == 0
    assert amb.chamadas("wake-lock") and (amb.run / "vigilia").exists(), "com o guarda ja de pe, a vigilia nova tem que segurar o celular"
    antes = len(amb.chamadas("wake-unlock"))
    assert amb.roda("ligar")[0] == 0
    assert not (amb.run / "vigilia").exists()
    assert len(amb.chamadas("wake-unlock")) > antes, "sem a opcao, a vigilia antiga tem que ser solta"


def test_ip_e_porta_do_pc_vao_na_url_do_teste(amb):
    amb.roda("status", extra={"SAIDA_PC_IP": "100.1.2.3", "SAIDA_PORTA": "1234"})
    assert any("http://100.1.2.3:1234/saude" in l for l in amb.chamadas("curl"))


def test_endereco_de_conferencia_configuravel_e_so_204_vale(amb):
    amb.roda("status", extra={"SAIDA_CONFERE": "http://exemplo.teste/204"})
    assert any("http://exemplo.teste/204" in l for l in amb.chamadas("curl"))


def test_numeros_invalidos_caem_no_padrao_e_tempo_zero_nao_vira_sem_limite(amb):
    rc, out = amb.roda("status", extra={"SAIDA_INTERVALO": "abc", "SAIDA_TEMPO": "0", "SAIDA_FALHAS": "-1", "SAIDA_OKS": "x"})
    assert rc == 0 and "Guarda: parado" in out
    assert not any(re.search(r"-m 0( |$)", l) for l in amb.chamadas("curl")), "curl -m 0 e sem limite de tempo"


# ---------------------------------------------------------------- o laco de verdade

def test_o_laco_encerra_sozinho_quando_a_saida_deixa_de_ser_pedida(amb):
    assert amb.roda("ligar")[0] == 0
    pid = amb.pid_laco()
    (amb.run / "desejada").unlink()
    assert amb.espera(lambda: not vivo(pid), 8)
    assert "encerrado" in (amb.run / "saida.log").read_text(encoding="utf-8")


def test_o_laco_de_verdade_suspende_quando_o_pc_some_e_religa_quando_volta(amb):
    assert amb.roda("ligar")[0] == 0
    amb.mundo(pc=False)   # o PC some: sem ele a internet pela saida para
    assert amb.espera(lambda: amb.arq("suspensa") is not None, 20), (amb.run / "saida.log").read_text(encoding="utf-8")
    assert not (amb.estado / "exit_on").exists()
    amb.mundo(pc=True)    # o PC volta
    assert amb.espera(lambda: amb.arq("suspensa") is None, 20), (amb.run / "saida.log").read_text(encoding="utf-8")
    assert (amb.estado / "exit_on").exists()
    assert amb.am()[0] == ("rafaparise", "true") and amb.am()[-1] == ("rafaparise", "true")


# ---- hotspot (05/11): com a saida pelo PC ligada, o que um app do celular INICIA para um aparelho do hotspot vai para o
# tunel e se perde (o Tailscale so deixa de fora a rede do Wi-Fi). Enquanto o hotspot estiver ligado, a saida fica PAUSADA.

def test_hotspot_ligado_pausa_a_saida_e_desligado_religa(amb):
    amb.pede()
    amb.mundo(exit_on=True)
    amb.mundo(hotspot=True)
    amb.ciclos(1)
    assert amb.am()[-1] == ("", "true") and amb.arq("hotspot") is not None
    assert "hotspot" in amb.roda("log")[1]
    amb.ciclos(2)  # enquanto o hotspot segue ligado, nada de novo
    assert len(amb.am()) == 1
    amb.mundo(hotspot=False)
    amb.ciclos(2 + 1)  # OKS=2 testes com o PC respondendo e religa
    assert amb.am()[-1] == ("rafaparise", "true")
    assert amb.arq("hotspot") is None and amb.arq("suspensa") is None


def test_hotspot_pausa_mesmo_com_a_saida_ja_suspensa(amb):
    amb.pede()
    amb.suspende()
    amb.mundo(hotspot=True, pc=True)
    amb.ciclos(3)
    assert all(nome == "" for nome, _ in amb.am())  # nunca religa com o hotspot ligado


def test_ligar_com_hotspot_ligado_fica_pausada(amb):
    amb.mundo(hotspot=True)
    rc, out = amb.roda("ligar")
    assert rc == 0 and "hotspot" in out.lower()
    assert amb.arq("desejada") == "true" and amb.arq("hotspot") is not None
    assert all(nome == "" for nome, _ in amb.am())


def test_status_mostra_a_pausa_do_hotspot(amb):
    amb.pede()
    amb.mundo(hotspot=True)
    amb.ciclos(1)
    assert "hotspot" in amb.roda("status")[1].lower()


def test_sem_hotspot_o_guarda_segue_igual(amb):
    amb.pede()
    amb.mundo(exit_on=True)
    amb.ciclos(3)
    assert amb.am() == [] and amb.arq("hotspot") is None