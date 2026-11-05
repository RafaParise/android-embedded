"""Testes de scripts/vpn-celular.py (VPN sempre ativa e saida de internet pelo PC, Tailscale, A12). Usa textos do `dumpsys connectivity` e do
`tailscale status --json` no formato real (01/11/2026, enderecos trocados) e um ambiente FALSO: nenhum teste toca o adb nem a Tailscale.
O que mais importa: a saida pelo PC SO liga com o PC aprovado e online (senao o celular fica sem internet) e DESFAZ sozinha se a internet nao passar."""
import json

import pytest

WIFI = ("NetworkAgentInfo{network{121}  handle{1}  ni{WIFI CONNECTED extra: } created=2026-11-01T05:05:59.288Z  lp{{InterfaceName: wlan0 LinkAddresses: [ 192.0.2.4/24 ] "
        "Routes: [ 0.0.0.0/0 -> 192.0.2.1 wlan0 mtu 0 ]}}  nc{[ Transports: WIFI Capabilities: NOT_METERED&INTERNET&TRUSTED&NOT_VPN&VALIDATED UnderlyingNetworks: Null]}  factorySerialNumber=8}")
MOVEL = ("NetworkAgentInfo{network{107}  handle{2}  ni{MOBILE[LTE] CONNECTED extra: ims}  lp{{InterfaceName: rmnet1 Routes: [ ::/0 -> fe80::3 rmnet1 mtu 1280 ]}}  "
         "nc{[ Transports: CELLULAR Capabilities: IMS&NOT_VPN&VALIDATED]}  factorySerialNumber=5}")


def vpn_linha(rotas, caps="NOT_METERED&INTERNET&NOT_RESTRICTED&TRUSTED&VALIDATED&NOT_ROAMING", estado="CONNECTED", base=121):
    return ("NetworkAgentInfo{network{120}  handle{3}  ni{VPN %s extra: } created=2026-11-01T03:16:03.592Z Score(Policies : EVER_EVALUATED&IS_VPN&EVER_VALIDATED&IS_VALIDATED ; KeepConnected : 0)  "
            "underlying{[%d]}  lp{{InterfaceName: tun0 LinkAddresses: [ 100.64.0.2/32 ] DnsAddresses: [ /100.100.100.100 ] Domains: exemplo.ts.net MTU: 1280 Routes: [ %s ]}}  "
            "nc{[ Transports: WIFI|VPN Capabilities: %s LinkUpBandwidth>=12000Kbps TransportInfo: <VpnTransportInfo{type=1}> UnderlyingNetworks: [%d]]}  factorySerialNumber=7}") % (estado, base, rotas, caps, base)


ROTAS_TS = "100.64.0.1/32 -> 0.0.0.0 tun0 mtu 0,100.100.100.100/32 -> 0.0.0.0 tun0 mtu 0,fd7a:115c:a1e0::/48 -> :: tun0 mtu 0"
ROTAS_SAIDA = ROTAS_TS + ",0.0.0.0/0 -> 0.0.0.0 tun0 mtu 0,::/0 -> :: tun0 mtu 0"


def dump(vpn=None):
    return "\n".join(["Active default network: 121", MOVEL, WIFI] + ([vpn] if vpn else []) + ["NetworkRequest [ LISTEN id=32 ]"])


DUMP_SEM_SAIDA = dump(vpn_linha(ROTAS_TS))
DUMP_COM_SAIDA = dump(vpn_linha(ROTAS_SAIDA))
DUMP_SAIDA_SEM_VALIDAR = dump(vpn_linha(ROTAS_SAIDA, caps="NOT_METERED&INTERNET&NOT_RESTRICTED&TRUSTED&NOT_ROAMING"))
DUMP_SEM_VPN = dump(None)

PREFS_OK = json.dumps({"AdvertiseRoutes": ["0.0.0.0/0", "::/0"], "ForceDaemon": True})
PREFS_SEM_ANUNCIO = json.dumps({"AdvertiseRoutes": None, "ForceDaemon": False})


