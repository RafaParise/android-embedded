"""Testes de scripts/saude.py (painel de saude do A12, SO LEITURA): cada leitura com saida real do aparelho (01/11/2026),
os limites exatos de cada aviso, a regra das mortes de apps (so Chimera/lmkd contam como falta de memoria), o historico de
espaco livre, a consulta online (sem rede de verdade) e o main inteiro com um adb falso que confere que so saem comandos de leitura.
"""
import datetime
import json
import re

import pytest

AGORA = datetime.datetime(2026, 11, 1, 11, 0, 0)
GB = 1024 * 1024  # em kB

BATERIA = """Current Battery Service state:
  AC powered: false
  USB powered: true
  Wireless powered: false
  Max charging current: 0
  Max charging voltage: 0
  Charge counter: 1185000
  status: 2
  health: 2
  present: true
  level: 23
  scale: 100
  voltage: 3723
  temperature: 325
  technology: Li-ion
  health: vendor.samsung.hardware.health@2.0::ISehHealth@Proxy
"""
TERMICA = """Thermal Status: 1
Cached temperatures:
\tTemperature{mValue=0.0, mType=2, mName=SUBBAT, mStatus=0}
\tTemperature{mValue=45.5, mType=0, mName=AP, mStatus=0}
\tTemperature{mValue=41.5, mType=5, mName=PA, mStatus=0}
\tTemperature{mValue=32.5, mType=2, mName=BAT, mStatus=0}
\tTemperature{mValue=47.0, mType=0, mName=AP, mStatus=0}
"""
MEMINFO = """MemTotal:        3841188 kB
MemFree:           93220 kB
MemAvailable:    1900000 kB
SwapTotal:       4194300 kB
SwapFree:        2096560 kB
"""
MM_STAT = "1713647616 389340629 435236864        0 915943424    22379   562986     6301"
PSI_MEM = "some avg10=0.72 avg60=1.07 avg300=0.76 total=119982842\nfull avg10=0.33 avg60=0.46 avg300=0.35 total=65427540"
PSI_CPU = "some avg10=3.07 avg60=5.85 avg300=4.63 total=1285600758"
PSI_IO = "some avg10=2.14 avg60=3.46 avg300=2.71 total=368702723\nfull avg10=1.47 avg60=1.57 avg300=1.41 total=256566290"
MEMINFO_PSS = """Applications Memory Usage (in Kilobytes):
Uptime: 123 Realtime: 456

Total PSS by process:
    749,140K: npm install omniroute (pid 20158)
    184,287K: system (pid 1267)
     54,945K: com.sec.android.app.launcher (pid 2056 / activities)

Total PSS by OOM adjustment:
    264,867K: Persistent
        184,287K: system (pid 1267)
    379,540K: Cached
        54,945K: com.sec.android.app.launcher (pid 2056 / activities)

Total PSS by category:
    300,000K: Native
"""
DF = "Filesystem       1K-blocks     Used Available Use% Mounted on\n/dev/block/dm-8   53762032 41257420  12504612  77% /data"
ALARMES = """+1m10s0ms running, 60 wakeups, 60 alarms: u0a187:com.google.android.gms
    +1m4s43ms running, 7 wakeups, 7 alarms: u0a93:com.android.providers.calendar
    +51s74ms running, 45 wakeups, 45 alarms: u0a187:com.google.android.gms
    +16s919ms running, 160 wakeups, 673 alarms: 1000:android
    +9s420ms running, 1 wakeups, 1 alarms: u0a186:com.android.vending"""
WIFI = ('Wifi is enabled\nWifi is connected to "Rede"\nWifiInfo: SSID: "Rede", BSSID: aa:bb, RSSI: -51, Link speed: 78Mbps, '
        'Tx Link speed: 78Mbps, Frequency: 2412MHz, Net ID: 3')
FOTA = """<?xml version="1.0" encoding="UTF-8" ?>
<versioninfo><firmware><model>SM-A125M</model><cc>ZTO</cc><version>
<latest o="12">A125MUBS6CXJ1/A125MOWO6CXJ1/A125MUBS6CXJ1</latest></version></firmware></versioninfo>"""
VERSOES = "package:org.fossify.phone versionCode:22\npackage:com.termux versionCode:1002\npackage:com.outro versionCode:7"


def _morte(mes_dia, hora, nome, adj, motivo):
    return f"{mes_dia} {hora}.085  1267  1636 I am_kill : [0,3046,{nome},{adj},{motivo}]"


def _bat(**mudar):
    base = {"nivel": 50, "estado": 3, "saude": 2, "temp_dec": 300, "carga_uah": 2_500_000}
    base.update(mudar)
    return base


