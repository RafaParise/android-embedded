"""Testes de scripts/modos.py: jogo ligar/desligar tem que desfazer no MESMO pacote que foi ligado,
nao no pacote padrao/CLI de quem chama 'desligar' (bug real de 30/10, corrigido aqui).

Nao esta em NUVEM.md secao 5 (que exclui reiniciar.py/teste-gravacao.py por agirem direto no
hardware real sem como simular). modos.py usa o mesmo padrao sh()-via-subprocess.run de todo
script ja testado neste projeto (lote-pacotes.py, ajustes-script.py...) e tem RAIZ, redirecionado
pela mesma fixture importa_script -- nao ha nada aqui que exija aparelho de verdade para testar a
logica de salvar/restaurar estado.
"""
import sys
import types

import pytest


def test_jogo_desligar_usa_o_pacote_que_foi_ligado_nao_o_padrao_da_cli(importa_script, monkeypatch):
    """Revisao de 30/10: 'cmd game downscale disable {a.pacote}' usava o pacote da chamada ATUAL
    de 'desligar' (ARENA por padrao), nao o 'pacote' salvo em est['jogo'] quando foi ligado. Ligar
    um jogo != ARENA e desligar sem repetir o nome deixava o downscale de verdade ainda ativo."""
    mod = importa_script("modos.py")
    chamadas = []

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        chamadas.append(c)
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c == "settings get global zen_mode":
            saida = "0"
        elif c == "dumpsys battery":
            saida = "level: 80\ntemperature: 250\nUSB powered: false"
        else:
            saida = ""
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    monkeypatch.setattr(sys, "argv", ["modos.py", "jogo", "ligar", "com.outro.jogo", "--escala", "0.7"])
    mod.main()
    assert "cmd game downscale 0.7 com.outro.jogo" in chamadas

    monkeypatch.setattr(sys, "argv", ["modos.py", "jogo", "desligar"])  # sem repetir o pacote
    mod.main()
    assert "cmd game downscale disable com.outro.jogo" in chamadas
    assert "cmd game downscale disable io.github.rafaparise.arena" not in chamadas


def test_jogo_desligar_sem_estado_salvo_usa_o_padrao(importa_script, monkeypatch):
    """Sem 'ligar' antes (nada em est['jogo']), 'desligar' cai no pacote padrao (ARENA) -- nao crasha."""
    mod = importa_script("modos.py")
    chamadas = []

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        chamadas.append(c)
        if c == "getprop ro.product.model":
            return types.SimpleNamespace(stdout="SM-A125M", stderr="")
        return types.SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["modos.py", "jogo", "desligar"])

    mod.main()  # nao deveria levantar excecao
    assert "cmd game downscale disable io.github.rafaparise.arena" in chamadas


def test_o_estado_dos_modos_vai_para_a_raiz_redirecionada_e_nunca_para_o_repositorio_real(importa_script):
    """Achado em 31/10: ESTADO era constante do modulo e a fixture so troca RAIZ, entao cada rodada de testes regravava o
    diagnostico/modos_estado.json REAL com {} (com o estado perdido, 'desligar' nao volta ao que era)."""
    from conftest import RAIZ as RAIZ_REAL
    real = RAIZ_REAL / "diagnostico" / "modos_estado.json"
    antes = real.read_bytes() if real.exists() else None
    mod = importa_script("modos.py")
    mod.salvar({"x": 1})
    assert (mod.RAIZ / "diagnostico" / "modos_estado.json").exists()
    assert mod.carregar() == {"x": 1}
    assert (real.read_bytes() if real.exists() else None) == antes


