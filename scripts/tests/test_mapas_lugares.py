"""Testes de scripts/mapas-lugares.py (listas KML de lugares para o Organic Maps): limpeza de texto, telefone, site, zonas de Sao Paulo, cortes e duplicados,
saida repetivel, regra dos essenciais, KML bem formado, verificador independente (aprova o que o gerador faz e REPROVA arquivo adulterado) e o GeoPackage do INEP.
Tudo em pasta temporaria; nenhuma rede (o conftest.py bloqueia urlopen) e nenhum adb."""
import json
import random
import sqlite3
import struct
import unicodedata
import xml.etree.ElementTree as ET

import pytest


@pytest.fixture
def ml(importa_script):
    return importa_script("mapas-lugares.py")


def linha(i, nome, conf=0.9, cat="restaurant", lon=-46.33, lat=-23.96, mun="Santos", status=None, end="Rua A, 10", tel="+5513991234567", site="https://x.com.br", cep=None):
    return {"id": f"id{i:04d}", "nome": nome, "conf": conf, "status": status, "cat": cat, "lon": lon, "lat": lat, "end": end, "cep": cep, "tel": tel, "site": site, "mun": mun}


# ---------------------------------------------------------------- texto

def test_limpa_texto_tira_emoji_controle_email_e_espacos(ml):
    # invisiveis montados por chr(): sequencias barra-u em arquivo gravado pela ferramenta Write viram o caractere de verdade
    assert ml.limpa_texto("Café ☕ do" + chr(0xA0) + "João\tcontato@x.com.br  " + chr(0xFFFD)) == "Café do João"
    assert ml.limpa_texto("👨" + chr(0x200D) + "👩" + chr(0xFE0F)) == ""
    assert ml.limpa_texto(None) == ""
    assert ml.limpa_texto("Padaria\x00\x07 Lua") == "Padaria Lua"
    assert ml.limpa_texto("Padaria\tLua\nSul") == "Padaria Lua Sul"  # tabulacao e quebra de linha viram ESPACO (nao somem e juntam as palavras)


def test_limpa_texto_nao_mexe_em_acentos_nem_pontuacao_normal(ml):
    assert ml.limpa_texto("Açaí & Cia. - 24h (Centro)") == "Açaí & Cia. - 24h (Centro)"


def _negrito(s):  # negrito matematico sem serifa (U+1D5D4 = A): a "fonte bonita" que alguns comercios copiam da rede social
    return "".join(chr(0x1D5D4 + ord(c) - 65) if "A" <= c <= "Z" else c for c in s)


def _largura_total(s):
    return "".join(chr(0xFF00 + ord(c) - 0x20) if 0x21 <= ord(c) <= 0x7E else c for c in s)


def test_limpa_texto_letra_estilizada_vira_letra_comum(ml):
    # a busca da lista casa pelo texto: quem digita "sapataria" nao acha SAPATARIA em negrito matematico (visto no aparelho em 01/11)
    assert ml.limpa_texto(_negrito("SAPATARIA SILVA")) == "SAPATARIA SILVA"
    assert ml.limpa_nome(_negrito("SAPATARIA SILVA")) == "Sapataria Silva"
    assert ml.limpa_texto(_largura_total("Braga (loja) 24h")) == "Braga (loja) 24h"
    assert ml.limpa_texto("Eco Ponto" + chr(0xFF08) + "ok" + chr(0xFF09)) == "Eco Ponto(ok)"  # pontuacao de largura total tambem
    assert ml.limpa_texto("Bar" + chr(0x1D9C) + chr(0x2E1)) == "Barcl"  # letras sobrescritas
    assert ml.limpa_texto("O" + chr(0xFB01) + "cina") == "Oficina"  # ligadura "fi"
    assert ml.limpa_texto(chr(0x1D7CF) + chr(0x1D7D0) + "h") == "12h"  # digitos em negrito matematico
    versalete = "".join(unicodedata.lookup("LATIN LETTER SMALL CAPITAL " + c) for c in "DRA")
    assert ml.limpa_texto(versalete + " Rebeca") == "dra Rebeca"
    assert len(ml.VERSALETE) == 25 and "x" not in ml.VERSALETE.values()  # o alfabeto inteiro menos o X, que nao tem versalete


def test_limpa_texto_so_troca_o_estilizado_ordinal_fracao_e_travessao_ficam(ml):
    s = "1º Tabelião – Drª Ana, Nº 5, ½ litro, 2ª via, m²"  # NFKC cru trocaria º, ª, ½ e ²: so o que passa do Latin-1 e estilizado e trocado
    assert ml.limpa_texto(s) == s
    coreano = chr(0xB9C8) + chr(0xB098)
    assert ml.limpa_texto("Mana Coffee " + coreano) == "Mana Coffee " + coreano  # letra de outro alfabeto nao e tocada


