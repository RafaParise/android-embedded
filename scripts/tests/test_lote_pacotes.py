"""Testes de scripts/lote-pacotes.py: regra PROTEGIDOS e simulacao sem --aplicar."""
import json
import re
import sys
import types

import pytest


def test_protegidos_tem_excecao_em_todos_os_lotes(importa_script):
    """Regra do executor (N2-a): todo pacote de lotes-bloatware.json que casa com
    PROTEGIDOS tem de estar em 'permitidos' ou 'substitutos' do MESMO lote. Guarda de
    regressao: hoje nao ha violacao (auditoria 29/10: OK 138, FALHA 0)."""
    lp = importa_script("lote-pacotes.py", copiar_lotes_json=True)
    lotes = json.loads((lp.RAIZ / "scripts" / "lotes-bloatware.json").read_text(encoding="utf-8"))

    for nome_lote, lote in lotes.items():
        livres = set(lote.get("permitidos", [])) | set(lote.get("substitutos", {}))
        ruins = [
            p for p in lote["pacotes"]
            if p not in livres and any(re.search(rx, p, re.I) for rx in lp.PROTEGIDOS)
        ]
        assert not ruins, f"lote {nome_lote}: pacote(s) protegido(s) sem permitidos/substitutos: {ruins}"


def test_appsedge_e_protegido_e_nenhum_lote_o_desativa(importa_script):
    """30/10, teste A/B no aparelho: com o Apps Edge desativado, 'Abrir em tela dividida' dos Recentes
    falha (ActivityNotFoundException em FromRecentEdgeActivity) e o dashcam perde a divisao.
    Fecha tambem a brecha de 'permitidos': nenhum lote pode listar o pacote."""
    lp = importa_script("lote-pacotes.py", copiar_lotes_json=True)
    pkg = "com.samsung.android.app.appsedge"
    assert any(re.search(rx, pkg, re.I) for rx in lp.PROTEGIDOS)
    lotes = json.loads((lp.RAIZ / "scripts" / "lotes-bloatware.json").read_text(encoding="utf-8"))
    assert [nome for nome, lote in lotes.items() if pkg in lote["pacotes"]] == []


def test_simulacao_nao_aplica_nada(importa_script, monkeypatch, capsys):
    """Sem --aplicar, so le (getprop + pm list packages) e nunca desativa nada."""
    lp = importa_script("lote-pacotes.py", copiar_lotes_json=True)

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c == "pm list packages":
            saida = "package:com.facebook.appmanager\npackage:com.samsung.android.app.omcagent"
        elif c == "pm list packages -d":
            saida = ""
        elif c.startswith(("pm disable-user", "pm enable")):
            raise AssertionError(f"SIMULACAO nao deveria alterar pacotes: {c!r}")
        else:
            raise AssertionError(f"comando nao mapeado no fake: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(lp.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", "A1"])

    lp.main()

    saida = capsys.readouterr().out
    assert "SIMULACAO" in saida
    assert not list((lp.RAIZ / "diagnostico").glob("*/lote_A1_antes.txt"))