# ------------------------------------------------------------------ leituras
def test_parse_bateria_le_os_numeros_e_ignora_a_linha_health_de_texto(importa_script):
    mod = importa_script("saude.py")
    assert mod.parse_bateria(BATERIA) == {"nivel": 23, "estado": 2, "saude": 2, "temp_dec": 325, "mv": 3723, "carga_uah": 1185000}
    assert mod.parse_bateria("nada") == {}


def test_capacidade_estimada_divide_a_carga_pelo_nivel_e_exige_nivel_15(importa_script):
    mod = importa_script("saude.py")
    assert mod.capacidade_estimada_mah({"nivel": 23, "carga_uah": 1185000}) == pytest.approx(5152.17, abs=0.01)
    assert mod.capacidade_estimada_mah({"nivel": 15, "carga_uah": 750000}) == pytest.approx(5000.0)
    assert mod.capacidade_estimada_mah({"nivel": 14, "carga_uah": 750000}) is None
    assert mod.capacidade_estimada_mah({"nivel": 50, "carga_uah": 0}) is None
    assert mod.capacidade_estimada_mah({"nivel": 50}) is None


def test_parse_termica_guarda_o_maior_valor_de_cada_sensor(importa_script):
    mod = importa_script("saude.py")
    t = mod.parse_termica(TERMICA)
    assert t["status"] == 1
    assert t["temps"]["AP"] == 47.0 and t["temps"]["BAT"] == 32.5 and t["temps"]["PA"] == 41.5
    assert mod.parse_termica("sem nada") == {"status": None, "temps": {}}


def test_parse_meminfo_zram_e_psi(importa_script):
    mod = importa_script("saude.py")
    assert mod.parse_meminfo(MEMINFO) == {"MemTotal": 3841188, "MemAvailable": 1900000, "SwapTotal": 4194300, "SwapFree": 2096560}
    z = mod.parse_mm_stat(MM_STAT)
    assert z["orig"] == 1713647616 and z["compr"] == 389340629 and z["usada"] == 435236864
    assert z["razao"] == pytest.approx(4.40, abs=0.01)
    assert mod.parse_mm_stat("") is None and mod.parse_mm_stat("a b c") is None
    assert mod.parse_mm_stat("100 0 50")["razao"] is None  # sem dividir por zero
    psi = mod.parse_psi(PSI_MEM)
    assert psi["some"]["avg60"] == 1.07 and psi["full"]["avg60"] == 0.46 and psi["some"]["avg10"] == 0.72
    assert mod.parse_psi(PSI_CPU) == {"some": {"avg10": 3.07, "avg60": 5.85, "avg300": 4.63}}
    assert mod.parse_psi("") == {}


def test_parse_pss_so_le_o_bloco_por_processo_e_ordena(importa_script):
    mod = importa_script("saude.py")
    assert mod.parse_pss(MEMINFO_PSS) == [(749140, "npm install omniroute", 20158), (184287, "system", 1267),
                                          (54945, "com.sec.android.app.launcher", 2056)]
    assert mod.parse_pss("Total PSS by OOM adjustment:\n    1,000K: x (pid 1)") == []  # sem o bloco certo, nada
    assert mod.parse_pss("Total PSS by process:\n    1.234K: y (pid 9)")[0][0] == 1234    # ponto como separador


def test_parse_df_pega_a_ultima_linha_numerica(importa_script):
    mod = importa_script("saude.py")
    assert mod.parse_df(DF) == {"total_kb": 53762032, "usado_kb": 41257420, "livre_kb": 12504612}
    assert mod.parse_df("Filesystem 1K-blocks\nsem numeros aqui") is None
    assert mod.parse_df("") is None


def test_parse_mortes_filtra_pela_janela_e_nao_pega_o_futuro(importa_script):
    mod = importa_script("saude.py")
    texto = "\n".join([
        _morte("11-01", "10:56:18", "com.google.android.tts", 905, "Chimera #0"),                 # 3 min antes: entra
        _morte("11-01", "10:00:00", "com.limite", 925, "Chimera #0"),                             # exatamente 60 min: entra
        _morte("11-01", "09:59:59", "com.fora", 925, "Chimera #0"),                               # 60 min e 1 s: fora
        _morte("11-01", "11:05:00", "com.futuro", 925, "Chimera #0"),                             # depois de 'agora': fora
        "linha que nao e de morte",
        _morte("10-31", "11:00:00", "com.ontem", 925, "Chimera #0"),                              # ontem: fora
    ])
    nomes = [m[1] for m in mod.parse_mortes(texto, AGORA)]
    assert nomes == ["com.google.android.tts", "com.limite"]
    assert "com.ontem" in [m[1] for m in mod.parse_mortes(texto, AGORA, minutos=24 * 60)]      # a janela e parametro