@pytest.mark.parametrize("bruto,esperado", [
    ("SUPERMERCADO ESTRELA DO MAR LTDA", "Supermercado Estrela do Mar LTDA"),
    ("Casa Do Norte E LaticÍNios Cantinho Da RoÇA", "Casa Do Norte E Laticínios Cantinho Da Roça"),
    ("iFood Restaurante", "iFood Restaurante"),
    ("-- Padaria Lua --", "Padaria Lua"),
    ("BRF DISTRIBUIDORA DE ALIMENTOS", "BRF Distribuidora de Alimentos"),
    ("BAR DO ZE", "Bar do Ze"),
    ("BAR X", "BAR X"),
    ("Studio Mel Lima contato@gmail.com", "Studio Mel Lima"),
    ("Talento  Lava   Rapido", "Talento Lava Rapido"),
    ("PIZZARIA PAPA II", "Pizzaria Papa II"),
    ("DO PORTO RESTAURANTE", "Do Porto Restaurante"),
    ("COLEGIO JOAO XXIII", "Colegio Joao XXIII"),
    ("PIZZAS", "Pizzas"),  # 6 letras: o limite de baixo do TUDO MAIUSCULO
    ("PIZZA", "PIZZA"),  # 5 letras: sigla possivel, fica como esta
])
def test_limpa_nome(ml, bruto, esperado):
    assert ml.limpa_nome(bruto) == esperado


def test_limpa_nome_no_limite_exato_nao_corta(ml):
    assert ml.limpa_nome("x" * 100) == "x" * 100 and ml.limpa_nome("x" * 101) == "x" * 99 + "…"


def test_limpa_nome_corta_nome_enorme_no_espaco(ml):
    n = ml.limpa_nome("Clinica " + "Odontologica Integrada " * 10)
    assert len(n) <= 100 and n.endswith("…") and not n.endswith(" …")
    assert n[:-1] == ("Clinica " + "Odontologica Integrada " * 10)[:len(n) - 1].rstrip()  # corta num limite de palavra, sem inventar texto
    assert ml.limpa_nome("x" * 300).endswith("…") and len(ml.limpa_nome("x" * 300)) == 100


@pytest.mark.parametrize("nome,motivo", [
    ("", "sem_nome"), (None, "sem_nome"), ("1", "nome_so_digitos_pontuacao_ou_1_letra"), ("---", "sem_nome"), ("@#$", "nome_so_digitos_pontuacao_ou_1_letra"),
    ("A", "nome_so_digitos_pontuacao_ou_1_letra"), ("Loja", "nome_generico"), ("LOJA!", "nome_generico"), ("Sem nome", "nome_generico"), ("N/A", "nome_generico"),
    ("Loja do Zé", None), ("Casa Verde Materiais", None),
    (chr(0x0E01) + chr(0x0E02) + chr(0x0E04), "nome_sem_letra_latina"), (chr(0x0627) + chr(0x0628) + " " + chr(0x062A), "nome_sem_letra_latina"),  # tailandes, arabe
    (chr(0x9EA5) + chr(0x7576) + chr(0x52DE) + " 25", "nome_sem_letra_latina"), ("Mana Coffee " + chr(0xB9C8) + chr(0xB098), None),  # chines so; latino + coreano fica
    ("Café 24h", None), ("7-Eleven", None),
])
def test_motivo_nome_ruim(ml, nome, motivo):
    assert ml.motivo_nome_ruim(ml.limpa_nome(nome)) == motivo


@pytest.mark.parametrize("bruto,esperado", [
    ("+5513991234567", "+55 13 99123-4567"), ("+551333221234", "+55 13 3322-1234"), ("(13) 3322-1234", "(13) 3322-1234"),
    ("13991234567", "(13) 99123-4567"), ("1333221234", "(13) 3322-1234"), ("190", "190"), ("", ""), (None, ""),
    ("+1 202 555 0100", "+1 202 555 0100"),
])
def test_formata_tel(ml, bruto, esperado):
    assert ml.formata_tel(bruto) == esperado


@pytest.mark.parametrize("bruto,esperado", [
    ("http://www.x.com/?utm_source=a#top", "http://www.x.com"), ("www.itanhaem.sp.gov.br", "https://www.itanhaem.sp.gov.br"),
    ("mailto:a@b.com", ""), ("a b", ""), ("", ""), (None, ""), ("https://www.tiktok.com/@loja", "https://www.tiktok.com/@loja"),
    ("https://x.com.br/" + "a" * 120, "https://x.com.br"), ("https://x.com/contato@gmail.com", "https://x.com"),
])
def test_limpa_site(ml, bruto, esperado):
    assert ml.limpa_site(bruto) == esperado


def test_limpa_endereco(ml):
    assert ml.limpa_endereco("Santos, SP, Brasil") == ""
    assert ml.limpa_endereco("Rua A, 10, ") == "Rua A, 10"
    assert ml.limpa_endereco(None) == ""
    assert len(ml.limpa_endereco("x" * 400)) == 140


