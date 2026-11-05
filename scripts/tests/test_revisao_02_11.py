"""Defeitos achados na revisao de ponta a ponta de 02/11: teste-gravacao.py, reiniciar.py, padroes de segredo e a soma de rotas do vpn-celular.py. adb sempre falso."""
import hashlib
import sys
import subprocess

import pytest


class AdbGravacao:
    """Celular falso: guarda o md5 do que recebeu e pode corromper o alvo depois que o cache gira."""

    def __init__(self, corrompe=None, falha_push=None, estoura=None, some_alvo=None, rm_falha=False, alvo_existe=True):
        self.corrompe, self.falha_push, self.estoura = corrompe, falha_push, estoura
        self.some_alvo, self.rm_falha, self.alvo_existe = some_alvo, rm_falha, alvo_existe
        self.h, self.girou, self.chamadas, self.removido = {}, False, [], False

    def __call__(self, args, timeout=300):
        j = " ".join(str(a) for a in args)
        self.chamadas.append(j)
        if self.estoura and self.estoura in j:
            raise subprocess.TimeoutExpired(j, timeout)
        if args[0] == "get-state":
            return "device"
        if args[0] == "push":
            if self.falha_push and self.falha_push in args[2]:
                return "adb: error: failed to copy: No space left on device"
            self.h[args[2]] = hashlib.md5(open(args[1], "rb").read()).hexdigest()
            return "1 file pushed"
        if "rm -rf" in j and not self.rm_falha:
            self.removido = True
            return ""
        if "ls -d" in j and "teste-gravacao-controle" in j:  # conferencia da limpeza
            if self.removido:
                return "ls: x: No such file or directory"+chr(10)+"ls: y: No such file or directory"
            return "/storage/x/.teste-gravacao"+chr(10)+"/data/local/tmp/teste-gravacao-controle.bin"
        if "ls -d" in j:
            return "" if self.alvo_existe else "ls: " + j + ": No such file or directory"
        if "md5sum" in j:
            alvo = j.split("'")[1]
            if self.some_alvo and self.girou and self.some_alvo in alvo:
                return "md5sum: " + alvo + ": No such file or directory"
            if alvo not in self.h:
                return "md5sum: " + alvo + ": No such file or directory"
            return ("0" * 32 if self.girou and self.corrompe and self.corrompe in alvo else self.h[alvo]) + "  " + alvo
        if "find /system" in j:
            self.girou = True
        return ""


@pytest.fixture
def tg(importa_script, monkeypatch):
    m = importa_script("teste-gravacao.py")
    monkeypatch.setattr(sys, "argv", ["teste-gravacao.py", "--mb", "1", "--alvo", "/storage/1A2B-3C4D"])
    return m


def limpou(f):
    return any("rm -rf" in c and ".teste-gravacao" in c and "controle" in c for c in f.chamadas)


@pytest.mark.parametrize("falso,saida", [
    (dict(), 0),
    (dict(corrompe="1A2B-3C4D"), 1),
    (dict(corrompe="controle"), 2),
    (dict(falha_push="1A2B-3C4D"), 2),
    (dict(falha_push="controle"), 2),
])
def test_gravacao_resultado_e_sempre_limpa(tg, monkeypatch, capsys, falso, saida):
    f = AdbGravacao(**falso)
    monkeypatch.setattr(tg, "adb", f)
    assert tg.main() == saida
    assert limpou(f)
    if falso.get("falha_push"):
        s = capsys.readouterr().out
        assert "CORROMPIDO" not in s and "Nao consegui gravar" in s


def test_gravacao_que_estoura_o_tempo_nao_vale_e_limpa(tg, monkeypatch):
    f = AdbGravacao(estoura="find /system")
    monkeypatch.setattr(tg, "adb", f)
    assert tg.main() == 2
    assert limpou(f)


def test_gravacao_alvo_que_some_na_segunda_leitura_nao_e_corrompido(tg, monkeypatch, capsys):
    f = AdbGravacao(some_alvo="1A2B-3C4D")
    monkeypatch.setattr(tg, "adb", f)
    assert tg.main() == 2
    s = capsys.readouterr().out
    assert "CORROMPIDO" not in s and "ler o alvo" in s
    assert limpou(f)


def test_gravacao_alvo_inexistente_nao_cria_pasta(tg, monkeypatch):
    f = AdbGravacao(alvo_existe=False)
    monkeypatch.setattr(tg, "adb", f)
    assert tg.main() == 2
    assert not any("mkdir" in c for c in f.chamadas)


def test_gravacao_avisa_quando_a_limpeza_falha(tg, monkeypatch, capsys):
    f = AdbGravacao(rm_falha=True)
    monkeypatch.setattr(tg, "adb", f)
    assert tg.main() == 0
    assert "Nao consegui apagar" in capsys.readouterr().out


