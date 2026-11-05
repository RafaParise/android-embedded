"""O contrato entre as IAs (memoria/PROTOCOLO-IAS.md) e o guia do Qwen (memoria/ESPECIALISTA-A12.md) nao podem apodrecer em silencio."""
import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
MEM = RAIZ / "memoria"
GUIA = MEM / "ESPECIALISTA-A12.md"
PROTOCOLO = MEM / "PROTOCOLO-IAS.md"
QWEN = RAIZ / "scripts" / "celular-kit" / "QWEN.md"


def texto(p):
    return p.read_text(encoding="utf-8")


@pytest.mark.parametrize("doc", [GUIA, PROTOCOLO])
def test_todo_documento_citado_existe(doc):
    citados = set(re.findall(r"`([A-Z][A-Z0-9-]+\.md)`", texto(doc)))
    assert citados, doc.name
    for nome in citados:
        assert (MEM / nome).exists() or (RAIZ / nome).exists(), f"{doc.name} cita {nome}, que nao existe"


def test_guia_cabe_na_janela_pequena_do_qwen():
    assert GUIA.stat().st_size < 12 * 1024


@pytest.mark.parametrize("doc", [GUIA, PROTOCOLO])
def test_sem_email_nem_chave(doc):
    t = texto(doc)
    assert not re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", t)
    assert not re.search(r"(nvapi-|AIza|sk-or-|gh[pousr]_)\w{6,}", t)


@pytest.mark.parametrize("tema", ["VPN", "DNS", "Wi-Fi da escola", "Dados móveis", "Espaço", "Mapas", "IAs", "Dashcam", "Lentidão"])
def test_guia_cobre_o_tema(tema):
    assert f"| {tema}" in texto(GUIA)


@pytest.mark.parametrize("proibido", ["private_dns_mode", "pm move-package", "pm move-primary-storage", "Magisk", "appops", "development_settings_enabled", "~/.omniroute", "curl"])
def test_guia_ensina_a_recusar_o_que_ja_causou_estrago(proibido):
    secao = texto(GUIA).split("## Quando ele mandar um script")[1]
    assert proibido in secao


def test_guia_nunca_manda_rodar_script_alheio():
    assert "Nunca rode" in texto(GUIA).split("## Quando ele mandar um script")[1]


def test_comandos_do_guia_existem_no_kit():
    caixa = texto(RAIZ / "scripts" / "celular-kit" / "bin" / "caixa")
    for sub in ("pedido", "modelo", "retrato", "status", "sincronizar"):
        assert re.search(rf"^\s*{sub}(\|\w+)?\)", caixa, re.M), sub
    assert (RAIZ / "scripts" / "celular-kit" / "bin" / "saida").exists()
    assert (RAIZ / "scripts" / "celular-kit" / "bin" / "ia").exists()


def test_protocolo_diz_que_pedido_da_caixa_nao_e_a_mensagem_do_rafael():
    t = texto(PROTOCOLO)
    assert "nunca ordem" in t
    assert "nunca roda como veio" in t
    assert "chat do Claude" in t


def test_qwen_aponta_para_o_guia_e_para_o_comando_de_pedido():
    t = texto(QWEN)
    assert "ESPECIALISTA-A12.md" in t
    assert "caixa pedido" in t
    assert "caixa retrato" in t


def test_qwen_nao_diz_mais_que_o_retrato_e_de_31_10():
    assert "de 31/10" not in texto(QWEN).split("## Ponte do PC")[1]