def test_zona_sp_pontos_cardeais_a_partir_da_se(ml):
    lat0, lon0 = ml.PRACA_DA_SE
    assert ml.zona_sp(lat0, lon0) == "Centro"
    assert ml.zona_sp(lat0 + 0.0005, lon0 - 0.0005) == "Centro"
    assert ml.zona_sp(lat0 + 0.09, lon0) == "Norte"
    assert ml.zona_sp(lat0 - 0.09, lon0) == "Sul"
    assert ml.zona_sp(lat0, lon0 + 0.10) == "Leste"
    assert ml.zona_sp(lat0, lon0 - 0.10) == "Oeste"
    assert ml.zona_sp(lat0 + 0.09, lon0 + 0.10) == "Leste"  # 45 graus exatos vao para a Leste


@pytest.mark.parametrize("nome,rot,esperado", [
    ("Drogaria Pacheco", "Farmácia", "Drogaria Pacheco (Farmácia)"), ("Farmácia São João", "Farmácia", "Farmácia São João"),
    ("Padaria Lua Nova", "Padaria", "Padaria Lua Nova"), ("Panificadora Lua", "Padaria", "Panificadora Lua (Padaria)"),
    ("Studio Mel Lima", "Salão de beleza", "Studio Mel Lima (Salão de beleza)"), ("Mercado Estrela", "Mercado", "Mercado Estrela"),
    ("Qualquer", "Sem categoria", "Qualquer"), ("Qualquer", "", "Qualquer"),
    ("Bar do Augusto", "Bar", "Bar do Augusto"), ("Barcelona Restaurante", "Bar", "Barcelona Restaurante (Bar)"),  # rotulo de 3 letras: so a palavra igual conta
    ("Spa Zen", "Spa", "Spa Zen"), ("Casa do Chopp", "Bar", "Casa do Chopp (Bar)"), ("Farmácias Nissei", "Farmácia", "Farmácias Nissei"),
])
def test_nome_com_categoria(ml, nome, rot, esperado):
    assert ml.nome_com_categoria(nome, rot) == esperado


def test_categorias_mais_frequentes_ja_vem_em_portugues(ml):
    # visto na lista do aparelho em 01/11: "Sapataria Silva (Shoe repair)"; quem busca "cartorio" nao acha "Notary public"
    assert ml.rotulo("shoe_repair") == "Sapataria" and ml.rotulo("notary_public") == "Cartório" and ml.rotulo("inn") == "Pousada" and ml.rotulo("fire_station") == "Corpo de Bombeiros"
    assert ml.nome_com_categoria("Silva", ml.rotulo("shoe_repair")) == "Silva (Sapataria)"
    assert set(ml.PT_MAIS) <= set(ml.PT) and len(ml.PT_MAIS) >= 250
    assert not any(" " in k or k != k.lower() for k in ml.PT_MAIS)  # chave do Overture: minuscula com sublinhado
    assert ml.rotulo("categoria_que_nao_existe") == "Categoria que nao existe"  # o resto continua com o texto original


def test_nome_com_categoria_nunca_passa_de_100_caracteres(ml):
    # o verificador recusa nome com mais de 120: "Serviço profissional" no fim de um nome de 100 caracteres daria 123
    longo = "Studio " + "x" * 70  # 77 + len(" (Serviço profissional)") = 100: cabe, com sufixo
    assert ml.nome_com_categoria(longo, "Serviço profissional") == longo + " (Serviço profissional)" and len(longo) + len(" (Serviço profissional)") == 100
    quase = longo + "y"  # um caractere a mais: estoura o limite, fica sem sufixo
    assert ml.nome_com_categoria(quase, "Serviço profissional") == quase
    assert len(ml.nome_com_categoria("z" * 100, "Serviço profissional")) == 100


def test_descricao_junta_so_o_que_existe(ml):
    d = ml.descricao("Farmácia", "Rua A, 10", "Santos", "11060-001", "+55 13 3322-1234", "https://x.com", 0.634)
    assert d == "Farmácia · Endereço: Rua A, 10 — Santos · CEP 11060-001 · Tel.: +55 13 3322-1234 · Site: https://x.com · Overture, confiança 0,63"
    assert ml.descricao("", "", "Santos", "", "", "", 1.0) == "Município: Santos · Overture, confiança 1,00"
    assert "— Santos" not in ml.descricao("", "Av. Ana Costa, 5, Santos", "Santos", "", "", "", 0.5)  # municipio ja esta no endereco
    assert "CEP" not in ml.descricao("", "Rua A, 11060-001", "Santos", "11060-001", "", "", 0.5)
    assert len(ml.descricao("x", "y" * 140, "Santos", "z" * 500, "", "", 0.5)) <= 420


def test_rotulo_traduz_e_tem_fallback(ml):
    assert ml.rotulo("pharmacy") == "Farmácia" and ml.rotulo("beach") == "Praia"
    assert ml.rotulo("alien_museum_shop") == "Alien museum shop"
    assert ml.rotulo(None) == "" and ml.rotulo("") == ""
    assert all(c in ml.PT for c in ("hospital", "pharmacy", "grocery_store", "gas_station", "school")) and ml.ESCOLA_BASICA <= set(ml.PT) | {"kindergarten", "montessori_school", "religious_school"}


