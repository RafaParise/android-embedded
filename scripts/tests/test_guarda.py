"""Testes de scripts/guarda.py e do /v1/varrer da ponte. O motor e um clamd FALSO numa porta livre: nenhum teste liga o ClamAV nem mexe nas pastas do Rafael."""
import http.client
import json
import os
import socket
import struct
import threading
import types

import pytest

TOKEN = "t0ken-de-teste-" + "y" * 30


class ClamdFalso:
    """Fala o protocolo de verdade: zPING, zSHUTDOWN e zINSTREAM com pedacos."""

    def __init__(self, resposta=b"stream: OK\0"):
        self.resposta, self.recebido, self.desligou = resposta, b"", False
        self.s = socket.socket()
        self.s.bind(("127.0.0.1", 0))
        self.s.listen(5)
        self.porta = self.s.getsockname()[1]
        threading.Thread(target=self._laco, daemon=True).start()

    def _laco(self):
        while True:
            try:
                c, _ = self.s.accept()
            except OSError:
                return
            with c:
                self._atende(c)

    def _le(self, c, n):
        b = b""
        while len(b) < n:
            d = c.recv(n - len(b))
            if not d:
                break
            b += d
        return b

    def _atende(self, c):
        cmd = b""
        while not cmd.endswith(b"\0"):
            d = c.recv(1)
            if not d:
                return
            cmd += d
        if cmd == b"zPING\0":
            c.sendall(b"PONG\0")
        elif cmd == b"zSHUTDOWN\0":
            self.desligou = True
        elif cmd == b"zINSTREAM\0":
            while True:
                n = struct.unpack("!L", self._le(c, 4))[0]
                if n == 0:
                    break
                self.recebido += self._le(c, n)
            c.sendall(self.resposta)

    def fecha(self):
        self.s.close()


@pytest.fixture
def g(importa_script):
    return importa_script("guarda.py")


@pytest.fixture
def mundo(g, tmp_path):
    amb = g.Ambiente(local=tmp_path / "local", perfil=tmp_path / "perfil")
    clamd = ClamdFalso()
    motor = g.Motor(amb, porta=clamd.porta, memoria=lambda: 8000, inicia=lambda: pytest.fail("nao devia subir: o falso ja esta vivo"))
    yield types.SimpleNamespace(g=g, amb=amb, clamd=clamd, motor=motor, tmp=tmp_path)
    clamd.fecha()


def _arq(mundo, nome="a.exe", dados=b"conteudo"):
    c = mundo.tmp / "perfil" / "Downloads" / nome
    c.parent.mkdir(parents=True, exist_ok=True)
    c.write_bytes(dados)
    return c


@pytest.mark.parametrize("resposta, esperado", [
    ("stream: OK\0", ("limpo", "")),
    ("stream: Eicar-Signature FOUND\0", ("infectado", "Eicar-Signature")),
    ("INSTREAM size limit exceeded. ERROR\0", "erro"),
    ("", "erro"),
    ("stream: OK e mais alguma coisa", "erro"),
    ("OK", "erro"),
    ("stream: ERROR", "erro"),
])
def test_so_resposta_exata_e_limpo(g, resposta, esperado):
    r = g.interpreta(resposta)
    assert (r[0] if isinstance(esperado, str) else r) == esperado


def test_motor_manda_tudo_e_acha_limpo(mundo):
    assert mundo.motor.varre([b"abc", b"", b"def"]) == ("limpo", "")
    assert mundo.clamd.recebido == b"abcdef"


def test_com_pouca_memoria_nao_sobe_o_motor(g, tmp_path):
    subiu = []
    m = g.Motor(g.Ambiente(local=tmp_path, perfil=tmp_path), porta=1, memoria=lambda: g.MEMORIA_MIN_MB - 1, inicia=lambda: subiu.append(1))
    with pytest.raises(g.SemMemoria):
        m.garante()
    assert not subiu


def test_motor_que_nao_responde_e_erro_e_nao_limpo(g, tmp_path):
    relogio = iter([0, 1, 2, 999])
    m = g.Motor(g.Ambiente(local=tmp_path, perfil=tmp_path), porta=1, memoria=lambda: 9000, inicia=lambda: None)
    with pytest.raises(g.MotorFora):
        m.garante(espera=5, dorme=lambda s: None, relogio=lambda: next(relogio))


