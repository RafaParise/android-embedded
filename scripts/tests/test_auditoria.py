"""Testes de scripts/auditoria.py: so leitura (11 secoes de relatorio), nunca escreve.

pm list packages/-d/-f todos vazios: todo app vira "ausente/fora do aparelho" (AVISO/FALHA
no relatorio, nunca crash) e evita ter que fingir dumpsys package/versionName para as ~24
entradas de FOSS (o loop pula todas com 'if p not in todos: continue', sem chamar adb por
pacote). lotes() e dashcam() importam lote-pacotes.py pela RAIZ isolada: precisa copiar o
arquivo, igual ao protegidos() do inventario.py. O ping de rede() responde "PING" de primeira,
entao o retry com sleep(10) nunca entra em jogo (nao precisa mockar time.sleep aqui).
"""
import shutil
import sys
import types

import pytest

from conftest import SCRIPTS

ESCRITAS = ("pm disable", "pm enable", "pm grant", "pm revoke", "settings put", "sm partition",
            "device_config put", "cmd appops set")

EXATOS = {
    "getprop ro.product.model": "SM-A125M",
    "getprop sys.boot_completed": "1",
    "dumpsys battery": "level: 80\n  AC powered: true",
    "uptime | sed 's/,  load.*//'": " 12:00:00 up 1 day",
    "sm list-volumes all": "",  # sem cartao: nenhum private:/public:
    "pm list packages": "",
    "pm list packages -d": "",
    "pm list packages -f": "",
    "sm get-primary-storage-uuid": "null",
    "df -h /data | tail -1": "/dev/x 50G 30G 20G 60% /data",
    "settings get global default_install_location": "1",
    "device_config get activity_manager max_phantom_processes": "2147483647",
    "cmd appops get com.android.vending RUN_IN_BACKGROUND": "RUN_IN_BACKGROUND: ignore",
    "cmd appops get com.microsoft.teams RUN_IN_BACKGROUND": "RUN_IN_BACKGROUND: ignore",
    "cmd appops get org.videolan.vlc MANAGE_EXTERNAL_STORAGE": "MANAGE_EXTERNAL_STORAGE: allow",
    "cmd appops get com.junkfood.seal MANAGE_EXTERNAL_STORAGE": "MANAGE_EXTERNAL_STORAGE: allow",
    "grep -E 'MemAvailable|SwapFree' /proc/meminfo": "MemAvailable: 1000000 kB\nSwapFree: 3000000 kB",
    "ime list -s": "helium314.keyboard/.latin.LatinIME",
    "settings get secure default_input_method": "helium314.keyboard/.latin.LatinIME",
    "settings get global private_dns_mode": "opportunistic",
    "settings get global captive_portal_mode": "1",
    "settings get global captive_portal_detection_enabled": "1",
    "ping -c1 -W4 google.com 2>&1 | head -1": "PING google.com",
    "ping -c1 -W4 packages-cf.termux.dev 2>&1 | head -1": "PING packages-cf.termux.dev",
    "ping -c1 -W4 www.youtube.com 2>&1 | head -1": "PING www.youtube.com",
    "cmd wifi status | head -3": "Wifi is enabled",
    "cmd wifi list-networks": "",
    "dumpsys deviceidle whitelist": "",
    "settings get global force_resizable_activities": "1",
    "settings get global enable_freeform_support": "1",
    "dumpsys package net.sourceforge.opencamera | grep -E 'android.permission.(CAMERA|RECORD_AUDIO):'": "",
    "dumpsys diskstats": "",
    "grep -c 'c2.mtk.avc.encoder' /vendor/etc/media_codecs_c2.xml": "0",
    "settings get global adb_enabled": "1",
    "settings get global development_settings_enabled": "1",
    "settings get global verifier_verify_adb_installs": "1",
    "dumpsys alarm | grep -c org.fossify.clock": "0",
    "cmd role get-role-holders android.app.role.SMS": "",
    "cmd role get-role-holders android.app.role.BROWSER": "",
    "cmd role get-role-holders android.app.role.HOME": "",
    "cmd role get-role-holders android.app.role.DIALER": "",
}


def _fake_run(cmd, **kw):
    if len(cmd) == 2 and cmd[1] == "devices":
        return types.SimpleNamespace(stdout="List of devices attached\nABC\tdevice\n", stderr="")
    c = cmd[2].strip()
    if c in EXATOS:
        return types.SimpleNamespace(stdout=EXATOS[c], stderr="")
    if c.startswith(ESCRITAS):
        raise AssertionError(f"auditoria.py e so leitura, nao deveria chamar: {c!r}")
    if c.startswith("settings get"):  # as 17 chaves de AJUSTES: valor exato nao importa para o smoke test
        return types.SimpleNamespace(stdout="null", stderr="")
    raise AssertionError(f"comando nao mapeado no fake: {c!r}")


