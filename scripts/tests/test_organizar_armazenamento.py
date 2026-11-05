"""Testes de scripts/organizar-armazenamento.py: so apaga a origem se o md5 bater nos
dois lados DEPOIS do cache descartado (mesma tecnica do teste-gravacao.py), so com
--confirmo-apagar-origem, nunca move para dentro de armazenamento ADOTADO (regra do projeto,
incidentes de 27/10 e 28/10) e recusa origem fora da pasta do usuario na interna (raiz, Android/).

Os 11 primeiros testes vieram da nuvem (30/10); o Claude local trocou o apagamento automatico pelo flag
--confirmo-apagar-origem, acrescentou as travas de caminho, de destino existente e da ultima barreira antes do rm
(link, contagem, arquivo novo) e os testes delas.
"""
import runpy
import subprocess
import sys
import types

import pytest

from conftest import SCRIPTS

CAMINHO = SCRIPTS / "organizar-armazenamento.py"

ORIGEM = "/storage/emulated/0/DCIM/Fotos"
DESTINO = "/storage/1234-5678/Fotos"  # 1234-5678 = cartao PORTATIL na VOLUMES abaixo

VOLUMES = "public:179,192 mounted 1234-5678\nprivate:179,160 mounted ABCD-0000\n"

HASH_A = "a" * 32
HASH_B = "b" * 32
DATA = 1577945045  # data de modificacao (s) de todo arquivo do dublê


def _md5_saida(pasta, arquivos):
    return "\n".join(f"{h}  {pasta.rstrip('/')}/{nome}" for nome, h in arquivos.items())


class Celular:
    """Aparelho de mentira: responde as leituras e guarda os comandos que MUDAM algo (mkdir, cp, rm).
    Qualquer comando fora da lista reprova o teste (o abort devia ter vindo antes)."""

    def __init__(self, origem=None, destino=None, bateria="  level: 80\n  status: 2", incomuns="", total=None,
                 origem_na_leitura=None, na_copia=None, volumes=VOLUMES, novos="", meta_destino=None, cartao_total=None,
                 rm_deixa_origem=False, volumes_no_final=None, trava_em=None):
        self.origem = dict(origem if origem is not None else {"a.jpg": HASH_A, "b.jpg": HASH_B})
        self.destino = None if destino is None else dict(destino)  # None = a pasta nao existe
        self.bateria, self.incomuns, self.total, self.volumes = bateria, incomuns, total, volumes
        self.origem_na_leitura = origem_na_leitura or (lambda n: self.origem)  # n = que leitura de md5 da origem e esta
        self.na_copia = na_copia or (lambda o: dict(o))  # o que o cp deixa no destino (default: copia perfeita)
        self.novos, self.cartao_total, self.rm_deixa_origem = novos, cartao_total, rm_deixa_origem
        self.meta_destino = meta_destino  # None = o destino tem o tamanho e a data da origem; ou {nome: (tamanho, data)}
        self.volumes_no_final = volumes_no_final  # volumes depois da marca de tempo (cartao ejetado no meio)
        self.trava_em = trava_em  # prefixo do comando que estoura o tempo (subprocess.TimeoutExpired)
        self.leituras_origem, self.apagado, self.marcou = 0, False, False
        self.comandos, self.escritas = [], []

    def _meta(self, nomes, meta=None):
        meta = meta or {}
        return "\n".join(f"{meta.get(n, (10, DATA))[0]} {meta.get(n, (10, DATA))[1]}.0000000000 {n}" for n in nomes)

    def run(self, cmd, **kw):
        c = cmd[2]
        self.comandos.append(c)
        if self.trava_em and c.startswith(self.trava_em):
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 0))
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c == "sm list-volumes all":
            saida = self.volumes_no_final if (self.volumes_no_final and self.leituras_origem >= 2) else self.volumes
        elif c == "dumpsys battery":
            saida = self.bateria
        elif c == "sync":
            saida = ""
        elif c.startswith("touch '"):
            self.marcou = True
            saida = ""
        elif c.startswith(f"find '{ORIGEM}' -newer"):
            saida = self.novos
        elif c.startswith(f"find '{ORIGEM}' -type f -printf"):
            saida = self._meta(self.origem)
        elif c.startswith(f"find '{DESTINO}' -type f -printf"):
            saida = self._meta(self.destino or {}, self.meta_destino)
        elif c.startswith(f"find '{DESTINO}' -type f | wc -l"):
            saida = str(len(self.destino or {}) if self.cartao_total is None else self.cartao_total)
        elif c.startswith(f"ls -d '{ORIGEM}'"):
            saida = f"ls: {ORIGEM}: No such file or directory" if (self.apagado and not self.rm_deixa_origem) else ORIGEM
        elif c.startswith(f"ls -d '{DESTINO}'"):
            saida = DESTINO if self.destino is not None else f"ls: {DESTINO}: No such file or directory"
        elif c.startswith(f"find '{ORIGEM}'") and "-exec md5sum" in c:
            self.leituras_origem += 1
            saida = _md5_saida(ORIGEM, self.origem_na_leitura(self.leituras_origem))
        elif c.startswith(f"find '{DESTINO}'") and "-exec md5sum" in c:
            saida = _md5_saida(DESTINO, self.destino or {})
        elif c.startswith(f"find '{ORIGEM}' ! -type f"):
            saida = self.incomuns
        elif c.startswith(f"find '{ORIGEM}' -type f | wc -l"):
            saida = str(len(self.origem) if self.total is None else self.total)
        elif c.startswith("find /system"):
            saida = "feito"
        elif c.startswith("mkdir -p"):
            self.escritas.append(c)
            saida = ""
        elif c.startswith("cp -r"):
            self.escritas.append(c)
            self.destino = self.na_copia(self.origem)
            saida = ""
        elif c.startswith("rm -rf"):
            self.escritas.append(c)
            assert c == f"rm -rf '{ORIGEM}'", f"rm na origem errada: {c!r}"
            self.apagado = True
            saida = ""
        else:
            raise AssertionError(f"comando nao mapeado: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")