class _Aparelho:
    """Aparelho falso: guarda settings e o estado da Economia de dados; registra a ordem das gravacoes."""

    def __init__(self, settings, restrict="disabled"):
        self.settings = dict(settings)
        self.restrict = restrict
        self.log = []

    def run(self, cmd, **kw):
        c = cmd[2].strip()
        self.log.append(c)
        saida = ""
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c.startswith("settings get "):
            _, _, ns, chave = c.split()
            saida = self.settings.get(f"{ns}/{chave}", "null")
        elif c.startswith("settings put "):
            _, _, ns, chave, valor = c.split()
            self.settings[f"{ns}/{chave}"] = valor
        elif c.startswith("settings delete "):
            _, _, ns, chave = c.split()
            self.settings.pop(f"{ns}/{chave}", None)
        elif c == "cmd netpolicy get restrict-background":
            saida = f"Restrict background status: {self.restrict}"
        elif c.startswith("cmd netpolicy set restrict-background "):
            self.restrict = "enabled" if c.endswith("true") else "disabled"
        elif c == "dumpsys battery":
            saida = "level: 80\ntemperature: 250\nUSB powered: false"
        return types.SimpleNamespace(stdout=saida, stderr="")


ANTES = {"secure/accessibility_display_daltonizer": "3", "secure/accessibility_display_daltonizer_enabled": "0",
         "global/low_power": "0", "system/screen_brightness_mode": "0", "system/screen_brightness": "52",
         "system/screen_off_timeout": "1800000"}


def test_economia_ligar_guarda_o_estado_antes_de_mexer_e_liga_tudo(importa_script, monkeypatch):
    mod = importa_script("modos.py")
    ap = _Aparelho(ANTES)
    visto = {}
    original = ap.run

    def run_vigiado(cmd, **kw):
        if cmd[2].startswith("settings put ") and "antes" not in visto:
            visto["antes"] = mod.carregar().get("economia")  # no instante da PRIMEIRA gravacao o estado de antes ja tem de estar no disco
        return original(cmd, **kw)

    monkeypatch.setattr(mod.subprocess, "run", run_vigiado)
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "ligar"])
    mod.main()
    assert visto["antes"]["secure/accessibility_display_daltonizer"] == "3"
    assert visto["antes"]["system/screen_brightness"] == "52"
    assert visto["antes"]["restrict_background"] is False
    s = ap.settings
    assert s["secure/accessibility_display_daltonizer"] == "0" and s["secure/accessibility_display_daltonizer_enabled"] == "1"
    assert s["global/low_power"] == "1" and ap.restrict == "enabled"
    assert s["system/screen_brightness_mode"] == "0" and s["system/screen_brightness"] == "30"
    assert s["system/screen_off_timeout"] == "15000"


def test_economia_nunca_aumenta_o_brilho(importa_script, monkeypatch):
    mod = importa_script("modos.py")
    ap = _Aparelho({**ANTES, "system/screen_brightness": "12"})
    monkeypatch.setattr(mod.subprocess, "run", ap.run)
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "ligar", "--brilho", "30"])
    mod.main()
    assert ap.settings["system/screen_brightness"] == "12"


def test_economia_desligar_restaura_tudo_inclusive_chave_que_nao_existia(importa_script, monkeypatch):
    mod = importa_script("modos.py")
    sem_chave = {k: v for k, v in ANTES.items() if k != "secure/accessibility_display_daltonizer"}  # 'null': a chave nao existia
    ap = _Aparelho(sem_chave)
    monkeypatch.setattr(mod.subprocess, "run", ap.run)
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "ligar"])
    mod.main()
    assert ap.settings["secure/accessibility_display_daltonizer"] == "0"
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "desligar"])
    mod.main()
    assert ap.settings == sem_chave                      # a chave criada pelo modo foi APAGADA, nao virou "null"
    assert ap.restrict == "disabled"
    assert "economia" not in mod.carregar()


def test_economia_desligar_mantem_economia_de_dados_que_ja_estava_ligada(importa_script, monkeypatch):
    mod = importa_script("modos.py")
    ap = _Aparelho(ANTES, restrict="enabled")
    monkeypatch.setattr(mod.subprocess, "run", ap.run)
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "ligar"])
    mod.main()
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "desligar"])
    mod.main()
    assert ap.restrict == "enabled"                      # estava ligada antes: o modo nao a desliga


