"""Testes de tela-apagada.py, tela-vigia.sh e da logica pura do Tela.java. O vigia roda de verdade em sh, com falsos no PATH; o Java roda no JDK do PC. O adb nunca e aberto.
Nada aqui prova o aparelho: o toque, o escuro e o cabo solto se conferem com a mao do Rafael (o toque morto de 04/11 passaria em qualquer teste com falso)."""
import os
import pathlib
import stat
import subprocess
import time

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
VIGIA = SCRIPTS / "tela-vigia.sh"
JAVA_FONTE = SCRIPTS / "celular-kit" / "tela" / "Tela.java"
JDK = pathlib.Path("/mnt/c/Projetos/ferramentas/compilar-dex/jdk/bin")


@pytest.fixture
def ta(importa_script):
    return importa_script("tela-apagada.py")


GETEVENT = """add device 1: /dev/input/event13
  name:     "GameSir-Nova Lite Consumer Control"
  events:
    KEY (0001): KEY_VOLUMEDOWN KEY_POWER
add device 2: /dev/input/event9
  name:     "mt-snd-card Headset Jack"
  events:
    KEY (0001): KEY_VOLUMEDOWN KEY_VOLUMEUP
add device 3: /dev/input/event1
  name:     "mtk-kpd"
  events:
    KEY (0001): KEY_VOLUMEUP
add device 4: /dev/input/event2
  name:     "mtk-pmic-keys"
  events:
    KEY (0001): KEY_VOLUMEDOWN KEY_POWER
add device 5: /dev/input/event3
  name:     "sec_touchscreen"
  events:
    ABS (0003): ABS_MT_TRACKING_ID
"""


def test_acha_os_nos_do_corpo_do_celular_e_nao_os_do_controle_nem_do_fone(ta):
    assert ta.nos_de_entrada(GETEVENT) == {"volume": "event2", "toque": "event3", "teclas": ["event1", "event2"]}
    assert ta.nos_de_entrada("") == {"volume": "", "toque": "", "teclas": []}


def respostas(ta, monkeypatch, shell, get_state="device"):
    monkeypatch.setattr(ta, "adb", lambda *a, timeout=30: type("R", (), {"stdout": get_state + "\n", "returncode": 0})())
    monkeypatch.setattr(ta, "shell", shell)
    monkeypatch.setattr(ta.time, "sleep", lambda s: None)


def test_nao_escurece_fora_do_adb(ta, monkeypatch, capsys):
    respostas(ta, monkeypatch, lambda c, timeout=30: pytest.fail("falou com o celular"), get_state="offline")
    assert ta.main(["apagar"]) == 2
    assert "adb" in capsys.readouterr().out


def test_nao_escurece_sem_como_acender(ta, monkeypatch, capsys):
    so_volume = 'add device 4: /dev/input/event2\n  name:     "mtk-pmic-keys"\n  events:\n    KEY (0001): KEY_VOLUMEDOWN\n'
    respostas(ta, monkeypatch, lambda c, timeout=30: so_volume if c.startswith("getevent") else "")
    assert ta.main(["apagar"]) == 2
    assert "sem como acender" in capsys.readouterr().out


def test_nao_escurece_com_o_pin_pedindo(ta, monkeypatch, capsys):
    comandos = []

    def shell(c, timeout=30):
        comandos.append(c)
        return GETEVENT if c.startswith("getevent") else "isKeyguardShowing=true\n"

    respostas(ta, monkeypatch, shell)
    assert ta.main(["apagar"]) == 2
    assert "PIN" in capsys.readouterr().out
    assert not any(" agora " in c for c in comandos)


def test_sem_camada_preta_desfaz_e_avisa(ta, monkeypatch, capsys):
    comandos = []

    def shell(c, timeout=30):
        comandos.append(c)
        if c.startswith("getevent"):
            return GETEVENT
        if c == ta.ESTADO:
            return "isKeyguardShowing=false\n"
        if c.startswith("[ -f"):
            return "vivo\n"
        if c == ta.TEM_CAMADA:
            return "0\n"
        return ""

    respostas(ta, monkeypatch, shell)
    assert ta.main(["apagar"]) == 1
    assert "Nao escureceu" in capsys.readouterr().out
    assert any("Tela luz volta" in c for c in comandos)