def _roda(monkeypatch, celular, *args):
    """Roda o script como __main__ com o aparelho de mentira; devolve a mensagem do SystemExit ('' se terminou sem abort)."""
    monkeypatch.setattr(sys, "argv", ["organizar-armazenamento.py", *args])
    monkeypatch.setattr(subprocess, "run", celular.run)
    try:
        runpy.run_path(str(CAMINHO), run_name="__main__")
    except SystemExit as e:
        return str(e)
    return ""


def test_relatorio_e_so_leitura_nao_mexe_em_nada(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["organizar-armazenamento.py"])
    chamadas = []

    def fake_run(cmd, **kw):
        c = cmd[2]
        chamadas.append(c)
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c.startswith("du -sm"):
            saida = "1200  /storage/emulated/0/DCIM\n300  /storage/emulated/0/Download"
        elif c == "sm list-volumes all":
            saida = VOLUMES
        else:
            raise AssertionError(f"relatorio nao deveria chamar: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runpy.run_path(str(CAMINHO), run_name="__main__")
    assert not any(c.startswith(("cp ", "rm ", "mkdir")) for c in chamadas)


def test_aborta_se_aparelho_nao_for_o_a12(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["organizar-armazenamento.py"])

    def fake_run(cmd, **kw):
        c = cmd[2]
        if c == "getprop ro.product.model":
            return types.SimpleNamespace(stdout="SM-G960F", stderr="")
        raise AssertionError(f"nao deveria chegar aqui: {c!r}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(CAMINHO), run_name="__main__")
    assert "ABORTADO" in str(exc.value)


def test_aborta_se_so_um_dos_dois_flags_for_dado(monkeypatch):
    celular = Celular()
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM)
    assert "--origem e --destino juntos" in msg
    assert celular.comandos == ["getprop ro.product.model"]


def test_aplicar_ou_confirmo_sem_origem_e_destino_aborta(monkeypatch):
    celular = Celular()
    msg = _roda(monkeypatch, celular, "--aplicar")
    assert "--origem e --destino" in msg
    assert celular.comandos == ["getprop ro.product.model"]


def test_confirmo_apagar_sem_aplicar_aborta_antes_de_qualquer_leitura(monkeypatch):
    celular = Celular()
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--confirmo-apagar-origem")
    assert "so vale junto com --aplicar" in msg
    assert celular.comandos == ["getprop ro.product.model"]


def test_aborta_se_origem_nao_existe(monkeypatch):
    monkeypatch.setattr(sys, "argv",
                         ["organizar-armazenamento.py", "--origem", ORIGEM, "--destino", DESTINO, "--aplicar"])

    def fake_run(cmd, **kw):
        c = cmd[2]
        if c == "getprop ro.product.model":
            saida = "SM-A125M"
        elif c.startswith("ls -d"):
            saida = f"ls: {ORIGEM}: No such file or directory"
        else:
            raise AssertionError(f"nao deveria chegar aqui: {c!r}")
        return types.SimpleNamespace(stdout=saida, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(CAMINHO), run_name="__main__")
    assert "ABORTADO" in str(exc.value) and "nao existe" in str(exc.value)


def test_aborta_se_destino_nao_for_cartao_portatil(monkeypatch):
    """Nunca 'organizar' para dentro do volume ADOTADO (private:) -- regra do projeto."""
    celular = Celular()
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", "/storage/ABCD-0000/Fotos")
    assert "ABORTADO" in msg and "adotado" in msg
    assert celular.escritas == []


def test_aborta_se_origem_nao_tem_arquivo(monkeypatch):
    celular = Celular(origem={})
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO)
    assert "ABORTADO" in msg and "nenhum arquivo" in msg