def test_parse_mortes_vira_o_ano_e_guarda_adj_e_motivo(importa_script):
    mod = importa_script("saude.py")
    virada = datetime.datetime(2027, 1, 1, 0, 10, 0)
    texto = _morte("12-31", "23:50:00", "app.virada", 0, "stop app.virada due to from pid 99")
    saida = mod.parse_mortes(texto, virada)
    assert len(saida) == 1
    assert saida[0][0] == datetime.datetime(2026, 12, 31, 23, 50, 0)
    assert saida[0][1:] == ("app.virada", 0, "stop app.virada due to from pid 99")
    assert mod.parse_mortes(_morte("02-30", "10:00:00", "x", 1, "m"), AGORA) == []  # data impossivel nao derruba


def test_parse_alarmes_vale_o_maior_valor_do_pacote_e_tira_o_prefixo_do_uid(importa_script):
    mod = importa_script("saude.py")
    assert mod.parse_alarmes(ALARMES) == [(160, "android"), (60, "com.google.android.gms"), (7, "com.android.providers.calendar"),
                                          (1, "com.android.vending")]
    assert mod.parse_alarmes("") == []


def test_parse_wakelocks_e_wifi(importa_script):
    mod = importa_script("saude.py")
    assert mod.parse_wakelocks("  Wake Locks: size=2") == 2
    assert mod.parse_wakelocks("nada") is None
    w = mod.parse_wifi(WIFI)
    assert w == {"conectado": True, "rssi": -51, "mbps": 78, "mhz": 2412}
    assert mod.parse_wifi("Wifi is disabled")["conectado"] is False
    assert mod.parse_wifi("Wifi is connected to x")["conectado"] is False  # sem RSSI nao ha o que avaliar


def test_parse_versoes_fota_e_build(importa_script):
    mod = importa_script("saude.py")
    assert mod.parse_versoes(VERSOES) == {"org.fossify.phone": 22, "com.termux": 1002, "com.outro": 7}
    assert mod.fota_ultima(FOTA) == "A125MUBS6CXJ1"
    assert mod.fota_ultima("") is None and mod.fota_ultima(None) is None
    assert mod.build_instalado("SP1A.210812.016.A125MUBS6CXJ1") == "A125MUBS6CXJ1"
    assert mod.build_instalado("") == ""


# ------------------------------------------------------------------ avaliacao: limites exatos
def test_av_bateria_limites_de_capacidade_e_temperatura(importa_script):
    mod = importa_script("saude.py")
    assert mod.av_bateria(_bat())[0] == mod.OK
    assert mod.av_bateria(_bat(carga_uah=2_000_000))[0] == mod.OK        # 4000 mAh = 80,0 %: ainda OK
    assert mod.av_bateria(_bat(carga_uah=1_999_000))[0] == mod.AT        # 79,96 %
    assert mod.av_bateria(_bat(carga_uah=1_500_000))[0] == mod.AT        # 60,0 %: ainda so atencao
    assert mod.av_bateria(_bat(carga_uah=1_499_000))[0] == mod.AL        # 59,96 %
    assert mod.av_bateria(_bat(temp_dec=399))[0] == mod.OK
    assert mod.av_bateria(_bat(temp_dec=400))[0] == mod.AT
    assert mod.av_bateria(_bat(temp_dec=449))[0] == mod.AT
    assert mod.av_bateria(_bat(temp_dec=450))[0] == mod.AL


def test_av_bateria_saude_estado_nivel_baixo_e_leitura_vazia(importa_script):
    mod = importa_script("saude.py")
    nivel, texto = mod.av_bateria(_bat(saude=3))
    assert nivel == mod.AT and "codigo 3" in texto
    nivel, texto = mod.av_bateria(_bat(nivel=14))
    assert nivel == mod.OK and "capacidade nao estimada (nivel abaixo de" in texto
    nivel, texto = mod.av_bateria(_bat(nivel=80, carga_uah=0))
    assert nivel == mod.OK and "sem charge counter" in texto and "nivel abaixo" not in texto
    assert mod.av_bateria({})[0] == mod.AT
    assert mod.av_bateria(_bat(carga_uah=1_499_000, temp_dec=410, saude=3))[0] == mod.AL   # alerta nao desce para atencao
    assert "carregando" in mod.av_bateria(_bat(estado=2))[1] and "100% do projeto" in mod.av_bateria(_bat())[1]


def test_av_termica_so_o_status_decide(importa_script):
    mod = importa_script("saude.py")
    assert [mod.av_termica({"status": s, "temps": {}})[0] for s in (0, 1, 2, 3, 4)] == [mod.OK, mod.OK, mod.AT, mod.AL, mod.AL]
    assert mod.av_termica({"status": None, "temps": {}})[0] == mod.AT
    nivel, texto = mod.av_termica({"status": 1, "temps": {"AP": 46.7, "BAT": 33.1, "LRB": 37.0, "USB": 0.0}})
    assert nivel == mod.OK and "AP 46.7 C" in texto and "BAT 33.1 C" in texto and "LRB" not in texto and "USB" not in texto
    assert "AP" not in mod.av_termica({"status": 0, "temps": {"AP": 0.0, "BAT": 33.1}})[1]      # sensor zerado nao e leitura