def test_economia_ligar_duas_vezes_recusa_para_nao_perder_o_estado_original(importa_script, monkeypatch):
    mod = importa_script("modos.py")
    ap = _Aparelho(ANTES)
    monkeypatch.setattr(mod.subprocess, "run", ap.run)
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "ligar"])
    mod.main()
    ja_ligado = dict(ap.settings)
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "ja esta LIGADO" in str(exc.value)
    assert ap.settings == ja_ligado
    assert mod.carregar()["economia"]["system/screen_brightness"] == "52"  # o estado original continua o de antes do 1o ligar


def test_economia_desligar_sem_estado_salvo_volta_ao_padrao_seguro(importa_script, monkeypatch, capsys):
    mod = importa_script("modos.py")
    ap = _Aparelho({**ANTES, "secure/accessibility_display_daltonizer_enabled": "1", "global/low_power": "1"}, restrict="enabled")
    monkeypatch.setattr(mod.subprocess, "run", ap.run)
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "desligar"])
    mod.main()
    assert "nao ha estado salvo" in capsys.readouterr().out
    assert ap.settings["secure/accessibility_display_daltonizer_enabled"] == "0"
    assert ap.settings["global/low_power"] == "0" and ap.restrict == "disabled"


def test_economia_ligar_aborta_sem_guardar_lixo_se_o_adb_cair_na_leitura(importa_script, monkeypatch):
    """Achado ao vivo em 31/10: o ADB piscou no meio do 'ligar'. Resposta que nao e valor de settings (ex.: 'adb.exe: no devices')
    NAO pode virar 'estado de antes': aborta antes de gravar o estado e antes de mudar qualquer coisa."""
    mod = importa_script("modos.py")
    ap = _Aparelho(ANTES)
    original = ap.run

    def adb_caiu(cmd, **kw):
        if cmd[2].startswith("settings get "):
            return types.SimpleNamespace(stdout="adb.exe: no devices/emulators found", stderr="")
        return original(cmd, **kw)

    monkeypatch.setattr(mod.subprocess, "run", adb_caiu)
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "ligar"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "ABORTADO" in str(exc.value) and "Nada foi alterado" in str(exc.value)
    assert "economia" not in mod.carregar()
    assert not any(c.startswith("settings put") for c in ap.log)


def test_economia_valor_estranho_no_estado_salvo_nao_vai_para_o_shell(importa_script, monkeypatch, capsys):
    """O valor guardado volta para o shell do aparelho no 'desligar': so numero passa (nada de ; ou $() ), mesmo com o arquivo adulterado."""
    mod = importa_script("modos.py")
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    ap = _Aparelho({**ANTES, "global/low_power": "1"})
    monkeypatch.setattr(mod.subprocess, "run", ap.run)
    mod.salvar({"economia": {**ANTES, "system/screen_off_timeout": "1; reboot", "restrict_background": False}})
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "desligar"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    assert not any("reboot" in c for c in ap.log)
    assert "valor inesperado" in capsys.readouterr().out
    assert "economia" in mod.carregar()                  # nao voltou por inteiro: o estado fica para tentar de novo


def test_economia_tenta_de_novo_quando_o_adb_perde_uma_gravacao(importa_script, monkeypatch):
    mod = importa_script("modos.py")
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    ap = _Aparelho(ANTES)
    original = ap.run
    descartadas = {"n": 0}

    def perde_a_primeira_gravacao_do_brilho(cmd, **kw):
        if cmd[2].startswith("settings put system screen_brightness ") and descartadas["n"] == 0:
            descartadas["n"] += 1          # como se o cabo piscasse: o comando nao chegou
            return types.SimpleNamespace(stdout="", stderr="")
        return original(cmd, **kw)

    monkeypatch.setattr(mod.subprocess, "run", perde_a_primeira_gravacao_do_brilho)
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "ligar"])
    mod.main()                                            # nao deve sair com erro
    assert descartadas["n"] == 1 and ap.settings["system/screen_brightness"] == "30"