def status_json(aprovado=True, pc_online=True, cel_online=True):
    return json.dumps({"Self": {"HostName": "meupc", "Online": pc_online, "ExitNodeOption": aprovado, "AllowedIPs": ["100.64.0.1/32"]},
                       "Peer": {"nodekey:aaa": {"HostName": "meu-a12", "OS": "android", "Online": cel_online},
                                "nodekey:bbb": {"HostName": "outro", "OS": "linux", "Online": False}}})


class Falso:
    """Ambiente falso: `dumps` e a sequencia de respostas do dumpsys (a cada leitura anda um passo, a ultima se repete); o broadcast troca o estado."""

    def __init__(self, antes, depois_ligar=None, depois_desligar=None, prefs=PREFS_OK, status=None, modelo="SM-A125M", app="com.tailscale.ipn", bloqueio="0"):
        self.estado = antes
        self.depois_ligar = depois_ligar or antes
        self.depois_desligar = depois_desligar or antes
        self.prefs = prefs
        self.status = status or status_json()
        self.modelo = modelo
        self.app = app
        self.bloqueio = bloqueio
        self.comandos = []
        self.dormiu = 0
        self.guarda_diz = ""
        self.guarda_erro = False

    def adb(self, comando, timeout=40):
        self.comandos.append(comando)
        if comando.startswith("getprop ro.product.model"):
            return self.modelo + "\n"
        if comando.startswith("dumpsys connectivity"):
            return self.estado
        if comando.startswith("settings get secure always_on_vpn_app"):
            return self.app + "\n"
        if comando.startswith("settings get secure always_on_vpn_lockdown"):
            return self.bloqueio + "\n"
        if comando.startswith("am broadcast"):
            self.estado = self.depois_desligar if "--es exitNode ''" in comando else self.depois_ligar
            return "Broadcast completed: result=0\n"
        raise AssertionError("comando inesperado no celular: " + comando)

    def ts(self, *args, timeout=40):
        if args[:2] == ("debug", "prefs"):
            return self.prefs
        if args[:2] == ("status", "--json"):
            return self.status
        raise AssertionError("comando inesperado na Tailscale: %r" % (args,))

    def dorme(self, s):
        self.dormiu += s

    def guarda(self):
        if self.guarda_erro:
            raise OSError("sem Termux")
        return self.guarda_diz

    def broadcasts(self):
        return [c for c in self.comandos if c.startswith("am broadcast")]


@pytest.fixture
def v(importa_script):
    return importa_script("vpn-celular.py")


# ---------------------------------------------------------------- leitura

def test_vpn_conectada_sem_saida(v):
    r = v.le_vpn(DUMP_SEM_SAIDA)
    assert r == {"conectada": True, "validada": True, "saida_ativa": False, "base": "WIFI"}


# Formato REAL do app com "acesso a rede local" (A12, 02/11/2026): nao ha 0.0.0.0/0; sao ~130 pedacos que deixam a rede local de fora (aqui, resumido e com a rede trocada)
ROTAS_SAIDA_COM_LAN = ", ".join(f"{r} -> 0.0.0.0 tun1 mtu 0" for r in (
    "0.0.0.0/1", "128.0.0.0/2", "192.0.0.0/9", "192.128.0.0/11", "192.160.0.0/13", "192.168.0.0/20", "193.0.0.0/8", "194.0.0.0/7", "196.0.0.0/6", "200.0.0.0/5", "208.0.0.0/4", "224.0.0.0/3")) + ", ::/3 -> :: tun1 mtu 0"


def test_saida_com_rede_local_nao_tem_rota_0_0_0_0_0_mas_conta_como_ativa(v):
    r = v.le_vpn(dump(vpn_linha(ROTAS_SAIDA_COM_LAN)))
    assert r["conectada"] is True and r["saida_ativa"] is True


