#!/usr/bin/env python3
"""adb do PC com o A12 SEM cabo, pela Tailscale (porta 5555), de qualquer lugar (Wi-Fi ou dados moveis).

  python scripts/adb-remoto.py garantir   cabo ligado? usa o cabo. Sem cabo: conecta <IP do celular na tailnet>:5555
                                          (saida 0 e a 1a linha diz "cabo", "tailscale" ou "tailscale-nova"; 1 = sem conexao)
  python scripts/adb-remoto.py soltar     desconecta SO a conexao da tailnet (o cabo nunca e tocado)
  python scripts/adb-remoto.py status     mostra o que ha

Para os outros scripts (12/11/2026): tem_cabo(), garantir_porta(usb) (com o cabo, deixa a 5555 aberta para tirar o cabo
sem parar), tipo_sem_fio(serial) ('wifi' ou 'dados') e Espelho, que mantem o scrcpy vivo trocando cabo <-> sem fio sozinho.

Autorizado pelo Rafael em 05/11 ("esse poder desbloqueado a qualquer lugar do mundo com dados moveis... nao deve depender
de cabo"), com o risco explicado: a porta 5555 do celular (adb tcpip) fica visivel em qualquer rede em que ele estiver;
so entra quem ja tem a chave autorizada (PC e Termux) ou quem ele aceitar no aviso da tela. Ela cai ao reiniciar o celular;
religa: com o cabo (`depuracao-sem-fio.py porta5555`) ou o `cel` do Termux, no Wi-Fi com a Depuracao sem fio.
A ponte do PC usa `garantir` antes de cada acao_pc e `soltar` depois, para nunca ficarem dois aparelhos no adb
(os scripts do projeto chamam `adb` sem -s).
"""
import json
import re
import socket
import subprocess
import sys
import threading
import time

PORTA = 5555
IP_RESERVA = "100.64.0.2"  # IP do A12 na tailnet em 05/11 (o script prefere o que a Tailscale diz agora)
NOME = "samsung-a12"
_executa = subprocess.run  # os testes trocam por um falso


def roda(cmd, limite=20):
    try:
        p = _executa(cmd, capture_output=True, text=True, timeout=limite)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


# A DMZ do FortiGate (13/11/2026): com o A12 no hub da porta DMZ, o PC chega nele direto em 10.0.10.50 (<1 ms, a regra
# 2 do FortiGate libera a 5555 so do PC). Pela Tailscale o mesmo caminho dava a volta na ONT. Conferido de 30 em 30 s.
IP_DMZ = "10.0.10.50"
_DMZ = {"quando": 0.0, "aberta": False}


def _dmz_aberta():
    """A porta 5555 do A12 responde pela DMZ? (nos testes, com o _executa falso, nunca: nada de rede de verdade)"""
    if _executa is not subprocess.run:
        return False
    agora = time.monotonic()
    if agora - _DMZ["quando"] < 30:
        return _DMZ["aberta"]
    try:
        with socket.create_connection((IP_DMZ, PORTA), timeout=0.4):
            aberta = True
    except OSError:
        aberta = False
    _DMZ.update(quando=agora, aberta=aberta)
    return aberta


def ip_celular():
    """O endereco sem fio do A12: o da DMZ, se ele estiver la com a 5555 aberta; senao o da tailnet."""
    if _dmz_aberta():
        return IP_DMZ
    rc, s = roda(["tailscale", "status", "--json"])
    if rc == 0:
        try:
            for par in (json.loads(s).get("Peer") or {}).values():
                if NOME in (par.get("HostName", "") + par.get("DNSName", "")).lower():
                    ips = [i for i in par.get("TailscaleIPs", []) if i.startswith("100.")]
                    if ips:
                        return ips[0]
        except ValueError:
            pass
    return IP_RESERVA


def aparelhos():
    """{serial: estado} do `adb devices`."""
    _, s = roda(["adb", "devices"])
    r = {}
    for linha in s.splitlines()[1:]:
        partes = linha.split("\t")
        if len(partes) == 2:
            r[partes[0].strip()] = partes[1].strip()
    return r