def test_av_memoria_limites_de_disponivel_e_swap(importa_script):
    mod = importa_script("saude.py")
    mi = {"MemTotal": 3841188, "MemAvailable": 500 * 1024, "SwapTotal": 1000, "SwapFree": 150}
    assert mod.av_memoria(mi, None)[0] == mod.OK                          # 500 MB exatos e swap 85,0 %
    assert mod.av_memoria({**mi, "MemAvailable": 500 * 1024 - 1}, None)[0] == mod.AT
    assert mod.av_memoria({**mi, "MemAvailable": 300 * 1024}, None)[0] == mod.AT
    assert mod.av_memoria({**mi, "MemAvailable": 300 * 1024 - 1}, None)[0] == mod.AL
    assert mod.av_memoria({**mi, "SwapFree": 149}, None)[0] == mod.AT     # 85,1 %
    assert mod.av_memoria({}, None)[0] == mod.AT
    assert mod.av_memoria({**mi, "MemAvailable": 1, "SwapFree": 100}, None)[0] == mod.AL   # swap a 90 % nao rebaixa o alerta


def test_av_memoria_mostra_zram_e_swap(importa_script):
    mod = importa_script("saude.py")
    z = mod.parse_mm_stat(MM_STAT)
    nivel, texto = mod.av_memoria(mod.parse_meminfo(MEMINFO), z)
    assert nivel == mod.OK
    assert "disponivel 1855 MB de 3751 MB" in texto and "swap 2049 MB usados (50%)" in texto and "4.4:1" in texto


def _psi(mem_some=1.0, mem_full=0.5, cpu_some=3.0, io_full=0.2):
    return {"memory": {"some": {"avg60": mem_some}, "full": {"avg60": mem_full}}, "cpu": {"some": {"avg60": cpu_some}},
            "io": {"full": {"avg60": io_full}}}


def test_av_pressao_limites(importa_script):
    mod = importa_script("saude.py")
    assert mod.av_pressao(_psi())[0] == mod.OK
    assert mod.av_pressao(_psi(mem_full=1.99))[0] == mod.OK
    assert mod.av_pressao(_psi(mem_full=2.0))[0] == mod.AT
    assert mod.av_pressao(_psi(mem_full=9.99))[0] == mod.AT
    assert mod.av_pressao(_psi(mem_full=10.0))[0] == mod.AL
    assert mod.av_pressao(_psi(mem_full=10.0, mem_some=20.0))[0] == mod.AL                  # outro aviso nao rebaixa o alerta
    assert mod.av_pressao(_psi(mem_some=14.9))[0] == mod.OK and mod.av_pressao(_psi(mem_some=15.0))[0] == mod.AT
    assert mod.av_pressao(_psi(cpu_some=39.9))[0] == mod.OK and mod.av_pressao(_psi(cpu_some=40.0))[0] == mod.AT
    assert mod.av_pressao(_psi(io_full=9.9))[0] == mod.OK and mod.av_pressao(_psi(io_full=10.0))[0] == mod.AT
    assert mod.av_pressao({})[0] == mod.AT
    assert mod.av_pressao({"memory": {"some": {"avg60": 1.0}, "full": {"avg60": 0.1}}})[0] == mod.OK   # CPU e disco ausentes nao sao problema
    assert "CPU espera ?" in mod.av_pressao({"memory": {"some": {"avg60": 1.0}}})[1]


def test_av_pesados_limites_e_nomes(importa_script):
    mod = importa_script("saude.py")
    mb = 1024
    leve = [(184 * mb, "system", 1), (179 * mb, "org.mozilla.fennec_fdroid", 2)]
    assert mod.av_pesados(leve)[0] == mod.OK
    assert mod.av_pesados([(450 * mb - 1, "x", 3)])[0] == mod.OK
    nivel, texto = mod.av_pesados([(450 * mb, "npm install omniroute", 4)] + leve)
    assert nivel == mod.AT and "ACIMA DE 450 MB" in texto and "npm install omniroute 450 MB" in texto
    assert mod.av_pesados([(700 * mb - 1, "x", 5)])[0] == mod.AT
    assert mod.av_pesados([(700 * mb, "y", 6)])[0] == mod.AL
    assert mod.av_pesados([])[0] == mod.AT
    cinco = [((100 - i) * mb, f"p{i}", i) for i in range(5)]
    texto = mod.av_pesados(cinco)[1]
    assert "p3 97 MB" in texto and "p4" not in texto                                          # o topo mostra 4 processos


