"""Testes de scripts/backup-cartao.py: copia do projeto no cartao PORTATIL, conferida por md5 com o cache descartado.

O que nao pode acontecer: gravar em simulacao, gravar em cartao adotado, enviar o que nao passou pela varredura do sync,
declarar a copia boa com md5 diferente ou apagar qualquer coisa no cartao.
"""
import hashlib
import io
import pathlib
import subprocess
import tarfile
import types

import pytest

ARQUIVOS = {"CLAUDE.md": b"regras\n", "memoria/ESTADO.md": "estado com acento: ção\r\n".encode(), "scripts/a b.py": b"print(1)\n"}
UUID = "1A2B-3C4D"
DESTINO = f"/storage/{UUID}/Backups/android-embeeded"
VOLUMES = f"public:179,97 mounted {UUID}\nprivate mounted null\nemulated;0 mounted null\n"
BATERIA = "  status: 2\n  level: 28\n"
SHA = "a" * 40


def md5(b):
    return hashlib.md5(b).hexdigest()


class Falso:
    """Faz o papel do git e do adb; guarda o que foi pedido e o que ficou no cartao."""

    def __init__(self, sha_origem=SHA, volumes=VOLUMES, bateria=BATERIA, estraga=None):
        self.chamadas = []
        self.sha_origem = sha_origem
        self.volumes = volumes
        self.bateria = bateria
        self.estraga = estraga  # nome relativo que chega errado ao cartao
        self.cartao = {}
        self.versao = []

    def __call__(self, args, **kw):
        self.chamadas.append(list(args))
        return types.SimpleNamespace(returncode=0, stdout=self.saida(list(args)), stderr="")

    def saida(self, a):
        if a[0] == "git":
            return self.git(a)
        if a[:2] == ["adb", "push"]:
            base = pathlib.Path(a[2].rstrip("."))
            for f in base.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(base).as_posix()
                    self.cartao[rel] = b"ERRADO" if rel == self.estraga else f.read_bytes()
            return "ok"
        return self.shell(a[2])

    def git(self, a):
        if a[1] == "rev-parse":
            return (self.sha_origem if "origin" in a[2] else SHA) + "\n"
        if a[1] == "archive":
            with tarfile.open(a[a.index("-o") + 1], "w") as t:
                for nome, dados in ARQUIVOS.items():
                    info = tarfile.TarInfo(nome)
                    info.size = len(dados)
                    t.addfile(info, io.BytesIO(dados))
            return ""
        if a[1] == "bundle":
            pathlib.Path(a[3]).write_bytes(b"historico")
        return ""

    def shell(self, c):
        if c == "dumpsys battery":
            return self.bateria
        if c == "sm list-volumes all":
            return self.volumes
        if c.startswith("echo "):
            self.versao.append(c)
            return ""
        if "md5sum" in c:
            return "".join(f"{md5(v)}  {DESTINO}/{k}\n" for k, v in self.cartao.items())
        if c.startswith("cat ") and "MD5SUMS" in c:
            return self.cartao.get("MD5SUMS.txt", b"").decode()
        return ""

    def gravou(self):
        return any(c[:2] == ["adb", "push"] for c in self.chamadas) or bool(self.versao)


@pytest.fixture
def bc(importa_script):
    return importa_script("backup-cartao.py")


def usa(bc, monkeypatch, tmp_path, **kw):
    f = Falso(**kw)
    monkeypatch.setattr(subprocess, "run", f)
    monkeypatch.setattr(bc, "RAIZ", tmp_path)
    return f


def test_escolhe_so_cartao_portatil_montado(bc):
    assert bc.cartao_portatil(VOLUMES) == UUID


@pytest.mark.parametrize("saida", [
    "private:179,98 mounted ABCD-0000\n",
    "public:179,97 unmounted 1A2B-3C4D\n",
    "public:179,97 mounted null\n",
    "public:1 mounted 1A2B-3C4D\npublic:2 mounted 1111-2222\n",
    "public:179,97 mounted x'; id;'\n",
    "",
])
def test_recusa_adotado_ausente_ambiguo_e_uuid_estranho(bc, saida):
    with pytest.raises(bc.Erro):
        bc.cartao_portatil(saida)


def test_diferencas_acha_falta_e_alterado_e_ignora_sobra(bc):
    esperado = {"a": "1", "b": "2"}
    assert bc.diferencas(esperado, {"a": "1", "b": "2", "velho": "9"}) == []
    assert bc.diferencas(esperado, {"a": "1"}) == ["falta: b"]
    assert bc.diferencas(esperado, {"a": "X", "b": "2"}) == ["diferente: a"]