@pytest.mark.parametrize("rotas,ativa", [
    ("0.0.0.0/0 -> 0.0.0.0 tun0 mtu 0", True),
    ("0.0.0.0/1 -> 0.0.0.0 tun0 mtu 0", True),
    ("0.0.0.0/2 -> 0.0.0.0 tun0 mtu 0", False),
    ("100.64.0.0/10 -> 0.0.0.0 tun0 mtu 0", False),
    ("100.100.100.100/32 -> 0.0.0.0 tun0 mtu 0, fd7a:115c:a1e0::/48 -> :: tun0 mtu 0", False),
    ("0.0.0.0/0 -> 192.0.2.1 wlan0 mtu 0", False),
    ("0.0.0.0/1 -> 0.0.0.0 tun0 mtu 0, 0.0.0.0/1 -> 0.0.0.0 tun1 mtu 0", True),
    ("0.0.0.0/2 -> 0.0.0.0 tun0 mtu 0, 0.0.0.0/2 -> 0.0.0.0 tun1 mtu 0", False),
    ("", False),
    ("lixo -> 0.0.0.0 tun0 mtu 0", False),
    ("999.0.0.0/1 -> 0.0.0.0 tun0 mtu 0", False),
])
def test_rota_de_saida_mede_o_espaco_que_passa_pelo_tunel(v, rotas, ativa):
    assert v.rota_de_saida(rotas) is ativa


def test_vpn_com_saida_so_conta_a_rota_padrao_do_tunel_nao_a_do_wifi(v):
    assert v.le_vpn(DUMP_COM_SAIDA)["saida_ativa"] is True
    # a rota 0.0.0.0/0 da rede Wi-Fi (wlan0) esta no dump em qualquer caso e NAO pode contar
    assert v.le_vpn(DUMP_SEM_SAIDA)["saida_ativa"] is False


def test_vpn_nao_validada_pelo_android(v):
    r = v.le_vpn(DUMP_SAIDA_SEM_VALIDAR)
    assert r["saida_ativa"] is True and r["validada"] is False


def test_validada_exige_o_token_inteiro_nao_so_a_palavra(v):
    # "NOT_VALIDATED" ou "EVER_VALIDATED" nao valem como VALIDATED
    r = v.le_vpn(dump(vpn_linha(ROTAS_SAIDA, caps="INTERNET&NOT_VALIDATED&EVER_VALIDATED")))
    assert r["validada"] is False


def test_sem_vpn_ou_desconectada(v):
    assert v.le_vpn(DUMP_SEM_VPN) == {"conectada": False, "validada": False, "saida_ativa": False, "base": "?"}
    assert v.le_vpn(dump(vpn_linha(ROTAS_TS, estado="CONNECTING")))["conectada"] is False


def test_rede_de_base_movel(v):
    assert v.le_vpn(dump(vpn_linha(ROTAS_TS, base=107)))["base"] == "CELLULAR"


def test_sempre_ativa(v):
    assert v.le_sempre_ativa("com.tailscale.ipn\n", "0\n") == {"app": "com.tailscale.ipn", "sempre_ativa": True, "bloqueio": False}
    assert v.le_sempre_ativa("null", "null")["sempre_ativa"] is False
    assert v.le_sempre_ativa("com.outro.vpn", "1")["sempre_ativa"] is False
    assert v.le_sempre_ativa("com.tailscale.ipn", "1")["bloqueio"] is True


def test_pc_anunciado_e_aprovado(v):
    r = v.le_pc(PREFS_OK, status_json())
    assert r == {"anuncia": True, "aprovado": True, "online": True, "nome": "meupc", "sem_usuario": True, "celular_online": True, "celular_nome": "meu-a12"}


def test_pc_anunciado_mas_nao_aprovado(v):
    r = v.le_pc(PREFS_OK, status_json(aprovado=False))
    assert r["anuncia"] is True and r["aprovado"] is False


def test_aprovacao_tambem_vale_pela_rota_nos_ips_permitidos(v):
    s = json.dumps({"Self": {"HostName": "meupc", "Online": True, "AllowedIPs": ["100.64.0.1/32", "0.0.0.0/0", "::/0"]}, "Peer": {}})
    assert v.le_pc(PREFS_OK, s)["aprovado"] is True


