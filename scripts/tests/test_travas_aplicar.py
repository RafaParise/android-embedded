"""Travas que os testes da nuvem nao cobriam (achadas por mutacao em 30/10/2026): o caminho --aplicar do lote-pacotes
(so 'pm disable-user --user 0', nunca uninstall; portoes de lote, aparelho e bateria), o UUID e o tamanho do cartao no
sd-adotar, a bateria ilegivel e o aparelho errado no medir. Tudo com adb falso: nada toca o aparelho (o conftest.py
reprova qualquer subprocess.run que o proprio teste nao tenha substituido)."""
import json
import runpy
import subprocess
import sys
import types

import pytest

from conftest import SCRIPTS

LOTE = {"T1": {"aplicavel": True, "descricao": "lote de teste", "pacotes": ["com.exemplo.a", "com.exemplo.b"]}}


class AdbFalso:
    """Celular de mentira para o lote-pacotes: responde as leituras e guarda os comandos que MUDAM algo."""

    def __init__(self, modelo="SM-A125M", bateria="level: 80\n  status: 2", desativados=()):
        self.modelo, self.bateria = modelo, bateria
        self.todos = {"com.exemplo.a", "com.exemplo.b"}
        self.off = set(desativados)
        self.escritas = []

    def run(self, cmd, **kw):
        c = cmd[2].strip()
        if c == "getprop ro.product.model":
            saida = self.modelo
        elif c == "pm list packages":
            saida = "\n".join(f"package:{p}" for p in sorted(self.todos))
        elif c == "pm list packages -d":
            saida = "\n".join(f"package:{p}" for p in sorted(self.off))
        elif c == "dumpsys battery":
            saida = self.bateria
        elif c.startswith("pm disable-user --user 0 "):
            self.escritas.append(c)
            self.off.add(c.rsplit(" ", 1)[1])
            saida = "ok"
        elif c.startswith("pm enable "):
            self.escritas.append(c)
            self.off.discard(c.rsplit(" ", 1)[1])
            saida = "ok"
        else:
            raise AssertionError(f"comando nao mapeado no fake: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")


def _lote(importa_script, monkeypatch, adb, *args, lotes=LOTE):
    lp = importa_script("lote-pacotes.py")
    (lp.RAIZ / "scripts" / "lotes-bloatware.json").write_text(json.dumps(lotes), encoding="utf-8")
    monkeypatch.setattr(lp.subprocess, "run", adb.run)
    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", *args])
    return lp


def test_aplicar_so_usa_disable_user_e_grava_o_registro_para_desfazer(importa_script, monkeypatch):
    adb = AdbFalso()
    lp = _lote(importa_script, monkeypatch, adb, "T1", "--aplicar")
    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert exc.value.code == 0
    assert adb.escritas == ["pm disable-user --user 0 com.exemplo.a", "pm disable-user --user 0 com.exemplo.b"]
    assert not any("uninstall" in c or "pm clear" in c for c in adb.escritas)
    assert list((lp.RAIZ / "diagnostico").glob("*/lote_T1_antes.txt"))


def test_restaurar_so_usa_pm_enable(importa_script, monkeypatch):
    adb = AdbFalso(desativados=("com.exemplo.a",))
    lp = _lote(importa_script, monkeypatch, adb, "T1", "--restaurar")
    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert exc.value.code == 0
    assert adb.escritas == ["pm enable com.exemplo.a"]


def test_lote_nao_aplicavel_aborta_antes_de_mexer_em_qualquer_pacote(importa_script, monkeypatch):
    adb = AdbFalso()
    lotes = {"T1": {"aplicavel": False, "descricao": "x", "pacotes": ["com.exemplo.a"]}}
    lp = _lote(importa_script, monkeypatch, adb, "T1", "--aplicar", lotes=lotes)
    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert "nao aplicavel" in str(exc.value)
    assert adb.escritas == []


def test_aparelho_inesperado_aborta_antes_de_mexer_em_qualquer_pacote(importa_script, monkeypatch):
    adb = AdbFalso(modelo="SM-G960F")
    lp = _lote(importa_script, monkeypatch, adb, "T1", "--aplicar")
    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert "aparelho inesperado" in str(exc.value)
    assert adb.escritas == []