def test_nenhum_caminho_aperta_energia_nem_apaga_o_painel_de_verdade(ta, monkeypatch):
    comandos = []

    def shell(c, timeout=30):
        comandos.append(c)
        return GETEVENT if c.startswith("getevent") else "powerMode=On\nmWakefulness=Awake\nisKeyguardShowing=false\n"

    respostas(ta, monkeypatch, shell)
    ta.acender()
    ta.parar()
    ta.status()
    junto = "\n".join(comandos)
    assert "keyevent 26" not in junto and "keyevent 223" not in junto and "Tela off" not in junto
    fonte = (SCRIPTS / "celular-kit" / "tela" / "Tela.java").read_text(encoding="utf-8")
    assert '"setDisplayPowerMode"' not in fonte  # foi o que deixou o toque morto em 04/11


def test_acender_avisa_se_a_camada_ficou(ta, monkeypatch, capsys):
    respostas(ta, monkeypatch, lambda c, timeout=30: "1\n" if c == ta.TEM_CAMADA else "isKeyguardShowing=false\n")
    assert ta.acender() == 1
    assert "Reiniciar" in capsys.readouterr().out


def test_alternar_acende_se_ja_esta_escura(ta, monkeypatch):
    chamou = []
    monkeypatch.setattr(ta, "escuro_agora", lambda: True)
    monkeypatch.setattr(ta, "acender", lambda: chamou.append("acender") or 0)
    monkeypatch.setattr(ta, "apagar", lambda: pytest.fail("escureceu de novo"))
    assert ta.main([]) == 0 and chamou == ["acender"]


def test_observar_religa_o_gesto_e_o_brilho_quando_o_cabo_volta(ta, monkeypatch):
    comandos, iniciou = [], []
    respostas(ta, monkeypatch, lambda c, timeout=30: comandos.append(c) or "")
    monkeypatch.setattr(ta, "iniciar", lambda: iniciou.append(1) or 0)
    assert ta.observa_uma_vez() is True
    assert iniciou == [1] and any("Tela luz volta" in c for c in comandos)


def test_observar_nao_mexe_na_tela_escura_e_so_religa_o_gesto(ta, monkeypatch):
    comandos, iniciou = [], []
    respostas(ta, monkeypatch, lambda c, timeout=30: comandos.append(c) or ("123\n" if c == ta.PROCESSO_ESCURO else ""))
    monkeypatch.setattr(ta, "iniciar", lambda: iniciou.append(1) or 0)
    assert ta.observa_uma_vez() is True
    assert iniciou == [1] and not any("Tela luz volta" in c for c in comandos)


@pytest.mark.parametrize("estado_adb,vivo", [("offline", ""), ("", ""), ("device", "vivo\n")])
def test_observar_nao_faz_nada_sem_celular_ou_com_gesto_vivo(ta, monkeypatch, estado_adb, vivo):
    respostas(ta, monkeypatch, lambda c, timeout=30: vivo if c.startswith("[ -f") else "", get_state=estado_adb)
    monkeypatch.setattr(ta, "iniciar", lambda: pytest.fail("religou sem precisar"))
    assert ta.observa_uma_vez() is False


def test_observar_religa_wifi_e_microfone_com_o_gesto_vivo(ta, monkeypatch):
    ligou = []
    monkeypatch.setattr(ta, "adb", lambda *a, **k: type("R", (), {"stdout": "device\n"})())
    monkeypatch.setattr(ta, "vigia_vivo", lambda: True)
    monkeypatch.setattr(ta, "turbo_vivo", lambda: False)
    monkeypatch.setattr(ta, "liga_turbo", lambda: ligou.append(1))
    monkeypatch.setattr(ta, "iniciar", lambda: pytest.fail("mexeu no gesto vivo"))
    assert ta.observa_uma_vez() is False
    assert ligou == [1]