def test_anuncio_exige_as_duas_familias(v):
    so4 = json.dumps({"AdvertiseRoutes": ["0.0.0.0/0"]})
    assert v.le_pc(so4, status_json())["anuncia"] is False
    assert v.le_pc(PREFS_SEM_ANUNCIO, status_json())["anuncia"] is False


def test_json_invalido_nao_derruba(v):
    assert v.le_pc("nao e json", "{").get("anuncia") is False


def test_celular_e_so_o_peer_android(v):
    r = v.le_pc(PREFS_OK, status_json(cel_online=False))
    assert r["celular_online"] is False and r["celular_nome"] == "meu-a12"


# ---------------------------------------------------------------- veredito

def _ver(v, pc=None, vpn=None, aa=None):
    pc0 = v.le_pc(PREFS_OK, status_json())
    vpn0 = v.le_vpn(DUMP_SEM_SAIDA)
    aa0 = v.le_sempre_ativa("com.tailscale.ipn", "0")
    pc0.update(pc or {})
    vpn0.update(vpn or {})
    aa0.update(aa or {})
    return v.veredito(pc0, vpn0, aa0)


def test_proximo_passo_em_cada_etapa(v):
    assert "advertise-exit-node" in _ver(v, pc={"anuncia": False})[1]
    assert "Aprovar o PC" in _ver(v, pc={"aprovado": False})[1]
    assert "Conectar a Tailscale" in _ver(v, vpn={"conectada": False})[1]
    assert "no Termux, saida ligar" in _ver(v)[1]
    assert "Saida em uso" in _ver(v, vpn={"saida_ativa": True})[1]


def test_veredito_marca_o_que_falta(v):
    m, _ = _ver(v, pc={"aprovado": False}, aa={"sempre_ativa": False, "bloqueio": True})
    assert any(a == "FALTA" and "APROVOU" in b for a, b in m)
    assert any(a == "aviso" and "Bloquear" in b for a, b in m)
    assert any(a == "FALTA" and "sempre ativada" in b for a, b in m)
    ok, _ = _ver(v)
    assert not any(a == "FALTA" for a, b in ok), "com tudo certo nao pode sobrar FALTA"


# ---------------------------------------------------------------- saida ligar

def test_recusa_sem_aprovacao_e_nao_manda_nada(v):
    f = Falso(DUMP_SEM_SAIDA, status=status_json(aprovado=False))
    assert v.cmd_ligar(f, True, True) == 1
    assert f.broadcasts() == []


@pytest.mark.parametrize("kw", [
    {"prefs": PREFS_SEM_ANUNCIO},
    {"status": status_json(pc_online=False)},
    {"status": status_json(cel_online=False)},
])
def test_recusa_se_o_pc_ou_o_celular_nao_estao_prontos(v, kw):
    f = Falso(DUMP_SEM_SAIDA, **kw)
    assert v.cmd_ligar(f, True, True) == 1 and f.broadcasts() == []


def test_recusa_com_a_vpn_desconectada(v):
    f = Falso(DUMP_SEM_VPN)
    assert v.cmd_ligar(f, True, True) == 1 and f.broadcasts() == []


def test_simulacao_nao_manda_nada(v, capsys):
    f = Falso(DUMP_SEM_SAIDA)
    assert v.cmd_ligar(f, False, True) == 0
    assert f.broadcasts() == [] and "SIMULACAO" in capsys.readouterr().out


def test_ligar_aplicado_manda_a_intencao_certa_e_confere(v):
    f = Falso(DUMP_SEM_SAIDA, depois_ligar=DUMP_COM_SAIDA)
    assert v.cmd_ligar(f, True, True) == 0
    (cmd,) = f.broadcasts()
    assert cmd == "am broadcast -n com.tailscale.ipn/.IPNReceiver -a com.tailscale.ipn.USE_EXIT_NODE --es exitNode 'meupc' --ez allowLanAccess true"


def test_sem_lan_desliga_o_acesso_a_rede_local(v):
    f = Falso(DUMP_SEM_SAIDA, depois_ligar=DUMP_COM_SAIDA)
    assert v.cmd_ligar(f, True, False) == 0
    assert f.broadcasts()[0].endswith("--ez allowLanAccess false")