def test_motor_so_escuta_no_proprio_pc(mundo):
    m = mundo.motor
    m._escreve_conf()
    texto = mundo.amb.conf.read_text(encoding="ascii")
    assert "TCPAddr 127.0.0.1\n" in texto and "StreamMaxLength 400M" in texto and "MaxThreads 2" in texto


def test_assinatura_de_prova_casa_com_o_texto(mundo):
    import hashlib

    pasta = mundo.amb.clam / "database"
    pasta.mkdir(parents=True)
    mundo.motor.garante_assinatura_teste()
    md5, tam, nome = (pasta / "guarda-teste.hdb").read_text(encoding="ascii").strip().split(":")
    assert md5 == hashlib.md5(mundo.g.TEXTO_TESTE).hexdigest() and int(tam) == len(mundo.g.TEXTO_TESTE) and nome == mundo.g.ASSINATURA_TESTE


def test_motor_ocioso_desce_e_usado_agora_fica(mundo):
    mundo.motor.varre([b"x"])
    assert mundo.motor.para_se_ocioso() is False and not mundo.clamd.desligou
    agora = float(mundo.amb.ultimo_uso.read_text(encoding="ascii"))
    assert mundo.motor.para_se_ocioso(agora + mundo.g.OCIOSO_S + 1) is True
    assert mundo.clamd.desligou


def test_le_eventos_do_windows(g):
    def bloco(prox, acao, nome):
        n = nome.encode("utf-16-le")
        return struct.pack("<III", prox, acao, len(n)) + n

    um = bloco(0, 1, "pasta\\novo.exe")
    primeiro = bloco(0, 4, "velho.txt")
    prox = len(primeiro) + (4 - len(primeiro) % 4) % 4
    dois = bloco(prox, 4, "velho.txt").ljust(prox, b"\0") + bloco(0, 5, "novo.txt")
    assert g.le_eventos(um) == [(1, "pasta\\novo.exe")]
    assert g.le_eventos(dois) == [(4, "velho.txt"), (5, "novo.txt")]
    assert g.le_eventos(b"") == [] and g.le_eventos(um[:14]) == []
    assert 2 not in g.ACOES_DE_ARQUIVO_NOVO and 4 not in g.ACOES_DE_ARQUIVO_NOVO and {1, 3, 5} <= g.ACOES_DE_ARQUIVO_NOVO


@pytest.mark.parametrize("nome, sim", [
    ("setup.exe", False), ("x.crdownload", True), ("x.PART", True), ("desktop.ini", True), ("a.quarentena", True),
    ("MAPAO_2B.xlsx", True), ("mapao_turma.xlsx", True), ("mapa.xlsx", False), ("MAPAO_notas.pdf", False),
])
def test_ignorar(g, nome, sim):
    assert g.ignorar("/x/" + nome) is sim


def test_planilha_de_notas_nunca_vai_ao_motor(mundo):
    c = _arq(mundo, "MAPAO_2B.xlsx")
    assert mundo.g.processa(mundo.amb, mundo.motor, str(c)) == "ignorado"
    assert mundo.clamd.recebido == b""


def test_fila_espera_parar_de_mudar(mundo):
    c = _arq(mundo)
    f = mundo.g.Fila(quieto=2)
    f.aviso(c, 100)
    assert f.prontos(100) == []  # primeira olhada so anota
    assert f.prontos(101) == []
    assert f.prontos(103) == [str(c)]
    assert f.prontos(103.5) == [], "em andamento nao sai duas vezes"


def test_fila_recomeca_se_o_arquivo_cresce(mundo):
    c = _arq(mundo)
    f = mundo.g.Fila(quieto=2)
    f.aviso(c, 100)
    f.prontos(100)
    c.write_bytes(b"conteudo maior agora")
    assert f.prontos(103) == []
    assert f.prontos(105) == [str(c)]


def test_fila_esquece_o_que_sumiu_e_o_temporario(mundo):
    c = _arq(mundo)
    f = mundo.g.Fila()
    f.aviso(c, 100)
    f.aviso(_arq(mundo, "y.crdownload"), 100)
    assert len(f) == 1
    c.unlink()
    assert f.prontos(200) == [] and len(f) == 0


