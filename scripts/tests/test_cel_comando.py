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
        *"#VG-PASTA"*) [ -f "$FALSO_DIR/sem_pasta" ] || echo /storage/1A2B-3C4D/Dashcam ;;
        *"#VG-TAM"*) [ -f "$FALSO_DIR/tam" ] || exit 0
                     n=$(cat "$FALSO_DIR/tam"); [ -f "$FALSO_DIR/gravando" ] && n=$((n + 5000)); echo $n > "$FALSO_DIR/tam"; echo $n ;;
        *"#VG-ULTIMO"*) echo /storage/1A2B-3C4D/Dashcam/VID_20261106_220000.mp4 ;;
        *"#VG-CONTA"*) cat "$FALSO_DIR/videos" 2>/dev/null || echo 0 ;;
        *"#VG-TAREFA"*) [ -f "$FALSO_DIR/camera_aberta" ] && echo "  * Task{e23d648 #554 type=standard A=10979:net.sourceforge.opencamera U=0 visible=true mode=freeform}" ;;
        *"#VG-GIRO"*) echo "    SurfaceOrientation: 1" ;;
        *"#VG-TELA"*) [ -f "$FALSO_DIR/tela_apagada" ] && echo "  mWakefulness=Asleep" || echo "  mWakefulness=Awake" ;;
        *"#VG-BLOQ"*) [ -f "$FALSO_DIR/bloqueado_vg" ] && echo "isKeyguardShowing=true" ;;
        *"input keyevent 224"*) rm -f "$FALSO_DIR/tela_apagada" ;;
        *"windowingMode 5 -n net.sourceforge.opencamera"*) [ -f "$FALSO_DIR/oc_falha" ] || touch "$FALSO_DIR/camera_aberta" ;;
        *"am force-stop net.sourceforge.opencamera"*) rm -f "$FALSO_DIR/camera_aberta" "$FALSO_DIR/gravando" ;;
        *"input keyevent 24"*)
          if [ -f "$FALSO_DIR/camera_aberta" ] && [ ! -f "$FALSO_DIR/oc_nao_grava" ]; then
            if [ -f "$FALSO_DIR/gravando" ]; then rm -f "$FALSO_DIR/gravando"
            else touch "$FALSO_DIR/gravando"; [ -f "$FALSO_DIR/tam" ] || echo 0 > "$FALSO_DIR/tam"; echo $(( $(cat "$FALSO_DIR/videos" 2>/dev/null || echo 0) + 1 )) > "$FALSO_DIR/videos"; fi
          fi
          k=$(( $(cat "$FALSO_DIR/teclas" 2>/dev/null || echo 0) + 1 )); echo $k > "$FALSO_DIR/teclas"
          [ -f "$FALSO_DIR/para_apos" ] && [ "$k" -ge "$(cat "$FALSO_DIR/para_apos")" ] && rm -f "$FALSO_DIR/home/.cache/viagem/ligada" ;;
        *"#OTIMIZA-LER"*) cat "$FALSO_DIR/otimiza.txt" 2>/dev/null ;;
        *"#OTIMIZA-FAZ"*) echo "MemAvailable:    1536000 kB" ;;
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


# ---- cel viagem (06/11 noite): Open Camera numa janela flutuante sobre o Organic Maps; calor so AVISA, camera que cai volta
EXTRAS_TERMUX = {
    "termux-notification": '#!/bin/bash\necho "notif $*" >> "$FALSO_LOG"\n',
    "termux-notification-remove": '#!/bin/bash\necho "notif-remove $*" >> "$FALSO_LOG"\n',
    "termux-vibrate": '#!/bin/bash\necho "vibra $*" >> "$FALSO_LOG"\n',
    "termux-battery-status": '#!/bin/bash\necho "{\\"temperature\\": $(cat "$FALSO_DIR/temp" 2>/dev/null || echo 30.0)}"\n',
}


@pytest.fixture
def viagem(cel):
    _conectado(cel)
    for nome, texto in EXTRAS_TERMUX.items():
        (cel.dir / "bin" / nome).write_text(texto)
        (cel.dir / "bin" / nome).chmod(0o755)
    vg = cel.dir / "home" / ".cache" / "viagem"
    yield types.SimpleNamespace(cel=cel, vg=vg, roda=lambda *a: cel.roda(*a))
    (vg / "ligada").unlink(missing_ok=True)
    (cel.dir / "gravando").unlink(missing_ok=True)