def test_slug(ml):
    assert ml.slug("São Vicente") == "sao-vicente" and ml.slug("Praia Grande") == "praia-grande" and ml.slug("Cubatão") == "cubatao"


# ---------------------------------------------------------------- KML

def test_kml_doc_bem_formado_oculto_e_com_escape(ml):
    xml = ml.kml_doc("Lugares — Teste & Cia <x>", "descr \"a\" & b", [
        {"nome": "Bar & Grill <1>", "desc": "a > b", "lon": -46.3, "lat": -23.9}, {"nome": "Café", "desc": "ok", "lon": -46.31234567, "lat": -23.91234567}])
    raiz = ET.fromstring(xml.encode("utf-8"))
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    doc = raiz.find("k:Document", ns)
    assert doc.findtext("k:name", namespaces=ns) == "Lugares — Teste & Cia <x>" and doc.findtext("k:visibility", namespaces=ns) == "0"
    nomes = [p.findtext("k:name", namespaces=ns) for p in doc.findall("k:Placemark", ns)]
    assert nomes == ["Bar & Grill <1>", "Café"]
    assert "-46.312346,-23.912346,0" in xml  # 6 casas decimais, lon,lat,alt
    assert xml.count("<Style id=\"placemark-blue\">") == 1 and "mapswithme.com/placemarks/placemark-blue.png" in xml


# ---------------------------------------------------------------- prepara (cortes, duplicados, ordem)

def test_prepara_conta_cada_corte_e_nao_perde_o_resto(ml):
    linhas = [
        linha(1, "Padaria Lua"), linha(2, "Padaria Fechada", status="permanently_closed"), linha(3, "Colégio Estrela", cat="private_school"),
        linha(4, "Faculdade Santa", cat="college_university"), linha(5, ""), linha(6, "1234"), linha(7, "Loja"), linha(8, "Mercado Sul", lon=None),
        linha(9, "Bar Aberto", status="open"),
    ]
    itens, cortes = ml.prepara(linhas)
    assert sorted(i["nome"] for i in itens) == ["Bar Aberto", "Faculdade Santa", "Padaria Lua"]
    assert cortes == {"escola_basica_(ja esta nas listas do INEP)": 1, "nome_generico": 1, "nome_so_digitos_pontuacao_ou_1_letra": 1, "sem_coordenada": 1,
                      "sem_nome": 1, "situacao_permanently_closed": 1}
    itens2, cortes2 = ml.prepara(linhas, com_escolas=True)
    assert "Colégio Estrela" in [i["nome"] for i in itens2] and "escola_basica_(ja esta nas listas do INEP)" not in cortes2


def test_prepara_corta_nome_sem_letra_latina_e_normaliza_o_estilizado(ml):
    itens, cortes = ml.prepara([linha(1, chr(0x0E01) + chr(0x0E02) + chr(0x0E04)), linha(2, _negrito("SAPATARIA SILVA"), lat=-23.9), linha(3, "Padaria Lua", lat=-23.8)])
    assert cortes == {"nome_sem_letra_latina": 1}
    assert sorted(i["nome"] for i in itens) == ["Padaria Lua", "Sapataria Silva"]


def test_prepara_duplicado_e_mesmo_nome_perto_de_qualquer_categoria_fica_o_de_maior_confianca(ml):
    perto = 0.00025  # ~28 m de latitude
    linhas = [
        linha(1, "Academia Forte", conf=0.6, cat="gym"), linha(2, "ACADEMIA FORTE", conf=0.9, cat="sport_or_fitness_facility", lat=-23.96 + perto),
        linha(3, "Academia Forte", conf=0.7, cat="gym", lat=-23.96 + 0.0009),  # ~100 m: outra unidade, fica
        linha(4, "Academia Forte", conf=0.8, cat="gym", lon=-46.20),  # outro bairro, fica
    ]
    itens, cortes = ml.prepara(linhas)
    assert len(itens) == 3 and cortes == {"duplicado (mesmo nome a ate 40 m)": 1}
    assert max(i["conf"] for i in itens if abs(i["lat"] + 23.96 - perto) < 1e-9) == 0.9
    assert not any(i["conf"] == 0.6 for i in itens)


def test_prepara_saida_repetivel_com_a_entrada_embaralhada(ml):
    rnd = random.Random(5)
    linhas = [linha(i, rnd.choice(["Padaria Lua", "Bar do Zé", "Farmácia São João", "Mercado Sul"]), conf=rnd.choice([0.5, 0.7, 0.9]),
                    lon=-46.33 + rnd.random() * 0.2, lat=-23.96 + rnd.random() * 0.2) for i in range(200)]
    a, _ = ml.prepara(linhas)
    embaralhada = linhas[:]
    rnd.shuffle(embaralhada)
    b, _ = ml.prepara(embaralhada)
    assert [i["id"] for i in a] == [i["id"] for i in b]


def test_prepara_ordena_por_nome_sem_acento(ml):
    itens, _ = ml.prepara([linha(1, "Zé Bar", lat=-23.1), linha(2, "Árvore Café", lat=-23.2), linha(3, "Bar do Ari", lat=-23.3), linha(4, "Açaí Sul", lat=-23.4)])
    assert [i["nome"] for i in itens] == ["Açaí Sul", "Árvore Café", "Bar do Ari", "Zé Bar"]


