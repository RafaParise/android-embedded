"""Testes do comando `cel` do Termux com bash de verdade e adb, settings e am FALSOS. Nenhum toca aparelho."""
import os
import pathlib
import subprocess
import types

import pytest

SCRIPT = pathlib.Path(os.environ.get("CEL_SCRIPT") or pathlib.Path(__file__).resolve().parent.parent / "celular-kit" / "bin" / "cel")  # mutantes: so em copia

ADB = r"""#!/bin/bash
echo "adb $*" >> "$FALSO_LOG"
case "$1" in
  devices) echo "List of devices attached"; [ -f "$FALSO_DIR/conectado" ] && printf '127.0.0.1:41234\tdevice\n'; exit 0 ;;
  connect) [ -f "$FALSO_DIR/depuracao" ] && [ "$2" = 127.0.0.1:41234 ] && { touch "$FALSO_DIR/conectado"; echo "connected to $2"; exit 0; }
           echo "failed to connect to $2"; exit 1 ;;
  pair) [ "$3" = 123456 ] && { touch "$FALSO_DIR/depuracao"; echo "Successfully paired"; exit 0; }; echo "Failed"; exit 1 ;;
  -s) shift 2; [ "$1" = shell ] || exit 1; shift; echo "SHELL $*" >> "$FALSO_LOG"
      case "$*" in
        *"pm list packages"*) printf 'package:com.exemplo.um\npackage:com.samsung.android.smartmirroring\n' ;;
        *"settings list"*) echo "bluetooth_on=1" ;;
        *"settings get global mobile_data"*) [ -f "$FALSO_DIR/sem_dados" ] && echo 0 || echo 1 ;;
        *"settings get global wifi_on"*) [ -f "$FALSO_DIR/sem_wifi" ] && echo 0 || echo 1 ;;
        *"df /data"*) echo "/dev/x 100 50 1000 5% /data" ;;
        *"pgrep -f"*) exit 0 ;;
        *"uiautomator dump"*) cat "$FALSO_DIR/tela.xml" 2>/dev/null ;;
        *"isKeyguardShowing"*) [ -f "$FALSO_DIR/bloqueado" ] && echo "isKeyguardShowing=true" ;;
        *"[T]ela escuro"*) [ -f "$FALSO_DIR/escura" ] && echo 4321 ;;
        *"ela-vigia.sh vigiar' | head"*) [ -f "$FALSO_DIR/vigia" ] && cat "$FALSO_DIR/vigia" ;;
        *"grep -c tela-preta"*) [ -f "$FALSO_DIR/escureceu" ] && echo 1 || echo 0 ;;
        *"setsid nohup sh -c 'sh /data/local/tmp/tela-vigia.sh agora"*) touch "$FALSO_DIR/escureceu" ;;
      esac; exit 0 ;;
esac
"""
PYTHON = r"""#!/bin/bash
# no lugar da pergunta mDNS: o Android so responde com a depuracao sem fio ligada; `python3 -c` (ler a tela) e o de verdade
[ "${1:-}" = -c ] && exec /usr/bin/python3 "$@"
cat > /dev/null; echo "mdns" >> "$FALSO_LOG"; [ -f "$FALSO_DIR/depuracao" ] && echo 41234; exit 0
"""
SETTINGS = r"""#!/bin/bash
echo "settings $*" >> "$FALSO_LOG"
[ -f "$FALSO_DIR/permissao" ] || exit 1
[ "$1" = put ] && touch "$FALSO_DIR/depuracao"
[ "$1" = get ] && { [ -f "$FALSO_DIR/depuracao" ] && echo 1 || echo 0; }
exit 0
"""