def test_gravacao_nao_avisa_quando_a_limpeza_funciona(tg, monkeypatch, capsys):
    monkeypatch.setattr(tg, "adb", AdbGravacao())
    assert tg.main() == 0
    assert "Nao consegui apagar" not in capsys.readouterr().out


def test_gravacao_recusa_tamanho_zero_sem_tocar_no_celular(tg, monkeypatch):
    f = AdbGravacao()
    monkeypatch.setattr(tg, "adb", f)
    monkeypatch.setattr(sys, "argv", ["teste-gravacao.py", "--mb", "0"])
    assert tg.main() == 2
    assert f.chamadas == ["get-state"]


def _jar_falso(pasta):
    import zipfile
    with zipfile.ZipFile(pasta / "index-v1.jar", "w") as z:
        z.writestr("META-INF/X.RSA", b"r")
        z.writestr("META-INF/X.SF", b"s")
        z.writestr("META-INF/MANIFEST.MF", b"m")
        z.writestr("index-v1.json", b"{}")


@pytest.mark.parametrize("n", [0, 2])
def test_indice_com_mais_de_um_certificado_e_reprovado(importa_script, monkeypatch, tmp_path, n):
    """Um indice falso assinado pelo 2o certificado, com o oficial em 1o, nao pode passar."""
    f = importa_script("fdroid-baixar.py")
    _jar_falso(tmp_path)

    def openssl(*a):
        if a[0] == "pkcs7":
            (tmp_path / "idx.pem").write_text("-----BEGIN CERTIFICATE-----\nx\n" * n)
        return 0, "SHA256 Fingerprint=" + f.CHAVE_FDROID
    monkeypatch.setattr(f, "openssl", openssl)
    with pytest.raises(SystemExit) as e:
        f.indice_verificado(tmp_path)
    assert "exatamente um certificado" in str(e.value)


def test_indice_com_um_certificado_segue_para_as_outras_conferencias(importa_script, monkeypatch, tmp_path):
    f = importa_script("fdroid-baixar.py")
    _jar_falso(tmp_path)

    def openssl(*a):
        if a[0] == "pkcs7":
            (tmp_path / "idx.pem").write_text("-----BEGIN CERTIFICATE-----\nx\n")
        return 0, "SHA256 Fingerprint=" + f.CHAVE_FDROID
    monkeypatch.setattr(f, "openssl", openssl)
    with pytest.raises(SystemExit) as e:
        f.indice_verificado(tmp_path)
    assert "digest do MANIFEST" in str(e.value)


@pytest.mark.parametrize("pacote", ["a;reboot", "$(id)", "com.x y", "-x", "semponto"])
def test_modo_jogo_recusa_nome_de_pacote_que_iria_ao_shell(importa_script, monkeypatch, pacote):
    m = importa_script("modos.py")
    monkeypatch.setattr(m, "sh", lambda c, timeout=60: "SM-A125M" if "getprop" in c else pytest.fail("foi ao shell: " + c))
    monkeypatch.setattr(sys, "argv", ["modos.py", "jogo", "ligar", "--", pacote])
    with pytest.raises(SystemExit) as e:
        m.main()
    assert "pacote" in str(e.value)


def test_reiniciar_recusa_outro_aparelho(importa_script, monkeypatch):
    m = importa_script("reiniciar.py")
    chamadas = []

    def adb(*a, timeout=30):
        chamadas.append(" ".join(a))
        return "SM-G999"
    monkeypatch.setattr(m, "adb", adb)
    monkeypatch.setattr(sys, "argv", ["reiniciar.py"])
    with pytest.raises(SystemExit) as e:
        m.main()
    assert "ABORTADO" in str(e.value) and "reboot" not in chamadas


@pytest.mark.parametrize("texto,tem", [
    ("AQ." + "a1B_-" * 10, True),
    ("tskey-auth-" + "kAbC123" * 4, True),
    ("o formato AQ. tem 53 caracteres", False),
    ("tskey-curta", False),
])
def test_padroes_novos_de_segredo(importa_script, texto, tem):
    assert importa_script("ponte-pc.py").tem_segredo(texto) is tem


def rotas_de(*redes):
    return "\n".join("%s -> 0.0.0.0 tun1 mtu 1280" % r for r in redes)


def test_rota_de_saida_soma_rotas_que_sozinhas_nao_bastam(importa_script):
    """Como o app faz com a rede local liberada: ~132 rotas, nenhuma com metade do espaco."""
    v = importa_script("vpn-celular.py")
    assert v.rota_de_saida(rotas_de("0.0.0.0/2", "64.0.0.0/2", "128.0.0.0/2")) is True
    assert v.rota_de_saida(rotas_de("0.0.0.0/3", "32.0.0.0/3", "64.0.0.0/3")) is False