def _vigia_ligada(viagem, **arquivos):
    viagem.vg.mkdir(parents=True, exist_ok=True)
    (viagem.vg / "ligada").write_text("")
    (viagem.vg / "pasta").write_text("/storage/1A2B-3C4D/Dashcam")
    for nome, texto in arquivos.items():
        (viagem.cel.dir / nome).write_text(texto)


def test_viagem_iniciar_abre_o_mapa_e_a_camera_em_janela_e_grava_pelo_volume(viagem):
    rc, s = viagem.roda("viagem", "iniciar")
    reg = viagem.cel.registro()
    assert rc == 0 and "Gravando a viagem" in s and "partes de 20 min" in s, s
    assert reg.index("app.organicmaps") < reg.index("--windowingMode 5 -n net.sourceforge.opencamera")
    assert "am task resize 554 1000 140 1510 470" in reg               # canto de cima a direita, deitado (testado 06/11)
    assert reg.index("input tap 1040 178") < reg.index("input keyevent 24")   # foco na barra da janela antes do volume
    assert "notif" in reg and "Parar" in reg and "viagem parar" in reg
    assert "GRAVANDO" in viagem.roda("viagem", "status")[1]
    assert "Ja esta gravando" in viagem.roda("viagem", "iniciar")[1]   # nao abre outra por cima
    rc, s = viagem.roda("viagem", "parar")
    assert rc == 0 and "Gravacao parada e salva" in s and "am force-stop net.sourceforge.opencamera" in viagem.cel.registro()
    reg = viagem.cel.registro()
    assert reg.rindex("input keyevent 24") < reg.rindex("am force-stop net.sourceforge.opencamera")   # para (salva) ANTES de fechar
    assert "Nao esta gravando" in viagem.roda("viagem", "status")[1]


def test_viagem_sem_mapa_nao_abre_o_organic_maps(viagem):
    assert viagem.roda("viagem", "iniciar", "--sem-mapa")[0] == 0
    assert "organicmaps" not in viagem.cel.registro()
    viagem.roda("viagem", "parar")


def test_viagem_que_nao_comecou_explica_e_nao_vigia(viagem):
    (viagem.cel.dir / "oc_nao_grava").write_text("")
    rc, s = viagem.roda("viagem", "iniciar")
    assert rc == 1 and "NAO comecou" in s and not (viagem.vg / "ligada").exists()
    assert viagem.cel.registro().count("SHELL input keyevent 24") == 2   # uma tentativa a mais, nunca um vai e volta


def test_viagem_sem_pasta_no_cartao(viagem):
    (viagem.cel.dir / "sem_pasta").write_text("")
    rc, s = viagem.roda("viagem", "iniciar")
    assert rc == 1 and "pasta Dashcam" in s and "opencamera" not in viagem.cel.registro()


def test_viagem_sem_conexao_ensina_o_jeito_a_mao(cel):
    rc, s = cel.roda("viagem", "iniciar")
    assert rc == 2 and "Open Camera em janela pop-up" in s


def _para_em(viagem, segundos=2):
    import threading, time
    def tira():
        time.sleep(segundos)
        (viagem.vg / "ligada").unlink(missing_ok=True)
    threading.Thread(target=tira).start()


def test_viagem_quente_so_avisa_e_nunca_mexe_na_gravacao(viagem):
    _vigia_ligada(viagem, camera_aberta="", gravando="", tam="100", temp="46.2")
    _para_em(viagem)
    rc, _ = viagem.cel.roda("viagem", "vigiar")
    reg = viagem.cel.registro()
    assert rc == 0 and "Celular QUENTE: 46 C" in reg and "Nada foi fechado" in reg and "vibra" in reg
    assert "input keyevent 24" not in reg and "force-stop" not in reg and "windowingMode" not in reg   # nada e parado nem fechado


def test_viagem_esquentando_avisa_sem_vibrar(viagem):
    _vigia_ligada(viagem, camera_aberta="", gravando="", tam="100", temp="43")
    _para_em(viagem)
    viagem.cel.roda("viagem", "vigiar")
    reg = viagem.cel.registro()
    assert "esquentando: 43 C" in reg and "QUENTE" not in reg and "vibra" not in reg