def test_limpo_fica_no_lugar_sem_registrar_o_nome(mundo):
    c = _arq(mundo, "segredo-pessoal.pdf")
    assert mundo.g.processa(mundo.amb, mundo.motor, str(c)) == "limpo"
    assert c.exists() and mundo.clamd.recebido == b"conteudo"
    assert "segredo-pessoal" not in mundo.amb.registro.read_text(encoding="utf-8")


def _infectado(mundo, nome="Win.Trojan.X"):
    mundo.clamd.resposta = f"stream: {nome} FOUND\0".encode()


def test_infectado_vai_para_a_quarentena_avisa_e_volta(mundo):
    _infectado(mundo)
    c = _arq(mundo)
    avisos = []
    assert mundo.g.processa(mundo.amb, mundo.motor, str(c), lambda a, t, x: avisos.append(x)) == "infectado"
    assert not c.exists() and len(avisos) == 1 and "Win.Trojan.X" in avisos[0]
    (item,) = mundo.g.lista_quarentena(mundo.amb)
    assert item["origem"] == str(c) and item["ameaca"] == "Win.Trojan.X"
    assert (mundo.amb.quarentena / item["arquivo"]).read_bytes() == b"conteudo", "quarentena nao altera nem apaga"
    assert mundo.g.devolve(mundo.amb, item["id"]) == c and c.read_bytes() == b"conteudo"
    assert mundo.g.lista_quarentena(mundo.amb) == []
    assert mundo.g.processa(mundo.amb, mundo.motor, str(c), lambda *a: pytest.fail("ja liberado nao avisa")) == "liberado"
    assert c.exists(), "o que voce devolveu nao pode ser levado de novo"


def test_liberado_vale_so_para_aquele_conteudo(mundo):
    _infectado(mundo)
    c = _arq(mundo)
    mundo.g.processa(mundo.amb, mundo.motor, str(c), lambda *a: None)
    (item,) = mundo.g.lista_quarentena(mundo.amb)
    mundo.g.devolve(mundo.amb, item["id"])
    c.write_bytes(b"outro conteudo")
    assert mundo.g.processa(mundo.amb, mundo.motor, str(c), lambda *a: None) == "infectado"


def test_devolver_nao_sobrescreve_nem_aceita_id_estranho(mundo):
    _infectado(mundo)
    c = _arq(mundo)
    mundo.g.processa(mundo.amb, mundo.motor, str(c), lambda *a: None)
    (item,) = mundo.g.lista_quarentena(mundo.amb)
    c.write_bytes(b"novo")
    with pytest.raises(ValueError):
        mundo.g.devolve(mundo.amb, item["id"])
    assert c.read_bytes() == b"novo" and len(mundo.g.lista_quarentena(mundo.amb)) == 1
    with pytest.raises(ValueError):
        mundo.g.devolve(mundo.amb, "../../x")


def test_nome_perigoso_nao_escapa_da_quarentena(mundo):
    _infectado(mundo)
    c = _arq(mundo, "a b;$(x)&.exe")
    mundo.g.processa(mundo.amb, mundo.motor, str(c), lambda *a: None)
    (item,) = mundo.g.lista_quarentena(mundo.amb)
    assert (mundo.amb.quarentena / item["arquivo"]).parent == mundo.amb.quarentena
    assert not set(item["arquivo"]) & set(";$()&")


def test_prova_nao_avisa_ninguem(mundo):
    _infectado(mundo, mundo.g.ASSINATURA_TESTE + ".UNOFFICIAL")  # assim o clamd devolve
    c = _arq(mundo)
    assert mundo.g.processa(mundo.amb, mundo.motor, str(c), lambda *a: pytest.fail("prova nao avisa")) == "infectado"