def test_se_a_rota_nao_entra_desfaz(v, capsys):
    f = Falso(DUMP_SEM_SAIDA, depois_ligar=DUMP_SEM_SAIDA)   # o app recusou: nada muda
    assert v.cmd_ligar(f, True, True) == 1
    cmds = f.broadcasts()
    assert len(cmds) == 2 and "--es exitNode ''" in cmds[1], "tem que mandar 'sem saida' para nao deixar o celular sem internet"
    assert "FALHOU" in capsys.readouterr().out
    assert f.dormiu > 0 and f.dormiu <= 150, "espera limitada"


def test_se_o_android_nao_valida_a_internet_desfaz(v):
    f = Falso(DUMP_SEM_SAIDA, depois_ligar=DUMP_SAIDA_SEM_VALIDAR, depois_desligar=DUMP_SEM_SAIDA)
    assert v.cmd_ligar(f, True, True) == 1
    cmds = f.broadcasts()
    assert len(cmds) == 2 and "--es exitNode ''" in cmds[1]
    assert v.le_vpn(f.estado)["saida_ativa"] is False


def test_ja_em_uso_nao_faz_nada(v):
    f = Falso(DUMP_COM_SAIDA)
    assert v.cmd_ligar(f, True, True) == 0 and f.broadcasts() == []


# ---------------------------------------------------------------- saida desligar

def test_desligar_simulacao_e_aplicado(v):
    f = Falso(DUMP_COM_SAIDA, depois_desligar=DUMP_SEM_SAIDA)
    assert v.cmd_desligar(f, False) == 0 and f.broadcasts() == []
    assert v.cmd_desligar(f, True) == 0
    (cmd,) = f.broadcasts()
    assert "--es exitNode ''" in cmd and "USE_EXIT_NODE" in cmd
    assert v.le_vpn(f.estado)["saida_ativa"] is False


def test_desligar_que_nao_pega_avisa_o_caminho_manual(v, capsys):
    f = Falso(DUMP_COM_SAIDA, depois_desligar=DUMP_COM_SAIDA)
    assert v.cmd_desligar(f, True) == 1
    assert "Exit node > None" in capsys.readouterr().out


def test_desligar_sem_saida_nao_faz_nada(v):
    f = Falso(DUMP_SEM_SAIDA)
    assert v.cmd_desligar(f, True) == 0 and f.broadcasts() == []


# ---------------------------------------------------------------- ambiente e garantias

def test_aparelho_errado_aborta(v):
    f = Falso(DUMP_SEM_SAIDA, modelo="SM-G991B")
    with pytest.raises(SystemExit) as e:
        v.coleta(f)
    assert "ABORTADO" in str(e.value) and "nao e o SM-A125M" in str(e.value)


def test_sem_aparelho_no_adb_sai_com_2_e_diz_que_nao_ha_aparelho(v, capsys):
    assert v.main(["status"], amb=Falso(DUMP_SEM_SAIDA, modelo="")) == 2
    out = capsys.readouterr().out
    assert "nenhum aparelho" in out and "nao e o SM-A125M" not in out


def test_desligar_confere_o_modelo_antes_de_mandar_o_broadcast(v):
    f = Falso(DUMP_COM_SAIDA, depois_desligar=DUMP_SEM_SAIDA, modelo="SM-G991B")
    with pytest.raises(SystemExit):
        v.cmd_desligar(f, True)
    assert f.broadcasts() == []


class SemLeitura(Falso):
    """O cabo cai: o dumpsys volta vazio (depois do primeiro broadcast, se `so_depois`)."""

    def __init__(self, *a, so_depois=True, **kw):
        super().__init__(*a, **kw)
        self.so_depois = so_depois
        self.mudo = not so_depois

    def adb(self, comando, timeout=40):
        r = super().adb(comando, timeout)
        if comando.startswith("am broadcast"):
            self.mudo = True
        if comando.startswith("dumpsys connectivity") and self.mudo:
            return ""
        return r