def test_economia_de_dados_tambem_e_conferida_lendo_de_volta(importa_script, monkeypatch, capsys):
    mod = importa_script("modos.py")
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    ap = _Aparelho(ANTES)
    original = ap.run

    def ignora_netpolicy(cmd, **kw):
        if cmd[2].startswith("cmd netpolicy set restrict-background"):
            return types.SimpleNamespace(stdout="", stderr="")
        return original(cmd, **kw)

    monkeypatch.setattr(mod.subprocess, "run", ignora_netpolicy)
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "ligar"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    assert "Economia de dados" in capsys.readouterr().out


def test_economia_avisa_e_sai_com_erro_se_algo_nao_ficou_aplicado(importa_script, monkeypatch, capsys):
    mod = importa_script("modos.py")
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    ap = _Aparelho(ANTES)
    original = ap.run

    def nunca_aplica_low_power(cmd, **kw):
        if cmd[2].startswith("settings put global low_power"):
            return types.SimpleNamespace(stdout="", stderr="")
        return original(cmd, **kw)

    monkeypatch.setattr(mod.subprocess, "run", nunca_aplica_low_power)
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "ligar"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    saida = capsys.readouterr().out
    assert "APLICADO PELA METADE" in saida and "Economia de energia" in saida
    assert mod.carregar()["economia"]["global/low_power"] == "0"      # o estado de antes ficou guardado
    monkeypatch.setattr(mod.subprocess, "run", ap.run)                # aparelho "normal" de novo
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "desligar"])
    mod.main()
    assert ap.settings == ANTES and "economia" not in mod.carregar()


@pytest.mark.parametrize("brilho", ["0", "256", "-5"])
def test_economia_recusa_brilho_fora_da_faixa(importa_script, monkeypatch, brilho):
    mod = importa_script("modos.py")
    ap = _Aparelho(ANTES)
    monkeypatch.setattr(mod.subprocess, "run", ap.run)
    monkeypatch.setattr(sys, "argv", ["modos.py", "economia", "ligar", "--brilho", brilho])
    with pytest.raises(SystemExit):
        mod.main()
    assert not any(c.startswith("settings put") for c in ap.log)


class _AparelhoTv:
    """Aparelho falso para tv/jogo: settings (aceita comandos separados por ';'), wm size e registro de comandos."""

    def __init__(self, settings=None, override=None, zen="0"):
        self.settings = dict(settings or {})
        self.override, self.zen, self.log = override, zen, []

    def run(self, cmd, **kw):
        c = cmd[2].strip()
        self.log.append(c)
        saida = ""
        for parte in (p.strip() for p in c.split(";")):
            if parte == "getprop ro.product.model":
                saida = "SM-A125M"
            elif parte == "wm size":
                saida = "Physical size: 720x1600" + (f"\nOverride size: {self.override}" if self.override else "")
            elif parte == "wm size reset":
                self.override = None
            elif parte.startswith("wm size "):
                self.override = parte.split()[2]
            elif parte == "settings get global zen_mode":
                saida = self.zen
            elif parte.startswith("cmd notification set_dnd "):
                self.zen = {"off": "0", "priority": "1", "none": "2", "alarms": "3"}[parte.split()[3]]
            elif parte.startswith("settings get "):
                _, _, ns, chave = parte.split()
                saida = self.settings.get(f"{ns}/{chave}", "null")
            elif parte.startswith("settings put "):
                _, _, ns, chave, valor = parte.split()
                self.settings[f"{ns}/{chave}"] = valor
            elif parte.startswith("settings delete "):
                _, _, ns, chave = parte.split()
                self.settings.pop(f"{ns}/{chave}", None)
        return types.SimpleNamespace(stdout=saida, stderr="")


TV_ANTES = {"system/accelerometer_rotation": "1", "system/user_rotation": "0", "system/screen_off_timeout": "120000"}