def test_erro_do_motor_nao_vira_limpo_e_fica_na_fila(mundo):
    mundo.clamd.resposta = b"size limit exceeded. ERROR\0"
    c = _arq(mundo)
    assert mundo.g.processa(mundo.amb, mundo.motor, str(c)) == "erro"
    assert c.exists() and mundo.g.lista_quarentena(mundo.amb) == []
    f = mundo.g.Fila(quieto=0)
    f.aviso(c, 100)
    f.prontos(100)
    mundo.g.trata_fila(mundo.amb, mundo.motor, f, 101)
    assert len(f) == 1, "tem de tentar de novo"
    for t in range(1000, 1000 + 500 * mundo.g.TENTATIVAS, 500):
        f.prontos(t)
        mundo.g.trata_fila(mundo.amb, mundo.motor, f, t + 1)
    assert len(f) == 0 and "nao-varrido" in mundo.amb.registro.read_text(encoding="utf-8")


def test_sem_memoria_espera_sem_gastar_tentativa(mundo):
    c = _arq(mundo)
    f = mundo.g.Fila(quieto=0)
    f.aviso(c, 100)
    f.prontos(100)

    def falta():
        raise mundo.g.SemMemoria("pouca")

    mundo.motor.garante = falta
    for t in range(101, 101 + 1000 * (mundo.g.TENTATIVAS + 2), 1000):
        f.prontos(t)
        f.prontos(t + 1)
        mundo.g.trata_fila(mundo.amb, mundo.motor, f, t + 1)
    assert len(f) == 1 and f.itens[str(c)]["tentativas"] == 0, "falta de memoria nao pode fazer perder o arquivo"


def test_arquivo_grande_e_registrado_sem_varrer(mundo):
    c = _arq(mundo)
    os.truncate(c, mundo.g.MAX_ARQUIVO + 1)
    assert mundo.g.processa(mundo.amb, mundo.motor, str(c)) == "grande"
    assert mundo.clamd.recebido == b"" and "grande-demais" in mundo.amb.registro.read_text(encoding="utf-8")


def test_atalho_e_vazio_nao_vao(mundo):
    alvo = _arq(mundo)
    atalho = alvo.with_name("atalho")
    atalho.symlink_to(alvo)
    vazio = _arq(mundo, "vazio", b"")
    assert mundo.g.processa(mundo.amb, mundo.motor, str(atalho)) == "ignorado"
    assert mundo.g.processa(mundo.amb, mundo.motor, str(vazio)) == "ignorado"


def test_recupera_o_que_chegou_com_a_vigia_parada(mundo):
    velho, novo, movido = _arq(mundo, "velho"), _arq(mundo, "novo"), _arq(mundo, "movido")
    datas = {"velho": (1000, 1000), "novo": (3000, 1000), "movido": (1000, 3000)}  # movido: data antiga, mas chegou agora
    verdadeiro = os.lstat

    def falso(c):
        nome = os.path.basename(c)
        return types.SimpleNamespace(st_mtime=datas[nome][0], st_ctime=datas[nome][1]) if nome in datas else verdadeiro(c)

    mundo.g.os.lstat = falso
    try:
        achados = sorted(mundo.g.arquivos_recentes([novo.parent], 2000))
    finally:
        mundo.g.os.lstat = verdadeiro
    assert achados == [str(movido), str(novo)] and str(velho) not in achados


NETSTAT = """
  TCP    0.0.0.0:3389           0.0.0.0:0              LISTENING       100
  TCP    127.0.0.1:20128        0.0.0.0:0              LISTENING       200
  TCP    0.0.0.0:49664          0.0.0.0:0              LISTENING       300
  TCP    100.64.1.2:20130       0.0.0.0:0              LISTENING       400
  TCP    [::1]:1234             [::]:0                 LISTENING       200
  TCP    [::]:1716              [::]:0                 LISTENING       500
  TCP    192.168.1.2:50000      8.8.8.8:443            ESTABLISHED     600
"""


def test_portas_so_o_que_escuta_para_fora(g):
    p = {"100": "svchost.exe", "200": "node.exe", "300": "lsass.exe", "400": "tailscaled.exe", "500": "kdeconnectd.exe"}
    assert g.analisa_portas(NETSTAT, p) == {"svchost:3389", "lsass:dinamica", "tailscaled:20130", "kdeconnectd:1716"}


