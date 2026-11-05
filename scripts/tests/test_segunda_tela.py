"""Testes do segunda-tela.py com adb, tailscale, scrcpy e sc FALSOS (nada abre e nenhum aparelho e tocado)."""
import importlib.util
import json
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "segunda-tela.py"


class R:
    def __init__(self, rc=0, out=""):
        self.returncode, self.stdout, self.stderr = rc, out, ""


@pytest.fixture
def m(tmp_path):
    spec = importlib.util.spec_from_file_location("segunda_tela", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    e = {"cabo": True, "tcp": False, "sunshine": None, "chamadas": []}
    mod.estado = e

    def falso(cmd, **kw):
        e["chamadas"].append(cmd)
        if cmd[:2] == ["tailscale", "status"]:
            return R(0, json.dumps({"Peer": {"x": {"HostName": "samsung-a12", "TailscaleIPs": ["100.99.1.2"]}}}))
        if cmd[:2] == ["adb", "devices"]:
            ls = ["List of devices attached"] + (["RQ8\tdevice"] if e["cabo"] else []) + (["100.99.1.2:5555\tdevice"] if e["tcp"] else [])
            return R(0, "\n".join(ls) + "\n")
        if cmd[:2] == ["adb", "connect"]:
            e["tcp"] = True
            return R(0, "connected")
        if cmd[:2] == ["adb", "disconnect"]:
            e["tcp"] = False
            return R(0, "")
        if cmd[-2:] == ["wm", "size"]:
            return R(0, "Physical size: 720x1600")
        if cmd[:2] == ["sc", "query"]:
            if e["sunshine"] is None:
                return R(1060, "nao existe")
            return R(0, "STATE: 4 RUNNING" if e["sunshine"] else "STATE: 1 STOPPED")
        return R(0, "")
    mod._executa = falso
    mod.scrcpy = lambda: "scrcpy.exe"
    mod.tamanho_monitor = lambda: (1440, 900)
    mod.MARCA = tmp_path / "preencher.marca"
    mod.INTERVALO = 0.01
    mod.onde_esta = lambda titulo: None  # sem janela real: a vigia nao faz nada nos testes antigos
    mod.monitores = lambda: [
        {"nome": "DISPLAY1", "x": 0, "y": 0, "w": 1440, "h": 900, "principal": True, "tv": False, "virtual": False},
        {"nome": "DISPLAY8", "x": 1440, "y": 0, "w": 1920, "h": 1080, "principal": False, "tv": True, "virtual": False}]
    return mod


def scrcpys(m):
    return [c for c in m.estado["chamadas"] if c[0] == "scrcpy.exe"]


def test_celular_pelo_cabo(m):
    assert m.main(["celular"]) == 0
    (c,) = scrcpys(m)
    assert c[1:3] == ["-s", "RQ8"] and "--stay-awake" in c


def test_nunca_apaga_a_tela_do_celular(m):
    m.main(["celular"])
    m.main(["extra"])
    for c in scrcpys(m):
        assert not [a for a in c if "turn-screen-off" in a or a == "-S"]


def test_sem_cabo_vai_pela_tailscale_e_solta(m):
    m.estado["cabo"] = False
    assert m.main(["celular", "--leve"]) == 0
    (c,) = scrcpys(m)
    assert c[1:3] == ["-s", "100.99.1.2:5555"] and "--video-bit-rate=2M" in c and "--stay-awake" not in c
    assert m.estado["chamadas"][-1] == ["adb", "disconnect", "100.99.1.2:5555"]


def test_extra_cria_tela_nova_com_app(m):
    assert m.main(["extra", "--app", "org.fossify.notes"]) == 0
    (c,) = scrcpys(m)
    assert "--new-display=1440x900/160" in c and "--start-app=org.fossify.notes" in c


def test_extra_padrao_abre_o_navegador(m):
    m.main(["extra"])
    assert "--start-app=org.fossify.notes" in scrcpys(m)[0]  # o Fennec fica preto na tela virtual (05/11)


@pytest.mark.parametrize("ruim", ["a;b", "x y", "../z", ""])
def test_app_com_nome_estranho_e_recusado(m, ruim):
    assert m.main(["extra", "--app", ruim]) == 2
    assert not scrcpys(m)


def test_pc_sem_sunshine_manda_instalar(m, capsys):
    assert m.main(["pc"]) == 2
    assert "segunda-tela-instalar.cmd" in capsys.readouterr().out


def test_pc_liga_o_sunshine_parado(m):
    m.estado["sunshine"] = False
    assert m.main(["pc"]) == 0
    assert ["sc", "start", "SunshineService"] in m.estado["chamadas"]


def test_sem_conexao_nao_abre(m):
    m.estado["cabo"] = False

    antigo = m._executa

    def recusa(cmd, **kw):
        if cmd[:2] == ["adb", "connect"]:
            m.estado["chamadas"].append(cmd)
            return R(1, "failed")
        return antigo(cmd, **kw)
    m._executa = recusa
    assert m.main(["celular"]) == 1
    assert not scrcpys(m)


def test_menu_tela_extra_pergunta_o_app(m, monkeypatch):
    respostas = iter(["2", "4"])
    monkeypatch.setattr("builtins.input", lambda *_: next(respostas))
    chamado = {}
    monkeypatch.setattr(m, "extra", lambda app, leve: chamado.setdefault("app", app) and 0)
    m.menu()
    assert chamado["app"] == "com.termux"


def test_escolha_invalida_cai_no_padrao(m, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "99")
    assert m.escolhe_app() == m.APP_PADRAO == "org.fossify.notes"


def wms(m):
    return [c[4:] for c in m.estado["chamadas"] if c[:1] == ["adb"] and c[3:5] == ["shell", "wm"]]


def test_forma_para_16x9_e_16x10():
    import importlib.util as iu
    spec = iu.spec_from_file_location("st", SCRIPT)
    mod = iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.forma_para((720, 1600), 1920, 1080) == (720, 1280)
    assert mod.forma_para((720, 1600), 1440, 900) == (720, 1152)
    assert mod.forma_para((720, 1600), 1080, 1920) == (720, 1280)  # monitor em pe: mesma proporcao
    assert mod.forma_para((720, 1600), 3440, 1440) is None  # monitor mais comprido que o celular: nada a mudar
    assert mod.forma_para(None, 1920, 1080) is None


def test_alvo_e_a_tv_e_nunca_o_virtual(m):
    tv = {"nome": "TV", "x": 9, "y": 0, "w": 1920, "h": 1080, "principal": False, "tv": True, "virtual": False}
    vir = {"nome": "V", "x": 0, "y": 0, "w": 1600, "h": 720, "principal": True, "tv": False, "virtual": True}
    pri = {"nome": "P", "x": 0, "y": 0, "w": 1440, "h": 900, "principal": True, "tv": False, "virtual": False}
    assert m.monitor_alvo([pri, vir, tv])["nome"] == "TV"
    assert m.monitor_alvo([vir, pri])["nome"] == "P"
    assert m.monitor_alvo([vir]) is None


def test_preencher_muda_o_tamanho_e_volta_depois_do_scrcpy(m):
    assert m.main(["celular", "--preencher"]) == 0
    (c,) = scrcpys(m)
    assert "--fullscreen" in c and "--window-x=1480" in c and "--window-y=40" in c
    ordem = [x for x in m.estado["chamadas"] if x[0] == "scrcpy.exe" or x[3:5] == ["shell", "wm"]]
    assert [x[4:] if x[0] == "adb" else "scrcpy" for x in ordem] == [
        ["wm", "size"], ["wm", "size", "720x1280"], "scrcpy", ["wm", "size", "reset"]]
    assert not m.MARCA.exists()


def test_preencher_volta_mesmo_se_o_scrcpy_falhar(m):
    antigo = m._executa

    def quebra(cmd, **kw):
        if cmd[0] == "scrcpy.exe":
            raise OSError("caiu")
        return antigo(cmd, **kw)
    m._executa = quebra
    with pytest.raises(OSError):
        m.main(["celular", "--preencher"])
    assert wms(m)[-1] == ["wm", "size", "reset"] and not m.MARCA.exists()


def test_preencher_pela_tailscale_volta_antes_de_soltar(m):
    m.estado["cabo"] = False
    m.main(["celular", "--preencher"])
    ch = m.estado["chamadas"]
    reset = max(i for i, c in enumerate(ch) if c[-1:] == ["reset"])
    solta = max(i for i, c in enumerate(ch) if c[:2] == ["adb", "disconnect"])
    assert reset < solta


def test_sem_preencher_nao_mexe_no_tamanho(m):
    m.main(["celular"])
    assert wms(m) == []
    assert "--fullscreen" not in scrcpys(m)[0]


def test_marca_esquecida_e_desfeita_na_proxima_vez(m):
    m.MARCA.write_text("720x1280")
    m.main(["celular"])
    assert wms(m) == [["wm", "size", "reset"]] and not m.MARCA.exists()


def test_normal_desfaz(m):
    assert m.main(["normal"]) == 0
    assert wms(m) == [["wm", "size", "reset"]]


def test_menu_6_preenche(m, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "6")
    m.main([])
    assert "--fullscreen" in scrcpys(m)[0]


class Parar:
    """Evento falso: deixa a vigia dar N olhadas e para."""
    def __init__(self, n):
        self.n = n

    def wait(self, _):
        self.n -= 1
        return self.n < 0


PC = {"hwnd": 1, "tv": False, "virtual": False, "cheia": False, "w": 1440, "h": 900}
PC_CHEIA = dict(PC, cheia=True)
TV = {"hwnd": 1, "tv": True, "virtual": False, "cheia": False, "w": 1920, "h": 1080}
TV_CHEIA = dict(TV, cheia=True)


def roda_vigia(m, posicoes, cheia_ok=True):
    fila = list(posicoes)
    m.onde_esta = lambda titulo: fila.pop(0) if fila else None
    pedidos = []
    m.poe_tela_cheia = lambda hwnd: pedidos.append(hwnd) or cheia_ok
    a = m.Ajuste("RQ8")
    m.vigia(a, Parar(len(posicoes)))
    return a, pedidos


def test_quer_tamanho(m):
    f = (720, 1600)
    assert m.quer_tamanho(f, None) is None
    assert m.quer_tamanho(f, PC) is None
    assert m.quer_tamanho(f, PC_CHEIA) == (720, 1152)
    assert m.quer_tamanho(f, TV) == (720, 1280)
    assert m.quer_tamanho(f, dict(TV_CHEIA, virtual=True)) is None


def test_janela_vai_para_a_tv_e_volta(m):
    a, pedidos = roda_vigia(m, [PC, TV, TV_CHEIA, TV_CHEIA, PC])
    assert pedidos == [1]  # tela cheia pedida UMA vez na chegada
    assert wms(m) == [["wm", "size"], ["wm", "size", "720x1280"], ["wm", "size", "reset"]]
    assert a.atual is None and not m.MARCA.exists()


def test_sai_da_tela_cheia_na_tv_e_nao_e_forcado_de_novo(m):
    a, pedidos = roda_vigia(m, [TV, TV_CHEIA, TV, TV])
    assert pedidos == [1] and a.atual == (720, 1280)


def test_tela_cheia_recusada_avisa_e_preenche_mesmo_assim(m, capsys):
    a, pedidos = roda_vigia(m, [TV], cheia_ok=False)
    assert "Alt+F" in capsys.readouterr().out and a.atual == (720, 1280)


def test_tela_cheia_no_monitor_do_pc_tambem_preenche(m):
    a, pedidos = roda_vigia(m, [PC_CHEIA])
    assert pedidos == [] and a.atual == (720, 1152)


def test_fechar_a_janela_desfaz_o_que_a_vigia_fez(m):
    fila = [TV_CHEIA]
    m.onde_esta = lambda titulo: fila.pop(0) if fila else None
    m.poe_tela_cheia = lambda hwnd: True
    antigo = m._executa

    def lento(cmd, **kw):  # o scrcpy fica aberto um pouco, para a vigia olhar
        if cmd[0] == "scrcpy.exe":
            import time
            time.sleep(0.2)
        return antigo(cmd, **kw)
    m._executa = lento
    m.main(["celular"])
    assert wms(m)[-2:] == [["wm", "size", "720x1280"], ["wm", "size", "reset"]] and not m.MARCA.exists()