"""Teste de scripts/teste-fumaca.py: smoke test, nao comportamental completo.

Interage com o aparelho de verdade (abre apps, tecla HOME, abre paginas das Configuracoes)
mas nada e persistente — e exatamente o motivo de nao ter uma trava --aplicar para testar,
diferente de lote-pacotes/ajustes-script/privacidade/sd-adotar. 'pm list packages -e' vazio
pula o loop dos 28 apps (nenhum 'pkg not in ativos'); as 4 paginas de Configuracoes sem
ESPERADO_SEM (Bateria, Apps, Contas, Teclados) sempre rodam, por isso ainda precisam de fake.
"""
import sys
import types

import pytest

EXATOS = {
    "getprop ro.product.model": "SM-A125M",
    "am get-started-user-state 0": "RUNNING_UNLOCKED",
    "input keyevent KEYCODE_WAKEUP": "",
    "wm dismiss-keyguard": "",
    "dumpsys window | grep -m1 mCurrentFocus": "mCurrentFocus=Window{abc u0 com.android.settings}",
    "pm list packages -e": "",
    "logcat -c": "",
    "am start -f 0x10008000 -a android.settings.BATTERY_SAVER_SETTINGS": "",
    "am start -f 0x10008000 -a android.settings.APPLICATION_SETTINGS": "",
    "am start -f 0x10008000 -a android.settings.SYNC_SETTINGS": "",
    "am start -f 0x10008000 -a android.settings.INPUT_METHOD_SETTINGS": "",
    "dumpsys activity activities | grep -m1 -E 'topResumedActivity|mResumedActivity'":
        "topResumedActivity=ActivityRecord{abc u0 com.android.settings/.Settings t1}",
    "logcat -d -b crash | grep -E 'Process:|>>> '": "",
    "input keyevent KEYCODE_HOME": "",
    "cmd package resolve-activity --brief -a android.media.action.STILL_IMAGE_CAMERA": "",
    "cmd package resolve-activity --brief -a android.intent.action.VIEW -d geo:-23.5,-46.6": "",
    "cmd package resolve-activity --brief -a android.intent.action.VIEW -t image/jpeg -d file:///sdcard/x.jpg": "",
    "settings get secure default_input_method": "",
    "grep -E 'MemAvailable|SwapFree' /proc/meminfo": "MemAvailable: 1000000 kB\nSwapFree: 3000000 kB",
}
ESCRITAS = ("pm disable", "pm enable", "pm grant", "pm revoke", "settings put",
            "sm partition", "device_config put", "cmd appops set")


def test_rapido_sem_apps_ativos_nao_escreve_e_sai_ok(importa_script, monkeypatch, capsys):
    mod = importa_script("teste-fumaca.py")
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    chamados = []

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        chamados.append(c)
        if c in EXATOS:
            return types.SimpleNamespace(stdout=EXATOS[c], stderr="")
        raise AssertionError(f"comando nao mapeado no fake: {c!r}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["teste-fumaca.py"])

    with pytest.raises(SystemExit) as exc:
        mod.main()

    assert exc.value.code == 0
    saida = capsys.readouterr().out
    assert "RESULTADO: tudo ok" in saida
    escritas = [c for c in chamados if c.startswith(ESCRITAS)]
    assert chamados and not escritas, f"teste-fumaca.py nao deveria mudar nada persistente: {escritas!r}"


def test_aborta_se_tela_travada(importa_script, monkeypatch):
    mod = importa_script("teste-fumaca.py")
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if c == "getprop ro.product.model":
            return types.SimpleNamespace(stdout="SM-A125M", stderr="")
        if c == "am get-started-user-state 0":
            return types.SimpleNamespace(stdout="RUNNING_UNLOCKED", stderr="")
        if c in ("input keyevent KEYCODE_WAKEUP", "wm dismiss-keyguard"):
            return types.SimpleNamespace(stdout="", stderr="")
        if c == "dumpsys window | grep -m1 mCurrentFocus":
            return types.SimpleNamespace(stdout="mCurrentFocus=Window{abc u0 com.android.Keyguard}", stderr="")
        raise AssertionError(f"nao deveria chegar a abrir nada com a tela travada: {c!r}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["teste-fumaca.py"])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "TRAVADO" in str(exc.value)