def test_desligar_com_leitura_vazia_nao_conclui_que_ja_esta_desligada(v, capsys):
    f = SemLeitura(DUMP_COM_SAIDA, so_depois=False)
    assert v.main(["saida", "desligar", "--aplicar"], amb=f) == 2
    out = capsys.readouterr().out
    assert "ja esta desligada" not in out and "OK" not in out and f.broadcasts() == []


def test_desligar_cujo_cabo_cai_depois_do_broadcast_nao_diz_ok(v, capsys):
    f = SemLeitura(DUMP_COM_SAIDA, depois_desligar=DUMP_SEM_SAIDA)
    assert v.main(["saida", "desligar", "--aplicar"], amb=f) == 2
    out = capsys.readouterr().out
    assert "OK:" not in out and "Exit node > None" in out


def test_ligar_cujo_cabo_cai_depois_do_broadcast_nao_diz_desfeito(v, capsys):
    f = SemLeitura(DUMP_SEM_SAIDA, depois_ligar=DUMP_COM_SAIDA)
    assert v.main(["saida", "ligar", "--aplicar"], amb=f) == 2
    out = capsys.readouterr().out
    assert "Desfeito" not in out and "OK:" not in out and "Exit node > None" in out
    assert len(f.broadcasts()) == 2 and "--es exitNode ''" in f.broadcasts()[1], "ainda tenta o desfazer"


def test_ligar_com_timeout_do_adb_na_conferencia_tenta_desfazer(v, capsys):
    import subprocess

    class Trava(Falso):
        def adb(self, comando, timeout=40):
            if comando.startswith("dumpsys connectivity") and self.broadcasts():
                raise subprocess.TimeoutExpired("adb", timeout)
            return super().adb(comando, timeout)

    f = Trava(DUMP_SEM_SAIDA, depois_ligar=DUMP_COM_SAIDA)
    assert v.main(["saida", "ligar", "--aplicar"], amb=f) == 2
    assert len(f.broadcasts()) == 2 and "--es exitNode ''" in f.broadcasts()[1]
    assert "Exit node > None" in capsys.readouterr().out


def test_desligar_com_a_saida_suspensa_pelo_guarda_nao_diz_nada_a_fazer(v, capsys):
    f = Falso(DUMP_SEM_SAIDA)
    f.guarda_diz = "  >> SUSPENSA pelo guarda ha 3s\nGuarda: rodando (pid 1)"
    assert v.main(["saida", "desligar", "--aplicar"], amb=f) == 1
    out = capsys.readouterr().out
    assert "nada a fazer" not in out and "saida desligar" in out and f.broadcasts() == []


def test_desligar_sem_saida_e_com_guarda_que_nao_responde_segue_sem_quebrar(v, capsys):
    f = Falso(DUMP_SEM_SAIDA)
    f.guarda_erro = True
    assert v.main(["saida", "desligar"], amb=f) == 0
    assert "nada a fazer" in capsys.readouterr().out


def test_adb_com_codigo_de_erro_vira_excecao(v, monkeypatch):
    class R:
        returncode, stdout, stderr = 1, b"", b"error: no devices/emulators found"

    monkeypatch.setattr(v.subprocess, "run", lambda *a, **k: R())
    with pytest.raises(RuntimeError, match="no devices"):
        v.Ambiente().adb("getprop ro.product.model")


def test_tailscale_com_codigo_de_erro_vira_saida_2_e_nao_um_estado_falso(v, monkeypatch, capsys):
    class R:
        returncode, stdout, stderr = 1, b"", b"failed to connect to local tailscaled"

    monkeypatch.setattr(v.subprocess, "run", lambda *a, **k: R())
    with pytest.raises(RuntimeError, match="tailscaled"):
        v.Ambiente().ts("status", "--json")

    class Parada(Falso):
        def ts(self, *args, timeout=40):
            raise RuntimeError("tailscale falhou")

    assert v.main(["status"], amb=Parada(DUMP_SEM_SAIDA)) == 2
    out = capsys.readouterr().out
    assert "FALTA" not in out and "ABORTADO" in out