def test_observar_nao_duplica_o_processo_vivo(ta, monkeypatch):
    monkeypatch.setattr(ta, "adb", lambda *a, **k: type("R", (), {"stdout": "device\n"})())
    monkeypatch.setattr(ta, "vigia_vivo", lambda: True)
    monkeypatch.setattr(ta, "turbo_vivo", lambda: True)
    monkeypatch.setattr(ta, "liga_turbo", lambda: pytest.fail("duplicou"))
    assert ta.observa_uma_vez() is False


def test_observar_recarrega_quando_o_script_muda(ta, monkeypatch):
    versoes = iter([1.0, 2.0, 2.0, 2.0])
    voltas = []

    def dorme(_):
        voltas.append(1)
        assert len(voltas) < 3, "nao recarregou: seguiria em laco para sempre"

    import types

    class Fim(Exception):
        pass

    novas = []
    novo = types.SimpleNamespace(observa_uma_vez=lambda: novas.append(1))

    def dorme(_):
        voltas.append(1)
        if len(voltas) >= 3:
            raise Fim

    monkeypatch.setattr(ta, "versao_do_script", lambda: next(versoes))
    monkeypatch.setattr(ta, "observa_uma_vez", lambda: False)
    monkeypatch.setattr(ta, "carrega_atual", lambda: novo)
    monkeypatch.setattr(ta.time, "sleep", dorme)
    monkeypatch.setattr(ta.os, "execv", lambda *a: pytest.fail("trocar de processo encerra a tarefa agendada do Windows"))
    with pytest.raises(Fim):
        ta.observar()
    assert novas, "depois da mudanca tem de rodar o codigo novo, no mesmo processo"


def test_observar_sobrevive_a_recarga_quebrada_e_a_erro_inesperado(ta, monkeypatch):
    versoes = iter([1.0, 2.0, 2.0, 2.0, 2.0])
    voltas, chamadas = [], []

    class Fim(Exception):
        pass

    def dorme(_):
        voltas.append(1)
        if len(voltas) >= 3:
            raise Fim

    def quebra():
        raise SyntaxError("arquivo salvo pela metade")

    def observa():
        chamadas.append(1)
        raise KeyError("erro novo")

    monkeypatch.setattr(ta, "versao_do_script", lambda: next(versoes))
    monkeypatch.setattr(ta, "observa_uma_vez", observa)
    monkeypatch.setattr(ta, "carrega_atual", quebra)
    monkeypatch.setattr(ta.time, "sleep", dorme)
    with pytest.raises(Fim):
        ta.observar()
    assert len(chamadas) == 3, "o vigia nao pode morrer nem parar de olhar"


def test_carrega_atual_le_o_arquivo_de_verdade(ta):
    m = ta.carrega_atual()
    assert callable(m.observa_uma_vez) and m is not ta


def test_encerrar_o_processo_devolve_o_microfone(ta, monkeypatch):
    comandos = []
    monkeypatch.setattr(ta, "shell", lambda c, timeout=30: comandos.append(c) or "")
    ta.para_turbo()
    assert any("Tela mic-solta" in c for c in comandos)


def test_observar_respeita_o_parar(ta, monkeypatch):
    respostas(ta, monkeypatch, lambda c, timeout=30: "sim\n" if ta.PARADO in c else "")
    monkeypatch.setattr(ta, "iniciar", lambda: pytest.fail("religou depois do parar"))
    assert ta.observa_uma_vez() is False


def test_parar_marca_e_iniciar_desmarca(ta, monkeypatch):
    comandos = []
    respostas(ta, monkeypatch, lambda c, timeout=30: comandos.append(c) or (GETEVENT if c.startswith("getevent") else "vivo\n" if c.startswith("[ -f") else ""))
    ta.parar()
    assert any(c == f"touch {ta.PARADO}" for c in comandos)
    comandos.clear()
    assert ta.iniciar() == 0
    assert any(f"rm -f {ta.PARADO}" in c for c in comandos)