def test_simulacao_nunca_copia_nem_apaga(monkeypatch):
    celular = Celular()
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO)
    assert msg == ""  # terminou a simulacao, nao abortou cedo
    assert celular.leituras_origem >= 1  # chegou a ler o md5 da origem
    assert celular.escritas == []
    assert "dumpsys battery" not in celular.comandos


@pytest.mark.parametrize("aplicar", [False, True])
def test_aborta_se_os_metadados_da_origem_vierem_vazios_ou_incompletos(monkeypatch, aplicar):
    # find -printf falhou ou fugiu do formato: a conferencia de tamanho e data nao conferiria nada
    celular = Celular()
    celular._meta = lambda nomes, meta=None: ""
    args = ("--origem", ORIGEM, "--destino", DESTINO) + (("--aplicar",) if aplicar else ())
    msg = _roda(monkeypatch, celular, *args)
    assert "ABORTADO" in msg and "tamanho" in msg
    assert celular.escritas == []


@pytest.mark.parametrize("bateria, motivo", [
    ("  level: 2\n  status: 2", "abaixo de 3% ou sem carregar"),    # 2% carregando
    ("  level: 90\n  status: 3", "abaixo de 3% ou sem carregar"),   # 90% descarregando (status 3)
    ("", "nao consegui ler a bateria"),                             # aparelho offline / saida vazia
])
def test_aborta_com_bateria_baixa_sem_carregar_ou_ilegivel_antes_de_copiar(monkeypatch, bateria, motivo):
    celular = Celular(bateria=bateria)
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar")
    assert "ABORTADO" in msg and motivo in msg
    assert celular.escritas == []


