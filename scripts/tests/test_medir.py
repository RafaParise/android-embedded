"""Testes de scripts/medir.py: a trava real e 'stay_on_while_plugged_in' voltar ao valor
original mesmo se a medicao falhar no meio (try/finally do proprio script) — o resto (CPU,
memoria, fluidez) e numero de diagnostico, nao caminho de seguranca. --rapido evita ter que
simular abertura a fria de 17 apps e a rolagem da tela.
"""
import sys
import types

import pytest

RESPOSTAS = {
    "getprop ro.product.model": "SM-A125M",
    "settings get global stay_on_while_plugged_in": "0",
    "uptime | sed 's/,.*//'": " 12:00:00 up 1 day",
    "dumpsys battery | grep -E 'level|temperature' | tr -s ' ' | tr '\\n' ' '": "level: 80 temperature: 300 ",
    "input keyevent KEYCODE_WAKEUP": "",
    "wm dismiss-keyguard": "",
    "dumpsys window | grep -m1 mCurrentFocus": "mCurrentFocus=Window{abc u0 com.android.settings}",
    "input keyevent KEYCODE_HOME": "",
    "am kill-all": "",
    "cat /proc/meminfo": ("MemAvailable: 1000000 kB\nMemFree: 500000 kB\nCached: 300000 kB\n"
                           "SwapTotal: 4000000 kB\nSwapFree: 3000000 kB\n"),
    "cat /sys/block/zram0/mm_stat": "0 0 0 0 0 0 0",
    "dumpsys meminfo | grep -m1 'Free RAM:'": "",
    "dumpsys meminfo | grep -m1 'Used RAM:'": "",
    "ps -A | wc -l": "120",
    "ps -A -o USER | grep -c '^u0_a'": "30",
    "dumpsys activity services | grep -c 'ServiceRecord{'": "8",
    "cat /proc/pressure/cpu": "some avg10=0.00 avg60=1.00 avg300=0.00 total=0\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0",
    "cat /proc/pressure/memory": "some avg10=0.00 avg60=0.20 avg300=0.00 total=0\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0",
    "cat /proc/pressure/io": "some avg10=0.00 avg60=0.10 avg300=0.00 total=0\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0",
    "df -k /data | tail -n 1": "/dev/x 50000000 30000000 20000000 60% /data",
    "pm list packages -e | wc -l": "260",
    "pm list packages -d | wc -l": "155",
    "pm list packages -s -e | wc -l": "200",
    "pm list packages -3 | wc -l": "60",
    "dumpsys power | grep -c 'PARTIAL_WAKE_LOCK'": "0",
    "dumpsys jobscheduler | grep -c 'JOB #'": "2",
    "head -n1 /proc/stat; top -b -n 2 -d 15 -m 8; head -n1 /proc/stat": "cpu  100 0 50 1000 0 0 0 0\ncpu  200 0 100 1100 0 0 0 0",
}


def test_restaura_stay_on_mesmo_se_algo_falhar_no_meio(importa_script, monkeypatch):
    mod = importa_script("medir.py")
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    chamadas_put = []

    def fake_run(cmd, **kw):
        c = cmd[2]
        if c.startswith("settings put global stay_on_while_plugged_in"):
            chamadas_put.append(c)
            return types.SimpleNamespace(stdout="", stderr="")
        if c == "am kill-all":
            raise RuntimeError("falha simulada no meio da medicao")
        if c not in RESPOSTAS:
            raise AssertionError(f"comando nao mapeado no fake: {c!r}")
        return types.SimpleNamespace(stdout=RESPOSTAS[c], stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["medir.py", "--rotulo", "teste", "--rapido"])

    with pytest.raises(RuntimeError):
        mod.main()

    assert chamadas_put == ["settings put global stay_on_while_plugged_in 3",
                             "settings put global stay_on_while_plugged_in 0"]


def test_rapido_grava_json_isolado(importa_script, monkeypatch):
    mod = importa_script("medir.py")
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    def fake_run(cmd, **kw):
        c = cmd[2]
        if c.startswith("settings put"):
            return types.SimpleNamespace(stdout="", stderr="")
        if c not in RESPOSTAS:
            raise AssertionError(f"comando nao mapeado no fake: {c!r}")
        return types.SimpleNamespace(stdout=RESPOSTAS[c], stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["medir.py", "--rotulo", "teste", "--rapido"])

    mod.main()

    arquivos = list((mod.RAIZ / "diagnostico").glob("*/medicao-teste.json"))
    assert len(arquivos) == 1


def test_apps_medidos_nao_incluem_termux(importa_script):
    # force-stop no Termux mataria o guarda da saida, o sshd e o laco do Termux:Boot (aparelho1-0)
    mod = importa_script("medir.py")
    assert all(pkg != "com.termux" for _, pkg in mod.APPS)


def _grava_medicao(tmp_path, nome, valores):
    import json
    arq = tmp_path / nome
    arq.write_text(json.dumps({"rotulo": nome, "quando": "x", "psi": valores,
                               "cpu": {"maiores": []}}), encoding="utf-8")
    return str(arq)


def test_comparar_base_zero_nao_vira_igual(importa_script, tmp_path, capsys):
    mod = importa_script("medir.py")
    a = _grava_medicao(tmp_path, "a.json", {"mem_some_avg60": 0.0})
    b = _grava_medicao(tmp_path, "b.json", {"mem_some_avg60": 12.5})
    mod.comparar(a, b)
    linha = [l for l in capsys.readouterr().out.splitlines() if "mem_some_avg60" in l][0]
    assert "PIOR" in linha


def test_comparar_base_zero_com_ruido_pequeno_fica_igual(importa_script, tmp_path, capsys):
    mod = importa_script("medir.py")
    a = _grava_medicao(tmp_path, "a.json", {"mem_some_avg60": 0.0})
    b = _grava_medicao(tmp_path, "b.json", {"mem_some_avg60": 0.13})
    mod.comparar(a, b)
    linha = [l for l in capsys.readouterr().out.splitlines() if "mem_some_avg60" in l][0]
    assert "igual" in linha
