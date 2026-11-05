"""backup-drive.py: so copia, nunca apaga no Drive; projetos antes dos jogos; segredo e planilha de aluno ficam de fora. Com rclone falso."""
import json
import types

import pytest


@pytest.fixture
def bd(importa_script, tmp_path, monkeypatch):
    m = importa_script("backup-drive.py")
    monkeypatch.setattr(m, "RAIZ", tmp_path)
    rclone = tmp_path / "rclone.exe"
    rclone.write_text("x", encoding="ascii")
    monkeypatch.setattr(m, "RCLONE", str(rclone))
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    monkeypatch.setattr(m, "ORIGENS", [(str(a), "A"), (str(b), "B")])
    m.chamadas = []
    m.resposta_copia = 0
    m.livre = 300 * 1024**3
    m.bytes_local = 10 * 1024**3
    m.bytes_la = 0

    def falso(cmd, **kw):
        m.confere_seguro(cmd)
        m.chamadas.append(cmd)
        acao = cmd[1]
        if acao == "about":
            return types.SimpleNamespace(returncode=0, stdout=json.dumps({"free": m.livre, "used": 1, "total": 2}), stderr="")
        if acao == "size":
            n = m.bytes_la if cmd[2].startswith(m.REMOTO) else m.bytes_local
            return types.SimpleNamespace(returncode=0, stdout=json.dumps({"bytes": n, "count": 1}), stderr="")
        if acao == "copy":
            m.filtro_visto = m.filtro_visto + [open(cmd[cmd.index("--filter-from") + 1], encoding="utf-8").read()]
            return types.SimpleNamespace(returncode=m.resposta_copia, stdout="", stderr="")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="Checks: ok")

    m.filtro_visto = []
    monkeypatch.setattr(m, "roda", falso)
    return m


def copias(m):
    return [c for c in m.chamadas if c[1] == "copy"]


def test_rodar_copia_as_duas_origens_duas_vezes_com_projetos_primeiro(bd):
    assert bd.rodar() == 0
    assert len(copias(bd)) == 4
    assert "arena-console/jogos" in bd.filtro_visto[0] and "arena-console/jogos" in bd.filtro_visto[1]
    assert "arena-console/jogos" not in bd.filtro_visto[2] and "arena-console/jogos" not in bd.filtro_visto[3]


@pytest.mark.parametrize("acao", sorted({"sync", "move", "moveto", "delete", "deletefile", "purge", "rmdir", "rmdirs", "dedupe", "cleanup"}))
def test_comando_que_apaga_e_recusado(bd, acao):
    with pytest.raises(bd.Erro):
        bd.confere_seguro(["rclone", acao, "x"])


@pytest.mark.parametrize("flag", ["--delete-excluded", "--delete-before", "--backup-dir"])
def test_flag_que_apaga_e_recusada(bd, flag):
    with pytest.raises(bd.Erro):
        bd.confere_seguro(["rclone", "copy", "a", "b", flag])


def test_o_envio_usa_copy_e_nao_tem_flag_de_apagar(bd):
    c = bd.comando_copia("o", "d", "f", "l")
    assert c[1] == "copy"
    assert not any(x.startswith("--delete") for x in c)
    assert "--dry-run" not in c


def test_simular_passa_dry_run_em_todas_e_nao_mede_cota_dos_jogos(bd):
    assert bd.rodar(simular=True) == 0
    assert all("--dry-run" in c for c in copias(bd)) and len(copias(bd)) == 4


@pytest.mark.parametrize("nome", ["*MAPAO*", "*mapao*", ".env", "*.pem", "*.key", "/adguard-home/**", "rclone.conf", "a12_termux*", "diagnostico/pytest-lib/**", "diagnostico/backup-drive/**"])
def test_ficam_sempre_de_fora(bd, nome):
    assert "- " + nome in bd.filtros() and "- " + nome in bd.filtros(sem_jogos=True)


def test_sem_espaco_vao_os_projetos_e_nao_os_jogos(bd, capsys):
    bd.livre = 5 * 1024**3
    bd.bytes_local = 149 * 1024**3
    assert bd.rodar() == 1
    assert len(copias(bd)) == 2
    assert all("arena-console/jogos" in f for f in bd.filtro_visto)
    assert "Nao cabe" in capsys.readouterr().out


def test_erro_do_rclone_vira_saida_1_e_estado_registra(bd):
    bd.resposta_copia = 3
    assert bd.rodar() == 1
    est = json.loads((bd.pasta_estado() / "estado.json").read_text(encoding="utf-8"))
    assert est["codigo"] == 1 and est["fim"]


def test_medida_que_falha_termina_a_rodada_no_estado_e_solta_a_trava(bd, monkeypatch):
    def falha(alvo, arq_filtro=None):
        raise bd.Erro("nao consegui medir")

    monkeypatch.setattr(bd, "tamanho", falha)
    with pytest.raises(bd.Erro):
        bd.rodar()
    p = bd.pasta_estado()
    est = json.loads((p / "estado.json").read_text(encoding="utf-8"))
    assert est["codigo"] == 2 and est["fim"] and "medir" in est["erro"]
    assert not (p / "rodando.lock").exists()


def test_rodada_nova_limpa_o_erro_da_anterior(bd):
    (bd.pasta_estado() / "estado.json").write_text(json.dumps({"erro": "velho"}), encoding="utf-8")
    assert bd.rodar() == 0
    assert json.loads((bd.pasta_estado() / "estado.json").read_text(encoding="utf-8"))["erro"] is None


def test_arquivo_parar_nao_envia_nada(bd):
    (bd.pasta_estado() / "PARAR").write_text("", encoding="ascii")
    assert bd.rodar() == 0
    assert bd.chamadas == []


def test_trava_viva_nao_deixa_rodar_de_novo(bd, monkeypatch):
    (bd.pasta_estado() / "rodando.lock").write_text("123", encoding="ascii")
    monkeypatch.setattr(bd, "ja_rodando", lambda t: True)
    assert bd.rodar() == 0
    assert bd.chamadas == []
    assert (bd.pasta_estado() / "rodando.lock").exists()


def test_a_trava_e_os_filtros_temporarios_nao_sobram(bd):
    assert bd.rodar() == 0
    p = bd.pasta_estado()
    assert not (p / "rodando.lock").exists()
    assert not list(p.glob("*.txt"))


def test_sem_rclone_aborta_com_2(bd, monkeypatch):
    monkeypatch.setattr(bd, "RCLONE", "/nao/existe")
    assert bd.main(["rodar"]) == 2


def test_drive_sem_resposta_aborta_e_nao_envia(bd, monkeypatch):
    monkeypatch.setattr(bd, "roda", lambda cmd, **kw: types.SimpleNamespace(returncode=1, stdout="", stderr="token expirado"))
    assert bd.main(["rodar"]) == 2
    assert not (bd.pasta_estado() / "rodando.lock").exists()


def test_filtros_mostra_o_que_fica_de_fora(bd, capsys):
    assert bd.main(["filtros"]) == 0
    assert "MAPAO" in capsys.readouterr().out