@pytest.mark.parametrize("origem", [
    "/storage/emulated/0",                              # a raiz da interna inteira
    "/storage/emulated/0/",
    "/storage/emulated/0/Android/data/com.exemplo",     # dados de app
    "/storage/emulated/0/android",
    "/storage/emulated/0/DCIM/../Android/data",         # '..' escapando da pasta
    "/data/data/com.exemplo",                           # fora da area do usuario
    "/storage/1234-5678/DCIM",                          # origem no cartao
    "DCIM/Fotos",                                       # relativo
    "/storage/emulated/0/Fotos'; rm -rf /sdcard; '",    # aspas: entraria no comando do shell
])
def test_origem_invalida_aborta_antes_de_qualquer_comando(monkeypatch, origem):
    celular = Celular()
    msg = _roda(monkeypatch, celular, "--origem", origem, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg
    assert celular.comandos == ["getprop ro.product.model"]


@pytest.mark.parametrize("caminho", [
    "DCIM/Fotos",                                       # relativo
    "/storage/emulated/0/DCIM/../Android",              # '..': recusa em vez de normalizar
    "/storage/emulated/0/../0/DCIM",
    "/storage/emulated/0/Fotos'; x; '",                 # aspa simples fecharia a aspa do comando do shell
    '/storage/emulated/0/"Fotos"',
    "/storage/emulated/0/Fo\\tos",                      # barra invertida
    "/storage/emulated/0/Fo\ntos",                      # caractere de controle
])
def test_caminho_limpo_recusa_o_que_nao_pode_ir_para_o_shell_do_aparelho(caminho):
    modulo = runpy.run_path(str(CAMINHO), run_name="organizar")  # nao e __main__: so define as funcoes
    with pytest.raises(SystemExit):
        modulo["caminho_limpo"](caminho)


def test_caminho_limpo_normaliza_barras_repetidas_ponto_e_barra_final():
    modulo = runpy.run_path(str(CAMINHO), run_name="organizar")
    assert modulo["caminho_limpo"]("/storage/emulated/0//DCIM/./Fotos/") == "/storage/emulated/0/DCIM/Fotos"


@pytest.mark.parametrize("destino", [
    "/storage/1234-5678",                               # a raiz do cartao
    "/storage/1234-5678/",
    "/storage/1234-5678-outro/Fotos",                   # outro volume com o mesmo comeco de nome
    "/storage/1234-5678/../emulated/0/Fotos",           # '..' voltando para a interna
    "/storage/emulated/0/Fotos",                        # destino na propria interna
])
def test_destino_invalido_aborta_antes_de_copiar_ou_apagar(monkeypatch, destino):
    celular = Celular()
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", destino, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg
    assert celular.escritas == []
    assert "dumpsys battery" not in celular.comandos


@pytest.mark.parametrize("estado", ["unmounted", "ejecting", "bad_removal", "unmountable"])
def test_cartao_portatil_que_nao_esta_montado_aborta(monkeypatch, estado):
    celular = Celular(volumes=f"public:179,192 {estado} 1234-5678\nprivate:179,160 mounted ABCD-0000\n")
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg and "PORTATIL montado" in msg
    assert celular.escritas == []


def test_destino_que_ja_existe_e_nao_bate_aborta_sem_copiar_nem_misturar(monkeypatch):
    """cp -r por cima de pasta existente sobrescreve arquivo de mesmo nome: nunca misturar."""
    celular = Celular(destino={"a.jpg": HASH_B})
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg and "ja existe" in msg
    assert celular.escritas == []


def test_aplicar_copia_confere_e_mantem_a_origem(monkeypatch):
    celular = Celular()
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar")
    assert msg == ""
    assert [c.split(" ")[0] for c in celular.escritas] == ["mkdir", "cp"]
    assert not any(c.startswith("rm") for c in celular.escritas)
    assert any(c.startswith("find /system") for c in celular.comandos)  # descartou o cache antes de concluir


def test_confirmo_apagar_origem_so_apaga_depois_de_conferir_com_cache_descartado(monkeypatch):
    celular = Celular()
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert msg == ""
    c = celular.comandos
    i_cp = next(i for i, x in enumerate(c) if x.startswith("cp -r"))
    i_cache = next(i for i, x in enumerate(c) if x.startswith("find /system"))
    i_rm = next(i for i, x in enumerate(c) if x.startswith("rm -rf"))
    assert i_cp < i_cache < i_rm
    assert celular.leituras_origem == 3  # antes de copiar, depois do descarte e de novo logo antes do rm


def test_destino_que_ja_tem_tudo_igual_nao_copia_de_novo_so_confere_e_apaga(monkeypatch):
    celular = Celular(destino={"a.jpg": HASH_A, "b.jpg": HASH_B, "extra.jpg": HASH_A})
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert msg == ""
    assert celular.escritas == [f"rm -rf '{ORIGEM}'"]  # nem mkdir nem cp


def test_aplicar_nunca_apaga_se_a_propria_origem_mudou_apos_descarte_de_cache(monkeypatch):
    """Se a ORIGEM muda de hash so por causa do descarte de cache, a leitura nao e confiavel
    -- nao e seguro concluir nada, e muito menos apagar."""
    celular = Celular(origem={"a.jpg": HASH_A}, origem_na_leitura=lambda n: {"a.jpg": HASH_A} if n == 1 else {"a.jpg": HASH_B})
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg and "ORIGEM" in msg
    assert not any(c.startswith("rm") for c in celular.escritas)


def test_aplicar_nunca_apaga_se_destino_ficou_incompleto_apos_descarte_de_cache(monkeypatch):
    celular = Celular(na_copia=lambda o: {"a.jpg": o["a.jpg"]})  # falta b.jpg (corrompeu ou nao copiou)
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg and "NAO apagada" in msg
    assert not any(c.startswith("rm") for c in celular.escritas)


def test_aplicar_nunca_apaga_se_um_arquivo_chegou_ao_destino_com_conteudo_errado(monkeypatch):
    """O defeito de 28/10: tamanho e contagem iguais, conteudo diferente."""
    celular = Celular(na_copia=lambda o: {"a.jpg": o["a.jpg"], "b.jpg": HASH_A})
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg and "NAO apagada" in msg
    assert not any(c.startswith("rm") for c in celular.escritas)


def test_nao_apaga_se_a_origem_tem_link_ou_item_que_nao_e_arquivo_comum(monkeypatch):
    celular = Celular(incomuns=f"{ORIGEM}/atalho")
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg and "nao e arquivo comum" in msg
    assert not any(c.startswith("rm") for c in celular.escritas)


def test_nao_apaga_se_o_md5sum_nao_viu_todos_os_arquivos(monkeypatch):
    """Nome estranho ou arquivo ilegivel some da lista do md5sum: o rm -rf o apagaria sem conferencia."""
    celular = Celular(total=3)  # o find acha 3 arquivos, o md5sum listou 2
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg and "3 arquivo(s)" in msg
    assert not any(c.startswith("rm") for c in celular.escritas)


def test_nao_apaga_se_chegou_arquivo_novo_na_origem_durante_a_conferencia(monkeypatch):
    """Foto tirada enquanto o script conferia o destino: o rm -rf a apagaria sem copia."""
    base = {"a.jpg": HASH_A, "b.jpg": HASH_B}
    celular = Celular(origem=base, origem_na_leitura=lambda n: base if n < 3 else dict(base, **{"nova.jpg": HASH_A}))
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg and "mudou durante a conferencia" in msg
    assert not any(c.startswith("rm") for c in celular.escritas)


# ---- v2 (30/10, revisao independente do organizador): sync, datas, tamanhos, marca de tempo, cartao no final, timeouts ----

def test_o_cp_preserva_as_datas_e_o_sync_vem_antes_do_descarte_de_cache(monkeypatch):
    celular = Celular()
    _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar")
    c = celular.comandos
    assert any(x.startswith("cp -rp '") for x in c)  # o cp -r do toybox do A12 perde as datas (medido em 30/10)
    i_cp = next(i for i, x in enumerate(c) if x.startswith("cp -r"))
    i_sync = next(i for i, x in enumerate(c) if x == "sync" and i > i_cp)
    i_cache = next(i for i, x in enumerate(c) if x.startswith("find /system"))
    assert i_cp < i_sync < i_cache  # pagina suja nao sai da RAM: sem o sync a leitura "fria" poderia vir da memoria


def test_copia_com_tamanho_menor_mesmo_com_md5_igual_nao_e_aceita(monkeypatch):
    """O md5sum do toybox trata erro de leitura como fim de arquivo: copia truncada pode dar o md5 do trecho lido."""
    celular = Celular(meta_destino={"b.jpg": (5, DATA)})
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg and "truncada" in msg and "NAO apagada" in msg
    assert not any(c.startswith("rm") for c in celular.escritas)


def test_copia_sem_as_datas_originais_nao_e_aceita(monkeypatch):
    celular = Celular(meta_destino={"a.jpg": (10, DATA + 3600)})
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg and "datas originais" in msg and "NAO apagada" in msg
    assert not any(c.startswith("rm") for c in celular.escritas)


def test_diferenca_de_data_dentro_da_tolerancia_do_exfat_passa(monkeypatch):
    celular = Celular(meta_destino={"a.jpg": (10, DATA + 2)})
    assert _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar") == ""


def test_marca_de_tempo_vem_antes_da_ultima_leitura_e_arquivo_mais_novo_aborta(monkeypatch):
    celular = Celular(novos=f"{ORIGEM}/nova.jpg")
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg and "durante a ultima leitura" in msg
    assert not any(c.startswith("rm") for c in celular.escritas)
    c = celular.comandos
    i_marca = next(i for i, x in enumerate(c) if x.startswith("touch '"))
    leituras = [i for i, x in enumerate(c) if x.startswith(f"find '{ORIGEM}'") and "-exec md5sum" in x]
    i_newer = next(i for i, x in enumerate(c) if "-newer" in x)
    assert leituras[-1] > i_marca and i_newer > leituras[-1]  # marca ANTES da 3a leitura, conferencia DEPOIS dela


def test_cartao_com_menos_arquivos_do_que_o_esperado_no_final_aborta(monkeypatch):
    """Cartao ejetado ou com erro de leitura entre a conferencia e o rm: nao apaga a unica copia boa."""
    celular = Celular(cartao_total=1)
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg and "cartao tem 1 arquivo" in msg
    assert not any(c.startswith("rm") for c in celular.escritas)


def test_cartao_desmontado_depois_da_conferencia_aborta_antes_do_rm(monkeypatch):
    """O cartao e ejetado depois das duas primeiras leituras da origem (antes da barreira final)."""
    celular = Celular(volumes_no_final="public:179,192 unmounted 1234-5678\n")
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg and "PORTATIL montado" in msg
    assert not any(c.startswith("rm") for c in celular.escritas)


def test_rm_que_nao_termina_e_avisado_em_vez_de_dizer_origem_apagada(monkeypatch, capsys):
    celular = Celular(rm_deixa_origem=True)
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "o rm nao terminou" in msg
    assert "origem apagada" not in capsys.readouterr().out


def test_timeout_no_cp_aborta_com_mensagem_e_sem_rm(monkeypatch):
    celular = Celular(trava_em="cp -r")
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar", "--confirmo-apagar-origem")
    assert "ABORTADO" in msg and "passou de" in msg
    assert not any(c.startswith("rm") for c in celular.escritas)


@pytest.mark.parametrize("flag", ["--conf", "--confirmo", "--confirmo-apagar", "--aplic", "--ap"])
def test_flag_abreviado_nao_vale_e_nada_muda(monkeypatch, flag):
    """argparse aceita abreviacao por padrao: --conf valeria como --confirmo-apagar-origem."""
    celular = Celular()
    args = ["--origem", ORIGEM, "--destino", DESTINO, "--aplicar", flag] if flag.startswith("--conf") else ["--origem", ORIGEM, "--destino", DESTINO, flag]
    monkeypatch.setattr(sys, "argv", ["organizar-armazenamento.py", *args])
    monkeypatch.setattr(subprocess, "run", celular.run)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(CAMINHO), run_name="__main__")
    assert exc.value.code == 2  # erro de uso do argparse, antes de qualquer comando
    assert celular.comandos == [] and celular.escritas == []


def test_destino_divergente_lista_os_arquivos_e_avisa_que_pode_ser_mais_novo(monkeypatch):
    celular = Celular(destino={"a.jpg": HASH_A, "b.jpg": HASH_A}, meta_destino={"b.jpg": (99, DATA + 500)})
    msg = _roda(monkeypatch, celular, "--origem", ORIGEM, "--destino", DESTINO, "--aplicar")
    assert "ja existe" in msg and "b.jpg" in msg and "MAIS NOVOS" in msg
    assert celular.escritas == []