def test_porta_nova_avisa_uma_vez(mundo):
    a = mundo.amb
    assert mundo.g.compara_portas(a, {"svchost:3389"}) == [], "a primeira vez so guarda"
    assert mundo.g.compara_portas(a, {"svchost:3389", "estranho:4444"}) == ["estranho:4444"]
    assert mundo.g.compara_portas(a, {"svchost:3389", "estranho:4444"}) == []
    assert mundo.g.compara_portas(a, {"svchost:9999"}) == [], "porta de servico do sistema nao vira aviso"


def test_aparelho_novo_na_vpn_avisa_uma_vez(mundo):
    a = mundo.amb
    um = {"Peer": {"x": {"PublicKey": "k1", "HostName": "celular"}}}
    dois = {"Peer": {"x": {"PublicKey": "k1", "HostName": "celular"}, "y": {"PublicKey": "k2", "HostName": "intruso"}}}
    assert mundo.g.compara_pares(a, um) == []
    assert mundo.g.compara_pares(a, dois) == ["intruso"]
    assert mundo.g.compara_pares(a, dois) == []


def test_mesmo_aparelho_com_outro_nome_nao_engana_e_chave_nova_avisa(mundo):
    a = mundo.amb
    mundo.g.compara_pares(a, {"Peer": {"x": {"PublicKey": "k1", "HostName": "celular"}}})
    assert mundo.g.compara_pares(a, {"Peer": {"x": {"PublicKey": "k9", "HostName": "celular"}}}) == ["celular"]


@pytest.mark.parametrize("dados, trecho", [
    ({"BackendState": "Stopped"}, "nao esta ligada"),
    ({"BackendState": "Running", "Self": {"AllowedIPs": ["100.64.0.1/32"]}}, "nao esta aprovado"),
    ({"BackendState": "Running", "Self": {"AllowedIPs": ["0.0.0.0/0"]}, "Peer": {"x": {"ExitNode": True, "HostName": "outro"}}}, "por outro"),
])
def test_problemas_da_vpn(g, dados, trecho):
    assert any(trecho in r for r in g.problemas_da_vpn(dados))


def test_vpn_certa_nao_reclama(g):
    assert g.problemas_da_vpn({"BackendState": "Running", "Self": {"AllowedIPs": ["0.0.0.0/0", "::/0"]}, "Peer": {"x": {"ExitNode": False}}}) == []


@pytest.mark.parametrize("regras, abertos", [
    ([{"perfil": "Any", "remoto": "100.64.0.0/255.192.0.0"}], 0),
    ([{"perfil": "Domain, Private", "remoto": "LocalSubnet,100.64.0.0/255.192.0.0"}], 0),
    ([{"perfil": "Public", "remoto": "Any"}], 1),
    ([{"perfil": "Any", "remoto": "LocalSubnet"}], 1),
])
def test_rdp_em_rede_publica(g, regras, abertos):
    assert len(g.rdp_exposto(regras)) == abertos


def test_consultar_a_vigia_muitas_vezes_nao_a_faz_parecer_desligada(g):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    porta = s.getsockname()[1]
    threading.Thread(target=g._atende_trava, args=(s,), daemon=True).start()
    for _ in range(30):
        with socket.create_connection(("127.0.0.1", porta), timeout=2):
            pass
    s.close()


def test_varredura_conta_sem_fingir_e_pula_o_que_nao_interessa(mundo):
    c = _arq(mundo)
    (c.parent / "node_modules").mkdir()
    (c.parent / "node_modules" / "z.js").write_bytes(b"z")
    (c.parent / "Backups").mkdir()
    (c.parent / "Backups" / "sms.db").write_bytes(b"z")
    _arq(mundo, "MAPAO_x.xlsx")
    conta = mundo.g.varredura(mundo.amb, [c.parent], mundo.motor, memoria=lambda: 8000, escreve=lambda t: None)
    assert conta["limpo"] == 1 and conta["ignorado"] == 1 and conta["erro"] == 0
    assert mundo.clamd.recebido == b"conteudo"


def test_varredura_espera_com_a_memoria_acabando(mundo):
    c = _arq(mundo)
    medidas = iter([100, 100, 8000, 8000])
    dormiu = []
    mundo.g.varredura(mundo.amb, [c.parent], mundo.motor, memoria=lambda: next(medidas), dorme=dormiu.append, escreve=lambda t: None)
    assert dormiu == [60, 60]


