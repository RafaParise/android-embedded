#!/usr/bin/env python3
"""Escurece a tela do A12 sem bloquear, com a depuracao ativa, com ou sem cabo. Camada preta + brilho temporario 0: nenhum ajuste salvo muda.

  python scripts/tela-apagada.py              escurece; se ja estiver escura, acende (e o que o atalho faz)
  python scripts/tela-apagada.py iniciar      liga o gesto do volume no celular, sem escurecer (precisa rodar 1 vez depois de reiniciar o celular)
  python scripts/tela-apagada.py apagar | acender | parar | status
  python scripts/tela-apagada.py turbo-ligar | turbo-desligar     Wi-Fi em alto desempenho enquanto a tela estiver em uso (padrao: ligado); medido em memoria/TELA-APAGADA.md
  python scripts/tela-apagada.py observar     fica no PC religando o gesto quando o cabo volta (recolocar o cabo reinicia o adbd e mata o gesto)
  python scripts/tela-apagada.py agendar      cria a tarefa TelaGesto, que roda o observar sem janela desde o logon; 'parar' desliga o gesto e a tarefa respeita

NO CELULAR, sem PC: VOLUME PARA BAIXO 3 VEZES escurece.
Acende: dois toques curtos (com ate 2 s entre eles), volume para cima, alarme ou chamada. O botao lateral bloqueia e mostra o PIN.
Limites: o toque continua chegando ao que esta por baixo; o gesto some ao reiniciar o celular, e religar pede o cabo.
Por que nao se apaga o painel de verdade: memoria/TELA-APAGADA.md. Saida: 0 = ok; 1 = nao confirmou; 2 = nao deu para rodar.
"""
import argparse
import importlib.util
import pathlib
import os
import re
import shutil
import subprocess
import sys
import time

AQUI = pathlib.Path(__file__).resolve().parent
LOCAL_VIGIA = AQUI / "tela-vigia.sh"
LOCAL_DEX = AQUI / "celular-kit" / "tela" / "tela.dex"
DIR = "/data/local/tmp"
VIGIA = f"{DIR}/tela-vigia.sh"
DEX = f"{DIR}/tela.dex"
PID = f"{DIR}/tela-vigia.pid"
TRAVA = f"{DIR}/tela-escuro.trava"
MOTIVO = f"{DIR}/tela-vigia.motivo"
HISTORICO = f"{DIR}/tela-vigia.historico"
PARADO = f"{DIR}/tela-vigia.parado"
PID_TURBO = f"{DIR}/tela-turbo.pid"
SEM_TURBO = f"{DIR}/tela-vigia.sem-turbo"
PROCESSO_TURBO = "ps -A -o PID,ARGS | grep '[T]ela wifi-turbo' | awk '{print $1}'"
TAREFA = "TelaGesto"
PROCESSO_ESCURO = "ps -A -o PID,ARGS | grep '[T]ela escuro' | awk '{print $1}'"
TEM_CAMADA = 'dumpsys SurfaceFlinger 2>/dev/null | grep -c "tela-preta"'
ESTADO = ('dumpsys SurfaceFlinger 2>/dev/null | grep -m1 -oE "powerMode=[A-Za-z]+"; dumpsys power 2>/dev/null | grep -m1 -oE "mWakefulness=[A-Za-z]+"; '
          'dumpsys window 2>/dev/null | grep -m1 -oE "isKeyguardShowing=[a-z]+"')


class Erro(Exception):
    pass


def adb(*a, timeout=30):
    # a tarefa roda com pythonw: sem isto, cada adb abriria uma janela preta na tela do Rafael
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    return subprocess.run(["adb", *a], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL, **flags)


def shell(cmd, timeout=30):
    return adb("shell", cmd, timeout=timeout).stdout


def nos_de_entrada(texto):
    """Do 'getevent -pl': onde chegam o volume para baixo, o toque e as teclas que acendem. O numero pode mudar ao reiniciar."""
    nos = {"volume": "", "toque": "", "teclas": []}
    for bloco in re.split(r"(?=^add device)", texto, flags=re.M):
        ev = re.search(r"/dev/input/(event\d+)", bloco)
        nome = re.search(r'name:\s+"(.*)"', bloco)
        if not ev or not nome:
            continue
        if nome.group(1) == "sec_touchscreen":
            nos["toque"] = ev.group(1)
        # so os botoes do corpo do aparelho: controle e conector de fone tambem anunciam volume (visto em 04/11)
        if not nome.group(1).startswith("mtk-"):
            continue
        if re.search(r"\bKEY_VOLUMEDOWN\b", bloco) and not nos["volume"]:
            nos["volume"] = ev.group(1)
        if re.search(r"\b(KEY_VOLUMEUP|KEY_POWER)\b", bloco):
            nos["teclas"].append(ev.group(1))
    return nos