def test_prepara_categoria_no_nome_so_quando_precisa(ml):
    itens, _ = ml.prepara([linha(1, "Drogaria Pacheco", cat="pharmacy"), linha(2, "Farmácia Sol", cat="pharmacy", lat=-23.9)], categoria_no_nome=True)
    nomes = {i["nome_puro"]: i["nome"] for i in itens}
    assert nomes == {"Drogaria Pacheco": "Drogaria Pacheco (Farmácia)", "Farmácia Sol": "Farmácia Sol"}


# ---------------------------------------------------------------- overture() de ponta a ponta + verificador

def _jsonl(tmp_path):
    linhas = [
        # Baixada: principal (conf >= 0.5), essencial com confianca baixa (entra), comum com confianca baixa (vai para os menos certos)
        linha(1, "Padaria Lua", conf=0.9, cat="bakery", mun="Santos"), linha(2, "Drogaria Pacheco", conf=0.25, cat="pharmacy", mun="Santos", lon=-46.31),
        linha(3, "Bar do Zé", conf=0.25, cat="bar", mun="Santos", lon=-46.30), linha(4, "Hotel Mar", conf=0.6, cat="hotel", mun="Praia Grande", lon=-46.5, lat=-24.0),
        linha(5, "Hospital Central", conf=0.1, cat="hospital", mun="Guarujá", lon=-46.25, lat=-23.99),  # 0,1 < 0,2: fica de fora da principal
        linha(6, "Colégio Estrela", conf=0.9, cat="private_school", mun="Santos", lon=-46.32),  # escola basica: sai
        linha(7, "Bar do Zé", conf=0.9, cat="bar", mun="Santos", lon=-46.30003),  # duplicado do 3 (mesmo nome a 3 m): fica o de maior confianca
        # capital: so >= 0.9 (ou essencial >= 0.7), por zona
        linha(8, "Loja Se", conf=0.95, cat="clothing_store", mun="São Paulo", lon=-46.6333, lat=-23.5505),
        linha(9, "Loja Norte", conf=0.92, cat="clothing_store", mun="São Paulo", lon=-46.6333, lat=-23.46),
        linha(10, "Loja Fraca", conf=0.6, cat="clothing_store", mun="São Paulo", lon=-46.6, lat=-23.5),
        linha(11, "Farmácia Sul", conf=0.75, cat="pharmacy", mun="São Paulo", lon=-46.6333, lat=-23.64),  # essencial >= 0.7: entra
        linha(12, "Sítio Longe", conf=0.99, cat="park", mun="Campinas", lon=-47.06, lat=-22.9),  # fora das duas regioes: ignorado
    ]
    p = tmp_path / "places.jsonl"
    p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in linhas) + "\n", encoding="utf-8")
    return p


def _nomes(ml, caminho):
    return [n for n, *_ in ml.le_kml(caminho)[3]]


def test_overture_gera_listas_manifesto_e_o_verificador_aprova(ml, tmp_path):
    saida = tmp_path / "kml"
    man = ml.overture(_jsonl(tmp_path), saida, release="2026-10-21.0")
    assert man["lidos_baixada"] == 7 and man["lidos_capital"] == 4
    por_arq = {a["arquivo"]: a for a in man["arquivos"]}
    assert set(por_arq) == {"lugares-baixada-santista.kml", "lugares-baixada-santista-menos-certos.kml", *[f"por-municipio/lugares-{m}.kml" for m in
                            ("bertioga", "cubatao", "guaruja", "itanhaem", "mongagua", "peruibe", "praia-grande", "santos", "sao-vicente")],
                            *[f"lugares-sao-paulo-{z}.kml" for z in ("centro", "norte", "leste", "sul", "oeste")]}
    assert sorted(_nomes(ml, saida / "lugares-baixada-santista.kml")) == ["Bar do Zé", "Drogaria Pacheco", "Hotel Mar", "Padaria Lua"]
    assert _nomes(ml, saida / "lugares-baixada-santista-menos-certos.kml") == ["Hospital Central"]
    assert _nomes(ml, saida / "lugares-sao-paulo-centro.kml") == ["Loja Se"] and _nomes(ml, saida / "lugares-sao-paulo-norte.kml") == ["Loja Norte"]
    assert _nomes(ml, saida / "lugares-sao-paulo-sul.kml") == ["Farmácia Sul"]
    assert _nomes(ml, saida / "por-municipio/lugares-santos.kml") == ["Bar do Zé", "Drogaria Pacheco", "Padaria Lua"]
    assert man["cortes"]["baixada"] == {"duplicado (mesmo nome a ate 40 m)": 1, "escola_basica_(ja esta nas listas do INEP)": 1}
    assert man["cortes"]["capital"]["fora_da_lista_por_confianca_(abaixo_de_0.9; essenciais abaixo de 0.7)"] == 1
    bar = next(p for p in ml.le_kml(saida / "lugares-baixada-santista.kml")[3] if p[0] == "Bar do Zé")
    assert "confiança 0,90" in bar[1]  # ficou o de maior confianca
    mensagens = []
    assert ml.verificar(saida, 0, saida=mensagens.append) == [], mensagens
    assert mensagens[-1] == "RESULTADO: APROVADO"


