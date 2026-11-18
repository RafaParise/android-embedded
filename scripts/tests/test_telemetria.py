"""Testes da telemetria de aparelhos (scripts/celular-kit/bin/telemetria e a rota PUT /v1/telemetria/perfil da ponte).
Pedido do Rafael em 17/11/2026: perfis de hardware, software e rede de qualquer aparelho, SEM dado pessoal.
Nada toca o celular, o adb ou a rede: as coletas de verdade foram conferidas a mao no PC (Windows e o .ps1 avulso)."""
import importlib.machinery
import importlib.util
import json
import pathlib
import types

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
TELEMETRIA = RAIZ / "scripts" / "celular-kit" / "bin" / "telemetria"


@pytest.fixture
def tel(tmp_path, monkeypatch):
    monkeypatch.setenv("UNIVO_TELEMETRIA_DIR", str(tmp_path / "base"))
    carregador = importlib.machinery.SourceFileLoader("telemetria_kit", str(TELEMETRIA))
    spec = importlib.util.spec_from_loader("telemetria_kit", carregador)
    m = importlib.util.module_from_spec(spec)
    carregador.exec_module(m)
    monkeypatch.setattr(m, "TERMUX", False)
    monkeypatch.setattr(m, "BASE", tmp_path / "base")
    return m


def perfil_ok(tel, **extra):
    dados = {"alvo": "android", "origem": "adb",
             "aparelho": {"fabricante": "samsung", "modelo": "SM-A125M", "abis": ["arm64-v8a", "armeabi-v7a"], "android": "12"},
             "cpu": {"nome": "MT6765V/CB", "nucleos": 8}, "memoria": {"total_mb": 3700},
             "gpu": {"opengles": "3.2", "vulkan": True}, "software": {"versao": "10.0.26200", "powershell": "5.1.26100.8328"},
             "testes": {"cpu_sha256_mb_s_1nucleo": 210.5}}
    dados.update(extra)
    return tel.monta(dados, "PC da sala 3")


@pytest.mark.parametrize("texto,achado", [
    ("aa:bb:cc:dd:ee:ff", "MAC"), ("AA-BB-CC-DD-EE-FF", "MAC"), ("imei " + "1" * 15, "IMEI"),   # montado aqui: o sync barra 15 digitos seguidos no arquivo
    ("gateway 192.168.1.1", "IP"), ("10.0.20.100", "IP"), ("aluno@escola.sp.gov.br", "e-mail"), ("123.456.789-09", "CPF"),
    ('{"ssid": "Casa"}', "identificador"), ('{"serial": "R58N"}', "identificador"), ("android_id", "identificador"),
])
def test_privado_acha_dado_proibido(tel, texto, achado):
    assert tel.privado(texto) == achado


@pytest.mark.parametrize("texto", ["10.0.26200", "5.1.26100.8328", "OpenGL ES 3.2", "SM-A125M", "1 Gbps", "3901 MHz",
                                   "1600 x 720 x 4294967296 cores", "Realtek Gaming 2.5GbE Family Controller", "31.0.15.5222"])
def test_privado_nao_confunde_versao_e_medida(tel, texto):
    assert tel.privado(texto) is None


def test_perfil_valido_grava_e_resume(tel):
    p = perfil_ok(tel)
    assert p["arena"] == {"nucleos": 8, "ram_gb": 3.6, "cpu_mb_s": 210.5, "arm64": True, "opengles": "3.2", "vulkan": True}
    arq = tel.grava(p)
    assert arq.name == f"{p['id']}.json" and json.loads(arq.read_text(encoding="utf-8"))["id"] == p["id"]
    texto = tel.resumo()
    assert p["id"] in texto and "SM-A125M" in texto and (tel.BASE / "PERFIS.md").exists()


def test_id_aleatorio_nao_identifica(tel):
    assert perfil_ok(tel)["id"] != perfil_ok(tel)["id"]


def test_perfil_com_mac_e_recusado_inteiro(tel):
    p = perfil_ok(tel, rede={"placa": "x", "endereco": "02:00:00:aa:bb:cc"})
    with pytest.raises(ValueError, match="MAC"):
        tel.grava(p)
    assert not list(tel.BASE.glob("*.json"))