def test_av_espaco_limites_e_queda(importa_script):
    mod = importa_script("saude.py")
    total = 50 * GB
    def livre(pct):
        return {"total_kb": total, "livre_kb": int(total * pct / 100)}
    assert mod.av_espaco(livre(15.0))[0] == mod.OK
    assert mod.av_espaco(livre(14.9))[0] == mod.AT
    assert mod.av_espaco(livre(10.0))[0] == mod.AT
    assert mod.av_espaco(livre(9.9))[0] == mod.AL
    assert mod.av_espaco(None)[0] == mod.AT
    atual = {"total_kb": total, "livre_kb": 12 * GB}
    antes = {"ts": "2026-10-31T21:00:00", "livre_kb": 14 * GB}
    nivel, texto = mod.av_espaco(atual, antes)
    assert nivel == mod.AT and "CAIU 2.0 GB desde 2026-10-31 21:00" in texto       # exatamente 2 GB ja avisa
    assert mod.av_espaco(atual, {"ts": "x", "livre_kb": 14 * GB - 1})[0] == mod.OK  # 1 kB a menos que 2 GB: nao avisa
    nivel, texto = mod.av_espaco(atual, {"ts": "2026-10-31T21:00:00", "livre_kb": 10 * GB})
    assert nivel == mod.OK and "subiu 2.0 GB" in texto
    assert "CAIU" not in mod.av_espaco(atual, {"livre_kb": None})[1]
    quase_cheio = {"total_kb": total, "livre_kb": int(total * 0.05)}
    assert mod.av_espaco(quase_cheio, {"ts": "x", "livre_kb": quase_cheio["livre_kb"] + 3 * GB})[0] == mod.AL   # queda nao rebaixa o alerta


def test_av_mortes_so_conta_memoria_de_verdade(importa_script):
    mod = importa_script("saude.py")
    q = AGORA
    def m(nome, adj, motivo):
        return (q, nome, adj, motivo)
    assert mod.av_mortes([])[0] == mod.OK
    # faxina normal, mesmo com adj 0 (o processo isolado do Vivo): nao e falta de memoria
    nivel, texto = mod.av_mortes([m("br.com.vivo.hj:tj", 0, "isolated not needed"), m("net.sourceforge.opencamera", 0, "stop net.sourceforge.opencamera due to from pid 9")])
    assert nivel == mod.OK and "2 no total, 0 por falta de memoria" in texto
    assert mod.av_mortes([m("a", 905, "Chimera #0"), m("b", 999, "Chimera #1")])[0] == mod.OK
    nivel, texto = mod.av_mortes([m("net.sourceforge.opencamera", 250, "Chimera #0")])
    assert nivel == mod.AL and "net.sourceforge.opencamera" in texto
    assert mod.av_mortes([m("x", 100, "ML_Kill: timeout 5 slots kill a")])[0] == mod.AL
    assert mod.av_mortes([m("x", 100, "lmkd kill")])[0] == mod.AL
    assert mod.av_mortes([m("x", 251, "Chimera #0")])[0] == mod.AT         # servico / ultimo app
    assert mod.av_mortes([m("x", 899, "Chimera #0")])[0] == mod.AT
    assert mod.av_mortes([m("x", 900, "Chimera #0")])[0] == mod.OK         # 900 ja e app em cache


def test_av_mortes_reciclagem_alta_a_partir_de_30(importa_script):
    mod = importa_script("saude.py")
    cached = [(AGORA, f"app{i}", 950, "Chimera #0") for i in range(30)]
    assert mod.av_mortes(cached[:29])[0] == mod.OK
    nivel, texto = mod.av_mortes(cached)
    assert nivel == mod.AT and "reciclagem alta" in texto


def test_av_acorda_wifi_firmware_e_apps(importa_script):
    mod = importa_script("saude.py")
    nivel, texto = mod.av_acorda([(160, "android"), (60, "gms"), (7, "cal"), (1, "vending")], 2)
    assert nivel == mod.OK and "android 160, gms 60, cal 7" in texto and "vending" not in texto and "agora: 2" in texto
    assert "sem dados" in mod.av_acorda([], None)[1] and "agora: ?" in mod.av_acorda([], None)[1]
    assert mod.av_wifi({"conectado": False})[0] == mod.OK
    assert mod.av_wifi({"conectado": True, "rssi": -75, "mbps": 10, "mhz": 2412})[0] == mod.OK
    assert mod.av_wifi({"conectado": True, "rssi": -76, "mbps": 10, "mhz": 2412})[0] == mod.AT
    assert "5 GHz" in mod.av_wifi({"conectado": True, "rssi": -50, "mbps": 300, "mhz": 5180})[1]
    assert "2,4 GHz" in mod.av_wifi({"conectado": True, "rssi": -50, "mbps": 70, "mhz": 2412})[1]
    assert mod.av_firmware("A125MUBS6CXJ1", "A125MUBS6CXJ1")[0] == mod.OK
    nivel, texto = mod.av_firmware("A125MUBS6CXJ1", "A125MUBS7CXK1")
    assert nivel == mod.AT and "A125MUBS7CXK1" in texto
    assert mod.av_firmware("A125MUBS6CXJ1", None)[0] == mod.AT