def test_aborta_antes_de_qualquer_adb_se_pacote_protegido_sem_excecao(importa_script, monkeypatch):
    """A trava 'ruins' tem de abortar ANTES do 1o comando adb (nem getprop deveria rodar)."""
    lp = importa_script("lote-pacotes.py")
    lote_ruim = {
        "X1": {"aplicavel": True, "descricao": "lote de teste com pacote protegido",
               "pacotes": ["com.android.vending"]},
    }
    (lp.RAIZ / "scripts" / "lotes-bloatware.json").write_text(json.dumps(lote_ruim), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", "X1"])

    def fake_run(cmd, **kw):
        raise AssertionError(f"nao deveria chamar adb: abortou antes ({cmd!r})")

    monkeypatch.setattr(lp.subprocess, "run", fake_run)

    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert "protegido" in str(exc.value)


def test_remover_e_aplicar_e_restaurar_sao_exclusivos(importa_script, monkeypatch):
    lp = importa_script("lote-pacotes.py", copiar_lotes_json=True)
    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", "FOSS-galeria", "--aplicar", "--remover"])

    def fake_run(cmd, **kw):
        raise AssertionError(f"nao deveria chamar adb: abortou antes ({cmd!r})")

    monkeypatch.setattr(lp.subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert "so uma de" in str(exc.value)


def test_remover_aborta_se_algum_pacote_do_lote_nao_tem_substituto(importa_script, monkeypatch):
    """--remover e mais arriscado (pm uninstall): so entra se TODO pacote do lote tiver
    substituto declarado -- nunca so parte do lote."""
    lp = importa_script("lote-pacotes.py")
    lote = {
        "X2": {"aplicavel": True, "descricao": "teste: 1 com substituto, 1 sem",
               "pacotes": ["com.sec.android.gallery3d", "com.exemplo.sememsubstituto"],
               "substitutos": {"com.sec.android.gallery3d": "org.fossify.gallery"}},
    }
    (lp.RAIZ / "scripts" / "lotes-bloatware.json").write_text(json.dumps(lote), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", "X2", "--remover"])

    def fake_run(cmd, **kw):
        raise AssertionError(f"nao deveria chamar adb: abortou antes ({cmd!r})")

    monkeypatch.setattr(lp.subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert "substituto declarado" in str(exc.value) and "com.exemplo.sememsubstituto" in str(exc.value)


def test_remover_pula_pacote_ainda_ativo_sem_abortar_o_lote(importa_script, monkeypatch, capsys):
    """--remover so atua no que JA esta desativado (estagio 2, depois do --aplicar). O que
    ainda esta ativo e pulado, com aviso, nao trava o resto do lote nem roda uninstall nele."""
    lp = importa_script("lote-pacotes.py", copiar_lotes_json=True)
    chamadas = []
    removido = {"valor": False}

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        chamadas.append(c)
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c == "dumpsys battery":
            saida = "level: 80\nstatus: 2"
        elif c == "pm list packages":
            pacotes_presentes = ["com.sec.android.app.myfiles", "com.samsung.android.video"]
            if not removido["valor"]:
                pacotes_presentes.append("com.sec.android.gallery3d")
            saida = "\n".join(f"package:{p}" for p in pacotes_presentes)
        elif c == "pm list packages -d":
            saida = "" if removido["valor"] else "package:com.sec.android.gallery3d"
        elif c == "pm list packages -e":
            saida = "package:org.fossify.gallery\npackage:org.fossify.filemanager\npackage:org.videolan.vlc"
        elif c == "pm uninstall -k --user 0 com.sec.android.gallery3d":
            removido["valor"] = True
            saida = "Success"
        elif c.startswith("pm uninstall") or c.startswith("pm disable") or c.startswith("pm enable"):
            raise AssertionError(f"so devia desinstalar o gallery3d (ja desativado), com -k: {c!r}")
        else:
            raise AssertionError(f"comando nao mapeado no fake: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(lp.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", "FOSS-galeria", "--remover"])

    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert exc.value.code == 0  # o unico pacote na fila (gallery3d) foi removido com sucesso

    saida = capsys.readouterr().out
    assert "PULADO" in saida and "com.sec.android.app.myfiles" in saida
    assert removido["valor"] is True
    assert any(c == "pm uninstall -k --user 0 com.sec.android.gallery3d" for c in chamadas)


def test_remover_usa_uninstall_user_0_e_restaurar_usa_install_existing(importa_script, monkeypatch, capsys):
    """Fecha o ciclo completo: --remover tira da lista 'todos' e usa -k (mantem dados do app,
    achado pelo Claude local, 30/10); --restaurar de um pacote AUSENTE (removido) usa
    'cmd package install-existing', nunca 'pm enable'."""
    lp = importa_script("lote-pacotes.py")
    lote = {
        "X3": {"aplicavel": True, "descricao": "1 pacote, com substituto, ja desativado",
               "pacotes": ["com.exemplo.alvo"],
               "substitutos": {"com.exemplo.alvo": "org.exemplo.substituto"}},
    }
    (lp.RAIZ / "scripts" / "lotes-bloatware.json").write_text(json.dumps(lote), encoding="utf-8")

    estado_pacote = {"presente": True, "desativado": True}

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if c == "getprop ro.product.model":
            return types.SimpleNamespace(stdout="SM-A125M", stderr="")
        if c == "dumpsys battery":
            return types.SimpleNamespace(stdout="level: 80\nstatus: 2", stderr="")
        if c == "pm list packages":
            saida = "package:com.exemplo.alvo" if estado_pacote["presente"] else ""
            return types.SimpleNamespace(stdout=saida, stderr="")
        if c == "pm list packages -d":
            saida = "package:com.exemplo.alvo" if (estado_pacote["presente"] and estado_pacote["desativado"]) else ""
            return types.SimpleNamespace(stdout=saida, stderr="")
        if c == "pm list packages -e":
            return types.SimpleNamespace(stdout="package:org.exemplo.substituto", stderr="")
        if c == "pm uninstall -k --user 0 com.exemplo.alvo":
            estado_pacote["presente"] = False
            return types.SimpleNamespace(stdout="Success", stderr="")
        if c == "pm uninstall --user 0 com.exemplo.alvo":
            raise AssertionError("--remover tem que usar -k (mantem dados do app), nao uninstall puro")
        if c == "cmd package install-existing com.exemplo.alvo":
            estado_pacote["presente"] = True
            estado_pacote["desativado"] = False
            return types.SimpleNamespace(stdout="Package com.exemplo.alvo installed", stderr="")
        if c == "pm enable com.exemplo.alvo":
            raise AssertionError("restaurar de pacote AUSENTE tem que usar install-existing, nao pm enable")
        raise AssertionError(f"comando nao mapeado no fake: {c!r}")

    monkeypatch.setattr(lp.subprocess, "run", fake_run)

    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", "X3", "--remover"])
    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert exc.value.code == 0
    assert estado_pacote["presente"] is False

    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", "X3", "--restaurar"])
    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert exc.value.code == 0
    assert estado_pacote["presente"] is True and estado_pacote["desativado"] is False


def _fake_lote_sem_substituto(estado_alvo):
    """Aparelho de mentira para um lote de telemetria: com.exemplo.telemetria ja desativado, com.exemplo.ativo ainda ativo."""
    chamadas = []

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        chamadas.append(c)
        if c == "getprop ro.product.model":
            return types.SimpleNamespace(stdout="SM-A125M", stderr="")
        if c == "dumpsys battery":
            return types.SimpleNamespace(stdout="level: 80\nstatus: 2", stderr="")
        if c == "pm list packages":
            presentes = ["com.exemplo.ativo"] + (["com.exemplo.telemetria"] if estado_alvo["presente"] else [])
            return types.SimpleNamespace(stdout="\n".join(f"package:{p}" for p in presentes), stderr="")
        if c == "pm list packages -d":
            return types.SimpleNamespace(stdout="package:com.exemplo.telemetria" if estado_alvo["presente"] else "", stderr="")
        if c == "pm uninstall -k --user 0 com.exemplo.telemetria":
            estado_alvo["presente"] = False
            return types.SimpleNamespace(stdout="Success", stderr="")
        raise AssertionError(f"comando nao esperado (so o uninstall COM -k do pacote desativado): {c!r}")

    return fake_run, chamadas


def test_remover_lote_sem_substituto_so_com_remocao_autorizada_e_sempre_com_dash_k(importa_script, monkeypatch, capsys):
    """Decisao do Rafael (30/10): telemetria/bloat sem substituto tambem pode sair, mas so em lote que declare
    'remocao_autorizada' e so o que ja esta desativado; o uninstall e SEMPRE com -k (mantem os dados)."""
    lp = importa_script("lote-pacotes.py")
    lote = {"X4": {"aplicavel": True, "descricao": "telemetria de teste", "remocao_autorizada": "Rafael, 30/10",
                   "pacotes": ["com.exemplo.telemetria", "com.exemplo.ativo"]}}
    (lp.RAIZ / "scripts" / "lotes-bloatware.json").write_text(json.dumps(lote), encoding="utf-8")
    estado = {"presente": True}
    fake_run, chamadas = _fake_lote_sem_substituto(estado)
    monkeypatch.setattr(lp.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", "X4", "--remover"])

    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert exc.value.code == 0
    assert estado["presente"] is False
    assert "pm uninstall -k --user 0 com.exemplo.telemetria" in chamadas
    assert not any(c.startswith("pm uninstall") and "com.exemplo.ativo" in c for c in chamadas)
    assert "PULADO" in capsys.readouterr().out


def test_remover_lote_sem_substituto_e_sem_autorizacao_aborta_antes_do_adb(importa_script, monkeypatch):
    lp = importa_script("lote-pacotes.py")
    lote = {"X5": {"aplicavel": True, "descricao": "sem substituto e sem autorizacao", "pacotes": ["com.exemplo.telemetria"]}}
    (lp.RAIZ / "scripts" / "lotes-bloatware.json").write_text(json.dumps(lote), encoding="utf-8")
    monkeypatch.setattr(lp.subprocess, "run", lambda cmd, **kw: (_ for _ in ()).throw(AssertionError(f"nao devia chamar adb: {cmd!r}")))
    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", "X5", "--remover"])
    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert "substituto declarado" in str(exc.value) and "com.exemplo.telemetria" in str(exc.value)


def test_remocao_autorizada_nao_libera_pacote_protegido(importa_script, monkeypatch):
    """A autorizacao do lote nao vale para a lista 'nunca desativar' (com.android.*, gms, launcher, teclado...)."""
    lp = importa_script("lote-pacotes.py")
    lote = {"X6": {"aplicavel": True, "descricao": "tenta remover a Play Store", "remocao_autorizada": "Rafael, 30/10",
                   "pacotes": ["com.android.vending"]}}
    (lp.RAIZ / "scripts" / "lotes-bloatware.json").write_text(json.dumps(lote), encoding="utf-8")
    monkeypatch.setattr(lp.subprocess, "run", lambda cmd, **kw: (_ for _ in ()).throw(AssertionError(f"nao devia chamar adb: {cmd!r}")))
    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", "X6", "--remover"])
    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert "protegido" in str(exc.value)


def test_aborta_se_substituto_nao_instalado_ou_ativo(importa_script, monkeypatch):
    """Lote COM substitutos (FOSS-navegador): --aplicar tem de abortar se o Fennec nao
    estiver instalado/ativo, ANTES de desativar o Chrome (lote-pacotes.py:81-85)."""
    lp = importa_script("lote-pacotes.py", copiar_lotes_json=True)

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c == "pm list packages":
            saida = "package:com.android.chrome"
        elif c == "pm list packages -d":
            saida = ""
        elif c == "pm list packages -e":
            saida = "package:com.android.chrome"  # Fennec (org.mozilla.fennec_fdroid) NAO esta ativo
        elif c.startswith(("pm disable-user", "pm enable")):
            raise AssertionError(f"nao deveria desativar nada sem o substituto pronto: {c!r}")
        else:
            raise AssertionError(f"comando nao mapeado no fake: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(lp.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", "FOSS-navegador", "--aplicar"])

    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert "substituto" in str(exc.value)


def _fake_lote(estado, ime="null", chamadas=None):
    """Aparelho falso para lote-pacotes: estado = {pacote: 'ativo'|'desativado'|'ausente'}; ime = valor de default_input_method."""

    def fake_run(cmd, **kw):
        c = cmd[2].strip()
        if chamadas is not None:
            chamadas.append(c)
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c == "dumpsys battery":
            saida = "level: 80\nstatus: 2"
        elif c == "pm list packages":
            saida = "\n".join(f"package:{p}" for p, e in estado.items() if e != "ausente")
        elif c == "pm list packages -d":
            saida = "\n".join(f"package:{p}" for p, e in estado.items() if e == "desativado")
        elif c == "pm list packages -e":
            saida = "\n".join(f"package:{p}" for p, e in estado.items() if e == "ativo")
        elif c == "settings get secure default_input_method":
            saida = ime
        elif c.startswith(("pm disable-user", "pm uninstall")):
            p = c.rsplit(" ", 1)[1]
            estado[p] = "desativado" if c.startswith("pm disable-user") else "ausente"
            saida = "ok"
        else:
            raise AssertionError(f"comando nao mapeado no fake: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")

    return fake_run


def test_remover_exige_substituto_ativo_mesmo_com_o_original_ja_desativado(importa_script, monkeypatch):
    lp = importa_script("lote-pacotes.py")
    lote = {"X7": {"aplicavel": True, "descricao": "original desativado, substituto sumiu", "pacotes": ["com.exemplo.alvo"],
                   "substitutos": {"com.exemplo.alvo": "org.exemplo.substituto"}}}
    (lp.RAIZ / "scripts" / "lotes-bloatware.json").write_text(json.dumps(lote), encoding="utf-8")
    chamadas = []
    estado = {"com.exemplo.alvo": "desativado", "org.exemplo.substituto": "desativado"}
    monkeypatch.setattr(lp.subprocess, "run", _fake_lote(estado, chamadas=chamadas))
    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", "X7", "--remover"])
    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert "substituto" in str(exc.value) and "org.exemplo.substituto" in str(exc.value)
    assert not any(c.startswith("pm uninstall") for c in chamadas)


def _lote_teclado(lp):
    lote = {"X8": {"aplicavel": True, "descricao": "teclados", "pacotes": ["com.google.android.inputmethod.latin",
                                                                         "com.samsung.android.honeyboard"],
                   "permitidos": ["com.google.android.inputmethod.latin", "com.samsung.android.honeyboard"]}}
    (lp.RAIZ / "scripts" / "lotes-bloatware.json").write_text(json.dumps(lote), encoding="utf-8")
    return {"com.google.android.inputmethod.latin": "ativo", "com.samsung.android.honeyboard": "ativo"}


def test_aplicar_aborta_se_o_teclado_em_uso_esta_na_fila(importa_script, monkeypatch):
    lp = importa_script("lote-pacotes.py")
    estado = _lote_teclado(lp)
    chamadas = []
    monkeypatch.setattr(lp.subprocess, "run", _fake_lote(
        estado, ime="com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME", chamadas=chamadas))
    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", "X8", "--aplicar"])
    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert "teclado" in str(exc.value) and "com.google.android.inputmethod.latin" in str(exc.value)
    assert not any(c.startswith("pm disable-user") for c in chamadas)


def test_aplicar_teclado_segue_se_o_teclado_em_uso_e_outro(importa_script, monkeypatch):
    lp = importa_script("lote-pacotes.py")
    estado = _lote_teclado(lp)
    monkeypatch.setattr(lp.subprocess, "run", _fake_lote(estado, ime="org.futo.inputmethod.latin/.LatinIME"))
    monkeypatch.setattr(sys, "argv", ["lote-pacotes.py", "X8", "--aplicar"])
    with pytest.raises(SystemExit) as exc:
        lp.main()
    assert exc.value.code == 0
    assert set(estado.values()) == {"desativado"}
