"""Testes do comando `guarda` do Termux, com bash de verdade e curl e pm falsos. Nenhum toca rede nem aparelho."""
import os
import pathlib
import subprocess
import time

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "celular-kit" / "bin" / "guarda"

CURL = """#!/bin/bash
# le o arquivo enviado e responde conforme FALSO_RESPOSTA; grava o que recebeu
cat > /dev/null
for a in "$@"; do case "$a" in @*) echo "${a#@}" >> "$FALSO_LOG" ;; esac; done
case "$FALSO_RESPOSTA" in
  fora) exit 7 ;;
  limpo) printf '{"estado": "limpo", "ameaca": ""}\\n200' ;;
  infectado) printf '{"estado": "infectado", "ameaca": "Android.Mal;rm"}\\n200' ;;
  ocupado) printf '{"erro": "ocupada"}\\n503' ;;
  estranho) printf 'qualquer coisa\\n200' ;;
esac
"""


@pytest.fixture
def cel(tmp_path):
    home, baixou, bin_ = tmp_path / "home", tmp_path / "Download", tmp_path / "bin"
    for d in (home / ".qwen", baixou, bin_):
        d.mkdir(parents=True)
    (home / ".qwen" / ".env").write_text("PONTE_PC_TOKEN=abc\n")
    (bin_ / "curl").write_text(CURL)
    (bin_ / "pm").write_text('#!/bin/bash\n[ -f "$FALSO_APPS" ] && cat "$FALSO_APPS"\n')
    for f in bin_.iterdir():
        f.chmod(0o755)
    log = tmp_path / "enviados"

    def roda(*args, resposta="limpo", **env):
        e = {"HOME": str(home), "PATH": f"{bin_}:/usr/bin:/bin", "GUARDA_PASTAS": str(baixou), "FALSO_LOG": str(log), "FALSO_RESPOSTA": resposta,
             "FALSO_APPS": str(tmp_path / "apps"), "GUARDA_LIMITE_MB": "1", "IA_CONECTA": "1", **env}
        p = subprocess.Popen(["/bin/bash", str(SCRIPT), *args], env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        saida, _ = p.communicate(timeout=60)
        return p.returncode, saida

    def enviados():
        return log.read_text().splitlines() if log.exists() else []

    import types
    return types.SimpleNamespace(roda=roda, home=home, baixou=baixou, enviados=enviados, tmp=tmp_path, base=home / ".cache" / "guarda")


def test_sintaxe():
    p = subprocess.Popen(["/bin/bash", "-n", str(SCRIPT)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    saida, _ = p.communicate(timeout=20)
    assert p.returncode == 0, saida


def test_limpo_fica(cel):
    a = cel.baixou / "foto.jpg"
    a.write_text("x")
    rc, s = cel.roda("varrer", str(a))
    assert rc == 0 and "Limpo" in s and a.exists()


def test_infectado_vai_para_a_quarentena_e_volta(cel):
    a = cel.baixou / "virus.apk"
    a.write_text("x")
    rc, s = cel.roda("varrer", str(a), resposta="infectado")
    assert rc == 1 and not a.exists() and "Isolado" in s
    rc, s = cel.roda("quarentena")
    assert "virus.apk" in s and "Android.Malrm" in s, "nome de ameaca vem limpo: so letras, numeros, ponto e traco"
    ident = s.split(" | ")[0]
    rc, s = cel.roda("devolver", ident)
    assert rc == 0 and a.read_text() == "x"
    assert "vazia" in cel.roda("quarentena")[1]


@pytest.mark.parametrize("resposta", ["fora", "ocupado", "estranho"])
def test_sem_resposta_certa_nunca_vira_limpo(cel, resposta):
    a = cel.baixou / "x.apk"
    a.write_text("x")
    rc, s = cel.roda("varrer", str(a), resposta=resposta)
    assert rc == 2 and "Limpo" not in s and "Nada foi dado como limpo" in s and a.exists()


def _notificacao(cel, corpo='echo "$*" >> "$HOME/notas"'):
    n = cel.tmp / "bin" / "termux-notification"
    n.write_text(f"#!/bin/bash\n{corpo}\n")
    n.chmod(0o755)
    return cel.home / "notas"


def test_isolar_avisa_no_celular(cel):
    notas = _notificacao(cel)
    a = cel.baixou / "v.apk"
    a.write_text("x")
    cel.roda("varrer", str(a), resposta="infectado")
    assert "arquivo isolado" in notas.read_text() and "Android.Malrm" in notas.read_text()


def test_prova_nao_avisa_no_celular(cel):
    notas = _notificacao(cel)
    falso = cel.tmp / "bin" / "curl"
    falso.write_text(CURL.replace("Android.Mal;rm", "Guarda.Teste.Inofensivo.UNOFFICIAL"))
    a = cel.baixou / "v.txt"
    a.write_text("x")
    cel.roda("varrer", str(a), resposta="infectado")
    assert not a.exists() and not notas.exists()


def test_aviso_que_trava_nao_prende_e_o_arquivo_isola(cel):
    _notificacao(cel, 'exit 9')
    a = cel.baixou / "v.apk"
    a.write_text("x")
    rc, s = cel.roda("varrer", str(a), resposta="infectado")
    assert rc == 1 and not a.exists() and "Isolado" in s
    assert "aviso nao saiu" in (cel.base / "registro").read_text()


def test_app_suspeito_avisa(cel):
    notas = _notificacao(cel)
    novo = cel.tmp / "novo.apk"
    novo.write_text("y")
    cel.base.mkdir(parents=True, exist_ok=True)
    (cel.base / "apps").write_text("com.exemplo.um\n")
    (cel.tmp / "apps").write_text(f"package:{novo}=com.exemplo.dois\n")
    _laco(cel, resposta="infectado")
    assert "com.exemplo.dois" in notas.read_text()


def test_devolver_nao_sobrescreve(cel):
    a = cel.baixou / "v.apk"
    a.write_text("velho")
    cel.roda("varrer", str(a), resposta="infectado")
    ident = cel.roda("quarentena")[1].split(" | ")[0]
    a.write_text("novo")
    rc, s = cel.roda("devolver", ident)
    assert rc == 1 and a.read_text() == "novo"
    assert ident in cel.roda("quarentena")[1]


@pytest.mark.parametrize("ident", ["", "../../etc/passwd", "a;b", "x y"])
def test_devolver_recusa_id_estranho(cel, ident):
    assert cel.roda("devolver", ident)[0] == 2


def _laco(cel, resposta="limpo", espera=3, inotify_pronto=False, **env):
    """Sobe o laco de verdade, com inotifywait falso que so dorme: testa a volta de leitura das pastas."""
    falso = cel.tmp / "bin" / "inotifywait"
    if not inotify_pronto:
        falso.write_text("#!/bin/bash\nexec sleep 300\n")
        falso.chmod(0o755)
    e = {"HOME": str(cel.home), "PATH": f"{cel.tmp}/bin:/usr/bin:/bin", "GUARDA_PASTAS": str(cel.baixou), "FALSO_LOG": str(cel.tmp / "enviados"), "FALSO_RESPOSTA": resposta,
         "FALSO_APPS": str(cel.tmp / "apps"), "GUARDA_LIMITE_MB": "1", "IA_CONECTA": "1", "GUARDA_CICLO": "1", **env}
    cel.base.mkdir(parents=True, exist_ok=True)
    (cel.base / "ligado").write_text("")
    p = subprocess.Popen(["/bin/bash", str(SCRIPT), "laco"], env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    time.sleep(espera)
    (cel.base / "ligado").unlink()
    time.sleep(1.5)
    try:
        os.killpg(p.pid, 9)
    except ProcessLookupError:
        pass
    p.communicate(timeout=10)


def test_primeira_vez_nao_manda_o_que_ja_estava_e_manda_o_que_chega(cel):
    velho = cel.baixou / "velho.apk"
    velho.write_text("x")
    os.utime(velho, (1000, 1000))
    falso = cel.tmp / "bin" / "inotifywait"
    falso.write_text("#!/bin/bash\nexec sleep 30\n")
    falso.chmod(0o755)
    env = {"GUARDA_CICLO": "1"}
    assert cel.roda("ligar", **env)[0] == 0
    novo = cel.baixou / "novo.apk"
    time.sleep(1.1)  # data do arquivo tem de ser posterior a marca
    novo.write_text("y")
    fim = time.time() + 12
    while time.time() < fim and str(novo) not in cel.enviados():
        time.sleep(0.5)
    cel.roda("desligar", **env)
    assert str(novo) in cel.enviados() and str(velho) not in cel.enviados()


def test_arquivo_avisado_vai_mesmo_com_data_antiga(cel):
    a = cel.baixou / "veio-do-bluetooth.apk"
    a.write_text("x")
    os.utime(a, (1000, 1000))
    cel.base.mkdir(parents=True, exist_ok=True)
    (cel.base / "marca").write_text("")
    falso = cel.tmp / "bin" / "inotifywait"
    falso.write_text(f"#!/bin/bash\necho '{a}'\nexec sleep 300\n")
    falso.chmod(0o755)
    _laco(cel, espera=5, inotify_pronto=True)
    assert str(a) in cel.enviados()


def test_arquivo_avisado_espera_o_pc_voltar(cel):
    a = cel.baixou / "p.apk"
    a.write_text("x")
    os.utime(a, (1000, 1000))
    cel.base.mkdir(parents=True, exist_ok=True)
    (cel.base / "marca").write_text("")
    (cel.base / "pendentes").write_text(f"{a}\n")
    _laco(cel, resposta="fora", espera=2)
    assert str(a) in (cel.base / "pendentes").read_text()
    _laco(cel, resposta="limpo", espera=2)
    assert (cel.base / "pendentes").read_text() == "" and str(a) in cel.enviados()


def test_desligar_nao_deixa_vigia_orfao(cel):
    falso = cel.tmp / "bin" / "inotifywait"
    falso.write_text("#!/bin/bash\nexec sleep 77\n")
    falso.chmod(0o755)
    assert cel.roda("ligar")[0] == 0
    time.sleep(1)
    pid = int((cel.base / "inotify.pid").read_text())
    assert os.path.exists(f"/proc/{pid}")
    assert cel.roda("desligar")[0] == 0
    time.sleep(0.5)
    assert not os.path.exists(f"/proc/{pid}") and not (cel.base / "inotify.pid").exists()


def test_volta_varre_uma_vez_so(cel):
    a = cel.baixou / "novo.apk"
    a.write_text("x")
    _laco(cel)
    assert cel.enviados().count(f"{a}") == 1, "arquivo sem mudanca nao pode gastar dados de novo"
    assert a.exists() and (cel.base / "marca").exists()


def test_ignora_temporario_e_planilha_de_notas(cel):
    for n in (".pending-123-a.apk", "b.crdownload", "MAPAO_2B.xlsx", "mapao_x.xlsx"):
        (cel.baixou / n).write_text("x")
    _laco(cel)
    assert cel.enviados() == []


def test_pc_fora_nao_avanca_a_marca(cel):
    a = cel.baixou / "n.apk"
    a.write_text("x")
    _laco(cel, resposta="fora")
    assert a.exists() and not (cel.base / "marca").exists(), "com o PC fora o arquivo tem de continuar pendente"
    assert not (cel.base / "vistos").exists()
    assert "esperando" in (cel.base / "registro").read_text()


def test_pendente_e_varrido_quando_o_pc_volta(cel):
    a = cel.baixou / "n.apk"
    a.write_text("x")
    _laco(cel, resposta="fora")
    _laco(cel, resposta="limpo")
    assert (cel.base / "marca").exists() and str(a) in cel.enviados()


def test_laco_isola_o_infectado(cel):
    a = cel.baixou / "m.apk"
    a.write_text("x")
    _laco(cel, resposta="infectado")
    assert not a.exists() and list((cel.base / "quarentena").glob("*.quarentena"))


def test_grande_nao_vai_e_fica_registrado(cel):
    a = cel.baixou / "grande.iso"
    with open(a, "wb") as f:
        f.truncate(2 * 1024 * 1024)
    _laco(cel)
    assert cel.enviados() == [] and "NAO varrido" in (cel.base / "registro").read_text()


def test_apps_primeira_vez_so_guarda_a_referencia(cel):
    apk = cel.tmp / "base.apk"
    apk.write_text("x")
    (cel.tmp / "apps").write_text(f"package:{apk}=com.exemplo.um\n")
    _laco(cel)
    assert cel.enviados() == [] and "com.exemplo.um" in (cel.base / "apps").read_text()


def test_app_novo_e_varrido_uma_vez_e_o_antigo_nao(cel):
    apk, novo = cel.tmp / "base.apk", cel.tmp / "novo.apk"
    apk.write_text("x")
    novo.write_text("y")
    cel.base.mkdir(parents=True, exist_ok=True)
    (cel.base / "apps").write_text("com.exemplo.um\n")
    (cel.tmp / "apps").write_text(f"package:{apk}=com.exemplo.um\npackage:{novo}=com.exemplo.dois\n")
    _laco(cel)
    assert cel.enviados().count(str(novo)) == 1 and str(apk) not in cel.enviados()


def test_app_novo_suspeito_fica_registrado(cel):
    novo = cel.tmp / "novo.apk"
    novo.write_text("y")
    cel.base.mkdir(parents=True, exist_ok=True)
    (cel.base / "apps").write_text("com.exemplo.um\n")
    (cel.tmp / "apps").write_text(f"package:{novo}=com.exemplo.dois\n")
    _laco(cel, resposta="infectado")
    assert "APP SUSPEITO com.exemplo.dois" in (cel.base / "registro").read_text()


def test_varredura_inteira_conta_e_inclui_apps(cel):
    a = cel.baixou / "d.pdf"
    a.write_text("x")
    apk = cel.tmp / "base.apk"
    apk.write_text("y")
    (cel.tmp / "apps").write_text(f"package:{apk}=com.exemplo.um\n")
    rc, s = cel.roda("varredura")
    assert rc == 0 and "2 limpos" in s and "0 suspeitos" in s


def test_varredura_para_com_pc_fora_sem_dizer_limpo(cel):
    (cel.baixou / "d.pdf").write_text("x")
    rc, s = cel.roda("varredura", resposta="fora")
    assert rc == 2 and "Nada do que faltava foi dado como limpo" in s


def test_token_nao_aparece_na_linha_de_comando():
    texto = SCRIPT.read_text(encoding="utf-8")
    assert "curl -sS -K -" in texto and "Bearer $t" not in texto.replace('Bearer %s"\\n\' "$t"', "")


# ------------------------------------------------- menu `antivirus` (texto, setas ou numero)

def _menu(cel, teclas, resposta="limpo", **env):
    link = cel.tmp / "bin" / "antivirus"
    if not link.exists():
        link.symlink_to(SCRIPT)
    e = {"HOME": str(cel.home), "PATH": f"{cel.tmp}/bin:/usr/bin:/bin", "GUARDA_PASTAS": str(cel.baixou), "FALSO_LOG": str(cel.tmp / "enviados"),
         "FALSO_RESPOSTA": resposta, "FALSO_APPS": str(cel.tmp / "apps"), "GUARDA_LIMITE_MB": "1", "IA_CONECTA": "1", **env}
    p = subprocess.Popen(["/bin/bash", str(link)], env=e, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    saida, _ = p.communicate(teclas, timeout=60)
    return p.returncode, saida


CIMA, BAIXO = "\x1b[A", "\x1b[B"


def test_menu_abre_mostra_as_opcoes_em_verde_e_sai(cel):
    rc, s = _menu(cel, "q")
    assert rc == 0 and "GUARDA" in s and "Iniciar varredura completa no dispositivo" in s and "\x1b[38;2;0;255;0m" in s
    assert "tempo real DESLIGADO" in s


def test_menu_sai_no_fim_da_entrada_sem_laco(cel):
    rc, _ = _menu(cel, "")
    assert rc == 0


def test_menu_numero_roda_a_situacao(cel):
    rc, s = _menu(cel, "1\nq")
    assert "Guarda: DESLIGADO" in s and "Quarentena: 0" in s


def test_menu_seta_para_baixo_e_enter_abre_a_varredura_e_nao_aceita_sem_confirmar(cel):
    (cel.baixou / "a.pdf").write_text("x")
    rc, s = _menu(cel, BAIXO + "\n" + "2" + "q")
    assert "Sim, iniciar agora" in s and "1 arquivo(s)" in s
    assert cel.enviados() == [], "sem o sim nada vai ao PC"


def test_menu_varredura_confirmada_varre(cel):
    (cel.baixou / "a.pdf").write_text("x")
    rc, s = _menu(cel, "2" + "1" + "\n" + "q")
    assert str(cel.baixou / "a.pdf") in cel.enviados() and "1 limpos" in s


def test_menu_seta_para_cima_no_topo_vai_ao_sair(cel):
    rc, s = _menu(cel, CIMA + "\n")
    assert rc == 0 and "❯ 9. Sair" in s and "Guarda:" not in s


def test_menu_varrer_arquivo_pela_lista(cel):
    a = cel.baixou / "novo.apk"
    a.write_text("x")
    rc, s = _menu(cel, "3" + "1" + "\n" + "q", resposta="infectado")
    assert "novo.apk" in s and not a.exists() and "Isolado" in s


def test_menu_devolver_pede_confirmacao_e_devolve(cel):
    a = cel.baixou / "v.apk"
    a.write_text("x")
    cel.roda("varrer", str(a), resposta="infectado")
    _menu(cel, "5" + "1" + "1" + "q")  # escolhe o arquivo e responde "Nao, deixar isolado"
    assert not a.exists()
    rc, s = _menu(cel, "5" + "1" + "2" + "\n" + "q")
    assert a.read_text() == "x" and "Devolvido" in s


def test_menu_ligar_e_desligar_com_confirmacao(cel):
    falso = cel.tmp / "bin" / "inotifywait"
    falso.write_text("#!/bin/bash\nexec sleep 30\n")
    falso.chmod(0o755)
    rc, s = _menu(cel, "6" + "\n" + "q")
    assert "Guarda ligado" in s
    rc, s = _menu(cel, "6" + "1" + "q")  # "Nao, manter ligada"
    assert "Desligar a proteção em tempo real" in s and cel.roda("status")[1].startswith("Guarda: ligado")
    rc, s = _menu(cel, "6" + "2" + "\n" + "q")
    assert "Guarda desligado" in s


def test_menu_teclado_nao_e_comido_pelo_curl(cel):
    """Um curl que le a entrada padrao nao pode engolir as teclas do menu."""
    rc, s = _menu(cel, "1\n1\nq")
    assert s.count("Guarda: DESLIGADO") == 2