@pytest.fixture
def cel(tmp_path):
    bin_, home = tmp_path / "bin", tmp_path / "home"
    bin_.mkdir()
    home.mkdir()
    for nome, texto in (("adb", ADB), ("settings", SETTINGS), ("am", '#!/bin/bash\necho "am $*" >> "$FALSO_LOG"\n'),
                        ("timeout", '#!/bin/bash\nshift\nexec "$@"\n'), ("sleep", "#!/bin/bash\nexit 0\n"),
                        ("python3", PYTHON)):
        (bin_ / nome).write_text(texto)
        (bin_ / nome).chmod(0o755)
    log = tmp_path / "log"

    def roda(*args, extra=None):
        env = {"HOME": str(home), "PATH": f"{bin_}:/usr/bin:/bin", "FALSO_LOG": str(log), "FALSO_DIR": str(tmp_path)}
        env.update(extra or {})
        p = subprocess.Popen(["/bin/bash", str(SCRIPT), *args], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        saida, _ = p.communicate(timeout=60)
        return p.returncode, saida

    def registro():
        return log.read_text() if log.exists() else ""

    return types.SimpleNamespace(roda=roda, registro=registro, dir=tmp_path)


def _conectado(cel):
    (cel.dir / "depuracao").write_text("")
    (cel.dir / "conectado").write_text("")


def test_sintaxe():
    p = subprocess.Popen(["/bin/bash", "-n", str(SCRIPT)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert p.communicate(timeout=20)[0] == "" and p.returncode == 0


def test_sem_depuracao_diz_o_que_fazer_e_nao_roda_nada(cel):
    rc, s = cel.roda("wifi", "desligar")
    assert rc == 2 and "Depuracao sem fio" in s and "SHELL" not in cel.registro()


def test_conecta_sozinho_pelo_mdns_e_guarda_a_porta(cel):
    (cel.dir / "depuracao").write_text("")
    rc, s = cel.roda("conectar")
    assert rc == 0 and "127.0.0.1:41234" in s and "adb connect 127.0.0.1:41234" in cel.registro()
    assert (cel.dir / "home" / ".cache" / "cel-porta").read_text().strip() == "41234"


def test_porta_guardada_vem_antes_do_mdns_e_porta_velha_cai_no_mdns(cel):
    (cel.dir / "depuracao").write_text("")
    (cel.dir / "home" / ".cache").mkdir(parents=True)
    (cel.dir / "home" / ".cache" / "cel-porta").write_text("41234")
    assert cel.roda("conectar")[0] == 0 and "mdns" not in cel.registro(), "a porta guardada basta"
    (cel.dir / "conectado").unlink()
    (cel.dir / "home" / ".cache" / "cel-porta").write_text("39999")   # a depuracao reiniciou: porta nova
    assert cel.roda("conectar")[0] == 0 and "adb connect 127.0.0.1:39999" in cel.registro() and "mdns" in cel.registro()
    assert (cel.dir / "home" / ".cache" / "cel-porta").read_text().strip() == "41234"


def test_mdns_aceita_so_a_resposta_do_proprio_aparelho():
    texto = SCRIPT.read_text(encoding="utf-8")
    assert "if quem[0] != eu:" in texto and "IP_MULTICAST_IF" in texto


def test_religa_a_depuracao_quando_o_termux_tem_permissao(cel):
    (cel.dir / "permissao").write_text("")
    rc, s = cel.roda("conectar")
    assert rc == 0 and "settings put global adb_wifi_enabled 1" in cel.registro()


def test_parear_so_aceita_numeros(cel):
    assert cel.roda("parear", "37a", "123456")[0] == 2
    assert cel.roda("parear", "37000", "12;rm")[0] == 2
    assert "adb pair" not in cel.registro()
    rc, s = cel.roda("parear", "37000", "123456")
    assert rc == 0 and "Pareado" in s and "adb pair 127.0.0.1:37000 123456" in cel.registro()


def test_desligar_wifi_sobrevive_a_queda_da_conexao(cel):
    _conectado(cel)
    cel.roda("wifi", "desligar")
    assert "setsid nohup sh -c 'svc wifi disable'" in cel.registro()


def test_reiniciar_wifi_e_internet_em_um_processo_solto(cel):
    _conectado(cel)
    cel.roda("wifi", "reiniciar")
    cel.roda("internet", "reiniciar")
    r = cel.registro()
    assert "setsid nohup sh -c 'svc wifi disable; sleep 4; svc wifi enable'" in r
    assert "airplane-mode enable; sleep 4; cmd connectivity airplane-mode disable" in r


def test_ligar_wifi_bluetooth_e_dados(cel):
    _conectado(cel)
    assert "Wi-Fi ligado" in cel.roda("wifi", "ligar")[1]
    assert "Bluetooth ligado" in cel.roda("bluetooth", "ligar")[1]
    assert "Dados moveis ligado" in cel.roda("dados", "ligar")[1]
    assert "svc data enable" in cel.registro()


@pytest.mark.parametrize("args", [("wifi", "talvez"), ("dados",), ("bluetooth", "x"), ("internet",), ("aviao", "x"), ("depuracao",)])
def test_uso_errado_nao_roda(cel, args):
    _conectado(cel)
    assert cel.roda(*args)[0] == 2 and "svc" not in cel.registro()


def test_limpar_usa_trim_caches_e_nunca_clear(cel):
    _conectado(cel)
    rc, s = cel.roda("limpar")
    assert "pm trim-caches 100G" in cel.registro() and "pm clear" not in cel.registro() and "Caches limpos" in s


def test_abrir_tela_conhecida_e_recusa_desconhecida(cel):
    _conectado(cel)
    assert cel.roda("abrir", "bluetooth")[0] == 0 and "am start -a android.settings.BLUETOOTH_SETTINGS" in cel.registro()
    assert cel.roda("abrir", "x;reboot")[0] == 2


def test_abrir_tela_sem_conexao_usa_o_am_do_termux(cel):
    assert cel.roda("abrir", "wifi")[0] == 0 and "am start -a android.settings.WIFI_SETTINGS" in cel.registro()


def test_abrir_app_valida_o_pacote(cel):
    _conectado(cel)
    assert cel.roda("abrir-app", "com.x;reboot")[0] == 2
    assert cel.roda("abrir-app", "org.fossify.messages")[0] == 0 and "monkey -p org.fossify.messages" in cel.registro()


def test_microfone_escreve_os_mesmos_arquivos_do_pc(cel):
    _conectado(cel)
    cel.roda("microfone", "sempre")
    cel.roda("microfone", "mudo")
    r = cel.registro()
    assert "echo fixo > /data/local/tmp/mic-bt.modo" in r and "touch /data/local/tmp/mic-celular.bloqueado" in r


def test_procurar_junta_arquivos_apps_configuracoes_e_telas(cel):
    _conectado(cel)
    rc, s = cel.roda("procurar", "blue")
    assert "bluetooth_on=1" in s and "cel abrir bluetooth" in s


def test_tv_abre_o_screenstream(cel):
    _conectado(cel)
    rc, s = cel.roda("tv")
    assert "info.dvkr.screenstream" in cel.registro() and "ScreenStream" in s and "CAST_SETTINGS" not in cel.registro()


def test_status_sem_conexao_nao_quebra(cel):
    rc, s = cel.roda("status")
    assert rc == 0 and "NAO" in s


def test_economia_de_dados_usa_o_netpolicy(cel):
    _conectado(cel)
    assert cel.roda("economia-dados", "ligar")[0] == 0
    assert cel.roda("economia-dados", "desligar")[0] == 0
    assert cel.roda("economia-dados", "status")[0] == 0
    reg = cel.registro()
    assert "cmd netpolicy set restrict-background true" in reg and "cmd netpolicy set restrict-background false" in reg
    assert "cmd netpolicy get restrict-background" in reg
    assert cel.roda("economia-dados", "comprimir")[0] == 2


def test_acordado_liga_e_desliga_o_permanecer_acordado(cel):
    _conectado(cel)
    assert cel.roda("acordado", "ligar")[0] == 0
    assert cel.roda("acordado", "desligar")[0] == 0
    assert cel.roda("acordado", "status")[0] == 0
    reg = cel.registro()
    assert "settings put global stay_on_while_plugged_in 7" in reg
    assert "settings put global stay_on_while_plugged_in 0" in reg
    assert "settings get global stay_on_while_plugged_in" in reg
    assert cel.roda("acordado", "sempre")[0] == 2


def test_lanterna_usa_o_termux_api_sem_depuracao(cel):
    (cel.dir / "bin" / "termux-torch").write_text('#!/bin/bash\necho "torch $*" >> "$FALSO_LOG"\n')
    (cel.dir / "bin" / "termux-torch").chmod(0o755)
    assert cel.roda("lanterna", "ligar")[0] == 0  # sem depuracao sem fio: o Termux:API nao precisa dela
    assert cel.roda("lanterna", "desligar")[0] == 0
    reg = cel.registro()
    assert "torch on" in reg and "torch off" in reg and "SHELL" not in reg
    assert cel.roda("lanterna", "piscar")[0] == 2


def test_lanterna_sem_termux_api_explica(cel):
    rc, s = cel.roda("lanterna", "ligar")
    assert rc == 1 and "Termux:API" in s


def test_tela_apagar_usa_os_botoes_da_vigia_e_confere_a_camada(cel):
    _conectado(cel)
    rc, s = cel.roda("tela", "apagar")
    assert rc == 2 and "vigia do gesto" in s and "tela-vigia.sh agora" not in cel.registro(), "sem saber os botoes, nao escurece"
    (cel.dir / "vigia").write_text("sh /data/local/tmp/tela-vigia.sh vigiar /dev/input/event2 /dev/input/event4 /dev/input/event0\n")
    rc, s = cel.roda("tela", "apagar")
    assert rc == 0 and "sem bloqueio" in s, s
    assert "tela-vigia.sh agora /dev/input/event2 /dev/input/event4 /dev/input/event0" in cel.registro()


def test_tela_nao_apaga_com_pin_na_tela_nem_com_botao_estranho(cel):
    _conectado(cel)
    (cel.dir / "vigia").write_text("sh /data/local/tmp/tela-vigia.sh vigiar /dev/input/event2;reboot\n")
    assert cel.roda("tela", "apagar")[0] == 2 and "agora" not in cel.registro()
    (cel.dir / "bloqueado").write_text("")
    rc, s = cel.roda("tela", "apagar")
    assert rc == 2 and "PIN" in s


def test_tela_acender_mata_a_camada_e_devolve_o_brilho(cel):
    _conectado(cel)
    assert cel.roda("tela", "acender")[0] == 0
    assert "Tela luz volta" in cel.registro() and "kill" in cel.registro()
    (cel.dir / "escura").write_text("")
    assert "escura" in cel.roda("tela", "status")[1]


CURL_FALSO = r"""#!/bin/bash
echo "curl $*" >> "$FALSO_LOG"
for a in "$@"; do case "$a" in */saude) printf 200; exit 0 ;; */mcp) cat > "$FALSO_DIR/curl-config"; touch "$FALSO_DIR/depuracao"; exit 0 ;; esac; done
exit 7
"""


def test_depuracao_desligada_o_cel_pede_ao_pc_pelo_cabo_e_conecta(cel):
    (cel.dir / "home" / ".qwen").mkdir(parents=True)
    (cel.dir / "home" / ".qwen" / ".env").write_text("PONTE_PC_TOKEN=token-de-teste-" + "x" * 30 + "\n")
    (cel.dir / "bin" / "curl").write_text(CURL_FALSO)
    (cel.dir / "bin" / "curl").chmod(0o755)
    rc, s = cel.roda("conectar")
    assert rc == 0, s
    reg = cel.registro()
    assert "depuracao-sem-fio-ligar" in reg and "token-de-teste" not in reg, "o token vai pela entrada padrao do curl"
    assert "Bearer token-de-teste" in (cel.dir / "curl-config").read_text()


def test_sem_token_o_cel_nao_chama_a_ponte(cel):
    (cel.dir / "bin" / "curl").write_text(CURL_FALSO)
    (cel.dir / "bin" / "curl").chmod(0o755)
    assert cel.roda("conectar")[0] == 2
    assert "curl" not in cel.registro()


TELA_APP = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?><hierarchy rotation="0">
<node index="0" text="" package="com.android.settings" class="android.widget.FrameLayout" clickable="false" bounds="[0,0][720,1600]">
<node text="Moonlight" resource-id="android:id/title" class="android.widget.TextView" package="com.android.settings" clickable="false" bounds="[100,100][400,160]" />
<node text="Abrir" resource-id="com.android.settings:id/button1" class="android.widget.Button" package="com.android.settings" clickable="true" bounds="[0,600][240,700]" />
<node text="Desinstalar" resource-id="com.android.settings:id/button2" class="android.widget.Button" package="com.android.settings" clickable="true" bounds="[240,600][480,700]" />
<node text="Ligar para 11 98765-4321 ou fulano@x.com" class="android.widget.TextView" package="com.android.settings" clickable="false" bounds="[0,800][720,860]" />
</node></hierarchy>"""


def test_ler_lista_a_tela_e_mascara_dados(cel):
    _conectado(cel)
    (cel.dir / "tela.xml").write_text(TELA_APP)
    rc, s = cel.roda("ler")
    assert rc == 0 and "com.android.settings" in s
    assert "Abrir [botao] (120,650)" in s and "Desinstalar [botao]" in s
    assert "98765" not in s and "fulano@" not in s and "[numero]" in s and "[e-mail]" in s


def test_tocar_por_texto_e_por_numero(cel):
    _conectado(cel)
    (cel.dir / "tela.xml").write_text(TELA_APP)
    rc, s = cel.roda("tocar", "Abrir")
    assert rc == 0 and "SHELL input tap 120 650" in cel.registro()
    cel.roda("ler")
    rc, s = cel.roda("tocar", "2")
    assert rc == 0 and cel.registro().count("SHELL input tap 120 650") == 2


def test_tocar_recusa_botao_sem_volta(cel):
    _conectado(cel)
    (cel.dir / "tela.xml").write_text(TELA_APP)
    rc, s = cel.roda("tocar", "desinstalar")
    assert rc == 3 and "Recusado" in s
    rc, s = cel.roda("tocar", "360", "650")  # por coordenada, em cima do botao: tambem recusa
    assert rc == 3
    assert "input tap" not in cel.registro()


def test_tocar_recusa_tudo_na_tela_de_autorizar_depuracao(cel):
    _conectado(cel)
    (cel.dir / "tela.xml").write_text(TELA_APP.replace("Moonlight", "Permitir depuração USB?").replace("Desinstalar", "Cancelar"))
    rc, s = cel.roda("tocar", "Abrir")
    assert rc == 3 and "input tap" not in cel.registro()


def test_tecla_nao_tem_liga_desliga(cel):
    _conectado(cel)
    rc, s = cel.roda("tecla", "power")
    assert rc == 2 and "keyevent" not in cel.registro()
    rc, s = cel.roda("tecla", "voltar")
    assert rc == 0 and "SHELL input keyevent 4" in cel.registro()


def test_palavra_perigosa_em_texto_comum_nao_trava_a_tela(cel):
    _conectado(cel)
    (cel.dir / "tela.xml").write_text(TELA_APP.replace("Moonlight", "Formatar numeros de telefone"))
    rc, s = cel.roda("tocar", "Abrir")
    assert rc == 0 and "SHELL input tap 120 650" in cel.registro()
    rc, s = cel.roda("tocar", "Formatar numeros de telefone")
    assert rc == 3


CURL_OBS = r"""#!/bin/bash
echo "curl $*" >> "$FALSO_LOG"
for a in "$@"; do case "$a" in
  */saude) printf 200; exit 0 ;;
  */mcp) cat > "$FALSO_DIR/curl-config"
         printf '%s' '{"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"{\"acao\": \"x\", \"saida\": \"camera virtual ligada agora\nPRONTO\"}"}],"isError":false}}'
         exit 0 ;;
esac; done
exit 7
"""


def _ponte_obs(cel):
    (cel.dir / "home" / ".qwen").mkdir(parents=True, exist_ok=True)
    (cel.dir / "home" / ".qwen" / ".env").write_text("PONTE_PC_TOKEN=token-de-teste-" + "x" * 30 + "\n")
    (cel.dir / "bin" / "curl").write_text(CURL_OBS)
    (cel.dir / "bin" / "curl").chmod(0o755)
    (cel.dir / "bin" / "python3").unlink()
    (cel.dir / "bin" / "python3").symlink_to("/usr/bin/python3")


@pytest.mark.parametrize("sub,acao", [("camera", "obs-camera-ligar"), ("frontal", "obs-camera-frontal"), ("tela", "obs-tela-ligar"),
                                      ("gravar", "obs-gravar-camera"), ("gravar-tela", "obs-gravar-tela"),
                                      ("parar-gravacao", "obs-parar-gravacao"), ("desligar", "obs-desligar"), ("status", "obs-status"), ("verificar", "obs-verificar"),
                                      ("live", "obs-live-iniciar"), ("parar-live", "obs-live-parar")])
def test_obs_pede_a_acao_certa_ao_pc_e_mostra_a_saida(cel, sub, acao):
    _ponte_obs(cel)
    rc, s = cel.roda("obs", sub)
    assert rc == 0, s
    assert "camera virtual ligada agora" in s
    assert f'"nome":"{acao}"' in cel.registro()
    assert "token-de-teste" not in cel.registro(), "o token vai pela entrada padrao do curl"


def test_obs_sem_pc_explica_e_uso_errado_nao_chama(cel):
    (cel.dir / "bin" / "curl").write_text("#!/bin/bash\necho \"curl $*\" >> \"$FALSO_LOG\"\nexit 7\n")
    (cel.dir / "bin" / "curl").chmod(0o755)
    (cel.dir / "home" / ".qwen").mkdir(parents=True)
    (cel.dir / "home" / ".qwen" / ".env").write_text("PONTE_PC_TOKEN=t" + "x" * 30 + "\n")
    rc, s = cel.roda("obs", "camera")
    assert rc == 1 and "PC nao respondeu" in s
    rc, s = cel.roda("obs", "apagar-tudo")
    assert rc == 2 and "/mcp" not in cel.registro().split("apagar-tudo")[-1]


def test_enviar_pc_recusa_fora_do_armazenamento_e_nome_perigoso(cel):
    _conectado(cel)
    assert cel.roda("enviar-pc")[0] == 2
    rc, s = cel.roda("enviar-pc", "/data/data/com.termux/files/home/segredo.txt", "/sdcard/a;rm.jpg")
    assert "So arquivo do armazenamento" in s and "caractere perigoso" in s
    assert "ShareActivity" not in cel.registro()


def test_nunca_deixa_o_celular_sem_internet(cel):
    """06/11: o Matrix desligou Wi-Fi e dados, perdeu o modelo da nuvem e nao conseguiu religar."""
    _conectado(cel)
    (cel.dir / "sem_dados").write_text("")
    rc, s = cel.roda("wifi", "desligar")
    assert rc == 3 and "SEM internet" in s and "svc wifi disable" not in cel.registro()
    (cel.dir / "sem_dados").unlink()
    (cel.dir / "sem_wifi").write_text("")
    rc, s = cel.roda("dados", "desligar")
    assert rc == 3 and "svc data disable" not in cel.registro()
    rc, s = cel.roda("aviao", "ligar")
    assert rc == 3 and "airplane-mode enable" not in cel.registro()
    (cel.dir / "sem_wifi").unlink()
    assert cel.roda("dados", "desligar")[0] == 0 and "svc data disable" in cel.registro()


# ---- cel viagem (06/11): FadCam grava em segundo plano no cartao, Organic Maps na tela, calor so AVISA
AM_FADCAM = r"""#!/bin/bash
echo "am $*" >> "$FALSO_LOG"
case "$*" in
  *RecordingStartActivity*)
    [ -f "$FALSO_DIR/fadcam_falha" ] && exit 0
    printf 'x%.0s' $(seq 1 1100) > "$VIAGEM_PASTA/FadCam_20261106_100000.mp4"   # o arquivo vazio (~1 KB) que o FadCam cria
    f="$VIAGEM_PASTA/FadCam_20261106_100001.mp4"; : > "$f"; touch "$FALSO_DIR/gravando"
    ( while [ -f "$FALSO_DIR/gravando" ]; do printf 'xxxxxxxxxxxxxxxx' >> "$f"; done ) >/dev/null 2>&1 &
    ;;
  *RecordingStopActivity*) rm -f "$FALSO_DIR/gravando" ;;