def estado():
    t = shell(ESTADO)
    achado = lambda rx: (re.search(rx, t) or [None, "?"])[1]
    return {"painel": achado(r"powerMode=(\w+)"), "acordado": achado(r"mWakefulness=(\w+)"), "bloqueado": achado(r"isKeyguardShowing=(\w+)")}


def escuro_agora():
    return bool(shell(PROCESSO_ESCURO).strip())


def vigia_vivo():
    return shell(f"[ -f {PID} ] && kill -0 $(cat {PID}) 2>/dev/null && echo vivo").strip() == "vivo"


def nos_conferidos():
    if adb("get-state").stdout.strip() != "device":
        raise Erro("o celular nao esta no adb: ligue o cabo")
    nos = nos_de_entrada(shell("getevent -pl 2>/dev/null", 40))
    if not (nos["volume"] and nos["toque"] and nos["teclas"]):
        raise Erro(f"nao achei os botoes ou o toque em getevent ({nos}): sem como acender, nao escureco a tela")
    return nos


def envia():
    for local, destino in ((LOCAL_VIGIA, VIGIA), (LOCAL_DEX, DEX)):
        if adb("push", str(local), destino).returncode != 0:
            raise Erro(f"nao consegui enviar {local.name}")


def args_do_vigia(modo, nos):
    return f"{VIGIA} {modo} {nos['volume']} {nos['toque']} {' '.join(nos['teclas'])}"


def iniciar(nos=None):
    nos = nos or nos_conferidos()
    envia()
    if vigia_vivo():
        para_vigia()
    shell(f"rm -f {PARADO}; setsid nohup sh {args_do_vigia('vigiar', nos)} >/dev/null 2>&1 </dev/null &")
    time.sleep(2)
    if not vigia_vivo():
        raise Erro("o vigia nao ficou de pe")
    liga_turbo()
    print("Gesto ligado: VOLUME PARA BAIXO 3 VEZES escurece. Vale ate reiniciar o celular.")
    return 0


def turbo_vivo():
    return shell(f"[ -f {PID_TURBO} ] && kill -0 $(cat {PID_TURBO}) 2>/dev/null && echo vivo").strip() == "vivo"


def para_turbo():
    shell(f"[ -f {PID_TURBO} ] && kill $(cat {PID_TURBO}) 2>/dev/null; rm -f {PID_TURBO}; for p in $({PROCESSO_TURBO}); do kill $p; done")
    # o mudo do microfone sobrevive ao processo (medido em 04/11): quem encerra devolve
    shell(f"CLASSPATH={DEX} app_process / Tela mic-solta >/dev/null 2>&1")


def liga_turbo():
    """Sem repetir se ja esta de pe; respeita quem desligou."""
    if shell(f"[ -f {SEM_TURBO} ] && echo sim").strip() == "sim" or turbo_vivo():
        return
    shell(f"setsid nohup sh {VIGIA} turbo >/dev/null 2>&1 </dev/null &")


def turbo_ligar():
    envia()
    shell(f"rm -f {SEM_TURBO}")
    liga_turbo()
    time.sleep(3)
    print("Wi-Fi em alto desempenho:", "ligado enquanto a tela estiver em uso." if turbo_vivo() else "NAO ficou de pe.")
    return 0 if turbo_vivo() else 1


def turbo_desligar():
    shell(f"touch {SEM_TURBO}")
    para_turbo()
    print("Wi-Fi em alto desempenho: desligado (o Wi-Fi volta a economizar energia).")
    return 0


def apagar():
    nos = nos_conferidos()
    if estado()["bloqueado"] == "true":
        raise Erro("o celular esta pedindo o PIN: desbloqueie e rode de novo")
    if escuro_agora():
        print("Ja esta escura.")
        return 0
    iniciar(nos)
    shell(f"setsid nohup sh {args_do_vigia('agora', nos)} >/dev/null 2>&1 </dev/null &")
    for _ in range(8):
        time.sleep(1)
        if shell(TEM_CAMADA).strip() not in ("", "0"):
            print("Tela escura, sem bloqueio. Depuracao ativa.")
            print("Acende com dois toques, volume para cima, alarme ou chamada. O botao lateral bloqueia e mostra o PIN.")
            return 0
    acender(silencioso=True)
    print("Nao escureceu:", shell(f"cat {MOTIVO} 2>/dev/null").strip() or "sem motivo registrado")
    return 1


def acender(silencioso=False):
    """Encerra o Tela: a camada morre com ele. Nada de tecla de energia aqui: ela bloqueia."""
    shell(f"for p in $({PROCESSO_ESCURO}); do kill $p; done")
    time.sleep(1)
    shell(f"CLASSPATH={DEX} app_process / Tela luz volta; rmdir {TRAVA} 2>/dev/null")
    if silencioso:
        return 0
    e = estado()
    if shell(TEM_CAMADA).strip() in ("", "0"):
        print(f"Tela acesa. Bloqueada: {e['bloqueado']}.")
        return 0
    print("A camada preta ainda aparece. Reiniciar o celular resolve (segure volume para baixo + botao lateral por 7 s).")
    return 1