@pytest.mark.parametrize("bateria, motivo", [
    ("level: 2\n  status: 2", "abaixo de 3%"),              # 2% carregando
    ("level: 90\n  status: 3", "sem carregar"),             # 90% descarregando (status 3)
    ("", "nao consegui ler a bateria"),                     # aparelho offline / saida vazia
])
def test_bateria_baixa_sem_carregar_ou_ilegivel_aborta_antes_de_mexer(importa_script, monkeypatch, bateria, motivo):
    adb = AdbFalso(bateria=bateria)
    lp = _lote(importa_script, monkeypatch, adb, "T1", "--aplicar")
    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert "ABORTADO" in str(exc.value) and motivo in str(exc.value)
    assert adb.escritas == []


CAMINHO_SD = SCRIPTS / "sd-adotar.py"


def _roda_sd(monkeypatch, argv, respostas):
    """sd-adotar.py roda tudo no nivel do modulo: runpy com sys.argv e subprocess.run falsos. Comando fora de 'respostas'
    (inclusive 'sm partition') reprova o teste: o abort tem de vir ANTES dele."""
    monkeypatch.setattr(sys, "argv", ["sd-adotar.py", *argv])

    def fake_run(cmd, **kw):
        c = cmd[2]
        for chave, saida in respostas.items():
            if chave in c:
                return types.SimpleNamespace(stdout=saida, stderr="")
        raise AssertionError(f"comando nao mapeado no fake (o abort devia vir antes): {c!r}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(CAMINHO_SD), run_name="__main__")
    return str(exc.value)


SD_BOM = {
    "sm list-disks": "disk:179,96",
    "sm list-volumes all": "public:179,97 mounted 1A2B-3C4D",
    "DiskInfo": 'DiskInfo{disk:179,96}:\n  size=512000000000 flags=4 label="SD-Card"',
    "dumpsys battery": "  level: 80\n  USB powered: true",
}


def test_sd_uuid_diferente_do_autorizado_aborta(monkeypatch):
    resp = dict(SD_BOM, **{"sm list-volumes all": "public:179,97 mounted 9999-9999"})
    msg = _roda_sd(monkeypatch, ["--modo", "public", "--uuid", "1A2B-3C4D", "--confirmo-apagar"], resp)
    assert "ABORTADO" in msg and "nao esta montado" in msg


def test_sd_disco_pequeno_ou_sem_flag_sd_aborta(monkeypatch):
    resp = dict(SD_BOM, DiskInfo='DiskInfo{disk:179,96}:\n  size=64000000000 flags=4 label="USB-Stick"')
    msg = _roda_sd(monkeypatch, ["--modo", "public", "--uuid", "1A2B-3C4D", "--confirmo-apagar"], resp)
    assert "ABORTADO" in msg and "nao parece o cartao" in msg


def test_sd_disco_grande_sem_flag_sd_aborta(monkeypatch):
    """512 GB mas sem 'SD' no DiskInfo (pendrive grande): so a condicao de SD pode barrar."""
    resp = dict(SD_BOM, DiskInfo='DiskInfo{disk:179,96}:\n  size=512000000000 flags=4 label="USB-Stick"')
    msg = _roda_sd(monkeypatch, ["--modo", "public", "--uuid", "1A2B-3C4D", "--confirmo-apagar"], resp)
    assert "ABORTADO" in msg and "nao parece o cartao" in msg


def test_sd_bateria_ilegivel_aborta(monkeypatch):
    resp = dict(SD_BOM, **{"dumpsys battery": ""})
    msg = _roda_sd(monkeypatch, ["--modo", "public", "--uuid", "1A2B-3C4D", "--confirmo-apagar"], resp)
    assert "ABORTADO" in msg and "bateria" in msg


def test_medir_aborta_em_aparelho_inesperado(importa_script, monkeypatch):
    mod = importa_script("medir.py")
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)

    def fake_run(cmd, **kw):
        if cmd[2] == "getprop ro.product.model":
            return types.SimpleNamespace(stdout="SM-G960F", stderr="")
        raise AssertionError(f"nao deveria ler mais nada num aparelho errado: {cmd[2]!r}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["medir.py", "--rotulo", "t", "--rapido"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "ABORTADO" in str(exc.value)
