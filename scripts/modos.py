#!/usr/bin/env python3
"""Modos do A12 por ADB, sem root e reversiveis (so usam comandos do proprio Android 12; nada fica instalado nem rodando).

  python scripts/modos.py jogo ligar [pacote] [--escala 0.8]   nao perturbe + limpa processos em cache + resolucao so do jogo + abre o app
  python scripts/modos.py jogo desligar [pacote]               desfaz
  python scripts/modos.py tv ligar [--res 1280x720]            paisagem 16:9 que PREENCHE a TV, tela acesa mais tempo, abre a tela Cast
  python scripts/modos.py tv desligar                          desfaz
  python scripts/modos.py economia ligar [--brilho 30]         escala de cinza + Economia de energia + Economia de dados + brilho baixo + tela apaga em 15 s
  python scripts/modos.py economia desligar                    volta ao que estava (o estado de antes fica em diagnostico/modos_estado.json)
  python scripts/modos.py status

Pacote padrao do jogo: ARENA. Escalas aceitas pelo Android: 0.3 a 0.9 (0.8 = 80% da resolucao, ~36% menos pixels para a GPU).
Modo economia = substituto aberto do Modo Ultra Economia da Samsung, SO com chaves do proprio Android 12 (nenhum app, nenhum dado enviado):
escala de cinza (daltonizer tipo 0 = monocromia; testado no A12 em 31/10, a matriz de cor do display vira a luminancia), Economia de energia
nativa (settings global low_power), Economia de dados (cmd netpolicy restrict-background) e brilho/tempo de tela menores. Limites: nao desliga
Wi-Fi, Bluetooth nem localizacao (o dashcam e a Tailscale precisam deles) e a captura de tela (screencap) continua colorida.
Limite honesto: frequencia da CPU, nucleos e prioridade de processos so mudam com root; nenhum app consegue sem ele.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ARENA = "io.github.rafaparise.arena"
ESCALAS = ("0.3", "0.35", "0.4", "0.45", "0.5", "0.55", "0.6", "0.65", "0.7", "0.75", "0.8", "0.85", "0.9")
ZEN = {"0": "off", "1": "priority", "2": "none", "3": "alarms"}
# chaves que o modo economia muda: (espaco, nome). O valor de ANTES de cada uma e guardado e restaurado ('null' = a chave nao existia: apaga)
ECONOMIA_CHAVES = (("secure", "accessibility_display_daltonizer"), ("secure", "accessibility_display_daltonizer_enabled"),
                   ("global", "low_power"), ("system", "screen_brightness_mode"), ("system", "screen_brightness"),
                   ("system", "screen_off_timeout"))
VALOR_SEGURO = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")  # o valor volta para o shell do aparelho: so numero passa


def sh(cmd, timeout=60):
    r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def arquivo_estado():
    # calculado a cada uso (nao constante do modulo): os testes redirecionam RAIZ e nao podem apagar o estado REAL dos modos
    # (achado em 31/10: cada rodada de testes regravava diagnostico/modos_estado.json com {}, e com o estado perdido o 'desligar' nao volta ao que era)
    return RAIZ / "diagnostico" / "modos_estado.json"


def carregar():
    f = arquivo_estado()
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def salvar(d):
    f = arquivo_estado()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, indent=1), encoding="utf-8")


def tamanho():
    t = sh("wm size")
    fis = re.search(r"Physical size: (\S+)", t)
    ov = re.search(r"Override size: (\S+)", t)
    return (fis.group(1) if fis else None), (ov.group(1) if ov else None)


def bateria():
    t = sh("dumpsys battery")
    nivel = re.search(r"level: (\d+)", t)
    temp = re.search(r"temperature: (\d+)", t)
    ligado = "USB powered: true" in t or "AC powered: true" in t
    return (int(nivel.group(1)) if nivel else -1), (int(temp.group(1)) / 10 if temp else -1), ligado


def jogo(a):
    est = carregar()
    if a.acao == "ligar":
        if "jogo" in est:  # um segundo 'ligar' gravaria o estado JA alterado (zen priority) como se fosse o original
            sys.exit("o modo jogo ja esta LIGADO (o estado de antes esta em diagnostico/modos_estado.json): rode 'jogo desligar' primeiro")
        if a.escala and a.escala not in ESCALAS:
            sys.exit("escala invalida; use uma de: " + " ".join(ESCALAS))
        est["jogo"] = {"zen": sh("settings get global zen_mode"), "pacote": a.pacote}
        sh("cmd notification set_dnd priority")
        sh("am kill-all")
        if a.escala:
            print("resolucao do jogo:", sh(f"cmd game downscale {a.escala} {a.pacote}"))
        sh(f"monkey -p {a.pacote} -c android.intent.category.LAUNCHER 1")
        salvar(est)
        nivel, temp, ligado = bateria()
        print(f"modo jogo LIGADO ({a.pacote}). bateria {nivel}% | {temp:.1f} C | " + ("carregando: esquenta mais, prefira jogar sem o cabo" if ligado else "na bateria"))
    else:
        dados = est.get("jogo", {})
        zen = dados.get("zen", "0")
        pacote = dados.get("pacote", a.pacote)  # desfaz no pacote que foi LIGADO, nao no padrao/CLI de "desligar"
        sh(f"cmd notification set_dnd {ZEN.get(zen, 'off')}")
        print("resolucao do jogo:", sh(f"cmd game downscale disable {pacote}"))
        est.pop("jogo", None)
        salvar(est)
        print("modo jogo DESLIGADO (nao perturbe e resolucao voltaram ao que eram)")


def tv(a):
    est = carregar()
    if a.acao == "ligar":
        if "tv" in est:  # um segundo 'ligar' gravaria o estado JA alterado como se fosse o original
            sys.exit("o modo TV ja esta LIGADO (o estado de antes esta em diagnostico/modos_estado.json): rode 'tv desligar' primeiro")
        largura, altura = (int(x) for x in a.res.lower().split("x"))
        _, ov = tamanho()
        est["tv"] = {"ov": ov, "rot_auto": sh("settings get system accelerometer_rotation"),
                     "rot": sh("settings get system user_rotation"), "timeout": sh("settings get system screen_off_timeout"),
                     "wifi_display": le("global", "wifi_display_on")}
        salvar(est)  # estado de antes gravado ANTES de qualquer mudanca: se o ligar cair no meio, o 'desligar' ainda sabe voltar
        sh("settings put system accelerometer_rotation 0; settings put system user_rotation 1")  # paisagem fixa
        sh(f"wm size {altura}x{largura}")  # tamanho no sentido natural (retrato) do painel; em paisagem vira {largura}x{altura}
        sh("settings put system screen_off_timeout 600000")
        sh("settings put global wifi_display_on 1")
        sh("am start -a android.settings.CAST_SETTINGS")
        salvar(est)
        print(f"modo TV LIGADO: imagem {largura}x{altura} (16:9, preenche a TV), paisagem fixa, tela acesa 10 min. "
              "Escolha a TV na tela Cast que abriu (Miracast/Chromecast) ou use o ScreenStream no navegador da TV.")
    else:
        t = est.get("tv")
        if t is None:  # sem estado salvo nao ha o que desfazer: chutar padroes mexeria no tempo de tela e na rotacao do Rafael
            print("aviso: nao ha estado salvo do modo TV; nao mexi em tamanho, rotacao nem tempo de tela")
            return
        sh("wm size reset" if not t.get("ov") else f"wm size {t['ov']}")
        sh(f"settings put system accelerometer_rotation {t.get('rot_auto', '1')}; settings put system user_rotation {t.get('rot', '0')}")
        sh(f"settings put system screen_off_timeout {t.get('timeout', '60000')}")
        if "wifi_display" in t and not poe("global", "wifi_display_on", str(t["wifi_display"])):
            print("aviso: wifi_display_on nao voltou ao valor de antes; confira o aparelho")
        est.pop("tv", None)
        salvar(est)
        print("modo TV DESLIGADO (tamanho, rotacao e tempo de tela voltaram ao que eram)")


def le(espaco, chave):
    """Valor atual de uma chave ('null' = nao existe). Se o aparelho nao respondeu (ADB caiu), aborta em vez de guardar lixo como 'estado de antes'."""
    v = sh(f"settings get {espaco} {chave}").strip()
    if v != "null" and not VALOR_SEGURO.match(v):
        sys.exit(f"ABORTADO: nao consegui ler {espaco}/{chave} (resposta {v[:40]!r}); o aparelho saiu do ADB? Nada foi alterado.")
    return v


def poe(espaco, chave, valor, tentativas=3):
    """Grava uma chave e CONFERE lendo de volta (o ADB do cabo pisca): tenta de novo ate 'tentativas' vezes. Devolve True se ficou certo.
    'null' ou vazio = a chave NAO existia antes: apaga, em vez de gravar a palavra null."""
    if valor not in ("null", "") and not VALOR_SEGURO.match(valor):
        print(f"  aviso: valor inesperado em {espaco}/{chave} ({valor[:20]!r}); nao gravei")
        return False
    esperado = "null" if valor in ("null", "") else valor
    for _ in range(tentativas):
        sh(f"settings delete {espaco} {chave}" if esperado == "null" else f"settings put {espaco} {chave} {valor}")
        if sh(f"settings get {espaco} {chave}").strip() == esperado:
            return True
        time.sleep(0.6)
    return False


def dados_economizando():
    return bool(re.search(r"status:\s*enabled", sh("cmd netpolicy get restrict-background").lower()))


def poe_dados(ligado, tentativas=3):
    """Economia de dados (restrict-background) ligada/desligada, conferida lendo de volta."""
    for _ in range(tentativas):
        sh("cmd netpolicy set restrict-background " + ("true" if ligado else "false"))
        if dados_economizando() == ligado:
            return True
        time.sleep(0.6)
    return False


def economia(a):
    est = carregar()
    if a.acao == "ligar":
        if "economia" in est:
            sys.exit("o modo economia ja esta LIGADO (o estado de antes esta em diagnostico/modos_estado.json): rode 'economia desligar' primeiro")
        if not 1 <= a.brilho <= 255:
            sys.exit("--brilho precisa estar entre 1 e 255")
        antes: dict = {f"{ns}/{k}": le(ns, k) for ns, k in ECONOMIA_CHAVES}
        antes["restrict_background"] = dados_economizando()
        est["economia"] = antes
        salvar(est)  # o estado de antes e gravado ANTES de qualquer mudanca: se algo falhar no meio, o 'desligar' ainda sabe voltar
        atual = antes["system/screen_brightness"]
        brilho = str(min(a.brilho, int(atual)) if atual.isdigit() else a.brilho)  # nunca aumenta o brilho
        falhas = [nome for nome, ok in (
            ("escala de cinza", poe("secure", "accessibility_display_daltonizer", "0") and poe("secure", "accessibility_display_daltonizer_enabled", "1")),  # tipo 0 = monocromia
            ("Economia de energia", poe("global", "low_power", "1")),
            ("Economia de dados", poe_dados(True)),                      # segundo plano sem rede movel
            ("brilho", poe("system", "screen_brightness_mode", "0") and poe("system", "screen_brightness", brilho)),
            ("tempo de tela", poe("system", "screen_off_timeout", "15000")),
        ) if not ok]
        if falhas:
            print("modo economia APLICADO PELA METADE; nao aplicou: " + ", ".join(falhas) + ". O estado de antes esta guardado: 'economia desligar' volta a tudo.")
            sys.exit(1)
        nivel, temp, ligado = bateria()
        print(f"modo economia LIGADO: escala de cinza, Economia de energia, Economia de dados, brilho {brilho} e tela apaga em 15 s. "
              f"bateria {nivel}% | {temp:.1f} C | " + ("carregando (com o cabo ligado a tela fica acesa se 'Permanecer ativo' estiver ligado)" if ligado else "na bateria"))
    else:
        guardado = est.get("economia")
        if guardado is None:
            print("aviso: nao ha estado salvo do modo economia; voltei so ao padrao seguro (cor normal, Economia de energia e de dados desligadas)")
            ok = [poe("secure", "accessibility_display_daltonizer_enabled", "0"), poe("global", "low_power", "0"), poe_dados(False)]
            if not all(ok):
                sys.exit("nao consegui confirmar todas as chaves; confira o aparelho e rode de novo")
            return
        falhas = [f"{ns}/{k}" for ns, k in ECONOMIA_CHAVES if not poe(ns, k, str(guardado.get(f"{ns}/{k}", "null")))]
        if not poe_dados(bool(guardado.get("restrict_background"))):
            falhas.append("Economia de dados")
        if falhas:
            print("modo economia NAO voltou por inteiro; falharam: " + ", ".join(falhas) + ". O estado de antes continua guardado: rode 'economia desligar' de novo.")
            sys.exit(1)
        est.pop("economia", None)
        salvar(est)
        print("modo economia DESLIGADO (cor, Economia de energia e de dados, brilho e tempo de tela voltaram ao que eram)")


def status():
    nivel, temp, ligado = bateria()
    fis, ov = tamanho()
    print(f"bateria {nivel}% {temp:.1f} C {'carregando' if ligado else 'na bateria'} | nao perturbe: {ZEN.get(sh('settings get global zen_mode'), '?')}"
          f" | tela {fis} (ajustada: {ov or 'nao'}) | estado salvo: {list(carregar())}")
    f0 = sh("cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq")
    f4 = sh("cat /sys/devices/system/cpu/cpufreq/policy4/scaling_cur_freq")
    print(f"CPU agora: grandes {int(f0) // 1000 if f0.isdigit() else '?'} MHz (900-2301), pequenos {int(f4) // 1000 if f4.isdigit() else '?'} MHz (400-1800)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="modo", required=True)
    j = sub.add_parser("jogo")
    j.add_argument("acao", choices=["ligar", "desligar"])
    j.add_argument("pacote", nargs="?", default=ARENA)
    j.add_argument("--escala")
    t = sub.add_parser("tv")
    t.add_argument("acao", choices=["ligar", "desligar"])
    t.add_argument("--res", default="1280x720")
    e = sub.add_parser("economia")
    e.add_argument("acao", choices=["ligar", "desligar"])
    e.add_argument("--brilho", type=int, default=30, help="brilho manual de 1 a 255 (nunca sobe o brilho atual); padrao 30")
    sub.add_parser("status")
    a = ap.parse_args()
    if "SM-A125" not in sh("getprop ro.product.model"):
        sys.exit("ABORTADO: aparelho nao encontrado ou inesperado")
    if a.modo == "jogo" and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+", a.pacote):  # o nome vai direto para o shell do aparelho
        sys.exit("ABORTADO: nome de pacote invalido (so letras, numeros, _ e pontos)")
    if a.modo == "status":
        status()
    else:
        {"jogo": jogo, "tv": tv, "economia": economia}[a.modo](a)


if __name__ == "__main__":
    main()