def para_vigia():
    shell(f"[ -f {PID} ] && kill $(cat {PID}) 2>/dev/null; rm -f {PID}; ps -A -o PID,ARGS | grep '[g]etevent -lc 2' | awk '{{print $1}}' | while read -r g; do kill $g; done")


def parar():
    shell(f"touch {PARADO}")  # sem isto a tarefa religaria o gesto em 30 s
    para_vigia()
    para_turbo()
    r = acender()
    print("Gesto desligado.")
    return r


def observa_uma_vez():
    """Celular no adb e sem gesto: religa, e devolve o brilho caso o escuro tenha morrido junto. Fora do adb, nada a fazer."""
    if adb("get-state").stdout.strip() != "device":
        return False
    if vigia_vivo():
        if not turbo_vivo():
            liga_turbo()  # Wi-Fi e microfone podem morrer sozinhos, com o gesto de pe; liga_turbo respeita quem desligou
        return False
    if shell(f"[ -f {PARADO} ] && echo sim").strip() == "sim":
        return False
    if not escuro_agora():
        shell(f"CLASSPATH={DEX} app_process / Tela luz volta; rmdir {TRAVA} 2>/dev/null")
    iniciar()
    return True


def versao_do_script():
    return os.path.getmtime(__file__)


def carrega_atual():
    """O codigo novo do arquivo, carregado DENTRO do mesmo processo. Trocar de processo (os.execv) no Windows encerra a tarefa agendada:
    em 04/11 a TelaGesto parou as 16:53 e, depois do reinicio do celular, nada religou o gesto, o Wi-Fi turbo nem o mudo."""
    spec = importlib.util.spec_from_file_location("tela_apagada_atual", os.path.abspath(__file__))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def observar(intervalo=30):
    # 04/11: a tarefa seguiu com o codigo da manha e, com o cabo de volta, nao religou o Wi-Fi nem o microfone. Script mudou: recarrega.
    versao = versao_do_script()
    atual = None  # None = o codigo deste proprio modulo
    while True:
        try:
            (atual.observa_uma_vez if atual else observa_uma_vez)()
        except (Erro, subprocess.TimeoutExpired, OSError) as e:
            print("observar:", e, flush=True)
        except Exception as e:  # noqa: BLE001 - o vigia nunca pode morrer: um erro novo so vira aviso
            print("observar (inesperado):", type(e).__name__, e, flush=True)
        time.sleep(intervalo)
        nova = versao_do_script()
        if nova != versao:
            try:
                atual = carrega_atual()
                versao = nova
            except Exception as e:  # noqa: BLE001 - arquivo salvo pela metade: segue com o codigo antigo e tenta na volta seguinte
                print("observar: recarga falhou:", type(e).__name__, e, flush=True)


def agendar():
    exe = shutil.which("pythonw") or sys.executable
    texto = f"""
$a = New-ScheduledTaskAction -Execute '{exe}' -Argument '"{pathlib.Path(__file__).resolve()}" observar'
$t = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)
$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName '{TAREFA}' -Action $a -Trigger $t -Settings $s -Principal $p -Force | Out-Null
Start-ScheduledTask -TaskName '{TAREFA}'
(Get-ScheduledTask -TaskName '{TAREFA}').State
"""
    r = subprocess.run(["pwsh", "-NoProfile", "-Command", texto], capture_output=True, text=True, errors="replace", timeout=60, stdin=subprocess.DEVNULL)
    print(r.stdout.strip() or r.stderr.strip()[-300:])
    return 0 if "Running" in r.stdout or "Ready" in r.stdout else 1


def status():
    e = estado()
    print(f"Painel {e['painel']}, aparelho {e['acordado']}, bloqueado {e['bloqueado']}; gesto {'ligado' if vigia_vivo() else 'desligado'}; Wi-Fi turbo {'ligado' if turbo_vivo() else 'desligado'}; tela {'escura' if escuro_agora() else 'normal'}")
    m = shell(f"tail -n 5 {HISTORICO} 2>/dev/null").strip()
    if m:
        print("Ultimas vezes (escureceu -> acendeu):\n" + m)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Escurece a tela do A12 sem bloquear")
    ap.add_argument("modo", nargs="?", default="alternar", choices=["alternar", "iniciar", "apagar", "acender", "parar", "status", "observar", "agendar", "turbo-ligar", "turbo-desligar"])
    a = ap.parse_args(argv)
    try:
        if a.modo == "alternar":
            return acender() if escuro_agora() else apagar()
        return {"iniciar": iniciar, "apagar": apagar, "acender": acender, "parar": parar, "status": status, "observar": observar, "agendar": agendar, "turbo-ligar": turbo_ligar, "turbo-desligar": turbo_desligar}[a.modo]()
    except Erro as e:
        print("NAO FEITO:", e)
        return 2
    except (subprocess.TimeoutExpired, OSError):
        print("NAO FEITO: o celular nao respondeu pelo adb.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