def test_overture_aceita_jsonl_gz_e_gera_exatamente_o_mesmo(ml, tmp_path):
    import gzip
    plano = _jsonl(tmp_path)
    comprimido = tmp_path / "places.jsonl.gz"
    with gzip.open(comprimido, "wb") as f:
        f.write(plano.read_bytes())
    a = ml.overture(plano, tmp_path / "kml-a", release="t")
    b = ml.overture(comprimido, tmp_path / "kml-b", release="t")
    assert [x["sha256"] for x in a["arquivos"]] == [x["sha256"] for x in b["arquivos"]] and len(a["arquivos"]) == 16


def test_overture_so_baixada_nao_gera_capital(ml, tmp_path):
    man = ml.overture(_jsonl(tmp_path), tmp_path / "kml", so_baixada=True)
    assert not any("sao-paulo" in a["arquivo"] for a in man["arquivos"]) and "capital" not in man["cortes"]


def test_overture_conf_baixada_mais_alta_empurra_para_os_menos_certos(ml, tmp_path):
    ml.overture(_jsonl(tmp_path), tmp_path / "kml", conf_baixada=0.95, so_baixada=True)
    assert _nomes(ml, tmp_path / "kml" / "lugares-baixada-santista.kml") == ["Drogaria Pacheco"]  # so o essencial (>= 0,2) passa de 0,95


