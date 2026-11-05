"""Testes dos comandos pequenos do kit do celular (projeto, qwen-pc, boot/iniciar-a12) e do QWEN.md, com bash de verdade e HOME falso.

Nada toca o celular, o adb nem a rede: curl, pgrep, sshd, saida e sleep sao falsos, dentro de uma pasta temporaria.
"""
import pathlib
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
KIT = RAIZ / "scripts" / "celular-kit"
BASH = next((p for p in ("/bin/bash", "/usr/bin/bash") if pathlib.Path(p).exists()), "/bin/bash")
pytestmark = pytest.mark.skipif(not pathlib.Path(BASH).exists(), reason="precisa de bash (os testes rodam no WSL)")
SISTEMA = "/usr/bin:/bin"


def _roda(script, args, home, path_extra="", env_extra=None):
    env = {"PATH": f"{path_extra}:{SISTEMA}" if path_extra else SISTEMA, "HOME": str(home)}
    env.update(env_extra or {})
    p = subprocess.Popen([BASH, str(script), *args], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    saida, _ = p.communicate(timeout=30)
    return p.returncode, saida


def _falso(pasta, nome, corpo):
    arq = pasta / nome
    arq.write_text("#!/bin/bash\n" + corpo + "\n", encoding="utf-8")
    arq.chmod(0o755)
    return arq


@pytest.mark.parametrize("nome", ["..", ".", "../x", "a/b", "a b", ""])
def test_projeto_recusa_nomes_que_escapam_de_projetos(tmp_path, nome):
    home = tmp_path / "home"
    (home / "projetos").mkdir(parents=True)
    rc, saida = _roda(KIT / "bin" / "projeto", [nome], home)
    assert rc == 1, (nome, saida)
    assert not list((home / "projetos").iterdir()) and not (home / "QWEN.md").exists() and not (home / ".git").exists()


def test_projeto_aceita_nome_comum_e_cria_a_pasta(tmp_path):
    home = tmp_path / "home"
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    _falso(fakebin, "qwen-pc", 'echo "abriu $1"')
    rc, saida = _roda(KIT / "bin" / "projeto", ["meu-app.v2"], home, path_extra=str(fakebin))
    assert rc == 0 and "abriu " + str(home / "projetos" / "meu-app.v2") in saida, saida
    assert (home / "projetos" / "meu-app.v2").is_dir()


def test_qwen_pc_nao_ensina_a_ponte_crua_do_ollama(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    _falso(fakebin, "curl", "exit 7")
    rc, saida = _roda(KIT / "bin" / "qwen-pc", [str(home)], home, path_extra=str(fakebin))
    assert rc == 1 and "11435" in saida, saida
    assert "adb reverse" not in saida, "o adb reverse escuta em todas as interfaces do celular: so pelo termux.ps1, com o sim do Rafael"
    assert "-Pontes" in saida and "-FecharPontes" in saida and "sim" in saida and "ia pc" in saida


def test_boot_registra_o_resultado_real_do_sshd_e_do_guarda(tmp_path):
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    # sshd nunca sobe (pgrep sempre falha), a saida nao esta pedida (rc 1) e o primeiro sleep derruba o laco de hora em hora
    _falso(home / "bin", "pgrep", "exit 1")
    _falso(home / "bin", "sshd", "exit 0")
    _falso(home / "bin", "saida", 'echo "A saida nao esta pedida: nada para vigiar (use: saida ligar)."; exit 1')
    _falso(home / "bin", "sleep", "kill -TERM $PPID")
    _roda(KIT / "boot" / "iniciar-a12", [], home)
    log = (home / ".cache" / "saida" / "boot.log").read_text(encoding="utf-8")
    assert "sshd NAO subiu" in log, log
    assert "guarda: rc=1" in log and "nao esta pedida" in log, log
    assert "conferidos" not in log, "o registro antigo afirmava sucesso sem olhar nada"


def test_boot_com_tudo_certo_diz_que_subiu(tmp_path):
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    _falso(home / "bin", "pgrep", "exit 0")
    _falso(home / "bin", "sshd", "exit 0")
    _falso(home / "bin", "saida", 'echo "Guarda de pe."; exit 0')
    _falso(home / "bin", "sleep", "kill -TERM $PPID")
    _roda(KIT / "boot" / "iniciar-a12", [], home)
    log = (home / ".cache" / "saida" / "boot.log").read_text(encoding="utf-8")
    assert "sshd ok" in log and "guarda: rc=0" in log and "Guarda de pe." in log, log


def test_qwen_md_traz_as_protecoes_do_projeto_e_nao_confunde_ia_qwen_com_o_combo_rapido():
    texto = (KIT / "QWEN.md").read_text(encoding="utf-8")
    linha = next(l for l in texto.splitlines() if l.startswith("- Nunca desativar:"))
    assert "com.samsung.android.app.appsedge" in linha, "protegido no CLAUDE.md e no lote-pacotes.py (divisao de tela quebra)"
    regra = next(l for l in texto.splitlines() if "Regra de modelo" in l)
    assert "(`ia qwen`)" not in regra, "ia qwen consulta o 27B do Groq, nao e o combo rapido"
    assert "ia rapido" in regra and "ia qwen" in regra
