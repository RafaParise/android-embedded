#!/usr/bin/env python3
"""Listas KML de LUGARES para o Organic Maps do A12 (so biblioteca padrao). Cada lista importa OCULTA (<visibility>0</visibility>): sem pinos no mapa;
o lugar se acha pelo NOME em Marcadores -> lista -> Buscar (a barra de busca principal NAO acha favoritos importados; medido em 31/10).

  python scripts/mapas-lugares.py escolas-inep <schools_2020.gpkg> <pasta_saida>
      escolas de SP do INEP/IPEA geobr (Censo Escolar 2020): Baixada Santista, capital e estaduais do resto do estado
  python scripts/mapas-lugares.py overture <places.jsonl> <pasta_saida> [--release R] [--conf-baixada 0.5] [--conf-capital 0.9] [--categoria-no-nome] [--com-escolas] [--so-baixada]
      lojas, servicos, saude, lazer... do Overture Maps (CDLA-Permissive-2.0): Baixada Santista (lista principal + "menos certos" + uma por municipio) e capital por zona
  python scripts/mapas-lugares.py verificar <pasta_kml> [N_nominatim]
      confere os KML contra o manifesto.json (SHA-256, XML, contagens, coordenadas, duplicados, e-mail/CPF, particao por municipio, buscas de nomes conhecidos);
      com N > 0, sorteia N lugares por municipio e compara com o geocodificador reverso do OpenStreetMap (1 pedido por segundo)

O JSONL do Overture sai de scripts/mapas-overture/ (venv com duckdb, pyarrow e shapely; ver o LEIAME dessa pasta). Entradas sao dados externos: so leitura.
Limites honestos: dado aberto tem lugar fechado, endereco velho e coordenada aproximada; nada disto e navegacao oficial. Os arquivos gerados NAO entram no git (dados de terceiros)."""
import argparse
import gzip
import hashlib
import json
import math
import pathlib
import random
import re
import sqlite3
import struct
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

BAIXADA = ["Bertioga", "Cubatão", "Guarujá", "Itanhaém", "Mongaguá", "Peruíbe", "Praia Grande", "Santos", "São Vicente"]
CAPITAL = "São Paulo"
BBOX = {"baixada": (-47.15, -24.50, -45.78, -23.55), "capital": (-46.83, -24.02, -46.36, -23.35)}  # lon_min, lat_min, lon_max, lat_max (com folga)
PRACA_DA_SE = (-23.5505, -46.6333)  # lat, lon
RAIO_CENTRO_KM = 3.0
TOL_DUP = 4000  # celula de 1/4000 grau (~28 m x ~25 m, diagonal ~38 m): o verificador chama de duplicado o mesmo nome na mesma celula
DIST_DUP_M = 40.0  # o gerador e mais rigoroso: mesmo nome a ate 40 m ja e duplicado (cobre qualquer par da mesma celula)
ZONAS = ("Centro", "Norte", "Leste", "Sul", "Oeste")
ICONE = "http://www.mapswithme.com/placemarks/placemark-blue.png"