def test_varredura_com_motor_fora_para_e_nao_diz_limpo(mundo):
    c = _arq(mundo)

    def fora():
        raise mundo.g.MotorFora("x")

    mundo.motor.garante = fora
    conta = mundo.g.varredura(mundo.amb, [c.parent], mundo.motor, memoria=lambda: 8000, escreve=lambda t: None)
    assert conta["limpo"] == 0 and conta["erro"] == 1


# ------------------------------------------------- rota da ponte

@pytest.fixture
def api(importa_script, tmp_path, monkeypatch, g):
    m = importa_script("ponte-pc.py")
    amb = g.Ambiente(local=tmp_path / "local", perfil=tmp_path / "perfil")
    clamd = ClamdFalso()
    avisos = []
    falso = types.SimpleNamespace(
        Ambiente=lambda: amb, Motor=lambda a: g.Motor(a, porta=clamd.porta, memoria=lambda: 8000, inicia=lambda: None),
        SemMemoria=g.SemMemoria, MotorFora=g.MotorFora, PEDACO=g.PEDACO, registra=g.registra, ASSINATURA_TESTE=g.ASSINATURA_TESTE,
        avisa=lambda a, t, x: avisos.append(x),
    )
    monkeypatch.setattr(m, "_guarda", lambda: falso)
    proj, base = tmp_path / "proj", tmp_path / "base"
    proj.mkdir()
    base.mkdir()
    srv = m.cria_servidor(m.Ponte(proj, base), TOKEN, 0, "127.0.0.1")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    porta = srv.server_address[1]

    def chama(corpo=b"dados", token=TOKEN):
        c = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
        h = {"Authorization": f"Bearer {token}"} if token else {}
        c.request("POST", "/v1/varrer", body=corpo, headers=h)
        r = c.getresponse()
        d = r.read()
        c.close()
        return r.status, json.loads(d)

    yield types.SimpleNamespace(chama=chama, clamd=clamd, avisos=avisos, falso=falso, m=m, amb=amb)
    srv.shutdown()
    srv.server_close()
    clamd.fecha()


def test_ponte_varre_sem_gravar_nada(api):
    assert api.chama(b"do celular") == (200, {"estado": "limpo", "ameaca": ""})
    assert api.clamd.recebido == b"do celular"


def test_ponte_exige_token(api):
    assert api.chama(token="errado")[0] == 401
    assert api.chama(token=None)[0] == 401
    assert api.clamd.recebido == b""


def test_ponte_acusa_e_avisa(api):
    api.clamd.resposta = b"stream: Android.Bad FOUND\0"
    assert api.chama() == (200, {"estado": "infectado", "ameaca": "Android.Bad"})
    assert api.avisos == ["Android.Bad"]


def test_ponte_prova_nao_avisa(api):
    api.clamd.resposta = b"stream: Guarda.Teste.Inofensivo.UNOFFICIAL FOUND\0"
    assert api.chama()[1]["estado"] == "infectado"
    assert api.avisos == []


def test_ponte_com_motor_em_erro_nunca_diz_limpo(api):
    api.clamd.resposta = b"size limit. ERROR\0"
    s, j = api.chama()
    assert s == 502 and "estado" not in j


def test_ponte_com_pouca_memoria_pede_para_tentar_depois(api, g):
    class M:
        def __init__(self, a):
            pass

        def garante(self):
            raise g.SemMemoria("pouca")

    api.falso.Motor = M
    s, j = api.chama()
    assert s == 503 and "estado" not in j


def test_ponte_recusa_vazio_e_grande(api, monkeypatch):
    assert api.chama(b"")[0] == 413
    monkeypatch.setattr(api.m, "MAX_VARRER", 3)
    assert api.chama(b"1234")[0] == 413
    assert api.clamd.recebido == b""


def test_ponte_libera_a_vaga_depois_de_erro(api):
    api.clamd.resposta = b"x ERROR\0"
    for _ in range(4):
        assert api.chama()[0] == 502, "vaga presa travaria a varredura para sempre"


# ------------------------------------------------- menu do PC

def _limpo(texto):
    import re as _re
    return _re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", texto)