def test_turbo_nao_liga_se_ele_desligou_e_nao_duplica(ta, monkeypatch):
    comandos = []
    respostas(ta, monkeypatch, lambda c, timeout=30: comandos.append(c) or ("sim\n" if ta.SEM_TURBO in c and c.startswith("[ -f") else ""))
    ta.liga_turbo()
    assert not any(" turbo " in c for c in comandos)
    comandos.clear()
    respostas(ta, monkeypatch, lambda c, timeout=30: comandos.append(c) or ("vivo\n" if ta.PID_TURBO in c else ""))
    ta.liga_turbo()
    assert not any("setsid" in c for c in comandos)
    comandos.clear()
    respostas(ta, monkeypatch, lambda c, timeout=30: comandos.append(c) or "")
    ta.liga_turbo()
    assert any("setsid" in c and " turbo " in c for c in comandos)


def test_desligar_turbo_marca_e_encerra(ta, monkeypatch):
    comandos = []
    respostas(ta, monkeypatch, lambda c, timeout=30: comandos.append(c) or "")
    assert ta.turbo_desligar() == 0
    assert comandos[0] == f"touch {ta.SEM_TURBO}" and any(ta.PROCESSO_TURBO in c for c in comandos)


def test_parar_tambem_para_o_turbo(ta, monkeypatch):
    comandos = []
    respostas(ta, monkeypatch, lambda c, timeout=30: comandos.append(c) or "")
    ta.parar()
    assert any(ta.PROCESSO_TURBO in c for c in comandos)


# ---- o vigia de verdade, em sh, com falsos no PATH


def falso(pasta, nome, corpo):
    f = pasta / nome
    f.write_text("#!/bin/sh\n" + corpo + "\n", encoding="utf-8", newline="\n")
    f.chmod(f.stat().st_mode | stat.S_IEXEC)