def garantir():
    lista = aparelhos()
    alvo = "%s:%d" % (ip_celular(), PORTA)
    if any(e == "device" and ":" not in s for s, e in lista.items()):
        if alvo in lista:  # cabo e tailnet juntos: o adb sem -s falharia; fica so o cabo
            roda(["adb", "disconnect", alvo])
        print("cabo")
        return 0
    if lista.get(alvo) == "device":
        print("tailscale")
        return 0
    roda(["adb", "connect", alvo], limite=15)
    if aparelhos().get(alvo) == "device":
        print("tailscale-nova")
        return 0
    roda(["adb", "disconnect", alvo])
    print("sem conexao: nem cabo nem a porta 5555 pela Tailscale (o celular reiniciou? religue com o cabo ou pelo cel no Wi-Fi)")
    return 1


def soltar():
    alvo = "%s:%d" % (ip_celular(), PORTA)
    roda(["adb", "disconnect", alvo])
    print("solto: " + alvo)
    return 0


def status():
    lista = aparelhos()
    alvo = "%s:%d" % (ip_celular(), PORTA)
    cabo = [s for s, e in lista.items() if e == "device" and ":" not in s]
    print("cabo: " + (", ".join(cabo) if cabo else "nao"))
    print("tailnet: " + alvo + " -> " + lista.get(alvo, "nao conectado"))
    return 0


# ---------------------------------------------------------------------------
# Troca automatica cabo <-> sem fio (12/11/2026)
# ---------------------------------------------------------------------------
TEMPO_TROCA = 60      # segundos esperando outra conexao (Wi-Fi -> dados moveis muda o caminho da Tailscale)
OLHADA = 1.0          # de quanto em quanto tempo o Espelho olha o adb (o `adb devices` e' barato)
ESPERA = 2.0          # entre tentativas de achar outra conexao


def tem_cabo(lista=None):
    """O serial do aparelho no cabo, ou ''."""
    lista = aparelhos() if lista is None else lista
    return next((s for s, e in lista.items() if e == "device" and ":" not in s), "")


def garantir_porta(usb):
    """Com o cabo: deixa a porta 5555 aberta (vale ate reiniciar o celular), para que tirar o cabo nao derrube nada.
    O `adb tcpip` reinicia o adb do celular: o cabo some por 1 ou 2 s e volta. True se a porta ja estava aberta."""
    _, s = roda(["adb", "-s", usb, "shell", "getprop service.adb.tcp.port"], 15)
    if s.strip() == str(PORTA):
        return True
    roda(["adb", "-s", usb, "tcpip", str(PORTA)], 20)
    time.sleep(1.5)
    for _ in range(16):
        if aparelhos().get(usb) == "device":
            break
        time.sleep(0.5)
    print("Sem fio pronto: tirar o cabo agora troca para o Wi-Fi ou os dados moveis sem parar (vale ate reiniciar o celular).")
    return False


def tipo_sem_fio(serial):
    """'wifi' se o celular esta num Wi-Fi; 'dados' se esta so nos dados moveis (gasta franquia)."""
    # 13/11/2026: o cabo de rede da DMZ (eth0) tambem e' rede de casa, sem franquia
    _, s = roda(["adb", "-s", serial, "shell", "ip -4 addr show wlan0; ip -4 addr show eth0"], 15)
    return "wifi" if re.search(r"inet \d+\.\d+\.\d+\.\d+", s) else "dados"