def test_overture_json_invalido_aborta_com_a_linha(ml, tmp_path):
    p = tmp_path / "ruim.jsonl"
    p.write_text('{"mun": "Santos"}\nisto nao e json\n', encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        ml.overture(p, tmp_path / "kml")
    assert "linha 2" in str(exc.value)


def _regrava_manifesto(pasta, arquivo, texto_novo):
    """Troca o conteudo do KML e atualiza SHA-256 e tamanho no manifesto: o que sobra para o verificador achar e o CONTEUDO."""
    import hashlib
    man = json.loads((pasta / "manifesto.json").read_text(encoding="utf-8"))
    (pasta / arquivo).write_bytes(texto_novo.encode("utf-8"))
    for a in man["arquivos"]:
        if a["arquivo"] == arquivo:
            a["sha256"] = hashlib.sha256((pasta / arquivo).read_bytes()).hexdigest()
            a["bytes"] = (pasta / arquivo).stat().st_size
    (pasta / "manifesto.json").write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")


def _gera(ml, tmp_path):
    saida = tmp_path / "kml"
    ml.overture(_jsonl(tmp_path), saida, release="t")
    return saida


def test_verificador_reprova_arquivo_adulterado_sem_atualizar_o_manifesto(ml, tmp_path):
    saida = _gera(ml, tmp_path)
    alvo = saida / "lugares-baixada-santista.kml"
    alvo.write_bytes(alvo.read_bytes().replace(b"Padaria Lua", b"Padaria Sol"))
    falhas = ml.verificar(saida, 0, saida=lambda m: None)
    assert any("SHA-256" in f for f in falhas)


def test_limpa_texto_tira_email_com_caractere_invisivel_no_meio(ml):
    # espaco de largura zero antes do arroba: a regex do e-mail nao casava antes de o caractere sair
    assert ml.limpa_texto("Loja contato" + chr(0x200B) + "@x.com.br") == "Loja"
    assert ml.limpa_texto("Loja contato@" + chr(0x200D) + "x.com.br Sul") == "Loja Sul"


def test_verificador_reprova_kml_fora_do_manifesto(ml, tmp_path):
    saida = _gera(ml, tmp_path)
    (saida / "lugares-sobrando.kml").write_bytes((saida / "lugares-baixada-santista.kml").read_bytes())
    assert any("fora do manifesto" in f for f in ml.verificar(saida, 0, saida=lambda m: None))


def test_verificador_reprova_manifesto_sem_arquivos(ml, tmp_path):
    saida = _gera(ml, tmp_path)
    man = json.loads((saida / "manifesto.json").read_text(encoding="utf-8"))
    man["arquivos"] = []
    (saida / "manifesto.json").write_text(json.dumps(man), encoding="utf-8")
    assert any("vazia" in f for f in ml.verificar(saida, 0, saida=lambda m: None))


def test_verificador_reprova_arquivo_que_sumiu(ml, tmp_path):
    saida = _gera(ml, tmp_path)
    (saida / "lugares-sao-paulo-leste.kml").unlink()
    assert any("nao existe" in f for f in ml.verificar(saida, 0, saida=lambda m: None))


@pytest.mark.parametrize("troca,trecho", [
    (lambda t: t.replace("Padaria Lua</name>", "Padaria Lua contato@x.com</name>"), "e-mail"),
    (lambda t: t.replace("-46.330000,-23.960000", "-23.960000,-46.330000"), "lon/lat invertidos"),
    (lambda t: t.replace("-46.330000,-23.960000", "-40.000000,-23.960000"), "fora da regiao"),
    (lambda t: t.replace("-46.330000,-23.960000", "0.000000,0.000000"), "coordenada zero"),
    (lambda t: t.replace("<visibility>0</visibility>", ""), "visibility"),
    (lambda t: t.replace("<name>Padaria Lua</name>", "<name></name>", 1), "nome vazio"),
    (lambda t: t.replace("Overture, confiança 0,90", "CPF 123.456.789-09"), "CPF"),
    (lambda t: t.replace("</Document>", '<Placemark><name>Padaria Lua</name><description>x</description><styleUrl>#placemark-blue</styleUrl>'
                         '<Point><coordinates>-46.330000,-23.960000,0</coordinates></Point></Placemark></Document>'), "duplicado"),
    (lambda t: t.replace("</Document>", "<Placemark><name>Extra</name><Point><coordinates>-46.33,-23.96,0</coordinates></Point></Placemark></Document>"), "Placemarks"),
])
def test_verificador_acha_defeito_no_conteudo_mesmo_com_manifesto_em_dia(ml, tmp_path, troca, trecho):
    saida = _gera(ml, tmp_path)
    arq = "lugares-baixada-santista.kml"
    texto = (saida / arq).read_text(encoding="utf-8")
    novo = troca(texto)
    assert novo != texto
    _regrava_manifesto(saida, arq, novo)
    falhas = ml.verificar(saida, 0, saida=lambda m: None)
    assert any(trecho in f for f in falhas), falhas


def test_verificador_acha_xml_quebrado(ml, tmp_path):
    saida = _gera(ml, tmp_path)
    arq = "lugares-baixada-santista.kml"
    _regrava_manifesto(saida, arq, (saida / arq).read_text(encoding="utf-8").replace("</Document>", ""))
    assert any("XML mal formado" in f for f in ml.verificar(saida, 0, saida=lambda m: None))


def test_verificador_recusa_kml_com_doctype_entity(ml, tmp_path):
    """Defesa contra expansao de entidades (billion laughs): KML de verdade nunca tem DOCTYPE."""
    saida = _gera(ml, tmp_path)
    arq = "lugares-baixada-santista.kml"
    texto = (saida / arq).read_text(encoding="utf-8").replace("<kml ", '<!DOCTYPE kml [<!ENTITY a "b">]>\n<kml ', 1)
    _regrava_manifesto(saida, arq, texto)
    assert any("XML mal formado" in f and "DOCTYPE" in f for f in ml.verificar(saida, 0, saida=lambda m: None))


def test_verificador_acha_municipio_que_nao_reproduz_a_lista_principal(ml, tmp_path):
    saida = _gera(ml, tmp_path)
    arq = "por-municipio/lugares-santos.kml"
    _regrava_manifesto(saida, arq, (saida / arq).read_text(encoding="utf-8").replace("Padaria Lua", "Padaria Mar", 1))
    assert any("nao reproduzem" in f for f in ml.verificar(saida, 0, saida=lambda m: None))


# ---------------------------------------------------------------- linha de comando

def test_main_valida_limites(ml, monkeypatch, tmp_path):
    for argv, trecho in [(["overture", "x.jsonl", str(tmp_path), "--conf-baixada", "1.5"], "--conf-baixada"),
                         (["overture", "x.jsonl", str(tmp_path), "--conf-essencial", "-0.1"], "--conf-essencial"),
                         (["verificar", str(tmp_path), "99"], "N_nominatim")]:
        monkeypatch.setattr("sys.argv", ["mapas-lugares.py"] + argv)
        with pytest.raises(SystemExit) as exc:
            ml.main()
        assert trecho in str(exc.value)


def test_main_verificar_sai_com_codigo_1_se_reprovado(ml, monkeypatch, tmp_path):
    saida = _gera(ml, tmp_path)
    (saida / "lugares-sao-paulo-leste.kml").unlink()
    monkeypatch.setattr("sys.argv", ["mapas-lugares.py", "verificar", str(saida)])
    with pytest.raises(SystemExit) as exc:
        ml.main()
    assert exc.value.code == 1


# ---------------------------------------------------------------- escolas do INEP (GeoPackage)

def _blob(lon, lat, envelope=False):
    flags = 3 if envelope else 1  # bit 0 = little endian; bits 1-3 = tipo de envelope (1 = 32 bytes)
    cab = b"GP" + bytes([0, flags]) + struct.pack("<i", 4326) + (b"\x00" * 32 if envelope else b"")
    return cab + b"\x01" + struct.pack("<I", 1) + struct.pack("<dd", lon, lat)


def test_ponto_gpkg_le_ponto_com_e_sem_envelope_e_recusa_o_resto(ml):
    assert ml.ponto_gpkg(_blob(-46.5, -24.0)) == (-46.5, -24.0)
    assert ml.ponto_gpkg(_blob(-46.5, -24.0, envelope=True)) == (-46.5, -24.0)
    assert ml.ponto_gpkg(b"XX" + _blob(-46.5, -24.0)[2:]) is None
    assert ml.ponto_gpkg(None) is None and ml.ponto_gpkg(b"") is None and ml.ponto_gpkg(_blob(-46.5, -24.0)[:20]) is None
    poligono = _blob(-46.5, -24.0)[:8] + b"\x01" + struct.pack("<I", 3) + b"\x00" * 16
    assert ml.ponto_gpkg(poligono) is None
    big_endian = _blob(-46.5, -24.0)[:3] + bytes([0]) + _blob(-46.5, -24.0)[4:8] + b"\x00" + struct.pack(">I", 1) + struct.pack(">dd", -46.5, -24.0)
    assert ml.ponto_gpkg(big_endian) == (-46.5, -24.0)


def test_bonito_mantem_siglas_particulas_e_romanos(ml):
    assert ml.bonito("ESCOLA ESTADUAL DE ENSINO FUNDAMENTAL JOSE DA SILVA II") == "Escola Estadual de Ensino Fundamental Jose da Silva II"
    assert ml.bonito("EMEF PROF ANA-MARIA DOS SANTOS") == "EMEF Prof Ana-Maria dos Santos"
    assert ml.bonito("") == "" and ml.bonito(None) == ""


def test_nome_escola_prefixo_de_estadual_e_particular(ml):
    assert ml.nome_escola("MARIA DAS GRACAS TESTE", "Estadual") == "E.E. Maria das Gracas Teste"
    assert ml.nome_escola("EE JOAO XXIII", "Estadual") == "EE Joao XXIII"
    assert ml.nome_escola("COLEGIO LUA", "Privada") == "Colegio Lua (particular)"
    assert ml.nome_escola("EMEF SOL", "Municipal") == "EMEF Sol"


def test_escolas_inep_de_ponta_a_ponta(ml, tmp_path):
    gpkg = tmp_path / "schools.gpkg"
    con = sqlite3.connect(gpkg)
    con.execute("create table schools_2020 (geom blob, name_muni text, code_school text, name_school text, education_level text, admin_category text, "
                "address text, phone_number text, government_level text, abbrev_state text)")
    linhas = [
        (_blob(-46.4, -24.0), "Praia Grande", "1", "MARIA DAS GRACAS TESTE", "Ensino Médio", "Pública", "RUA DO TESTE 100", "(13) 0000-0000", "Estadual", "SP"),
        (_blob(-46.6, -23.5), "São Paulo", "2", "EMEF SOL", "Fundamental", "Pública", "RUA X 1", None, "Municipal", "SP"),
        (_blob(-47.06, -22.9), "Campinas", "3", "ESCOLA ESTADUAL LUA", "Médio", "Pública", None, None, "Estadual", "SP"),
        (_blob(-47.06, -22.9), "Campinas", "4", "ESCOLA MUNICIPAL ESTRELA", "Fundamental", "Pública", None, None, "Municipal", "SP"),
        (b"lixo", "Santos", "5", "ESCOLA SEM PONTO", None, None, None, None, "Estadual", "SP"),
        (_blob(-46.3, -23.9), "Santos", "6", "   ", None, None, None, None, "Estadual", "SP"),
        (_blob(10.0, 50.0), "Santos", "7", "ESCOLA FORA DO ESTADO", None, None, None, None, "Estadual", "SP"),
        (_blob(-46.4, -24.0), "Praia Grande", "1", "MARIA DAS GRACAS TESTE", "Ensino Médio", "Pública", "RUA DO TESTE 100", "(13) 0000-0000", "Estadual", "SP"),
        (_blob(-43.2, -22.9), "Rio de Janeiro", "8", "ESCOLA DO RIO", None, None, None, None, "Estadual", "RJ"),
    ]
    con.executemany("insert into schools_2020 values (?,?,?,?,?,?,?,?,?,?)", linhas)
    con.commit()
    con.close()
    saida = tmp_path / "kml-inep"
    man = ml.escolas_inep(gpkg, saida)
    assert man["descartes"] == {"sem_ponto": 1, "fora_do_estado": 1, "sem_nome": 1}
    assert {a["arquivo"]: a["lugares"] for a in man["arquivos"]} == {"escolas-baixada-santista.kml": 1, "escolas-sao-paulo-capital.kml": 1, "escolas-estaduais-sp-interior.kml": 1}
    titulo, descr, vis, itens, n_doc = ml.le_kml(saida / "escolas-baixada-santista.kml")
    assert vis == "0" and n_doc == 1 and titulo == "Escolas — Baixada Santista"
    assert itens[0][0] == "E.E. Maria das Gracas Teste"
    assert "Escola estadual" in itens[0][1] and "Rua do Teste 100" in itens[0][1] and "INEP 1" in itens[0][1]
    assert abs(itens[0][2] + 46.4) < 1e-6 and abs(itens[0][3] + 24.0) < 1e-6
    assert [n for n, *_ in ml.le_kml(saida / "escolas-estaduais-sp-interior.kml")[3]] == ["E.E. Escola Estadual Lua"]