esac
exit 0
"""
EXTRAS_TERMUX = {
    "termux-notification": '#!/bin/bash\necho "notif $*" >> "$FALSO_LOG"\n',
    "termux-notification-remove": '#!/bin/bash\necho "notif-remove $*" >> "$FALSO_LOG"\n',
    "termux-vibrate": '#!/bin/bash\necho "vibra $*" >> "$FALSO_LOG"\n',
    "termux-battery-status": '#!/bin/bash\necho "{\\"temperature\\": $(cat "$FALSO_DIR/temp" 2>/dev/null || echo 30.0)}"\n',
}


@pytest.fixture
def viagem(cel):
    pasta = cel.dir / "Viagens"
    pasta.mkdir()
    for nome, texto in {"am": AM_FADCAM, **EXTRAS_TERMUX}.items():
        (cel.dir / "bin" / nome).write_text(texto)
        (cel.dir / "bin" / nome).chmod(0o755)
    extra = {"VIAGEM_PASTA": str(pasta)}
    yield types.SimpleNamespace(cel=cel, pasta=pasta, roda=lambda *a: cel.roda(*a, extra=extra))
    (cel.dir / "gravando").unlink(missing_ok=True)
    (cel.dir / "home" / ".cache" / "viagem" / "ligada").unlink(missing_ok=True)


def test_viagem_sem_am_ensina_a_instalar(cel):
    (cel.dir / "bin" / "am").unlink()
    rc, s = cel.roda("viagem", "iniciar")
    assert rc == 1 and "pkg install termux-am" in s


def test_viagem_iniciar_abre_o_fadcam_antes_grava_e_abre_o_mapa(viagem):
    rc, s = viagem.roda("viagem", "iniciar")
    assert rc == 0, s
    reg = viagem.cel.registro()
    # o FadCam frio trava se mandar gravar na hora: abre o app ANTES do comando de gravar
    assert reg.index("com.fadcam/.SplashActivity") < reg.index("RecordingStartActivity") < reg.index("app.organicmaps")
    assert "Gravando a viagem" in s and "so AVISO" in s
    assert "notif" in reg and "Parar" in reg and "viagem parar" in reg
    assert "GRAVANDO" in viagem.roda("viagem", "status")[1]
    assert "Ja esta gravando" in viagem.roda("viagem", "iniciar")[1]  # nao abre de novo por cima
    rc, s = viagem.roda("viagem", "parar")
    assert rc == 0 and "Gravacao parada" in s and "RecordingStopActivity" in viagem.cel.registro()
    nomes = sorted(p.name for p in viagem.pasta.iterdir())
    assert nomes == ["FadCam_20261106_100001.mp4"]  # o arquivo vazio de ~1 KB sumiu; o video ficou
    assert "Nao esta gravando" in viagem.roda("viagem", "status")[1]


def test_viagem_sem_mapa_nao_abre_o_organic_maps(viagem):
    assert viagem.roda("viagem", "iniciar", "--sem-mapa")[0] == 0
    assert "organicmaps" not in viagem.cel.registro()
    viagem.roda("viagem", "parar")


def test_viagem_que_nao_comecou_explica_e_nao_vigia(viagem):
    (viagem.cel.dir / "fadcam_falha").write_text("")
    rc, s = viagem.roda("viagem", "iniciar")
    assert rc == 1 and "NAO comecou" in s and "Fechar app" in s
    assert not (viagem.cel.dir / "home" / ".cache" / "viagem" / "ligada").exists()


def test_viagem_sem_pasta_no_cartao(cel):
    (cel.dir / "bin" / "am").write_text(AM_FADCAM)
    (cel.dir / "bin" / "am").chmod(0o755)
    rc, s = cel.roda("viagem", "iniciar", extra={"VIAGEM_PASTA": str(cel.dir / "nao-existe")})
    assert rc == 1 and "cartao SD" in s and "SplashActivity" not in cel.registro()


def test_viagem_vigia_so_avisa_o_calor_e_avisa_quando_a_gravacao_para(viagem):
    vg = viagem.cel.dir / "home" / ".cache" / "viagem"
    vg.mkdir(parents=True, exist_ok=True)
    (vg / "ligada").write_text("")
    (viagem.cel.dir / "temp").write_text("46.2")
    rc, _ = viagem.roda("viagem", "vigiar")  # nada gravando: avisa o calor, percebe a parada em 2 voltas e sai
    reg = viagem.cel.registro()
    assert rc == 0 and "Celular QUENTE: 46 C" in reg and "Nada foi fechado" in reg and "vibra" in reg
    assert "PAROU" in reg and not (vg / "ligada").exists()
    assert "RecordingStopActivity" not in reg and "force-stop" not in reg  # nunca fecha nada sozinho


def test_viagem_vigia_atencao_sem_vibrar(viagem):
    vg = viagem.cel.dir / "home" / ".cache" / "viagem"
    vg.mkdir(parents=True, exist_ok=True)
    (vg / "ligada").write_text("")
    (viagem.cel.dir / "temp").write_text("43")
    viagem.roda("viagem", "vigiar")
    reg = viagem.cel.registro()
    assert "esquentando: 43 C" in reg and "QUENTE" not in reg


def test_viagem_lanterna_nao_mexe_no_fadcam_e_explica(viagem):
    rc, s = viagem.roda("viagem", "lanterna")
    assert rc == 1 and "trava" in s and "TOGGLE_TORCH" not in viagem.cel.registro()  # 06/11: apagar travou o FadCam
    assert viagem.roda("viagem", "talvez")[0] == 2


def test_lanterna_ocupada_ensina_a_do_fadcam(cel):
    (cel.dir / "bin" / "termux-torch").write_text("#!/bin/bash\nexit 1\n")
    (cel.dir / "bin" / "termux-torch").chmod(0o755)
    rc, s = cel.roda("lanterna", "ligar")
    assert rc == 1 and "lanterna segura" in s