def test_secao_desconhecida_e_recusada(tel):
    p = perfil_ok(tel)
    p["contatos"] = []
    with pytest.raises(ValueError, match="secao"):
        tel.confere(p)


def test_monta_descarta_secao_fora_da_lista(tel):
    p = perfil_ok(tel, apps=["com.whatsapp"])
    assert "apps" not in p and "whatsapp" not in json.dumps(p)


@pytest.mark.parametrize("rotulo", ["celular 11987654321", "ra 123456789", "fulano@gmail.com", "PC 192.168.0.10"])
def test_rotulo_com_dado_pessoal_e_recusado(tel, rotulo):
    with pytest.raises(SystemExit):
        tel.limpa_rotulo(rotulo)


def test_regua_do_pc_ignora_placa_virtual(tel):
    p = tel.monta({"alvo": "pc", "cpu": {"nucleos": 6, "avx": True, "avx2": True}, "memoria": {"total_mb": 12074},
                   "gpu": {"placas": [{"nome": "Virtual Display Driver"}, {"nome": "AMD Radeon(TM) Graphics"}]}}, None)
    assert p["arena"]["gpu"] == "AMD Radeon(TM) Graphics" and p["arena"]["avx"] is True


def test_script_pc_nao_le_identificador(tel):
    ps = tel.PS_COLETA.lower()
    for proibido in ("serialnumber", "macaddress", "csname", "username", "registereduser", "uuid", "processorid", "domain"):
        assert proibido not in ps, proibido


def test_adb_nunca_pede_propriedade_de_serie(tel):
    assert not any("serial" in chave or "imei" in chave for chave in tel.PROPS.values())


# ------------------------------------------------------------------ a ponte do PC recebe o perfil
@pytest.fixture
def ponte(tmp_path, importa_script):
    m = importa_script("ponte-pc.py")
    proj, base = tmp_path / "proj", tmp_path / "caixa"
    (proj / "scripts").mkdir(parents=True)
    p = m.Ponte(proj, base)
    p.perfis = tmp_path / "perfis"
    return types.SimpleNamespace(m=m, p=p)


def test_ponte_grava_perfil_valido_sem_sobrescrever(ponte, tel):
    perfil = perfil_ok(tel)
    corpo = tel.confere(perfil).encode("utf-8")
    assert ponte.p.telemetria_receber(perfil["id"], corpo) == {"gravado": f"{perfil['id']}.json"}
    assert "ja estava" in ponte.p.telemetria_receber(perfil["id"], corpo)["aviso"]
    assert len(list(ponte.p.perfis.glob("*.json"))) == 1


@pytest.mark.parametrize("estrago,status", [
    (lambda d: {**d, "rede": {"ip": "192.168.1.40"}}, 422),
    (lambda d: {**d, "rede": {"x": "02:00:00:aa:bb:cc"}}, 422),
    (lambda d: {**d, "contatos": []}, 422),
    (lambda d: {**d, "univo_telemetria": 9}, 400),
    (lambda d: {**d, "id": "000000000000"}, 400),
])
def test_ponte_recusa_perfil_ruim(ponte, tel, estrago, status):
    perfil = perfil_ok(tel)
    corpo = json.dumps(estrago(perfil)).encode("utf-8")
    with pytest.raises(ponte.m.ErroPonte) as e:
        ponte.p.telemetria_receber(perfil["id"], corpo)
    assert e.value.status == status and not ponte.p.perfis.exists()


@pytest.mark.parametrize("nome", ["", "../x", "abc", "ABCDEF123456", None, "a" * 13])
def test_ponte_recusa_nome_ruim(ponte, nome):
    with pytest.raises(ponte.m.ErroPonte) as e:
        ponte.p.telemetria_receber(nome, b"{}")
    assert e.value.status == 400


def test_ponte_recusa_perfil_grande(ponte):
    with pytest.raises(ponte.m.ErroPonte) as e:
        ponte.p.telemetria_receber("a" * 12, b"x" * (ponte.m.MAX_PERFIL + 1))
    assert e.value.status == 413


def test_instalador_leva_o_comando_telemetria(ponte):
    assert ponte.m.ARQUIVOS_KIT_CELULAR["telemetria"] == "bin/telemetria"
    assert '"Bash(telemetria *)"' in ponte.m._MESCLA_PY