def test_status_so_manda_rodar_saida_guarda_se_o_guarda_esta_pedido_e_parado(v, capsys):
    f = Falso(DUMP_COM_SAIDA)
    f.guarda_diz = "Saida pelo PC: nao pedida\nGuarda: parado"
    v.main(["status"], amb=f)
    out = capsys.readouterr().out
    assert "[aviso" in out and "No Termux: saida ligar" in out and "saida guarda" not in out


def test_erro_de_ambiente_vira_saida_2(v, capsys):
    class Quebrado(Falso):
        def adb(self, comando, timeout=40):
            raise FileNotFoundError("adb")

    assert v.main(["status"], amb=Quebrado(DUMP_SEM_SAIDA)) == 2
    assert "ABORTADO" in capsys.readouterr().out


def test_nome_da_saida_vem_do_dns_e_nao_do_hostname_do_windows(v):
    s = json.dumps({"Self": {"HostName": "RafaParise", "DNSName": "rafaparise.exemplo.ts.net.", "Online": True}, "Peer": {}})
    assert v.le_pc(PREFS_OK, s)["nome"] == "rafaparise"
    s = json.dumps({"Self": {"HostName": "RafaParise", "Online": True}, "Peer": {}})
    assert v.le_pc(PREFS_OK, s)["nome"] == "RafaParise", "sem DNSName, cai no HostName"


def test_status_mostra_o_guarda_rodando(v, capsys):
    f = Falso(DUMP_COM_SAIDA)
    f.guarda_diz = "Guarda: rodando (pid 1)"
    assert v.main(["status"], amb=f) == 0
    saida = capsys.readouterr().out
    assert "guarda do Termux rodando" in saida and "SUSPENSA" not in saida


def test_status_mostra_o_guarda_com_a_saida_suspensa(v, capsys):
    f = Falso(DUMP_SEM_SAIDA)
    f.guarda_diz = "  >> SUSPENSA pelo guarda ha 3s\nGuarda: rodando (pid 1)"
    assert v.main(["status"], amb=f) == 0
    assert "SUSPENSA" in capsys.readouterr().out


def test_status_avisa_se_a_saida_esta_em_uso_sem_guarda(v, capsys):
    f = Falso(DUMP_COM_SAIDA)
    f.guarda_diz = "Guarda: PARADO"
    assert v.main(["status"], amb=f) == 0
    saida = capsys.readouterr().out
    assert "[aviso" in saida and "PARADO" in saida and "saida guarda" in saida


def test_status_nao_quebra_se_nao_alcanca_o_termux(v, capsys):
    f = Falso(DUMP_COM_SAIDA)
    f.guarda_erro = True
    assert v.main(["status"], amb=f) == 0
    assert "nao conferido" in capsys.readouterr().out


def test_status_sem_saida_e_sem_guarda_nao_avisa(v, capsys):
    assert v.main(["status"], amb=Falso(DUMP_SEM_SAIDA)) == 0
    assert "guarda do Termux" not in capsys.readouterr().out


def test_ligar_por_aqui_avisa_que_o_guarda_nao_fica_vigiando(v, capsys):
    assert v.main(["saida", "ligar", "--aplicar"], amb=Falso(DUMP_SEM_SAIDA, depois_ligar=DUMP_COM_SAIDA)) == 0
    assert "guarda NAO fica vigiando" in capsys.readouterr().out


def test_status_completo_e_saida_zero(v, capsys):
    assert v.main(["status"], amb=Falso(DUMP_SEM_SAIDA)) == 0
    saida = capsys.readouterr().out
    assert "[ok" in saida and "proximo passo:" in saida


def test_o_script_nunca_muda_ajustes_do_android():
    import pathlib
    fonte = (pathlib.Path(__file__).resolve().parent.parent / "vpn-celular.py").read_text(encoding="utf-8")
    assert "settings put" not in fonte and "pm disable" not in fonte, "so manda a intencao ao app; a VPN sempre ativada e o bloqueio sao da tela de VPN do Android"
    assert fonte.isascii()