def test_logo_tem_linhas_do_mesmo_tamanho_e_sombra_escura(g):
    assert len({len(l) for l in g.LOGO}) == 1
    linhas = g.logo_colorido()
    assert all(g.VERDE in l and g.SOMBRA in l for l in linhas[:5])
    assert [_limpo(l).strip() for l in linhas] == [l.strip() for l in g.LOGO]


@pytest.mark.parametrize("tecla, esperado", [
    ("\xe0H", "cima"), ("\x00H", "cima"), ("\xe0P", "baixo"), ("\r", "ok"), ("\x1b", "sair"), ("q", "sair"),
    ("3", "3"), ("0", "0"), ("x", "nada"), ("\xe0K", "nada"),
])
def test_traduz_teclas_do_windows(g, tecla, esperado):
    assert g.traduz(tecla) == esperado


def test_desenha_marca_so_o_escolhido_e_cabe_na_largura(g):
    tela = g.desenha("O que fazer?", ["Um", "Dois", "Sair"], 1, ["linha 1", "linha 2"])
    assert tela.count(g.SEL) == 1 and "► 2  Dois" in _limpo(tela) and "0  Sair" in _limpo(tela)
    assert max(len(l) for l in _limpo(tela).splitlines()) <= g.LARGURA + 2


@pytest.mark.parametrize("teclas, esperado", [
    (["ok"], 0), (["baixo", "ok"], 1), (["cima", "ok"], 2), (["2"], 1), (["0"], 2), (["sair"], -1), (["9", "nada", "1"], 0),
])
def test_escolhe(g, teclas, esperado):
    t = iter(teclas)
    assert g.escolhe("?", ["A", "B", "Sair"], ["x"], lambda: next(t), lambda s: None) == esperado


class _Painel:
    def __init__(self, g, amb, teclas, textos=()):
        self.rodou = []
        t, tx = iter(teclas), iter(textos)
        self.p = g.Painel(amb, tecla=lambda: next(t), escreve=lambda s: None, pergunta_texto=lambda _: next(tx),
                          roda=lambda titulo, cmd: self.rodou.append(cmd[3:] if "guarda.py" in " ".join(cmd) else cmd))


def test_menu_situacao_e_sair(mundo):
    p = _Painel(mundo.g, mundo.amb, ["1", "0"])
    assert p.p.laco() == 0 and p.rodou == [["status"]]


def test_menu_varredura_completa_so_com_confirmacao(mundo):
    p = _Painel(mundo.g, mundo.amb, ["2", "2", "2", "1", "0"])  # nao, depois sim
    p.p.laco()
    assert p.rodou == [["varredura", "--tudo"]]


def test_menu_varrer_arquivo_digitado(mundo):
    _arq(mundo, "a.exe")
    p = _Painel(mundo.g, mundo.amb, ["3", "3", "2", "0"], textos=['"C:/pasta/b.exe"'])  # outras > arquivo > digitar (a lista tem 1)
    p.p.laco()
    assert p.rodou == [["varrer", "C:/pasta/b.exe"]], "as aspas que o Windows poe ao colar o caminho saem"


def test_menu_varrer_arquivo_da_lista(mundo):
    c = _arq(mundo, "novo.exe")
    p = _Painel(mundo.g, mundo.amb, ["3", "3", "1", "0"])
    p.p.laco()
    assert p.rodou == [["varrer", str(c)]]


def test_menu_quarentena_devolve_so_com_sim(mundo):
    _infectado(mundo)
    mundo.g.processa(mundo.amb, mundo.motor, str(_arq(mundo)), lambda *a: None)
    (item,) = mundo.g.lista_quarentena(mundo.amb)
    p = _Painel(mundo.g, mundo.amb, ["4", "1", "1", "4", "1", "2", "0"])  # nao; depois sim
    p.p.laco()
    assert p.rodou == [["devolver", item["id"]]]


def test_menu_varredura_rapida_e_celular_pede_confirmacao(mundo):
    p = _Painel(mundo.g, mundo.amb, ["3", "1", "3", "4", "2", "0"])
    p.p.laco()
    assert p.rodou == [["varredura"]], "celular sem o sim nao roda"


def test_menu_esc_sai(mundo):
    assert _Painel(mundo.g, mundo.amb, ["sair"]).p.laco() == 0