class Vigia:
    def __init__(self, tmp, teclas="", motivo="toques", bloqueado="false", modo="vigiar"):
        self.tmp = tmp
        self.bin = tmp / "bin"
        self.bin.mkdir()
        self.fila = tmp / "fila"
        self.fila.write_text(teclas, encoding="utf-8")
        (tmp / "motivo-falso").write_text(motivo, encoding="utf-8")
        falso(self.bin, "dumpsys", f'echo "isKeyguardShowing={bloqueado}"')
        falso(self.bin, "input", f'echo "$*" >> {tmp}/input.log')
        falso(self.bin, "app_process", f'echo "$*" >> {tmp}/tela.log\ncase "$3" in escuro) m=$(cat {tmp}/motivo-falso); [ "$m" = morreu ] && exit 137; echo "acendeu: $m";; esac')
        # cada linha da fila = atraso e tecla; fila vazia = fica esperando
        falso(self.bin, "getevent", f"""
linha=$(head -n1 {self.fila})
if [ -z "$linha" ]; then /bin/sleep 30; exit 0; fi
sed -i 1d {self.fila}
/bin/sleep "${{linha%% *}}"
echo "EV_KEY ${{linha#* }} DOWN"; echo "EV_SYN SYN_REPORT 0\"""")
        env = dict(os.environ, PATH=f"{self.bin}:/usr/bin:/bin", TELA_DIR=str(tmp), TELA_JANELA="1", TELA_ESPERA_PIN="0")
        self.proc = subprocess.Popen(["sh", str(VIGIA), modo, "vol", "toque", "cima", "energia"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)

    def ler(self, nome):
        f = self.tmp / nome
        return f.read_text(encoding="utf-8") if f.exists() else ""

    def espera(self, cond, limite=8):
        fim = time.time() + limite
        while time.time() < fim:
            if cond():
                return True
            time.sleep(0.1)
        return False

    def escureceu(self):
        return self.ler("tela.log").count("toque cima energia")

    def fecha(self):
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()


@pytest.fixture
def vigia(tmp_path):
    criados = []

    def cria(**k):
        v = Vigia(tmp_path, **k)
        criados.append(v)
        return v

    yield cria
    for v in criados:
        v.fecha()


TRES = "0 KEY_VOLUMEDOWN\n0 KEY_VOLUMEDOWN\n0 KEY_VOLUMEDOWN\n"


def test_volume_tres_vezes_escurece_e_registra_o_motivo(vigia):
    v = vigia(teclas=TRES)
    assert v.espera(lambda: "toques" in v.ler("tela-vigia.motivo"))
    assert "Tela escuro 3 toque cima energia" in v.ler("tela.log")  # devolve os 3 apertos que baixaram a midia
    assert "keyevent" not in v.ler("input.log")  # acendeu por toque: nada de tecla
    assert not (v.tmp / "tela-escuro.trava").exists()


def test_o_gesto_funciona_de_novo_depois_de_acender(vigia):
    v = vigia(teclas=TRES + TRES)
    assert v.espera(lambda: v.escureceu() == 2)


@pytest.mark.parametrize("teclas,espera", [("0 KEY_VOLUMEDOWN\n0 KEY_VOLUMEDOWN\n", 2), ("0 KEY_VOLUMEUP\n0 KEY_VOLUMEUP\n0 KEY_VOLUMEUP\n", 2), ("0 KEY_VOLUMEDOWN\n3 KEY_VOLUMEDOWN\n3 KEY_VOLUMEDOWN\n", 8)])
def test_outros_gestos_nao_escurecem(vigia, teclas, espera):
    v = vigia(teclas=teclas)
    assert not v.espera(v.escureceu, espera)


def test_nao_escurece_com_o_celular_bloqueado(vigia):
    v = vigia(teclas=TRES, bloqueado="true")
    assert not v.espera(v.escureceu, 2)


@pytest.mark.parametrize("motivo", ["energia", "dormiu", "bloqueou"])
def test_botao_ou_bloqueio_mostra_o_pin_sem_apertar_energia(vigia, motivo):
    v = vigia(teclas=TRES, motivo=motivo)
    assert v.espera(lambda: "keyevent 224" in v.ler("input.log"))
    assert "keyevent 26" not in v.ler("input.log")


@pytest.mark.parametrize("motivo", ["toques", "volume", "alarme", "chamada"])
def test_acender_normal_nao_mexe_no_bloqueio(vigia, motivo):
    v = vigia(teclas=TRES, motivo=motivo)
    assert v.espera(lambda: motivo in v.ler("tela-vigia.motivo"))
    time.sleep(0.3)
    assert v.ler("input.log") == ""


def test_se_o_tela_morrer_o_brilho_volta(vigia):
    v = vigia(teclas=TRES, motivo="morreu")
    assert v.espera(lambda: "encerrada" in v.ler("tela-vigia.motivo"))
    assert "Tela luz volta" in v.ler("tela.log")


def test_turbo_religa_se_morrer_e_para_com_a_marca(tmp_path):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    falso(bin_, "app_process", f'echo "$*" >> {tmp_path}/tela.log')
    env = dict(os.environ, PATH=f"{bin_}:/usr/bin:/bin", TELA_DIR=str(tmp_path), TELA_TURBO_ESPERA="0.1")
    p = subprocess.Popen(["sh", str(VIGIA), "turbo"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    try:
        fim = time.time() + 5
        log = tmp_path / "tela.log"
        while time.time() < fim and not (log.exists() and log.read_text(encoding="utf-8").count("wifi-turbo") >= 2):
            time.sleep(0.05)
        assert log.read_text(encoding="utf-8").count("wifi-turbo") >= 2  # o processo saiu e voltou
        assert (tmp_path / "tela-turbo.pid").read_text(encoding="utf-8").strip() == str(p.pid)
        (tmp_path / "tela-vigia.sem-turbo").write_text("", encoding="utf-8")
        assert p.wait(5) == 0
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


def test_agora_nao_abre_um_segundo_escuro(vigia, tmp_path):
    (tmp_path / "tela-escuro.trava").mkdir()
    v = vigia(modo="agora")
    v.proc.wait(5)
    assert v.escureceu() == 0


def test_agora_escurece_uma_vez_e_termina(vigia):
    v = vigia(modo="agora")
    v.proc.wait(5)
    assert "Tela escuro 0 toque cima energia" in v.ler("tela.log")  # pelo PC ninguem apertou volume
    assert not (v.tmp / "tela-escuro.trava").exists()


# ---- a logica pura do Tela.java, no JDK do PC


def executa(cmd, entrada=""):
    """Popen, e nao subprocess.run: o conftest tranca o run em todo teste. O comando nunca cita adb."""
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    saida, erro = p.communicate(entrada, timeout=60)
    return p.returncode, saida.strip(), erro


@pytest.fixture(scope="module")
def java(tmp_path_factory):
    if not (JDK / "javac.exe").exists() or not pathlib.Path("/usr/bin/wslpath").exists():
        pytest.skip("sem o JDK portatil do PC")
    pasta = tmp_path_factory.mktemp("tela", numbered=True)
    # o JDK e do Windows: fonte e classes em pasta que ele enxerga
    win = executa(["/usr/bin/wslpath", "-w", str(pasta)])[1]
    (pasta / "Tela.java").write_bytes(JAVA_FONTE.read_bytes())
    codigo, _, erro = executa([str(JDK / "javac.exe"), "--release", "8", "-Xlint:-options", "-d", win, win + "\Tela.java"])
    assert codigo == 0, erro
    return lambda modo, entrada: executa([str(JDK / "java.exe"), "-cp", win, "Tela", modo], entrada)[1]


def toque(ms_desce, ms_sobe, dedo=1):
    return f"{ms_desce} 3 57 {dedo}\n{ms_desce} 0 0 0\n{ms_sobe} 3 57 -1\n{ms_sobe} 0 0 0\n"


@pytest.mark.parametrize("nome,entrada,dispara", [
    ("dois rapidos", toque(0, 80) + toque(200, 280), True),
    ("com 1 s entre eles, como o Rafael toca", toque(0, 80) + toque(1080, 1160), True),
    ("no limite de 2 s", toque(0, 80) + toque(2080, 2160), True),
    ("um so", toque(0, 80), False),
    ("devagar demais", toque(0, 80) + toque(2081, 2160), False),
    ("primeiro longo (mao, bolso)", toque(0, 501) + toque(700, 780), False),
    ("segundo longo", toque(0, 80) + toque(200, 900), False),
    ("longo no meio zera a conta", toque(0, 80) + toque(200, 900) + toque(1000, 1080), False),
    ("dois dedos juntos", "0 3 57 1\n10 3 57 2\n60 3 57 -1\n70 3 57 -1\n" + toque(200, 280), False),
    ("outros eventos nao contam", "0 3 53 100\n5 1 330 1\n9 0 0 0\n" + toque(10, 90), False),
])
def test_dois_toques(java, nome, entrada, dispara):
    assert bool(java("testa-toques", entrada)) is dispara, nome


def test_tres_toques_disparam_uma_vez_so(java):
    assert java("testa-toques", toque(0, 80) + toque(200, 280) + toque(400, 480)) == "dispara 280"


@pytest.mark.parametrize("saida,motivo", [
    ("mCallState=0\nmCallState=0\nalarmes=0\nmWakefulness=Awake\nisKeyguardShowing=false\n", "null"),
    ("    mCallState=0\n    mCallState=1\nalarmes=0\nmWakefulness=Awake\nisKeyguardShowing=false\n", "chamada"),
    ("mCallState=2\nalarmes=0\nmWakefulness=Awake\nisKeyguardShowing=false\n", "null"),  # ja em ligacao: nao acende so por isso
    ("mCallState=0\nalarmes=1\nmWakefulness=Awake\nisKeyguardShowing=false\n", "alarme"),
    ("mCallState=0\nalarmes=0\nmWakefulness=Dozing\nisKeyguardShowing=true\n", "bloqueou"),
    ("mCallState=0\nalarmes=0\nmWakefulness=Asleep\nisKeyguardShowing=false\n", "dormiu"),
    ("mCallState=1\nalarmes=1\nmWakefulness=Dozing\n", "chamada"),
    ("mCallState=0\nalarmes=2\nmWakefulness=Dozing\n", "alarme"),
    ("", "null"),
    ("alarmes=\n", "null"),
])
def test_vigilancia(java, saida, motivo):
    assert java("testa-vigilancia", saida) == motivo