def test_viagem_camera_fechada_pelo_calor_volta_sozinha(viagem):
    _vigia_ligada(viagem, tam="100", para_apos="1")   # sem camera_aberta: o sistema a fechou
    viagem.cel.roda("viagem", "vigiar")
    reg = viagem.cel.registro()
    assert "--windowingMode 5 -n net.sourceforge.opencamera" in reg and "VOLTOU sozinha" in reg
    assert (viagem.cel.dir / "gravando").exists()


def test_viagem_tela_apagada_e_bloqueada_pede_o_desbloqueio_e_nao_abre_por_cima(viagem):
    _vigia_ligada(viagem, tam="100", tela_apagada="", bloqueado_vg="")
    (viagem.cel.dir / "bin" / "termux-vibrate").write_text(
        '#!/bin/bash\necho "vibra $*" >> "$FALSO_LOG"\nrm -f "$FALSO_DIR/home/.cache/viagem/ligada"\n')
    viagem.cel.roda("viagem", "vigiar")
    reg = viagem.cel.registro()
    assert "input keyevent 224" in reg and "Desbloqueie" in reg and "windowingMode" not in reg
    assert "keyevent 26" not in reg and "keyevent 223" not in reg   # nunca bloqueia nem apaga


def test_viagem_parada_no_proprio_open_camera_e_respeitada(viagem):
    _vigia_ligada(viagem, camera_aberta="", tam="100")   # janela aberta, sem gravar: foi o Rafael
    viagem.cel.roda("viagem", "vigiar")
    reg = viagem.cel.registro()
    assert "Gravacao parada no Open Camera" in reg and not (viagem.vg / "ligada").exists()
    assert "input keyevent 24" not in reg and "windowingMode" not in reg and "force-stop" not in reg


def test_viagem_desiste_so_depois_de_40_tentativas_em_10_minutos(viagem):
    _vigia_ligada(viagem, tam="100", oc_falha="")   # a camera nunca abre
    viagem.cel.roda("viagem", "vigiar")
    reg = viagem.cel.registro()
    assert reg.count("SHELL am start --windowingMode 5 -n net.sourceforge.opencamera") == 40 and "PAROU" in reg


def test_viagem_lanterna_explica(viagem):
    rc, s = viagem.roda("viagem", "lanterna")
    assert rc == 1 and "nao libera a lanterna" in s
    assert viagem.roda("viagem", "talvez")[0] == 2


def test_lanterna_ocupada_explica_pela_viagem(cel):
    (cel.dir / "bin" / "termux-torch").write_text("#!/bin/bash\nexit 1\n")
    (cel.dir / "bin" / "termux-torch").chmod(0o755)
    rc, s = cel.roda("lanterna", "ligar")
    assert rc == 1 and "cel viagem lanterna" in s


OTIMIZA = """M=1024000
K=com.samsung.android.honeyboard/.service.HoneyBoardService
C=com.google.android.gm
C=com.santander.app
C=com.google.android.gm
C=com.kgurgul.cpuinfo
C=com.fadcam
C=com.whatsapp
C=com.samsung.android.honeyboard
C=com.google.android.gms.persistent
C=com.android.phone
C=com.android.systemui
C=android
C=x;reboot
"""


def test_otimizar_fecha_so_os_parados_poupa_os_essenciais_e_mostra_a_ram(cel):
    _conectado(cel)
    (cel.dir / "otimiza.txt").write_text(OTIMIZA)
    rc, s = cel.roda("otimizar")
    reg = cel.registro()
    faz = [l for l in reg.splitlines() if "#OTIMIZA-FAZ" in l][0]
    assert rc == 0 and "am kill com.google.android.gm;" in faz and "am kill com.santander.app" in faz and "am kill com.whatsapp" in faz
    assert faz.count("am kill com.google.android.gm;") == 1   # sem repetir
    assert "am force-stop com.kgurgul.cpuinfo" in faz and "am force-stop com.fadcam" in faz
    for nunca in ("honeyboard", "gms", "com.android.", "kill android", "reboot"):
        assert nunca not in faz.replace("pm trim-caches", ""), nunca
    assert "force-stop com.whatsapp" not in faz and "force-stop com.google.android.gm" not in faz   # force-stop cortaria os avisos
    assert "Fechei 3 apps" in s and "RAM livre: antes 1000 MB, depois 1500 MB (500 MB)" in s and "screenstream" not in faz


