"""microfone-bt.py: leitura, travas e medida. O adb nunca e aberto; o canal real se prova com o fone do Rafael."""
import math
import pathlib
import subprocess

import pytest

JDK = pathlib.Path("/mnt/c/Projetos/ferramentas/compilar-dex/jdk/bin")
RAIZ = pathlib.Path(__file__).resolve().parent.parent
FONTE = RAIZ / "celular-kit" / "tela" / "Tela.java"


@pytest.fixture
def m(importa_script):
    return importa_script("microfone-bt.py")


OLHA = """disp 80000008 = 1
disp 80000010 = 0
disp 20 = 1
disp 80 = 1
disp 80001000 = 0
modo 0
sco true
mudo false
gravando 2
"""


def test_le_olhada(m):
    d = m.le_olhada(OLHA)
    assert d == {"fone": True, "fio": False, "usb": False, "sco": True, "mudo": False, "modo": 0, "gravando": 2}


def test_le_olhada_sem_nada_fica_no_seguro(m):
    d = m.le_olhada("erro qualquer")
    assert not d["fone"] and not d["sco"] and d["gravando"] == 0


def test_recusa_outro_aparelho(m, monkeypatch):
    monkeypatch.setattr(m, "sh", lambda c, timeout=30: "SM-G991B")
    monkeypatch.setattr(m.sys, "argv", ["x", "celular-mudo"])
    with pytest.raises(SystemExit):
        m.main()


@pytest.mark.parametrize("arg,modo", [("auto", "auto"), ("fixo", "fixo"), ("ligar", "fixo"), ("desligar", "desligado")])
def test_grava_o_modo(m, monkeypatch, arg, modo):
    cs = []

    def falso(c, timeout=30):
        cs.append(c)
        return m.MODELO if "ro.product.model" in c else "1"

    monkeypatch.setattr(m, "sh", falso)
    monkeypatch.setattr(m.sys, "argv", ["x", arg])
    assert m.main() == 0
    assert f"echo {modo} > {m.MODO}" in cs


def test_processo_parado_avisa(m, monkeypatch, capsys):
    monkeypatch.setattr(m, "sh", lambda c, timeout=30: m.MODELO if "ro.product.model" in c else "0")
    assert m.define_modo("auto") == 1
    assert "iniciar" in capsys.readouterr().out


def test_celular_ligado_tira_o_bloqueio_e_solta(m, monkeypatch):
    cs = []

    def falso(c, timeout=30):
        cs.append(c)
        return m.MODELO if "ro.product.model" in c else "liberado"

    monkeypatch.setattr(m, "sh", falso)
    assert m.celular_ligado() == 0
    assert f"rm -f {m.BLOQUEIO}" in cs
    assert [c for c in cs if "mic-solta" in c]


def seno(hz, taxa=48000, seg=1.0, amp=8000):
    return [int(amp * math.sin(2 * math.pi * hz * i / taxa)) for i in range(int(taxa * seg))]


def test_medida_voz_estreita(m):
    r = m.mede_amostras(seno(1000), 48000)
    assert r["faixas"][0] > 0.99
    assert "estreita" in m.veredito(r)


def test_medida_voz_larga(m):
    r = m.mede_amostras([a + b for a, b in zip(seno(1000), seno(6000, amp=3000))], 48000)
    assert r["faixas"][1] > 0.05
    assert "larga" in m.veredito(r)


def test_medida_silencio(m):
    assert "silencio" in m.veredito(m.mede_amostras([0] * 48000, 48000))


def test_medida_corte(m):
    r = m.mede_amostras([32767 if i % 2 else -32768 for i in range(48000)], 48000)
    assert r["corte"] > 0.9
    assert "CORTANDO" in m.veredito(r)


def test_medida_vazia(m):
    assert m.mede_amostras([], 48000) is None


def executa(cmd, entrada=""):
    """Popen, e nao subprocess.run: o conftest tranca o run em todo teste. O comando nunca cita adb."""
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    saida, erro = p.communicate(entrada, timeout=120)
    return p.returncode, saida.strip(), erro


def java(entrada, pasta):
    # o JDK e do Windows: fonte e classes em pasta que ele enxerga
    win = executa(["/usr/bin/wslpath", "-w", str(pasta)])[1]
    (pasta / "Tela.java").write_bytes(FONTE.read_bytes())
    codigo, _, erro = executa([str(JDK / "javac.exe"), "--release", "8", "-Xlint:-options", "-d", win, win + chr(92) + "Tela.java"])
    assert codigo == 0, erro
    return executa([str(JDK / "java.exe"), "-cp", win, "Tela", "testa-mic"], entrada)[1].split()


CASOS = [
    # modo fone gravando modoAudio -> canal
    ("sco auto 1 1 0", "true"),
    ("sco auto 1 0 0", "false"),  # sem gravacao, a musica fica em AAC
    ("sco auto 0 1 0", "false"),  # fone saiu
    ("sco fixo 1 0 0", "true"),
    ("sco fixo 0 0 0", "false"),
    ("sco desligado 1 1 0", "false"),
    ("sco auto 1 1 2", "false"),  # em chamada quem manda e o Android
    ("sco fixo 1 0 3", "false"),
    # bloqueio externo modoAudio -> mudo
    ("mudo 1 0 0", "true"),
    ("mudo 0 0 0", "false"),
    ("mudo 1 1 0", "false"),  # fone ou fio conectado: nunca mudo
    ("mudo 1 0 1", "false"),  # tocando chamada
    ("mudo 1 0 2", "false"),  # em chamada
    ("mudo 1 0 3", "false"),  # chamada por app
    # fone canalAberto modo -> fone conta como microfone
    ("util 1 1 auto", "true"),
    ("util 1 0 auto", "false"),  # canal abrindo: segura o mudo, sem chiado no comeco
    ("util 0 1 auto", "false"),
    ("util 1 0 desligado", "true"),  # canal desligado por escolha: nunca fica mudo com o fone
    ("util 0 0 desligado", "false"),
    ("fonte 1999", "false"),
    ("fonte 1997", "false"),
    ("fonte 1", "true"),
    ("fonte 7", "true"),
]


@pytest.mark.skipif(not (JDK / "javac.exe").exists() or not pathlib.Path("/usr/bin/wslpath").exists(), reason="sem o JDK do PC")
def test_decisoes_do_java(tmp_path):
    entrada = "\n".join(c for c, _ in CASOS)
    assert java(entrada, tmp_path) == [e for _, e in CASOS]