def test_fdroid_desatualizado_variante_de_abi_nao_e_atraso(importa_script):
    mod = importa_script("saude.py")
    api = {"suggestedVersionCode": 13070208, "packages": [{"versionCode": 13070208, "versionName": "3.7.2"},
                                                         {"versionCode": 13070206, "versionName": "3.7.2"}]}
    assert mod.fdroid_desatualizado(13070208, api) is False
    assert mod.fdroid_desatualizado(13070206, api) is False     # mesma versao, outra ABI
    assert mod.fdroid_desatualizado(13070300, api) is False     # mais novo que o sugerido
    api2 = {"suggestedVersionCode": 22, "packages": [{"versionCode": 22, "versionName": "1.11.1"}, {"versionCode": 21, "versionName": "1.11.0"}]}
    assert mod.fdroid_desatualizado(21, api2) is True
    assert mod.fdroid_desatualizado(5, api2) is True            # codigo que o F-Droid nem lista mais: pode haver versao nova
    assert mod.fdroid_desatualizado(22, api2) is False
    assert mod.fdroid_desatualizado(22, {}) is None and mod.fdroid_desatualizado(None, api2) is None
    assert mod.fdroid_desatualizado(3, {"suggestedVersionCode": "x"}) is None
    assert mod.fdroid_desatualizado(5, {"suggestedVersionCode": 30, "packages": []}) is True    # nome desconhecido dos dois lados nao e "mesma versao"
    assert mod.fdroid_desatualizado(30, {"suggestedVersionCode": 30, "packages": []}) is False


def test_av_apps_conta_em_dia_atrasados_e_sem_resposta(importa_script):
    mod = importa_script("saude.py")
    nivel, texto = mod.av_apps({"a": False, "b": False})
    assert nivel == mod.OK and "2 em dia de 2 consultados" in texto
    nivel, texto = mod.av_apps({"a": False, "b": True, "c": None})
    assert nivel == mod.AT and "1 em dia de 3" in texto and "1 sem resposta" in texto and "MAIS NOVOS NO F-DROID: b" in texto
    assert mod.av_apps({})[0] == mod.AT


# ------------------------------------------------------------------ historico
def test_historico_le_o_ultimo_registro_e_ignora_arquivo_ruim(importa_script, tmp_path):
    mod = importa_script("saude.py")
    arq = tmp_path / "sub" / "h.jsonl"
    assert mod.ler_anterior(arq) is None                                   # nao existe
    mod.gravar_registro(arq, {"ts": "2026-11-01T10:00:00", "livre_kb": 1})
    mod.gravar_registro(arq, {"ts": "2026-11-01T11:00:00", "livre_kb": 2})
    assert arq.read_text(encoding="utf-8").count("\n") == 2                 # uma linha por registro, a pasta foi criada
    assert mod.ler_anterior(arq)["livre_kb"] == 2
    arq.write_text("isto nao e json\n", encoding="utf-8")
    assert mod.ler_anterior(arq) is None
    arq.write_text("", encoding="utf-8")
    assert mod.ler_anterior(arq) is None


# ------------------------------------------------------------------ rede (sem rede de verdade)
def test_consulta_online_usa_get_e_erro_vira_none(importa_script, monkeypatch):
    mod = importa_script("saude.py")
    pedidos = []
    def baixa(url, timeout=25):
        pedidos.append(url)
        if "fota-cloud" in url:
            return FOTA
        if url.endswith("/org.fossify.phone"):
            return json.dumps({"suggestedVersionCode": 22, "packages": []})
        raise OSError("sem rede")
    monkeypatch.setattr(mod, "baixa", baixa)
    ultimo, estados = mod.consulta_online("ZTO", "SM-A125M", {"org.fossify.phone": 22, "com.termux": 1002, "com.outro": 7})
    assert ultimo == "A125MUBS6CXJ1"
    assert estados == {"org.fossify.phone": False, "com.termux": None}     # com.outro nao esta na lista FOSS: nem e consultado
    assert pedidos[0] == "https://fota-cloud-dn.ospserver.net/firmware/ZTO/SM-A125M/version.xml"
    assert "https://f-droid.org/api/v1/packages/org.fossify.phone" in pedidos and not any("com.outro" in p for p in pedidos)
    monkeypatch.setattr(mod, "baixa", lambda url, timeout=25: (_ for _ in ()).throw(OSError("fora do ar")))
    assert mod.consulta_online("ZTO", "SM-A125M", {})[0] is None