PARTICULAS = {"de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas", "a", "o", "para", "por", "com", "ao"}
def _romano(n):
    s = ""
    for valor, letras in ((10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while n >= valor:
            s += letras
            n -= valor
    return s


ROMANOS = {_romano(i) for i in range(1, 40)}  # i ... xxxix ("Joao XXIII" e nome comum de escola; "di" e "mi" NAO entram)
SIGLAS = {"me", "epp", "ltda", "sa", "eireli", "mei", "sp", "rj", "mg", "pr", "sc", "rs", "ba", "df", "ti", "tv", "dj", "pc", "uti", "cia", "dvd", "gps", "led", "bmw", "vw", "gm",
          "bb", "cef", "inss", "senai", "sesc", "sesi", "apae", "ong", "usf", "ubs", "upa", "cras", "creas", "ceu", "emef", "emei"}
GENERICOS = {"loja", "casa", "empresa", "comercio", "negocio", "sem nome", "teste", "test", "ponto", "local", "escritorio", "consultorio", "sala", "galpao", "deposito",
             "obra", "terreno", "predio", "imovel", "apartamento", "lote", "sitio", "chacara", "unnamed", "no name", "n a", "na", "null", "none"}
REMOVER = {"Cc", "Cf", "Cs", "Co", "Cn", "So", "Me"}  # controle, formato (ZWJ), substituto, uso privado, nao atribuido, simbolo/emoji, marca envolvente
RE_ESPACOS = re.compile(r"\s+")
RE_ACENTO_NO_MEIO = re.compile(r"[a-zà-öø-ÿ][À-ÖØ-Þ]")
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
RE_ALTO = re.compile("[" + chr(0x100) + "-" + chr(0x10FFFF) + "]")  # so o que passa do Latin-1: "º", "ª", "²" e as vogais acentuadas ficam como estao
VERSALETE = {}  # versalete latino (nomes em estilo de rede social) -> letra comum; montado pelos nomes do Unicode, sem digitar caractere exotico
for _ini, _fim in ((0x0250, 0x02B0), (0x1D00, 0x1D30), (0xA730, 0xA7B0)):
    for _o in range(_ini, _fim):
        _nome_unicode = unicodedata.name(chr(_o), "")
        if _nome_unicode.startswith("LATIN LETTER SMALL CAPITAL ") and len(_nome_unicode) == 28:
            VERSALETE[chr(_o)] = _nome_unicode[-1].lower()

# Rotulos em portugues das categorias do Overture (taxonomy.primary, release 2026-10-21.0): as 366 mais frequentes na Baixada e na capital (mais as 259 de PT_MAIS, abaixo).
# O que nao esta aqui vira o texto original sem sublinhado e com a 1a letra maiuscula.
PT = {
    "beauty_salon": "Salão de beleza", "professional_service": "Serviço profissional", "real_estate_service": "Imobiliária",
    "historic_site": "Local histórico", "clothing_store": "Loja de roupas", "restaurant": "Restaurante", "bar": "Bar",
    "christian_place_of_worship": "Igreja cristã", "party_and_event_planning": "Festas e eventos", "dental_clinic": "Clínica odontológica",
    "shopping": "Comércio", "automotive_repair": "Oficina mecânica", "attorney_or_law_firm": "Advocacia", "barber": "Barbearia",
    "pizza_restaurant": "Pizzaria", "religious_organization": "Organização religiosa", "grocery_store": "Mercado",
    "womens_clothing_store": "Moda feminina", "social_or_community_service": "Serviço social e comunitário", "bakery": "Padaria",
    "hair_salon": "Cabeleireiro", "spa": "Spa", "auto_parts_store": "Autopeças", "furniture_store": "Loja de móveis", "gym": "Academia",
    "brazilian_restaurant": "Restaurante brasileiro", "auto_dealer": "Revenda de veículos", "insurance_agency": "Seguros",
    "pharmacy": "Farmácia", "school": "Escola", "accountant": "Contabilidade", "pet_store": "Pet shop", "burger_restaurant": "Hamburgueria",
    "real_estate_agent": "Corretor de imóveis", "gas_station": "Posto de combustível", "doctors_office": "Consultório médico",
    "tattoo_and_piercing": "Tatuagem e piercing", "hospital": "Hospital", "beauty_supply_store": "Loja de cosméticos", "psychology": "Psicologia",
    "education": "Educação", "travel_service": "Agência de viagens", "flowers_and_gifts_store": "Floricultura e presentes",
    "property_management": "Administração de imóveis", "fast_food_restaurant": "Fast food", "hotel": "Hotel", "health_care": "Saúde",
    "marketing_agency": "Agência de marketing", "shoe_store": "Loja de calçados", "printing_service": "Gráfica",
    "industrial_equipment_manufacturer": "Fabricante de equipamentos industriais", "ice_cream_shop": "Sorveteria",
    "it_service_and_computer_repair": "Informática e conserto de computadores", "eyewear_store": "Ótica", "protestant_place_of_worship": "Igreja protestante",
    "college_university": "Faculdade ou universidade", "building_supply_store": "Material de construção", "veterinarian": "Veterinário",
    "travel_and_transportation": "Viagem e transporte", "nail_salon": "Manicure", "dessert_shop": "Doceria", "electronics_store": "Loja de eletrônicos",
    "advertising_agency": "Agência de publicidade", "manufacturer": "Fábrica", "software_development": "Desenvolvimento de software",
    "engineering_service": "Engenharia", "arts_and_entertainment": "Arte e entretenimento", "architectural_designer": "Arquitetura",
    "jewelry_store": "Joalheria", "music_venue": "Casa de shows", "hardware_store": "Ferragens", "building_or_construction_service": "Construção civil",
    "lodging": "Hospedagem", "financial_service": "Serviço financeiro", "information_technology_company": "Empresa de tecnologia",
    "pentecostal_place_of_worship": "Igreja pentecostal", "pilates_studio": "Estúdio de pilates", "park": "Parque", "coffee_shop": "Cafeteria",
    "arts_crafts_and_hobby_store": "Artesanato e hobbies", "mobile_phone_store": "Loja de celulares", "physical_therapy": "Fisioterapia", "cafe": "Café",
    "beach": "Praia", "corporate_or_business_office": "Escritório", "government_office": "Órgão público", "elementary_school": "Escola de ensino fundamental",
    "childrens_clothing_store": "Moda infantil", "outpatient_care_facility": "Ambulatório", "public_plaza": "Praça", "nutrition_service": "Nutrição",
    "convenience_store": "Loja de conveniência", "bank_or_credit_union": "Banco ou cooperativa de crédito", "auto_detailing": "Estética automotiva",
    "liquor_store": "Loja de bebidas", "parking": "Estacionamento", "roman_catholic_place_of_worship": "Igreja católica", "counseling": "Terapia e aconselhamento",
    "language_school": "Escola de idiomas", "car_wash": "Lava-jato", "freight_and_cargo_service": "Frete e cargas", "martial_arts_club": "Artes marciais",
    "naturopathic_medicine": "Terapias naturais", "candy_store": "Doces e balas", "metal_fabricator": "Metalúrgica", "general_dentistry": "Dentista",
    "legal_service": "Serviço jurídico", "private_school": "Escola particular", "italian_restaurant": "Restaurante italiano",
    "fashion_accessories_store": "Acessórios de moda", "preschool": "Educação infantil", "fashion_and_apparel_store": "Moda e vestuário",
    "shopping_mall": "Shopping", "japanese_restaurant": "Restaurante japonês", "caterer": "Buffet e eventos", "laundromat": "Lavanderia",
    "automotive_service": "Serviço automotivo", "contractor": "Reformas e obras", "bank": "Banco", "telecommunications_company": "Telecomunicações",
    "psychotherapy": "Psicoterapia", "party_supply_store": "Artigos para festas", "dermatology": "Dermatologia", "event_photography_service": "Fotografia de eventos",
    "bookstore": "Livraria", "health_food_store": "Produtos naturais", "dance_studio": "Estúdio de dança", "food_delivery_service": "Delivery de comida",
    "computer_store": "Loja de informática", "internet_marketing_service": "Marketing digital", "animal_or_pet_service": "Serviços para pets",
    "home_goods_store": "Casa e decoração", "sushi_restaurant": "Restaurante de sushi", "buffet_restaurant": "Restaurante buffet", "chocolatier": "Chocolateria",
    "medical_service_organization": "Serviço médico", "driving_school": "Autoescola", "mens_clothing_store": "Moda masculina", "smoothie_juice_bar": "Sucos e vitaminas",
    "tire_dealer_and_repair": "Pneus", "home_improvement_store": "Construção e reforma (loja)", "specialty_school": "Escola especializada",
    "public_school": "Escola pública", "graphic_designer": "Designer gráfico", "motorcycle_repair": "Oficina de motos", "butcher_shop": "Açougue",
    "lingerie_store": "Lingerie", "home_cleaning": "Limpeza residencial", "pet_groomer": "Banho e tosa", "commercial_industrial": "Comercial e industrial",
    "warehouse_club_store": "Atacadista", "sports_and_recreation": "Esporte e lazer", "glass_and_mirror_sales_service": "Vidraçaria",
    "sporting_goods_store": "Artigos esportivos", "department_store": "Loja de departamentos", "tobacco_shop": "Tabacaria", "art_gallery": "Galeria de arte",
    "interior_design": "Design de interiores", "plastic_and_reconstructive_surgery": "Cirurgia plástica", "massage_therapy": "Massoterapia",
    "retirement_home": "Casa de repouso", "non_governmental_association": "Associação ou ONG", "toy_store": "Loja de brinquedos",
    "hair_supply_store": "Produtos para cabelo", "sport_league": "Liga esportiva", "laboratory_testing": "Laboratório",
    "obstetrics_and_gynecology": "Ginecologia e obstetrícia", "holiday_rental_home": "Casa de temporada", "shipping_center": "Envios e encomendas",
    "music_production": "Produção musical", "food_beverage_distributor": "Distribuidora de alimentos e bebidas", "baptist_place_of_worship": "Igreja batista",
    "b2b_advertising_and_marketing_service": "Publicidade e marketing (empresas)", "food_and_drink": "Alimentação e bebidas", "dance_club": "Casa noturna",
    "barbecue_restaurant": "Churrascaria", "auto_body_shop": "Funilaria e pintura", "storage_facility": "Guarda-volumes e depósito",
    "bar_and_grill_restaurant": "Bar e grill", "steakhouse": "Steakhouse", "internet_service_provider": "Provedor de internet",
    "appliance_repair_service": "Conserto de eletrodomésticos", "sport_or_fitness_facility": "Centro esportivo", "skin_care_and_makeup": "Pele e maquiagem",
    "motorcycle_dealer": "Concessionária de motos", "financial_advising": "Consultoria financeira", "bike_store": "Bicicletaria",
    "community_and_government": "Comunidade e governo", "hvac_service": "Ar-condicionado", "office_supply_store": "Papelaria",
    "mattress_store": "Colchões", "vitamin_and_supplement_store": "Suplementos", "sewing_and_alterations": "Costura e ajustes", "cultural_center": "Centro cultural",
    "music_school": "Escola de música", "investing": "Investimentos", "vision_or_eye_care_clinic": "Clínica oftalmológica", "tour_operator": "Operadora de turismo",
    "charity_organization": "Instituição de caridade", "industrial_company": "Empresa industrial", "chemical_plant": "Indústria química",
    "cosmetic_dentistry": "Odontologia estética", "fashion_boutique": "Boutique", "key_and_locksmith": "Chaveiro", "podiatry": "Podologia",
    "police_station": "Delegacia ou polícia", "medical_spa": "Medicina estética", "diner": "Lanchonete", "textile_manufacturer": "Indústria têxtil",
    "home_service": "Serviços domésticos", "stadium_arena": "Estádio ou arena", "carpenter": "Marcenaria", "fabric_store": "Tecidos",
    "fitness_trainer": "Personal trainer", "furniture_assembly": "Montagem de móveis", "second_hand_store": "Brechó", "electrician": "Eletricista",
    "used_auto_dealer": "Carros usados", "orthopedics": "Ortopedia", "lighting_store": "Iluminação", "orthodontics": "Ortodontia", "publisher": "Editora",
    "auto_company": "Empresa automotiva", "pediatric_clinic": "Pediatria", "home_developer": "Construtora", "luggage_store": "Malas e bolsas",
    "metal_supplier": "Fornecedor de metais", "rental_service": "Locação", "surgery": "Cirurgia", "food_and_beverage_store": "Loja de alimentos e bebidas",
    "installment_loans": "Empréstimos", "car_stereo_store": "Som automotivo", "lounge": "Lounge", "automation_service": "Automação", "acupuncture": "Acupuntura",
    "uniform_store": "Uniformes", "produce_store": "Hortifruti", "campus_building": "Prédio de campus", "soccer_field": "Campo de futebol",
    "carpet_store": "Tapetes e carpetes", "car_rental_service": "Locadora de veículos", "employment_law": "Direito trabalhista",
    "musical_instrument_store": "Instrumentos musicais", "home_security": "Segurança residencial", "cocktail_bar": "Coquetelaria", "makeup_artist": "Maquiagem",
    "broadcasting_media_production": "Produção audiovisual", "media_agency": "Agência de mídia", "pub": "Pub", "b2b_business_management_service": "Gestão empresarial",
    "discount_store": "Loja de descontos", "food_truck_stand": "Food truck ou barraca", "linen_store": "Cama, mesa e banho", "post_office": "Correios",
    "bridal_shop": "Noivas", "clothing_company": "Confecção", "yoga_studio": "Estúdio de yoga", "farmers_market": "Feira",
    "t_shirt_printing_service": "Estamparia", "employment_agency": "Agência de empregos", "b2b_surgical_appliances_and_supplies": "Material cirúrgico",
    "movie_theater": "Cinema", "day_care_preschool": "Creche", "broker": "Corretor", "hostel": "Hostel", "bottled_water_company": "Água mineral",
    "tutoring_service": "Aulas particulares", "seafood_restaurant": "Frutos do mar", "hookah_bar": "Narguilé", "sportswear_store": "Moda esportiva",
    "beer_bar": "Bar de cerveja", "hardware_home_and_garden_store": "Casa e jardim", "taxi_service": "Táxi", "jewelry_and_watches_manufacturer": "Joias e relógios (fábrica)",
    "newspaper_and_magazines_store": "Jornais e revistas", "occupational_safety": "Segurança do trabalho", "theatre_venue": "Teatro", "granite_supplier": "Granitos e mármores",
    "machine_shop": "Usinagem", "nursery_and_gardening_store": "Plantas e jardinagem", "web_designer": "Web design", "chicken_restaurant": "Frango e rotisseria",
    "beauty_product_supplier": "Fornecedor de beleza", "medical_supply_store": "Produtos médicos", "library": "Biblioteca", "computer_hardware_company": "Hardware de computadores",
    "brewery": "Cervejaria", "video_game_store": "Games", "sandwich_shop": "Sanduicheria", "cardiology": "Cardiologia", "vocational_and_technical_school": "Escola técnica",
    "psychiatry": "Psiquiatria", "tanning_salon": "Bronzeamento", "art_school": "Escola de artes", "laser_hair_removal": "Depilação a laser",
    "educational_service": "Serviço educacional", "electronic_equipment_supplier": "Equipamentos eletrônicos", "sign_making": "Comunicação visual", "atm": "Caixa eletrônico",
    "auto_customization": "Customização automotiva", "chiropractic": "Quiropraxia", "dry_cleaning": "Lavagem a seco", "chinese_restaurant": "Restaurante chinês",
    "psychic_advising": "Esoterismo", "ear_nose_and_throat": "Otorrinolaringologia", "labor_union": "Sindicato", "specialty_foods_store": "Empório",
    "media_news_company": "Jornalismo e mídia", "reproductive_perinatal_and_womens_care": "Saúde da mulher", "speech_therapy": "Fonoaudiologia", "landscaping": "Paisagismo",
    "bus_station": "Terminal de ônibus", "masonry_concrete": "Alvenaria e concreto", "high_school": "Ensino médio", "cosmetics_and_fragrance_store": "Perfumaria",
    "urology": "Urologia", "oral_and_maxillofacial_surgery": "Cirurgia bucomaxilofacial", "b2b_energy_and_utility_service": "Energia e utilidades", "tea_room": "Casa de chá",
    "museum": "Museu", "appliance_store": "Eletrodomésticos", "music_and_dvd_store": "Música e DVD", "gelato_shop": "Gelateria", "swimwear_store": "Moda praia",
    "fishmonger": "Peixaria", "commercial_real_estate": "Imóveis comerciais", "pest_control_service": "Dedetização", "surf_store": "Surf shop",
    "weight_loss_center": "Emagrecimento", "outlet_store": "Outlet", "gift_shop": "Presentes", "motel": "Motel", "plastics_company": "Indústria de plásticos",
    "vegetarian_restaurant": "Restaurante vegetariano", "medical_research_institute": "Pesquisa médica", "hair_extensions": "Mega hair",
    "bike_repair_maintenance": "Conserto de bicicletas", "town_hall": "Prefeitura ou órgão municipal", "antique_store": "Antiguidades", "cosmetology_school": "Escola de estética",
    "endocrinology": "Endocrinologia", "recycling_center": "Reciclagem", "lottery_vendor": "Lotérica", "life_coach": "Coaching", "garbage_collection_service": "Coleta de lixo",
    "amusement_park": "Parque de diversões", "costume_store": "Fantasias", "train_station": "Estação de trem", "cupcake_shop": "Cupcakes",
    "pharmaceutical_company": "Indústria farmacêutica", "appraisal_service": "Avaliação e perícia", "arabian_restaurant": "Restaurante árabe", "auction_house": "Leilão",
    "oil_change_station": "Troca de óleo", "neurology": "Neurologia", "courthouse": "Fórum ou tribunal", "condominium": "Condomínio", "beer_garden": "Beer garden",
    "health_food_restaurant": "Comida saudável", "middle_eastern_restaurant": "Restaurante do Oriente Médio", "wine_bar": "Wine bar", "superstore": "Hipermercado",
    "middle_school": "Ensino fundamental", "kindergarten": "Educação infantil", "montessori_school": "Escola Montessori", "religious_school": "Escola religiosa",
}
# As 259 categorias seguintes mais frequentes (Baixada + capital) que ficavam em ingles; a busca da lista casa pelo nome e o rotulo vai no nome ("Cartorio", nao "Notary public").
PT_MAIS = {
    "luggage_storage": "Guarda-volumes", "bed_and_breakfast": "Pousada", "notary_public": "Cartório", "portuguese_restaurant": "Restaurante português", "inn": "Pousada",
    "kids_recreation_and_party": "Festas e recreação infantil", "lumber_store": "Madeireira", "tennis_court": "Quadra de tênis",
    "latin_american_restaurant": "Restaurante latino-americano", "shoe_repair": "Sapataria", "pet_boarding": "Hotel para pets", "theatrical_production": "Produção teatral",
    "hot_dog_restaurant": "Cachorro-quente", "campground": "Camping", "auto_glass_service": "Vidraçaria automotiva", "asian_restaurant": "Restaurante asiático",
    "marina": "Marina", "cooking_school": "Escola de culinária", "community_center": "Centro comunitário", "pool_cleaning": "Limpeza de piscina",
    "money_transfer_service": "Envio de dinheiro", "gastropub": "Gastropub", "waxing": "Depilação", "hair_removal": "Depilação", "pediatric_dentistry": "Odontopediatria",
    "mexican_restaurant": "Restaurante mexicano", "day_spa": "Spa", "hunting_and_fishing_store": "Loja de caça e pesca", "computer_coaching": "Curso de informática",
    "emergency_department": "Pronto-socorro", "auto_restoration_service": "Restauração de carros", "performing_arts_venue": "Casa de espetáculos",
    "wholesale_grocer": "Atacado de alimentos", "currency_exchange": "Casa de câmbio", "french_restaurant": "Restaurante francês", "b2b_service": "Serviço para empresas",
    "telecommunications_service": "Telecomunicações", "embassy": "Embaixada ou consulado", "service_apartment": "Apart-hotel", "skate_store": "Loja de skate",
    "tapas_bar": "Bar de tapas", "boxing_class": "Aulas de boxe", "optometry": "Optometria", "commercial_refrigeration": "Refrigeração comercial", "lodge": "Pousada",
    "travel_agent": "Agência de viagens", "criminal_defense_law": "Advocacia criminal", "flea_market": "Feira", "youth_organization": "Organização de jovens",
    "organic_grocery_store": "Mercado de orgânicos", "fire_station": "Corpo de Bombeiros", "delicatessen": "Empório", "educational_research_institute": "Instituto de pesquisa",
    "cheese_shop": "Queijaria", "resort": "Resort", "test_preparation": "Curso preparatório", "pancake_house": "Panquecaria", "military_site": "Área militar",
    "argentine_restaurant": "Restaurante argentino", "meat_wholesaler": "Atacado de carnes", "towing_service": "Guincho", "truck_repair": "Oficina de caminhões",
    "hobby_shop": "Loja de hobbies", "sports_bar": "Bar esportivo", "skate_park": "Pista de skate", "abuse_and_addiction_treatment_center": "Clínica de dependência química",
    "boat_service": "Serviço náutico", "peruvian_restaurant": "Restaurante peruano", "korean_restaurant": "Restaurante coreano",
    "audio_visual_equipment_store": "Loja de áudio e vídeo", "swimming_pool": "Piscina", "funeral_service": "Funerária", "fertility_clinic": "Clínica de fertilidade",
    "elevator_service": "Elevadores", "karaoke_venue": "Karaokê", "theme_restaurant": "Restaurante temático", "educational_supply_store": "Material escolar",
    "lebanese_restaurant": "Restaurante libanês", "gastroenterology": "Gastroenterologia", "private_association": "Associação", "radio_station": "Estação de rádio",
    "energy_company": "Empresa de energia", "credit_union": "Cooperativa de crédito", "restaurant_equipment_and_supply": "Equipamentos para restaurantes",
    "poke_restaurant": "Poke", "wedding_planning": "Cerimonial de casamento", "river": "Rio", "geographic_entities": "Entidade geográfica", "hair_replacement": "Prótese capilar",
    "camera_and_photography_store": "Loja de fotografia", "health_department": "Secretaria de saúde", "aquatic_pet_store": "Aquarismo", "amateur_sport_team": "Time amador",
    "scuba_diving_center": "Mergulho", "fire_protection_service": "Proteção contra incêndio", "monument": "Monumento", "adult_entertainment_venue": "Entretenimento adulto",
    "senior_citizen_service": "Serviço para idosos", "political_organization": "Organização política", "movie_television_studio": "Estúdio de cinema e TV",
    "shooting_range": "Estande de tiro", "solar_installation": "Energia solar", "department_of_motor_vehicles": "Detran", "internet_cafe": "Lan house",
    "divorce_and_family_law": "Direito de família", "boot_camp": "Treinamento funcional", "animal_shelter": "Abrigo de animais", "gymnastics_center": "Ginástica",
    "buddhist_place_of_worship": "Templo budista", "warehouse": "Armazém", "prosthetics": "Próteses", "audiology": "Audiologia",
    "environmental_conservation_organization": "Conservação ambiental", "windows_installation": "Instalação de janelas", "periodontics": "Periodontia", "ambulance_or_ems_service": "Ambulância",
    "oncology": "Oncologia", "endodontics": "Endodontia", "swimming_instructor": "Aulas de natação", "playground": "Playground", "glass_manufacturer": "Fábrica de vidros",
    "medical_school": "Faculdade de medicina", "architect": "Arquiteto", "environmental_or_ecological_service": "Serviço ambiental", "baseball_field": "Campo de beisebol",
    "surfing": "Surfe", "airport": "Aeroporto", "winery": "Vinícola", "mediterranean_restaurant": "Restaurante mediterrâneo", "plastic_manufacturer": "Fábrica de plásticos",
    "health_spa": "Spa", "laboratory": "Laboratório", "history_museum": "Museu de história", "reptile_store": "Loja de répteis", "prosthodontics": "Prótese dentária",
    "self_storage_facility": "Guarda-móveis", "race_track": "Pista de corrida", "b2b_water_treatment_service": "Tratamento de água", "arcade": "Fliperama",
    "german_restaurant": "Restaurante alemão", "commercial_vehicle_dealer": "Veículos comerciais", "print_media": "Mídia impressa", "dog_trainer": "Adestrador de cães",
    "bridge": "Ponte", "family_practice": "Clínica geral", "boat_rental_and_training": "Aluguel de barcos", "boat_dealer": "Loja de barcos",
    "vending_machine_supplier": "Máquinas de venda", "bike_rental": "Aluguel de bicicletas", "plumbing": "Encanador", "meditation_center": "Meditação",
    "pool_billiards": "Sinuca e bilhar", "breakfast_and_brunch_restaurant": "Café da manhã e brunch", "aquarium": "Aquário", "art_museum": "Museu de arte",
    "neuropathology": "Neuropatologia", "hospice": "Cuidados paliativos", "flight_school": "Escola de aviação", "fishing_club": "Clube de pesca", "farm": "Fazenda",
    "ferry_boat_company": "Balsa", "b2b_science_and_technology_service": "Serviço científico e tecnológico", "soccer_stadium": "Estádio de futebol", "boat_tour": "Passeio de barco",
    "car_window_tinting": "Insulfilm", "comic_books_store": "Loja de quadrinhos", "comfort_food_restaurant": "Comida caseira", "second_hand_clothing_store": "Brechó",
    "media_service": "Serviço de mídia", "salad_bar": "Saladas", "carpet_cleaning": "Limpeza de tapetes", "jewish_place_of_worship": "Sinagoga", "paint_store": "Loja de tintas",
    "cycling_class": "Aulas de ciclismo", "geological_service": "Serviço geológico", "packing_supply_store": "Embalagens", "painting": "Pintor",
    "countertop_installation": "Bancadas e pias", "auto_manufacturer": "Montadora", "fish_and_chips_restaurant": "Fish and chips", "radiology": "Radiologia",
    "real_estate_investment": "Investimento imobiliário", "truck_dealer": "Concessionária de caminhões", "b2b_marketing_consultant": "Consultoria de marketing", "circus_venue": "Circo",
    "nursing_school": "Escola de enfermagem", "mountain": "Montanha", "cottage": "Chalé", "logging_service": "Extração de madeira", "donut_shop": "Donuts",
    "automotive_consultant": "Consultoria automotiva", "emissions_inspection": "Inspeção veicular", "boat_parts_store": "Peças náuticas", "sunglasses_store": "Óculos de sol",
    "apartment": "Apartamento", "airline": "Companhia aérea", "blood_and_plasma_donation_center": "Doação de sangue", "bags_luggage_company": "Bolsas e malas", "pier": "Píer",
    "roofing": "Telhados", "disability_services_and_support_organization": "Apoio a pessoas com deficiência", "security_systems": "Sistemas de segurança",
    "motorsports_store": "Loja de motos e acessórios", "appliance_manufacturer": "Fábrica de eletrodomésticos", "spanish_restaurant": "Restaurante espanhol", "auditorium": "Auditório",
    "tv_mounting": "Instalação de TV", "nephrology": "Nefrologia", "texmex_restaurant": "Restaurante tex-mex", "electric_utility_provider": "Companhia de energia elétrica",
    "tax_law": "Direito tributário", "american_restaurant": "Restaurante americano", "hearing_aid_store": "Aparelhos auditivos", "bowling_alley": "Boliche",
    "thai_restaurant": "Restaurante tailandês", "rheumatology": "Reumatologia", "mobile_phone_repair": "Conserto de celular", "apparel_manufacturer": "Confecção",
    "alcohol_and_drug_treatment_center": "Clínica de dependência química", "public_utility": "Serviço público", "souvenir_store": "Loja de souvenirs", "gay_bar": "Bar LGBT",
    "coworking_space": "Coworking", "public_market": "Mercado público", "muslim_place_of_worship": "Mesquita", "credit_and_debt_counseling": "Orientação de crédito e dívidas",
    "event_venue": "Espaço de eventos", "bartender": "Bartender", "pet_sitting": "Pet sitter", "real_estate_law": "Direito imobiliário", "computer_wholesaler": "Atacado de informática",
    "home_decor_store": "Decoração", "art_restoration_service": "Restauração de arte", "sightseeing_tour_agency": "Agência de passeios", "gardener": "Jardinagem",
    "dog_park": "Parque para cães", "fence_and_gate_sales_service": "Cercas e portões", "junkyard": "Ferro-velho", "aromatherapy": "Aromaterapia",
    "travel_company": "Empresa de turismo", "surgery_center": "Centro cirúrgico", "escape_room": "Escape room", "gun_and_ammo_store": "Armas e munições",
    "dialysis_clinic": "Clínica de hemodiálise", "maternity_wear": "Moda gestante", "maternity_center": "Maternidade", "indian_restaurant": "Restaurante indiano",
    "comedy_club": "Casa de comédia", "paintball": "Paintball", "mover": "Mudanças", "water_park": "Parque aquático", "anglican_or_episcopal_place_of_worship": "Igreja anglicana",
    "television_service_provider": "TV por assinatura", "european_restaurant": "Restaurante europeu", "image_consultant": "Consultoria de imagem",
    "pet_breeder": "Canil e criadouro", "political_party_office": "Partido político", "water_utility_provider": "Companhia de água", "record_label": "Gravadora",
}
PT.update(PT_MAIS)
# Escola de EDUCACAO BASICA: as escolas oficiais (INEP, Censo Escolar 2020) ja estao nas listas "Escolas ...", com o nome oficial. Faculdade, idiomas, autoescola,
# musica, tecnica e afins NAO estao la e ficam.
ESCOLA_BASICA = {"school", "elementary_school", "middle_school", "high_school", "preschool", "day_care_preschool", "public_school", "private_school", "kindergarten",
                 "montessori_school", "religious_school"}
# Categorias do dia a dia que entram na lista PRINCIPAL mesmo com confianca baixa (a confianca do Overture mede mais a atividade online da pagina do que a existencia do
# lugar: 99 dos 406 hospitais e 90 das 530 farmacias da Baixada ficam abaixo de 0,5).
ESSENCIAIS = {"hospital", "government_office", "town_hall", "police_station", "fire_station", "courthouse", "post_office", "bank", "bank_or_credit_union", "pharmacy",
              "gas_station", "college_university", "shopping_mall", "bus_station", "train_station", "beach", "park", "public_plaza", "museum", "library", "cultural_center",
              "stadium_arena", "outpatient_care_facility", "laboratory_testing", "grocery_store", "superstore", "community_and_government", "atm"}


def rotulo(cat):
    if not cat:
        return ""
    if cat in PT:
        return PT[cat]
    t = cat.replace("_", " ").strip()
    return t[:1].upper() + t[1:]


# ------------------------------------------------------------------ texto
def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").casefold()


def chave_nome(s):
    return RE_ESPACOS.sub(" ", re.sub(r"[^0-9a-z ]+", " ", sem_acento(s))).strip()


def _comum(m):
    """Letra estilizada (negrito matematico, largura total, sobrescrita, versalete) vira a letra comum; qualquer outra fica como esta."""
    c = m.group(0)
    if c in VERSALETE:
        return VERSALETE[c]
    if 0xFF01 <= ord(c) <= 0xFF5E or (unicodedata.category(c)[0] in "LN" and unicodedata.decomposition(c).startswith("<")):
        k = unicodedata.normalize("NFKC", c)
        if k.isascii():
            return k
    return c


def limpa_texto(s):
    """Tira e-mail, controle, emoji, simbolos soltos, U+FFFD e espacos repetidos; letra estilizada vira comum (a busca da lista nao acha o estilizado). Nao muda maiusculas."""
    s = unicodedata.normalize("NFC", s or "").replace(chr(0xFFFD), "")  # U+FFFD = caractere de substituicao (texto quebrado na origem)
    s = RE_ALTO.sub(_comum, s)
    s = RE_ESPACOS.sub(" ", s)
    s = "".join(c for c in s if (unicodedata.category(c) not in REMOVER and not 0xFE00 <= ord(c) <= 0xFE0F and not 0x1F3FB <= ord(c) <= 0x1F3FF) or c == " ")
    s = RE_EMAIL.sub("", s)  # e-mail (de pessoa ou de empresa) nao entra em nome, endereco nem descricao; depois do filtro, senao um caractere invisivel no meio o esconde
    return RE_ESPACOS.sub(" ", s).strip()


def _capitaliza_letras(tok):
    return re.sub(r"[A-Za-zÀ-ÿ]+", lambda m: m.group(0).capitalize(), tok.lower())


def _titulo_token(tok, primeiro):
    nucleo = re.sub(r"[^A-Za-zÀ-ÿ0-9]", "", tok).lower()
    if nucleo in PARTICULAS and not primeiro:
        return tok.lower()
    if nucleo in ROMANOS or nucleo in SIGLAS or (0 < len(nucleo) <= 3 and nucleo.isalpha() and not re.search(r"[aeiouáéíóúâêôãõà]", nucleo)):
        return tok.upper()
    return _capitaliza_letras(tok)


def limpa_nome(s, maximo=100):
    """Nome de exibicao: texto limpo; TUDO MAIUSCULO vira Capitalizado; acento maiusculo no meio da palavra (LaticÍNios) e consertado; corta nome enorme."""
    n = limpa_texto(s).strip(" -|.,;:_*•/\\")
    if sum(c.isalpha() for c in n) >= 6 and n == n.upper():
        n = " ".join(_titulo_token(t, i == 0) for i, t in enumerate(n.split(" ")))
    else:
        n = " ".join(_capitaliza_letras(t) if RE_ACENTO_NO_MEIO.search(t) else t for t in n.split(" "))
    if len(n) > maximo:
        corte = n.rfind(" ", 0, maximo - 1)
        n = n[: corte if corte > maximo // 2 else maximo - 1].rstrip(" -|.,;:") + "…"
    return n


def motivo_nome_ruim(n):
    """None se o nome serve; senao o motivo do corte."""
    if not n:
        return "sem_nome"
    if len(n) < 2 or not any(c.isalpha() for c in n):
        return "nome_so_digitos_pontuacao_ou_1_letra"
    if not any(c.isalpha() and unicodedata.name(c, "").startswith("LATIN") for c in n):  # so tailandes, arabe, chines...: ninguem busca nem le isso aqui
        return "nome_sem_letra_latina"
    if chave_nome(n) in GENERICOS:
        return "nome_generico"
    return None


def formata_tel(t):
    if not t:
        return ""
    d = re.sub(r"\D", "", t)
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
        return f"+55 {d[:2]} {d[2:-4]}-{d[-4:]}"
    if len(d) in (10, 11) and not t.strip().startswith("+"):  # "+1 202..." e de outro pais: nao e DDD brasileiro
        return f"({d[:2]}) {d[2:-4]}-{d[-4:]}"
    return limpa_texto(t)[:30]


def limpa_site(s):
    if not s:
        return ""
    s = limpa_texto(s).split("#")[0].split("?")[0].rstrip("/")
    if not s or " " in s or s.lower().startswith("mailto:"):
        return ""
    if not re.match(r"^https?://", s, re.I):
        s = "https://" + s
    if len(s) > 90:
        m = re.match(r"^(https?://[^/]+)", s, re.I)
        s = m.group(1) if m else ""
    return s


def limpa_endereco(e):
    e = limpa_texto(e)
    if re.fullmatch(r"[^,]+, ?[A-Z]{2}, ?Brasil", e):  # so "Cidade, SP, Brasil": nao e endereco
        return ""
    return e.strip(" ,-")[:140]


def zona_sp(lat, lon):
    lat0, lon0 = PRACA_DA_SE
    dx = (lon - lon0) * math.cos(math.radians(lat0)) * 111.32
    dy = (lat - lat0) * 110.57
    if math.hypot(dx, dy) <= RAIO_CENTRO_KM:
        return "Centro"
    ang = math.degrees(math.atan2(dx, dy)) % 360  # 0 = norte, sentido horario
    if ang >= 315 or ang < 45:
        return "Norte"
    if ang < 135:
        return "Leste"
    if ang < 225:
        return "Sul"
    return "Oeste"


def nome_com_categoria(nome, rot):
    """Acrescenta '(Categoria)' ao nome quando nenhuma palavra importante do rotulo ja esta nele (a busca da lista casa pelo NOME)."""
    if not rot or rot == "Sem categoria":
        return nome
    palavras = [p for p in chave_nome(rot).split() if len(p) >= 3]
    kn = chave_nome(nome).split()
    # palavra do rotulo ja no nome: igual, ou (se tem 4+ letras) comeca igual ("Farmacias" x "Farmacia"); com 3 letras so a igual ("Bar" nao e "Barcelona")
    if any(p in kn or (len(p) >= 4 and any(t.startswith(p[:5]) for t in kn)) for p in palavras):
        return nome
    sufixo = f" ({rot})"
    return nome if len(nome) + len(sufixo) > 100 else nome + sufixo  # nome ja no limite de 100 caracteres: sem sufixo (o verificador recusa nome > 120)


def descricao(rot, end, mun, cep, tel, site, conf):
    partes = []
    if rot:
        partes.append(rot)
    if end:
        partes.append(f"Endereço: {end}" + (f" — {mun}" if mun and mun.casefold() not in end.casefold() else ""))
    elif mun:
        partes.append(f"Município: {mun}")
    if cep and cep not in (end or ""):
        partes.append(f"CEP {cep}")
    if tel:
        partes.append(f"Tel.: {tel}")
    if site:
        partes.append(f"Site: {site}")
    partes.append("Overture, confiança " + f"{conf:.2f}".replace(".", ","))
    return " · ".join(partes)[:420]


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", sem_acento(s)).strip("-")


# ------------------------------------------------------------------ KML
def kml_doc(titulo, descr, itens):
    """itens: dicts com nome, desc, lon, lat. A lista importa OCULTA (sem pinos): <visibility>0</visibility> no Document."""
    cab = ['<?xml version="1.0" encoding="UTF-8"?>', '<kml xmlns="http://www.opengis.net/kml/2.2">', "  <Document>",
           f"    <name>{escape(titulo)}</name>", f"    <description>{escape(descr)}</description>", "    <visibility>0</visibility>",
           f'    <Style id="placemark-blue"><IconStyle><Icon><href>{ICONE}</href></Icon></IconStyle></Style>']
    corpo = [f"    <Placemark><name>{escape(it['nome'])}</name><description>{escape(it['desc'])}</description><styleUrl>#placemark-blue</styleUrl>"
             f"<Point><coordinates>{it['lon']:.6f},{it['lat']:.6f},0</coordinates></Point></Placemark>" for it in itens]
    return "\n".join(cab + corpo + ["  </Document>", "</kml>", ""])


def sha256_arquivo(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def grava(pasta, nome_arquivo, titulo, descr, itens, manifesto, regiao):
    caminho = pasta / nome_arquivo
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(kml_doc(titulo, descr, itens).encode("utf-8"))
    info = {"arquivo": nome_arquivo.replace("\\", "/"), "titulo": titulo, "regiao": regiao, "lugares": len(itens), "bytes": caminho.stat().st_size, "sha256": sha256_arquivo(caminho)}
    manifesto["arquivos"].append(info)
    print(f"  {info['arquivo']}: {info['lugares']} lugares, {info['bytes'] / 1048576:.1f} MB")
    return info


# ------------------------------------------------------------------ Overture
def prepara(linhas, categoria_no_nome=False, com_escolas=False):
    """Linhas (dicts do JSONL) -> (itens limpos, sem duplicados, em ordem estavel; cortes por motivo)."""
    cortes = {}

    def corta(motivo):
        cortes[motivo] = cortes.get(motivo, 0) + 1

    itens = []
    for r in linhas:
        status = r.get("status")
        if status not in (None, "open"):
            corta(f"situacao_{status}")
            continue
        cat = r.get("cat")
        if cat in ESCOLA_BASICA and not com_escolas:
            corta("escola_basica_(ja esta nas listas do INEP)")
            continue
        n = limpa_nome(r.get("nome"))
        motivo = motivo_nome_ruim(n)
        if motivo:
            corta(motivo)
            continue
        try:
            lon, lat = float(r["lon"]), float(r["lat"])
        except (KeyError, TypeError, ValueError):
            corta("sem_coordenada")
            continue
        rot = rotulo(cat) or "Sem categoria"
        conf = float(r.get("conf") or 0)
        itens.append({"id": str(r.get("id", "")), "nome": nome_com_categoria(n, rot) if categoria_no_nome else n, "nome_puro": n, "cat": cat or "",
                      "desc": descricao("" if rot == "Sem categoria" else rot, limpa_endereco(r.get("end")), r.get("mun"), limpa_texto(r.get("cep")),
                                        formata_tel(r.get("tel")), limpa_site(r.get("site")), conf),
                      "lon": lon, "lat": lat, "conf": conf, "mun": r.get("mun")})
    itens.sort(key=lambda x: (-x["conf"], x["id"]))
    por_nome, saida = {}, []
    for it in itens:  # duplicado = mesmo nome a no maximo DIST_DUP_M metros, de qualquer categoria; fica o de maior confianca
        pontos = por_nome.setdefault(chave_nome(it["nome_puro"]), [])
        kx = 111320.0 * math.cos(math.radians(it["lat"]))
        if any(math.hypot((it["lon"] - lon) * kx, (it["lat"] - lat) * 110574.0) <= DIST_DUP_M for lat, lon in pontos):
            corta(f"duplicado (mesmo nome a ate {DIST_DUP_M:.0f} m)")
            continue
        pontos.append((it["lat"], it["lon"]))
        saida.append(it)
    saida.sort(key=lambda x: (sem_acento(x["nome_puro"]), -x["conf"], x["id"]))
    return saida, dict(sorted(cortes.items()))


def le_jsonl(caminho):
    """Uma linha = um lugar (JSON). Aceita .jsonl e .jsonl.gz (o gz guarda o recorte inteiro em ~35 MB para regerar as listas sem baixar de novo)."""
    abre = gzip.open if str(caminho).endswith(".gz") else open
    with abre(caminho, "rt", encoding="utf-8") as f:
        for n, linha in enumerate(f, 1):
            if linha.strip():
                try:
                    yield json.loads(linha)
                except json.JSONDecodeError as e:
                    raise SystemExit(f"ABORTADO: {caminho} linha {n} nao e JSON ({e})") from None


def overture(jsonl, saida, release="desconhecida", conf_baixada=0.5, conf_capital=0.9, categoria_no_nome=False, com_escolas=False, so_baixada=False,
             conf_essencial=0.2, conf_essencial_capital=0.7):
    saida = pathlib.Path(saida)
    atribuicao = (f"Dados: Overture Maps Foundation (release {release}), licença CDLA-Permissive-2.0 (fontes Meta, Microsoft e outras; Foursquare em Apache-2.0; AllThePlaces em CC0-1.0). "
                  "Pode haver lugares fechados, mudados de endereço ou com coordenada aproximada. A busca principal do Organic Maps NÃO acha esta lista: use Buscar dentro dela.")
    manifesto = {"release": release, "licenca": "CDLA-Permissive-2.0 (Foursquare Apache-2.0; AllThePlaces CC0-1.0)",
                 "parametros": {"conf_baixada": conf_baixada, "conf_capital": conf_capital, "conf_essencial": conf_essencial, "conf_essencial_capital": conf_essencial_capital,
                                "categoria_no_nome": categoria_no_nome, "com_escolas": com_escolas}, "arquivos": [], "cortes": {}}
    baixada, capital = [], []
    for r in le_jsonl(jsonl):
        if r.get("mun") in BAIXADA:
            baixada.append(r)
        elif r.get("mun") == CAPITAL:
            capital.append(r)
    manifesto["lidos_baixada"], manifesto["lidos_capital"] = len(baixada), len(capital)

    itens, cortes = prepara(baixada, categoria_no_nome, com_escolas)
    def principal(i, minimo, minimo_essencial):
        return i["conf"] >= minimo or (i["cat"] in ESSENCIAIS and i["conf"] >= minimo_essencial)

    mais = [i for i in itens if principal(i, conf_baixada, conf_essencial)]
    menos = [i for i in itens if not principal(i, conf_baixada, conf_essencial)]
    regra = f"confiança >= {conf_baixada}, ou categoria do dia a dia (hospital, farmácia, mercado, órgão público, praia...) com confiança >= {conf_essencial}"
    print(f"Baixada: {len(baixada)} lidos -> {len(itens)} depois da limpeza ({len(mais)} na lista principal, {len(menos)} nos menos certos)")
    grava(saida, "lugares-baixada-santista.kml", "Lugares — Baixada Santista",
          f"Comércios, serviços, saúde, lazer e turismo dos 9 municípios da Baixada Santista ({regra}). " + atribuicao, mais, manifesto, "baixada")
    grava(saida, "lugares-baixada-santista-menos-certos.kml", "Lugares — Baixada Santista (menos certos)",
          "Lugares da Baixada Santista que ficaram fora da lista principal (confiança baixa): negócios pequenos reais, mas também páginas antigas. " + atribuicao, menos, manifesto, "baixada")
    for m in BAIXADA:
        grava(saida, f"por-municipio/lugares-{slug(m)}.kml", f"Lugares — {m}", f"Lugares de {m} ({regra}). " + atribuicao,
              [i for i in mais if i["mun"] == m], manifesto, "baixada")
    manifesto["cortes"]["baixada"] = cortes

    if not so_baixada:
        def vale_capital(r):
            c = float(r.get("conf") or 0)
            return c >= conf_capital or (r.get("cat") in ESSENCIAIS and c >= conf_essencial_capital)

        abaixo = sum(1 for r in capital if not vale_capital(r))
        itens, cortes = prepara([r for r in capital if vale_capital(r)], categoria_no_nome, com_escolas)
        cortes[f"fora_da_lista_por_confianca_(abaixo_de_{conf_capital}; essenciais abaixo de {conf_essencial_capital})"] = abaixo
        print(f"Sao Paulo: {len(capital)} lidos -> {len(itens)} com confianca >= {conf_capital} depois da limpeza")
        por_zona = {}
        for i in itens:
            por_zona.setdefault(zona_sp(i["lat"], i["lon"]), []).append(i)
        for z in ZONAS:
            grava(saida, f"lugares-sao-paulo-{slug(z)}.kml", f"Lugares — São Paulo, zona {z}",
                  f"Capital paulista, zona {z} (referência: Praça da Sé; confiança >= {conf_capital}, ou categoria do dia a dia com confiança >= {conf_essencial_capital}). " + atribuicao,
                  por_zona.get(z, []), manifesto, "capital")
        manifesto["cortes"]["capital"] = dict(sorted(cortes.items()))
    (saida / "manifesto.json").write_text(json.dumps(manifesto, indent=1, ensure_ascii=False), encoding="utf-8")
    print("cortes:", json.dumps(manifesto["cortes"], ensure_ascii=False))
    return manifesto


# ------------------------------------------------------------------ escolas do INEP (GeoPackage)
SIGLAS_ESCOLA = {"EE", "EM", "EMEF", "EMEI", "EMEIEF", "CEI", "CEU", "EMEFM", "EMEB", "CEMEI", "CIEJA", "ETEC", "FATEC", "IF", "CE", "CEEJA", "CMEI", "EEPG", "EEPSG", "EMPG", "EEEF",
                 "EEEFM", "EEEM", "CEEFM", "EMEBS", "EMEIF", "UBS", "SESI", "SENAI", "SESC", "APAE", "ONG", "CIEP", "CAIC", "ETE", "CEPE", "EMI", "ESC", "COL", "CEMEB", "NEI", "CRECHE"}


def bonito(nome):
    """MAIUSCULAS do INEP -> Capitalizado, mantendo siglas e numerais romanos."""
    saida = []
    for i, p in enumerate((nome or "").split()):
        baixo = p.lower()
        if p.upper() in SIGLAS_ESCOLA:
            saida.append(p.upper())
        elif baixo in ROMANOS and len(p) <= 5:
            saida.append(p.upper())
        elif baixo in PARTICULAS and i > 0:
            saida.append(baixo)
        else:
            saida.append("-".join(x.capitalize() for x in p.split("-")))
    return " ".join(saida)


def ponto_gpkg(blob):
    """GeoPackage binary (cabecalho 'GP') -> (lon, lat) de um WKB Point; None se invalido."""
    if not blob or blob[:2] != b"GP":
        return None
    env = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}.get((blob[3] >> 1) & 7)
    if env is None:
        return None
    wkb = blob[8 + env:]
    if len(wkb) < 21:
        return None
    fmt = "<" if wkb[0] == 1 else ">"
    if struct.unpack(fmt + "I", wkb[1:5])[0] & 0xFFFF != 1:
        return None
    return struct.unpack(fmt + "dd", wkb[5:21])


def nome_escola(nome, rede):
    n = bonito(nome)
    if rede == "Estadual":
        return n if re.match(r"^(E\.?E\.?|EE|EEEF|EEEFM|EEEM|EEPG|EEPSG|ETEC|CEEJA|CEEFM)\b", n) else "E.E. " + n
    if rede == "Privada":
        return n + " (particular)"
    return n


def descricao_escola(r):
    rede = r["government_level"] or ""
    partes = ["Escola particular" if (r["admin_category"] == "Privada" or rede == "Privada")
              else {"Estadual": "Escola estadual", "Municipal": "Escola municipal", "Federal": "Escola federal"}.get(rede, "Escola")]
    if r["education_level"]:
        partes.append(r["education_level"])
    if r["address"]:
        partes.append("Endereço: " + bonito(r["address"]))
    if r["phone_number"]:
        partes.append("Tel.: " + r["phone_number"])
    partes.append(f"INEP {r['code_school']} (Censo Escolar 2020; coordenada aproximada)")
    return " · ".join(partes)


def escolas_inep(gpkg, saida):
    saida = pathlib.Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect("file:" + str(gpkg).replace("\\", "/") + "?mode=ro&immutable=1", uri=True)
    con.row_factory = sqlite3.Row
    linhas = con.execute("select geom, name_muni, code_school, name_school, education_level, admin_category, address, phone_number, government_level "
                         "from schools_2020 where abbrev_state='SP'").fetchall()
    grupos = {"A": [], "B": [], "C": []}
    descartes = {"sem_ponto": 0, "fora_do_estado": 0, "sem_nome": 0}
    vistos = set()
    for r in linhas:
        if not (r["name_school"] or "").strip():
            descartes["sem_nome"] += 1
            continue
        p = ponto_gpkg(r["geom"])
        if not p:
            descartes["sem_ponto"] += 1
            continue
        lon, lat = p
        if not (-53.3 < lon < -44.0 and -25.4 < lat < -19.7):
            descartes["fora_do_estado"] += 1
            continue
        chave = (r["code_school"], r["name_school"])
        if chave in vistos:
            continue
        vistos.add(chave)
        item = {"nome": nome_escola(r["name_school"], r["government_level"]), "desc": descricao_escola(r), "lon": lon, "lat": lat}
        if r["name_muni"] in BAIXADA:
            grupos["A"].append(item)
        elif r["name_muni"] == CAPITAL:
            grupos["B"].append(item)
        elif r["government_level"] == "Estadual":
            grupos["C"].append(item)
    espec = {
        "A": ("escolas-baixada-santista", "Escolas — Baixada Santista", "Todas as redes (estadual, municipal, federal, particular) de Bertioga, Cubatão, Guarujá, Itanhaém, Mongaguá, Peruíbe, Praia Grande, Santos e São Vicente."),
        "B": ("escolas-sao-paulo-capital", "Escolas — São Paulo capital", "Todas as redes do município de São Paulo."),
        "C": ("escolas-estaduais-sp-interior", "Escolas estaduais — resto de SP", "Rede estadual (SEDUC-SP) fora da Baixada Santista e da capital."),
    }
    print("linhas SP lidas:", len(linhas), "| descartes:", descartes)
    manifesto = {"fonte": "INEP/IPEA geobr, Censo Escolar 2020 (schools_2020.gpkg)", "arquivos": [], "descartes": descartes}
    for k, (arq, titulo, d) in espec.items():
        itens = sorted(grupos[k], key=lambda x: sem_acento(x["nome"]))
        grava(saida, f"{arq}.kml", titulo, d + " Fonte: INEP, Censo Escolar 2020 (dados abertos). Coordenadas aproximadas; escolas abertas ou fechadas depois de 2020 podem não constar ou ter mudado.",
              itens, manifesto, "escolas")
    (saida / "manifesto.json").write_text(json.dumps(manifesto, indent=1, ensure_ascii=False), encoding="utf-8")
    return manifesto


# ------------------------------------------------------------------ verificacao (so le os KML e o manifesto; reaproveita do gerador as funcoes de texto, RE_EMAIL, BBOX e sha256_arquivo)
CONSULTAS = ["mercado municipal", "aquario", "guilherme alvaro", "praiamar", "rodoviaria", "drogasil", "droga raia", "pacheco", "extra", "shell", "ipiranga", "carrefour",
             "atacadao", "assai", "habibs", "mcdonald", "santa casa", "unimed", "caixa economica", "banco do brasil", "correios", "farmacia", "padaria", "hotel", "pousada"]


def le_kml(caminho):
    """(titulo, descricao, visibilidade, [(nome, desc, lon, lat)], n_documents); levanta ET.ParseError se o XML nao presta e ValueError se tem DOCTYPE/ENTITY."""
    with open(caminho, "rb") as f:
        inicio = f.read(8192).lower()
    if b"<!doctype" in inicio or b"<!entity" in inicio:  # expansao de entidades (billion laughs): KML de verdade nunca tem
        raise ValueError("DOCTYPE/ENTITY no inicio do arquivo")
    pilha, doc, itens, n_doc, atual = [], {"name": None, "description": None, "visibility": None}, [], 0, None
    for ev, el in ET.iterparse(str(caminho), events=("start", "end")):
        tag = el.tag.rsplit("}", 1)[-1]
        if ev == "start":
            pilha.append(tag)
            if tag == "Document":
                n_doc += 1
            if tag == "Placemark":
                atual = {}
            continue
        pilha.pop()
        pai = pilha[-1] if pilha else ""
        if pai == "Document" and tag in doc and doc[tag] is None:
            doc[tag] = el.text
        elif tag == "Placemark" and atual is not None:
            c = atual.get("c", "").split(",")
            itens.append((atual.get("n", ""), atual.get("d", ""), float(c[0]), float(c[1])))
            atual = None
            el.clear()
        elif atual is not None and pai == "Placemark":
            if tag == "name":
                atual["n"] = el.text or ""
            elif tag == "description":
                atual["d"] = el.text or ""
        elif atual is not None and tag == "coordinates":
            atual["c"] = (el.text or "").strip()
    return doc["name"], doc["description"], doc["visibility"], itens, n_doc


def verificar(pasta, n_nominatim=0, saida=print):
    """Devolve a lista de falhas (vazia = APROVADO). So le."""
    pasta = pathlib.Path(pasta)
    falhas = []

    def ok(cond, msg):
        if not cond:
            falhas.append(msg)
            saida("  FALHA: " + msg)
        return cond

    man = json.loads((pasta / "manifesto.json").read_text(encoding="utf-8"))
    saida(f"arquivos no manifesto: {len(man['arquivos'])}")
    ok(bool(man["arquivos"]), "manifesto com lista de arquivos vazia (nada foi conferido)")
    no_manifesto = {pathlib.PurePosixPath(i["arquivo"]).as_posix() for i in man["arquivos"]}
    for kml in sorted(pasta.rglob("*.kml")):
        rel = kml.relative_to(pasta).as_posix()
        ok(rel in no_manifesto, f"{rel}: KML na pasta fora do manifesto (sobra de outra geracao; nao foi conferido)")
    dados = {}
    for info in man["arquivos"]:
        arq = pasta / info["arquivo"]
        saida(f"[{info['arquivo']}]")
        if not ok(arq.is_file(), f"{info['arquivo']}: arquivo nao existe"):
            continue
        ok(sha256_arquivo(arq) == info["sha256"] and arq.stat().st_size == info["bytes"], f"{info['arquivo']}: SHA-256 ou tamanho diferem do manifesto")
        try:
            titulo, descr, vis, itens, n_doc = le_kml(arq)
        except (ET.ParseError, ValueError, IndexError) as e:
            ok(False, f"{info['arquivo']}: XML mal formado ({e})")
            continue
        ok(n_doc == 1 and bool(titulo) and bool(descr) and (vis or "").strip() == "0", f"{info['arquivo']}: Document (n={n_doc}, titulo, descricao) ou visibility != 0")
        ok(titulo == info["titulo"], f"{info['arquivo']}: titulo difere do manifesto")
        ok(len(itens) == info["lugares"], f"{info['arquivo']}: {len(itens)} Placemarks, manifesto diz {info['lugares']}")
        regiao = BBOX.get(info["regiao"])
        ruins = {"nome vazio": 0, "nome longo": 0, "controle": 0, "fora da regiao": 0, "lon/lat invertidos": 0, "coordenada zero": 0, "e-mail": 0, "CPF": 0}
        vistos, dup = set(), 0
        for n, d, lon, lat in itens:
            ruins["nome vazio"] += not n.strip()
            ruins["nome longo"] += len(n) > 120
            ruins["controle"] += any(unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co") for ch in n + d)
            if regiao:
                ruins["fora da regiao"] += not (regiao[0] <= lon <= regiao[2] and regiao[1] <= lat <= regiao[3])
                ruins["lon/lat invertidos"] += lon > lat  # nas regioes de SP lon (-47..-45) e sempre menor que lat (-24..-23)
            ruins["coordenada zero"] += abs(lon) < 1e-6 and abs(lat) < 1e-6
            ruins["e-mail"] += bool(RE_EMAIL.search(n) or RE_EMAIL.search(d))
            ruins["CPF"] += bool(RE_CPF.search(n) or RE_CPF.search(d))
            k = (sem_acento(n), round(lat * TOL_DUP), round(lon * TOL_DUP))
            dup += k in vistos
            vistos.add(k)
        for k, v in ruins.items():
            ok(v == 0, f"{info['arquivo']}: {v} placemark(s) com problema '{k}'")
        ok(dup == 0, f"{info['arquivo']}: {dup} duplicado(s) (mesmo nome na mesma celula de ~28 m)")
        saida(f"  {len(itens)} lugares, {info['bytes'] / 1048576:.1f} MB, sha256 {info['sha256'][:12]}..., duplicados {dup}, problemas {sum(ruins.values())}")
        dados[info["arquivo"]] = itens

    principal = dados.get("lugares-baixada-santista.kml")
    if principal is not None:
        chaves = {(n, round(lon, 6), round(lat, 6)) for n, _, lon, lat in principal}
        soma, uniao, repetidos = 0, set(), 0
        for arq, itens in dados.items():
            if arq.startswith("por-municipio/"):
                ks = [(n, round(lon, 6), round(lat, 6)) for n, _, lon, lat in itens]
                soma += len(ks)
                repetidos += len(set(ks) & uniao)
                uniao |= set(ks)
        saida(f"particao: soma dos municipios {soma} | lista principal {len(principal)} | repetidos entre municipios {repetidos}")
        ok(soma == len(principal) and uniao == chaves, "as listas por municipio nao reproduzem a lista principal")
        ok(repetidos == 0, "lugar em mais de um municipio")
        saida("busca por nome (acento ignorado) [principal | menos certos | capital]:")
        pr = [sem_acento(n) for n, *_ in principal]
        me = [sem_acento(n) for n, *_ in dados.get("lugares-baixada-santista-menos-certos.kml", [])]
        ca = [sem_acento(n) for a, it in dados.items() if a.startswith("lugares-sao-paulo-") for n, *_ in it]
        for q in CONSULTAS:
            saida(f"  {q:20} {sum(q in n for n in pr):5} | {sum(q in n for n in me):5} | {sum(q in n for n in ca):5}")

    if n_nominatim > 0:
        random.seed(11)
        total = acertos = 0
        for arq, itens in sorted(dados.items()):
            if not arq.startswith("por-municipio/") or not itens:
                continue
            esperado = sem_acento(next(i["titulo"] for i in man["arquivos"] if i["arquivo"] == arq).split("—", 1)[1].strip())
            for n, d, lon, lat in random.sample(itens, min(n_nominatim, len(itens))):
                url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode({"lat": f"{lat:.6f}", "lon": f"{lon:.6f}", "format": "jsonv2", "zoom": 10, "addressdetails": 1})
                req = urllib.request.Request(url, headers={"User-Agent": "android-embeeded-verificacao/1.0 (uso pessoal; conferencia de listas de lugares)", "Accept-Language": "pt-BR"})
                try:
                    with urllib.request.urlopen(req, timeout=30) as r:
                        ad = json.load(r).get("address", {})
                    achado = sem_acento(ad.get("city") or ad.get("town") or ad.get("municipality") or ad.get("village") or ad.get("county") or "")
                except (OSError, ValueError) as e:
                    achado = f"(erro: {type(e).__name__})"
                total += 1
                bate = esperado == achado
                acertos += bate
                if not bate:
                    saida(f"   difere: esperado {esperado!r}, OSM diz {achado!r} em ({lat:.4f},{lon:.4f})")
                time.sleep(1.1)
        saida(f"Nominatim: {acertos} de {total} batem com o municipio da lista")
        ok(total == 0 or acertos / total >= 0.85, f"so {acertos} de {total} batem com o OpenStreetMap")
    saida("RESULTADO: " + ("APROVADO" if not falhas else f"REPROVADO ({len(falhas)} falha(s))"))
    return falhas


def main():
    ap = argparse.ArgumentParser(description="Listas KML de lugares para o Organic Maps (importam ocultas).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("escolas-inep")
    p.add_argument("gpkg")
    p.add_argument("saida")
    p = sub.add_parser("overture")
    p.add_argument("jsonl")
    p.add_argument("saida")
    p.add_argument("--release", default="desconhecida")
    p.add_argument("--conf-baixada", type=float, default=0.5)
    p.add_argument("--conf-capital", type=float, default=0.9)
    p.add_argument("--conf-essencial", type=float, default=0.2)
    p.add_argument("--conf-essencial-capital", type=float, default=0.7)
    p.add_argument("--categoria-no-nome", action="store_true")
    p.add_argument("--com-escolas", action="store_true")
    p.add_argument("--so-baixada", action="store_true")
    p = sub.add_parser("verificar")
    p.add_argument("pasta")
    p.add_argument("n_nominatim", nargs="?", type=int, default=0)
    a = ap.parse_args()
    if a.cmd == "escolas-inep":
        escolas_inep(a.gpkg, a.saida)
    elif a.cmd == "overture":
        for nome in ("conf_baixada", "conf_capital", "conf_essencial", "conf_essencial_capital"):
            if not 0.0 <= getattr(a, nome) <= 1.0:
                sys.exit(f"ABORTADO: --{nome.replace('_', '-')} entre 0 e 1")
        overture(a.jsonl, a.saida, a.release, a.conf_baixada, a.conf_capital, a.categoria_no_nome, a.com_escolas, a.so_baixada, a.conf_essencial, a.conf_essencial_capital)
    else:
        if not 0 <= a.n_nominatim <= 50:
            sys.exit("ABORTADO: N_nominatim entre 0 e 50 (limite de uso educado do servico gratuito)")
        sys.exit(1 if verificar(a.pasta, a.n_nominatim) else 0)


if __name__ == "__main__":
    main()