def test_otimizar_avisa_do_screenstream_e_so_encerra_com_tudo(cel):
    _conectado(cel)
    (cel.dir / "otimiza.txt").write_text("M=1024000\nSS=1\n")
    rc, s = cel.roda("otimizar")
    assert rc == 0 and "otimizar --tudo" in s and "force-stop info.dvkr.screenstream" not in cel.registro()
    (cel.dir / "bin" / "pgrep").write_text("#!/bin/bash\nexit 1\n")   # nenhum link no ar
    (cel.dir / "bin" / "pgrep").chmod(0o755)
    rc, s = cel.roda("otimizar", "--tudo")
    assert "ENCERRADO" in s and "am force-stop info.dvkr.screenstream" in cel.registro()


def test_otimizar_com_tudo_nao_encerra_o_screenstream_se_o_link_esta_no_ar(cel):
    _conectado(cel)
    (cel.dir / "otimiza.txt").write_text("M=1024000\nSS=1\n")
    (cel.dir / "bin" / "pgrep").write_text("#!/bin/bash\nexit 0\n")
    (cel.dir / "bin" / "pgrep").chmod(0o755)
    rc, s = cel.roda("otimizar", "--tudo")
    assert "FICOU" in s and "force-stop info.dvkr.screenstream" not in cel.registro()


FRASES = [
    ("Grava a viagem", "cel viagem iniciar"),
    ("matrix, grava o caminho enquanto uso o mapa por favor", "cel viagem iniciar"),
    ("liga a câmera do carro", "cel viagem iniciar"),
    ("PARA A GRAVAÇÃO", "cel viagem parar"),
    ("terminei a viagem", "cel viagem parar"),
    ("tá gravando?", "cel viagem status"),
    ("acende a lanterna", "cel lanterna ligar"),
    ("apaga a lanterna", "cel lanterna desligar"),
    ("o celular está lento, libera a memória", "cel otimizar"),
    ("otimiza tudo no máximo", "cel otimizar --tudo"),
    ("limpa o cache", "cel limpar"),
    ("faixa preta na câmera do OBS", "cel obs verificar"),
    ("vira câmera do PC para a aula", "cel obs camera"),
    ("webcam com a câmera frontal", "cel obs frontal"),
    ("grava a minha tela", "cel obs gravar-tela"),
    ("manda a tela para a TV", "link tela"),
    ("manda a tela para o notebook com som", "link tela --som"),
    ("mostra a tela na TV em tela cheia", "link tela --preencher"),
    ("para de transmitir", "link parar"),
    ("internet livre para o notebook do hotspot", "link internet"),
    ("a VPN está ligada?", "saida status"),
    ("desliga a VPN", "saida desligar"),
    ("desliga o Wi-Fi", "cel wifi desligar"),
    ("liga o bluetooth", "cel bluetooth ligar"),
    ("apaga a tela", "cel tela apagar"),
    ("a internet caiu", "cel internet reiniciar"),
    ("como está a bateria", "cel status"),
]


@pytest.mark.parametrize("frase,cmd", FRASES)
def test_faz_entende_a_frase_do_jeito_dele(cel, frase, cmd):
    # so a decisao: o cel faz roda o comando de verdade, aqui o "Entendi:" mostra qual foi
    rc, s = cel.roda("faz", "--mostra", frase)
    assert f"Entendi: {cmd}\n" in s, (frase, s[:300])


def test_faz_pede_o_detalhe_que_falta_e_nao_reconhece_o_que_nao_sabe(cel):
    rc, s = cel.roda("faz", "manda essa foto para o PC")
    assert rc == 3 and "cel enviar-pc CAMINHO" in s
    rc, s = cel.roda("faz", "faz um bolo de cenoura")
    assert rc == 4 and "cel faz --lista" in s and "Entendi" not in s


def test_faz_nunca_executa_texto_do_usuario(cel):
    rc, s = cel.roda("faz", "--mostra", "grava a viagem; reboot $(reboot) `reboot`")
    assert "Entendi: cel viagem iniciar" in s and "reboot" not in cel.registro()


def test_faz_lista_mostra_as_frases(cel):
    rc, s = cel.roda("faz", "--lista")
    assert rc == 0 and "grava a viagem" in s and "link internet" in s