def test_baixa_manda_so_um_get_com_o_user_agent_que_a_samsung_exige(importa_script, monkeypatch):
    mod = importa_script("saude.py")
    visto = {}
    class Resposta:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return "café".encode("utf-8")
    def falso(req, timeout=None):
        visto.update(url=req.full_url, ua=req.get_header("User-agent"), metodo=req.get_method(), dados=req.data, timeout=timeout)
        return Resposta()
    monkeypatch.setattr(mod.urllib.request, "urlopen", falso)
    assert mod.baixa("https://exemplo.test/x", timeout=7) == "café"
    assert visto == {"url": "https://exemplo.test/x", "ua": "Kies2.0", "metodo": "GET", "dados": None, "timeout": 7}


# ------------------------------------------------------------------ main com adb falso
SOMENTE_LEITURA = re.compile(r"^(getprop |date |dumpsys |cat /proc/|cat /sys/|df |logcat |cmd wifi status$|pm list packages)")
VERBOS_PROIBIDOS = re.compile(r"\b(put|set|setprop|settings|disable|enable|install|uninstall|force-stop|kill|compile|trim|reboot|svc|rm|am|input|wm)\b")


COMANDOS_PERMITIDOS = {
    "getprop ro.product.model", "getprop ro.build.display.id", "getprop ro.csc.sales_code",
    "date '+%Y-%m-%d %H:%M:%S'", "dumpsys battery", "dumpsys thermalservice", "cat /proc/meminfo",
    "cat /sys/block/zram0/mm_stat", "cat /proc/pressure/memory", "cat /proc/pressure/cpu", "cat /proc/pressure/io",
    "dumpsys meminfo", "df -k /data", "logcat -b events -d | grep am_kill", "dumpsys alarm | grep wakeups",
    "dumpsys power | grep 'Wake Locks: size='", "cmd wifi status", "pm list packages --show-versioncode",
}


def _respostas(mod, **mudar):
    amostras = {"modelo": "SM-A125M", "build": "SP1A.210812.016.A125MUBS6CXJ1", "csc": "ZTO", "hora": "2026-11-01 11:00:00",
                "bateria": BATERIA, "termica": TERMICA, "meminfo": MEMINFO, "zram": MM_STAT, "psi_memory": PSI_MEM, "psi_cpu": PSI_CPU,
                "psi_io": PSI_IO, "pss": MEMINFO_PSS.replace("749,140K", "149,140K"), "df": DF, "mortes": "", "alarmes": ALARMES,
                "wakelocks": "  Wake Locks: size=0", "wifi": WIFI, "versoes": VERSOES}
    amostras.update(mudar)
    return {mod.CMD[k]: v for k, v in amostras.items()}


def _prepara(mod, monkeypatch, **mudar):
    resp = _respostas(mod, **mudar)
    chamados = []
    def falso(cmd, timeout=90):
        chamados.append(cmd)
        return resp.get(cmd, "")
    monkeypatch.setattr(mod, "sh", falso)
    return chamados


def test_main_saudavel_so_chama_comandos_de_leitura_e_nao_usa_a_rede(importa_script, monkeypatch, capsys):
    mod = importa_script("saude.py")
    chamados = _prepara(mod, monkeypatch)
    monkeypatch.setattr(mod, "baixa", lambda *a, **k: pytest.fail("sem --online nao pode abrir a rede"))
    assert mod.main(["--sem-historico"]) == 0
    saida = capsys.readouterr().out
    assert "SAUDE DO A12 em 01/11/2026 11:00" in saida and "VEREDITO: SAUDAVEL (0 alertas, 0 atencoes)" in saida
    assert saida.count("[OK     ]") == 9 and "Firmware" not in saida
    esperado = set(mod.CMD.values()) - {mod.CMD["build"], mod.CMD["csc"], mod.CMD["versoes"]}
    assert set(chamados) == esperado                                        # nem a mais nem a menos
    # lista LITERAL (nao derivada de mod.CMD): trocar um comando de leitura por outro com verbo diferente reprova aqui
    assert set(chamados) <= COMANDOS_PERMITIDOS, set(chamados) - COMANDOS_PERMITIDOS
    assert set(mod.CMD.values()) == COMANDOS_PERMITIDOS, set(mod.CMD.values()) ^ COMANDOS_PERMITIDOS
    for cmd in chamados:
        assert SOMENTE_LEITURA.match(cmd), cmd
        antes_do_pipe = cmd.split("|")[0]
        assert not VERBOS_PROIBIDOS.search(antes_do_pipe.replace("dumpsys battery", "")), cmd
        assert all(parte.strip().startswith("grep ") for parte in cmd.split("|")[1:]), cmd  # pipe so para grep