def test_roda_as_11_secoes_sem_crash_e_isola_o_relatorio(importa_script, monkeypatch, capsys):
    mod = importa_script("auditoria.py", copiar_lotes_json=True)
    shutil.copy(SCRIPTS / "lote-pacotes.py", mod.RAIZ / "scripts" / "lote-pacotes.py")
    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    monkeypatch.setattr(sys, "argv", ["auditoria.py"])

    with pytest.raises(SystemExit) as exc:
        mod.main()

    saida = capsys.readouterr().out
    assert "Resumo: OK=" in saida
    for secao in ("Aparelho", "Armazenamento", "Lotes", "Essenciais", "Papeis e teclado", "Rede",
                  "Ajustes do script", "Apps de codigo aberto", "Dashcam", "Depuracao e privacidade"):
        assert secao in saida
    relatorios = list((mod.RAIZ / "diagnostico").glob("*/auditoria.md"))
    assert len(relatorios) == 1
    assert exc.value.code in (0, 1)  # 1 e esperado aqui: todos os pacotes "ausentes" vira FALHA em Essenciais


def test_papeis_mostra_o_esperado_quando_o_dono_atual_esta_errado_nao_so_quando_vazio(importa_script, monkeypatch, capsys):
    """Revisao de 30/10: por precedencia de operador, 'atual or "SEM DONO" + f"..."' so mostrava
    "(esperado X)" quando atual era vazio (SEM DONO); quando atual era um valor ERRADO (caso real
    de FALHA, ex.: role voltou pro dialer da Samsung numa OTA), a mensagem omitia o que era
    esperado. Corrigido; este teste trava o caso "errado, nao vazio"."""
    mod = importa_script("auditoria.py", copiar_lotes_json=True)
    shutil.copy(SCRIPTS / "lote-pacotes.py", mod.RAIZ / "scripts" / "lote-pacotes.py")
    exatos_com_dialer_errado = dict(EXATOS, **{
        "cmd role get-role-holders android.app.role.DIALER": "com.samsung.android.dialer",
    })

    def fake_run(cmd, **kw):
        if len(cmd) == 2 and cmd[1] == "devices":
            return types.SimpleNamespace(stdout="List of devices attached\nABC\tdevice\n", stderr="")
        c = cmd[2].strip()
        if c in exatos_com_dialer_errado:
            return types.SimpleNamespace(stdout=exatos_com_dialer_errado[c], stderr="")
        if c.startswith(ESCRITAS):
            raise AssertionError(f"auditoria.py e so leitura, nao deveria chamar: {c!r}")
        if c.startswith("settings get"):
            return types.SimpleNamespace(stdout="null", stderr="")
        raise AssertionError(f"comando nao mapeado no fake: {c!r}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["auditoria.py"])

    with pytest.raises(SystemExit):
        mod.main()

    saida = capsys.readouterr().out
    assert "[FALHA] DIALER: com.samsung.android.dialer (esperado org.fossify.phone)" in saida


def test_aborta_se_aparelho_offline(importa_script, monkeypatch):
    mod = importa_script("auditoria.py")

    def fake_run(cmd, **kw):
        if len(cmd) == 2 and cmd[1] == "devices":
            return types.SimpleNamespace(stdout="List of devices attached\n", stderr="")
        raise AssertionError(f"nao deveria chegar a ler nada sem aparelho: {cmd!r}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["auditoria.py"])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "offline" in str(exc.value)


def test_df_sem_resposta_nao_vira_ok_em_data(importa_script, monkeypatch, capsys):
    mod = importa_script("auditoria.py", copiar_lotes_json=True)
    shutil.copy(SCRIPTS / "lote-pacotes.py", mod.RAIZ / "scripts" / "lote-pacotes.py")
    exatos = dict(EXATOS, **{"df -h /data | tail -1": ""})  # df sem resposta: antes saia "[OK] /data -1% usado"

    def fake_run(cmd, **kw):
        if len(cmd) == 2 and cmd[1] == "devices":
            return types.SimpleNamespace(stdout="List of devices attached\nABC\tdevice\n", stderr="")
        c = cmd[2].strip()
        if c in exatos:
            return types.SimpleNamespace(stdout=exatos[c], stderr="")
        if c.startswith("settings get"):
            return types.SimpleNamespace(stdout="null", stderr="")
        raise AssertionError(f"comando nao mapeado no fake: {c!r}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["auditoria.py"])
    with pytest.raises(SystemExit):
        mod.main()
    linhas = [l for l in capsys.readouterr().out.splitlines() if "/data" in l and "nao consegui ler o df" in l]
    assert linhas and "AVISO" in linhas[0] and "OK" not in linhas[0].split("/data")[0]
    assert not any("-1%" in l for l in linhas)