def test_le_md5_tira_o_destino_e_aceita_espaco_e_acento(bc):
    saida = f"{'a' * 32}  {DESTINO}/scripts/a b.py\n{'b' * 32}  {DESTINO}/memoria/ção.md\nlixo\n"
    assert bc.le_md5(saida, DESTINO) == {"scripts/a b.py": "a" * 32, "memoria/ção.md": "b" * 32}


def test_simulacao_nao_grava_nada_no_celular(bc, monkeypatch, tmp_path):
    f = usa(bc, monkeypatch, tmp_path)
    assert bc.main([]) == 0
    assert not f.gravou()
    assert not any(c[:3] == ["adb", "shell", "sync"] for c in f.chamadas)


def test_aplicar_copia_confere_e_grava_versao_so_no_fim(bc, monkeypatch, tmp_path):
    f = usa(bc, monkeypatch, tmp_path)
    assert bc.main(["--aplicar"]) == 0
    for nome, dados in ARQUIVOS.items():
        assert f.cartao["projeto/" + nome] == dados, nome
    assert "historico.bundle" in f.cartao and "MD5SUMS.txt" in f.cartao
    assert "EM ANDAMENTO" in f.versao[0] and SHA in f.versao[-1] and "CONFERIDA" in f.versao[-1]
    i_push = next(i for i, c in enumerate(f.chamadas) if c[:2] == ["adb", "push"])
    i_fim = next(i for i, c in enumerate(f.chamadas) if c[:2] == ["adb", "shell"] and "CONFERIDA" in c[2])
    i_sync = next(i for i, c in enumerate(f.chamadas) if c[:3] == ["adb", "shell", "sync"])
    i_md5 = next(i for i, c in enumerate(f.chamadas) if c[:2] == ["adb", "shell"] and "md5sum" in c[2])
    assert i_push < i_sync < i_md5 < i_fim  # conferir so depois de descartar o cache


def test_md5_diferente_nao_declara_a_copia_boa(bc, monkeypatch, tmp_path, capsys):
    f = usa(bc, monkeypatch, tmp_path, estraga="projeto/memoria/ESTADO.md")
    assert bc.main(["--aplicar"]) == 1
    assert not any("CONFERIDA" in v for v in f.versao)
    assert any("FALHOU" in v for v in f.versao)
    assert "projeto/memoria/ESTADO.md" in capsys.readouterr().out


def test_conferir_acha_estrago_sem_gravar(bc, monkeypatch, tmp_path):
    f = usa(bc, monkeypatch, tmp_path)
    assert bc.main(["--aplicar"]) == 0
    f.versao.clear()
    assert bc.main(["--conferir"]) == 0
    f.cartao["CLAUDE.md"] = b"sobra"  # arquivo fora do manifesto nao atrapalha
    assert bc.main(["--conferir"]) == 0
    f.cartao["projeto/CLAUDE.md"] = b"estragado"
    assert bc.main(["--conferir"]) == 1
    assert not f.versao


def test_conferir_sem_copia_no_cartao_nao_passa(bc, monkeypatch, tmp_path):
    usa(bc, monkeypatch, tmp_path)
    assert bc.main(["--conferir"]) == 2


@pytest.mark.parametrize("kw", [
    {"sha_origem": "b" * 40},  # commit que ainda nao passou pela varredura do sync
    {"volumes": "private:179,98 mounted ABCD-0000\n"},
    {"bateria": "  status: 3\n  level: 90\n"},  # sem carregar
    {"bateria": "  status: 2\n  level: 2\n"},  # regra do Rafael: para com 3%
    {"bateria": "erro: aparelho offline\n"},
])
def test_recusas_antes_de_gravar(bc, monkeypatch, tmp_path, kw):
    f = usa(bc, monkeypatch, tmp_path, **kw)
    assert bc.main(["--aplicar"]) == 2
    assert not f.gravou()


def test_comando_que_falha_para_tudo_sem_declarar_a_copia_boa(bc, monkeypatch, tmp_path, capsys):
    f = usa(bc, monkeypatch, tmp_path)

    def falha_no_push(args, **kw):
        if list(args)[:2] == ["adb", "push"]:
            f.chamadas.append(list(args))
            return types.SimpleNamespace(returncode=1, stdout="", stderr="cartao sumiu")
        return f(args, **kw)

    monkeypatch.setattr(subprocess, "run", falha_no_push)
    assert bc.main(["--aplicar"]) == 2
    assert "cartao sumiu" in capsys.readouterr().out
    assert not any("CONFERIDA" in v for v in f.versao)
    assert "EM ANDAMENTO" in f.versao[-1]  # o que ficou no cartao avisa que nao e de confiar


def test_script_nao_tem_comando_de_apagar(bc):
    fonte = pathlib.Path(bc.__file__).read_text(encoding="utf-8")
    for proibido in ("rm -", "rmdir", "pm move", "move-primary", "mkfs", "sm format", "sm partition"):
        assert proibido not in fonte, proibido