def test_main_alerta_devolve_1_e_atencao_devolve_0(importa_script, monkeypatch, capsys):
    mod = importa_script("saude.py")
    _prepara(mod, monkeypatch, termica="Thermal Status: 3\n")
    assert mod.main(["--sem-historico"]) == 1
    saida = capsys.readouterr().out
    assert "[ALERTA ] Termica: status 3 (grave)" in saida and "VEREDITO: ALERTA (1 alertas, 0 atencoes)" in saida
    _prepara(mod, monkeypatch, pss=MEMINFO_PSS)                             # o npm de 749 MB
    assert mod.main(["--sem-historico"]) == 1                                # 749 MB >= 700: ALERTA
    assert "npm install omniroute 732 MB" in capsys.readouterr().out
    _prepara(mod, monkeypatch, pss=MEMINFO_PSS.replace("749,140K", "500,000K"))
    assert mod.main(["--sem-historico"]) == 0                                # so atencao: saida 0
    assert "VEREDITO: ATENCAO (0 alertas, 1 atencoes)" in capsys.readouterr().out


def test_main_nao_e_o_a12_ou_sem_adb(importa_script, monkeypatch, capsys):
    mod = importa_script("saude.py")
    chamados = _prepara(mod, monkeypatch, modelo="Pixel 7")
    assert mod.main(["--sem-historico"]) == 2
    assert "ABORTADO" in capsys.readouterr().out and chamados == [mod.CMD["modelo"]]
    def sem_adb(cmd, timeout=90):
        raise FileNotFoundError("adb")
    monkeypatch.setattr(mod, "sh", sem_adb)
    assert mod.main([]) == 2
    assert "adb nao esta no PATH" in capsys.readouterr().out


def test_main_grava_historico_e_avisa_da_queda_na_leitura_seguinte(importa_script, monkeypatch, capsys):
    mod = importa_script("saude.py")
    _prepara(mod, monkeypatch, df="Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/x 53762032 36000000 18000000 67% /data")
    assert mod.main([]) == 0
    arq = mod.arquivo_historico()
    assert arq.parent == mod.RAIZ / "diagnostico" and arq.exists()
    reg = json.loads(arq.read_text(encoding="utf-8").splitlines()[-1])
    assert reg["livre_kb"] == 18000000 and reg["total_kb"] == 53762032 and reg["mem_disp_kb"] == 1900000
    assert reg["ts"] == "2026-11-01T11:00:00" and reg["termica"] == 1 and reg["bateria"] == 23
    capsys.readouterr()
    _prepara(mod, monkeypatch)                                              # agora 12.504.612 kB livres: caiu mais de 5 GB
    assert mod.main([]) == 0
    saida = capsys.readouterr().out
    assert "CAIU 5.2 GB desde 2026-11-01 11:00" in saida and "VEREDITO: ATENCAO (0 alertas, 1 atencoes)" in saida
    assert arq.read_text(encoding="utf-8").count("\n") == 2
    _prepara(mod, monkeypatch)
    assert mod.main(["--sem-historico"]) == 0
    capsys.readouterr()
    assert arq.read_text(encoding="utf-8").count("\n") == 2                 # --sem-historico nao grava


def test_main_online_mostra_firmware_e_apps_e_pede_so_leitura(importa_script, monkeypatch, capsys):
    mod = importa_script("saude.py")
    chamados = _prepara(mod, monkeypatch)
    recebido = {}
    def consulta(csc, modelo, versoes):
        recebido.update(csc=csc, modelo=modelo, versoes=versoes)
        return "A125MUBS6CXJ1", {"org.fossify.phone": False, "com.termux": True}
    monkeypatch.setattr(mod, "consulta_online", consulta)
    assert mod.main(["--online", "--sem-historico"]) == 0
    saida = capsys.readouterr().out
    assert "Firmware: A125MUBS6CXJ1 e a ultima" in saida and "MAIS NOVOS NO F-DROID: com.termux" in saida
    assert recebido == {"csc": "ZTO", "modelo": "SM-A125M", "versoes": {"org.fossify.phone": 22, "com.termux": 1002, "com.outro": 7}}
    assert set(chamados) == set(mod.CMD.values())
    for cmd in chamados:
        assert SOMENTE_LEITURA.match(cmd), cmd


def test_saude_samsung_asoc_aparece_e_usa_os_mesmos_limites(importa_script):
    """06/11: o dumpsys battery da Samsung traz mSavedBatteryAsoc (86 no A12), que a conta do charge counter nao enxerga."""
    mod = importa_script("saude.py")
    assert mod.parse_bateria(BATERIA + "\n  mSavedBatteryAsoc: 86\n")["asoc"] == 86
    assert "asoc" not in mod.parse_bateria(BATERIA)
    nivel, texto = mod.av_bateria(_bat(asoc=86))
    assert nivel == mod.OK and "saude Samsung (ASOC) 86%" in texto
    assert mod.av_bateria(_bat(asoc=80))[0] == mod.OK
    assert mod.av_bateria(_bat(asoc=79))[0] == mod.AT
    assert mod.av_bateria(_bat(asoc=60))[0] == mod.AT
    assert mod.av_bateria(_bat(asoc=59))[0] == mod.AL
    assert "ASOC" not in mod.av_bateria(_bat())[1]