def _roda_modos(mod, monkeypatch, ap, *args):
    monkeypatch.setattr(mod.subprocess, "run", ap.run)
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    monkeypatch.setattr(sys, "argv", ["modos.py", *args])
    mod.main()


def test_tv_ligar_duas_vezes_recusa_e_desligar_volta_ao_original(importa_script, monkeypatch):
    mod = importa_script("modos.py")
    ap = _AparelhoTv(TV_ANTES)
    _roda_modos(mod, monkeypatch, ap, "tv", "ligar")
    with pytest.raises(SystemExit) as exc:
        _roda_modos(mod, monkeypatch, ap, "tv", "ligar", "--res", "1920x1080")
    assert "ja esta LIGADO" in str(exc.value)
    _roda_modos(mod, monkeypatch, ap, "tv", "desligar")
    assert ap.override is None
    assert ap.settings["system/screen_off_timeout"] == "120000"
    assert ap.settings["system/accelerometer_rotation"] == "1"


def test_tv_desligar_restaura_wifi_display_on_que_nao_existia(importa_script, monkeypatch):
    mod = importa_script("modos.py")
    ap = _AparelhoTv(TV_ANTES)  # global/wifi_display_on nao existe
    _roda_modos(mod, monkeypatch, ap, "tv", "ligar")
    assert ap.settings["global/wifi_display_on"] == "1"
    _roda_modos(mod, monkeypatch, ap, "tv", "desligar")
    assert "global/wifi_display_on" not in ap.settings


def test_tv_desligar_restaura_wifi_display_on_com_valor_antigo(importa_script, monkeypatch):
    mod = importa_script("modos.py")
    ap = _AparelhoTv(dict(TV_ANTES, **{"global/wifi_display_on": "0"}))
    _roda_modos(mod, monkeypatch, ap, "tv", "ligar")
    _roda_modos(mod, monkeypatch, ap, "tv", "desligar")
    assert ap.settings["global/wifi_display_on"] == "0"


def test_tv_ligar_grava_o_estado_antes_de_mudar_qualquer_ajuste(importa_script, monkeypatch):
    mod = importa_script("modos.py")
    ap = _AparelhoTv(TV_ANTES)
    visto = []
    original = ap.run

    def vigiado(cmd, **kw):
        if cmd[2].startswith(("wm size 1", "wm size 7", "settings put")):
            visto.append("tv" in mod.carregar())
        return original(cmd, **kw)

    ap.run = vigiado
    _roda_modos(mod, monkeypatch, ap, "tv", "ligar")
    assert visto and all(visto)


def test_tv_desligar_sem_estado_nao_mexe_em_tempo_de_tela_nem_rotacao(importa_script, monkeypatch, capsys):
    mod = importa_script("modos.py")
    ap = _AparelhoTv(TV_ANTES)
    _roda_modos(mod, monkeypatch, ap, "tv", "desligar")
    assert ap.settings == TV_ANTES
    assert not any(c.startswith(("settings put", "wm size")) for c in ap.log)
    assert "nao ha estado" in capsys.readouterr().out


def test_jogo_ligar_duas_vezes_recusa_e_nao_perde_o_zen_original(importa_script, monkeypatch):
    mod = importa_script("modos.py")
    ap = _AparelhoTv(zen="0")
    _roda_modos(mod, monkeypatch, ap, "jogo", "ligar")
    assert ap.zen == "1"
    with pytest.raises(SystemExit) as exc:
        _roda_modos(mod, monkeypatch, ap, "jogo", "ligar")
    assert "ja esta LIGADO" in str(exc.value)
    _roda_modos(mod, monkeypatch, ap, "jogo", "desligar")
    assert ap.zen == "0"


def test_jogo_desligar_sem_estado_roda_o_downscale_disable_do_arena(importa_script, monkeypatch):
    mod = importa_script("modos.py")
    ap = _AparelhoTv()
    _roda_modos(mod, monkeypatch, ap, "jogo", "desligar")
    assert "cmd game downscale disable io.github.rafaparise.arena" in ap.log