class Espelho:
    """Mantem um programa que fala com o celular (o scrcpy) vivo trocando de conexao sozinho.

    escolher() -> (serial, tipo) ou (None, None): a melhor conexao agora (cabo primeiro).
    montar(serial, tipo) -> a linha de comando para essa conexao.
    ao_trocar(serial, tipo): chamado depois de cada troca (refazer o que dependia do serial).
    Regras: o programa saiu com 0 = a pessoa fechou a janela: acabou. Saiu de outro jeito e o celular sumiu dessa
    conexao (ou saiu com 2, "desconectado" no scrcpy) = troca: espera ate TEMPO_TROCA por outra conexao e reabre.
    No sem fio e o cabo apareceu = passa ao cabo (fecha e reabre, ~2 s). poll()/wait()/terminate() como um Popen."""

    def __init__(self, escolher, montar, serial, tipo, ao_trocar=None, iniciar=subprocess.Popen, aviso=print,
                 cabo=tem_cabo, presentes=aparelhos, **kw_popen):
        self.escolher, self.montar, self.ao_trocar = escolher, montar, ao_trocar
        self.serial, self.tipo = serial, tipo
        self.iniciar, self.aviso, self.cabo, self.presentes, self.kw = iniciar, aviso, cabo, presentes, kw_popen
        self.proc, self.fim, self.trocas = None, None, 0
        self._parar = threading.Event()
        self._t = None

    def _abre(self):
        self.proc = self.iniciar(self.montar(self.serial, self.tipo), **self.kw)

    def start(self):
        self._abre()
        self._t = threading.Thread(target=self._vigia, daemon=True)
        self._t.start()
        return self

    def _troca(self, motivo):
        self.aviso("Conexao com o celular: %s; procurando outra..." % motivo)
        fim = time.monotonic() + TEMPO_TROCA
        while not self._parar.is_set():
            serial, tipo = self._seguro(self.escolher, (None, None))
            if serial:
                self.serial, self.tipo = serial, tipo
                self.trocas += 1
                self.aviso("Conexao com o celular: agora %s (%s)." % ({"cabo": "pelo cabo", "dados": "pelos DADOS MOVEIS (gasta a franquia)", "tailscale": "pela Tailscale"}
                                                                      .get(tipo, "pelo Wi-Fi"), serial))
                if self.ao_trocar:
                    try:
                        self.ao_trocar(serial, tipo)
                    except Exception as falha:  # noqa: BLE001 - refazer o extra nao pode derrubar o espelho
                        self.aviso("(depois da troca: %s)" % falha)
                self._abre()
                return True
            if time.monotonic() > fim:
                self.aviso("Nenhuma conexao em %d s (cabo, Wi-Fi e Tailscale): encerrando." % TEMPO_TROCA)
                return False
            self._parar.wait(ESPERA)
        return False

    def _seguro(self, f, padrao):
        """O adb pode travar ou falhar no meio da troca de rede: a vigia nunca morre por isso."""
        try:
            return f()
        except Exception:  # noqa: BLE001
            return padrao

    def _vigia(self):
        try:
            self._vigia_laco()
        finally:
            if self.fim is None:
                self.fim = 1   # a vigia nunca termina sem dizer como acabou (quem espera pelo poll() nao fica preso)

    def _vigia_laco(self):
        while not self._parar.is_set():
            rc = self.proc.poll()
            if rc is not None:
                if rc == 0 or self._parar.is_set():
                    self.fim = rc
                    return
                sumiu = rc == 2 or self._seguro(self.presentes, {}).get(self.serial) != "device"
                if not sumiu or not self._troca("caiu (%s)" % ("cabo solto" if self.tipo == "cabo" else "rede")):
                    self.fim = rc
                    return
                continue
            if self.tipo != "cabo" and self._seguro(self.cabo, ""):
                self.proc.terminate()
                try:
                    self.proc.wait(10)
                except Exception:  # noqa: BLE001
                    pass
                if not self._troca("cabo ligado, passando para ele"):
                    self.fim = 1
                    return
                continue
            self._parar.wait(OLHADA)

    def poll(self):
        return self.fim if self._t is not None and not self._t.is_alive() else None

    def wait(self, timeout=None):
        if self._t is not None:
            self._t.join(timeout)
        return self.poll()

    @property
    def returncode(self):
        return self.poll()

    def terminate(self):
        self._parar.set()
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()


def main(args):
    cmd = args[0] if args else "status"
    if cmd == "garantir":
        return garantir()
    if cmd == "soltar":
        return soltar()
    if cmd == "status":
        return status()
    print(__doc__.strip())
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
