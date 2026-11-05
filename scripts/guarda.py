#!/usr/bin/env python3
"""guarda: vigia de arquivos com o motor ClamAV, o mesmo para o PC e o celular (`celular-kit/bin/guarda` manda os arquivos do celular para ca).

Tempo real de verdade, com um limite que nao muda: o arquivo e varrido logo DEPOIS de gravado; nada impede de abrir um programa antes
disso. Nao olha trafego, nao mexe em firewall, em VPN, em DNS nem em configuracao do sistema, e so vigia as pastas da lista VIGIADAS.
Parado nao gasta: o motor (cerca de 1 GB) so sobe quando chega arquivo e desce depois de OCIOSO_S. Com pouca memoria ele espera.
Nunca apaga: o que acusa vai para a quarentena e `devolver` desfaz.

  guarda.py status | vigiar | varrer ARQ | varredura [PASTA] [--tudo] | quarentena | devolver ID | provar | rede [--aceitar] | atualizar
Regras e medidas: memoria/ANTIVIRUS.md.
"""
import argparse
import hashlib
import json
import os
import re
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

PORTA = 33100
PORTA_TRAVA = 33099
OCIOSO_S = 300
MEMORIA_MIN_MB = 2500
MAX_ARQUIVO = 400 * 1024 * 1024
PEDACO = 256 * 1024
QUIETO_S = 2.0
ESPERA_SEM_MEMORIA_S = 120
TENTATIVAS = 4
ATUALIZA_S = 24 * 3600
REDE_S = 30 * 60
ESPERA_MOTOR_S = 180

IGNORAR_FIM = (".crdownload", ".part", ".partial", ".tmp", ".download", ".opdownload", ".!qb", ".quarentena")
IGNORAR_NOME = {"desktop.ini", "thumbs.db"}
ASSINATURA_TESTE = "Guarda.Teste.Inofensivo"
TEXTO_TESTE = b"GUARDA-TESTE-INOFENSIVO-CONFERE-O-CAMINHO-INTEIRO\n"  # nao e virus: so casa com a assinatura propria abaixo
PROCESSOS_DO_SISTEMA = {"system", "svchost", "lsass", "wininit", "services", "spoolsv", "system idle process"}


class SemMemoria(Exception):
    pass


class MotorFora(Exception):
    pass


class Ambiente:
    def __init__(self, local=None, perfil=None):
        self.local = Path(local or os.environ.get("LOCALAPPDATA") or Path.home())
        self.perfil = Path(perfil or os.environ.get("USERPROFILE") or Path.home())
        self.clam = self.local / "Programs" / "ClamAV"
        self.base = self.local / "Guarda"
        self.quarentena = self.base / "quarentena"
        self.registro = self.base / "guarda.log"
        self.estado = self.base / "estado.json"
        self.portas_base = self.base / "portas-base.json"
        self.liberados = self.base / "liberados.json"
        self.conf = self.base / "clamd.conf"
        self.ultimo_uso = self.base / "ultimo-uso"

    def vigiadas(self):
        """So o que chega de fora: navegador, KDE Connect, entregas das IAs. Jogos, gravacoes do OBS, backups e o projeto ficam de fora de proposito."""
        return [
            self.perfil / "Downloads",
            self.perfil / "Desktop",
            Path(r"C:\Projetos\qwen-celular\saida"),
            Path(r"C:\Projetos\qwen-celular\entrada"),
            Path(r"C:\Projetos\hermes-trabalho\android-embeeded\saida"),
            self.perfil / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup",  # onde praga costuma se instalar
        ]


def registra(amb, evento, **dados):
    amb.base.mkdir(parents=True, exist_ok=True)
    linha = json.dumps({"quando": time.strftime("%Y-%m-%d %H:%M:%S"), "evento": evento, **dados}, ensure_ascii=False)
    with open(amb.registro, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def interpreta(resposta):
    """So 'stream: OK' exato e limpo. Qualquer outra coisa (limite, erro, resposta cortada) NUNCA vira limpo."""
    texto = resposta.strip("\0 \r\n")
    if texto == "stream: OK":
        return "limpo", ""
    m = re.fullmatch(r"stream: (.+) FOUND", texto)
    if m:
        return "infectado", m.group(1)
    return "erro", texto[:120]


def memoria_livre_mb():
    if os.name != "nt":
        return 1 << 20
    import ctypes

    class Estado(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("livre", ctypes.c_ulonglong),
                    ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]

    e = Estado()
    e.dwLength = ctypes.sizeof(Estado)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(e))
    return e.livre // (1024 * 1024)


class Motor:
    """Fala com o clamd so em 127.0.0.1. Quem sobe e o primeiro que precisa; quem desce e o vigia, depois de ocioso."""

    def __init__(self, amb, porta=PORTA, memoria=memoria_livre_mb, inicia=None):
        self.amb, self.porta, self.memoria = amb, porta, memoria
        self.inicia = inicia or self._inicia
        self._trava = threading.Lock()

    def _fala(self, comando, timeout=5):
        with socket.create_connection(("127.0.0.1", self.porta), timeout=timeout) as s:
            s.sendall(comando)
            partes = []
            while True:
                d = s.recv(4096)
                if not d:
                    break
                partes.append(d)
        return b"".join(partes).decode("utf-8", "replace").strip("\0 \r\n")

    def vivo(self):
        try:
            return self._fala(b"zPING\0", 3) == "PONG"
        except OSError:
            return False

    def _escreve_conf(self):
        self.amb.base.mkdir(parents=True, exist_ok=True)
        self.amb.conf.write_text(
            f"Foreground yes\nDatabaseDirectory {self.amb.clam / 'database'}\nTCPSocket {self.porta}\nTCPAddr 127.0.0.1\n"
            "MaxThreads 2\nConcurrentDatabaseReload no\nStreamMaxLength 400M\nMaxFileSize 400M\nMaxScanSize 400M\nLogVerbose no\n",
            encoding="ascii",
        )

    def garante_assinatura_teste(self):
        pasta = self.amb.clam / "database"
        if pasta.is_dir():
            md5 = hashlib.md5(TEXTO_TESTE).hexdigest()
            (pasta / "guarda-teste.hdb").write_text(f"{md5}:{len(TEXTO_TESTE)}:{ASSINATURA_TESTE}\n", encoding="ascii")

    def _inicia(self):
        self._escreve_conf()
        self.garante_assinatura_teste()
        abaixo_do_normal, sem_janela = 0x00004000, 0x08000000
        flags = abaixo_do_normal | sem_janela if os.name == "nt" else 0
        subprocess.Popen([str(self.amb.clam / "clamd.exe"), "-c", str(self.amb.conf)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=flags)

    def garante(self, espera=ESPERA_MOTOR_S, dorme=time.sleep, relogio=time.monotonic):
        with self._trava:
            if self.vivo():
                return
            livre = self.memoria()
            if livre < MEMORIA_MIN_MB:
                raise SemMemoria(f"{livre} MB livres")
            self.inicia()
            fim = relogio() + espera
            while relogio() < fim:
                if self.vivo():
                    registra(self.amb, "motor-ligado", livre_mb=livre)
                    return
                dorme(1)
            raise MotorFora("o motor nao respondeu a tempo")

    def varre(self, pedacos):
        """Manda os bytes pelo protocolo INSTREAM. Nada e gravado por aqui. Devolve (estado, detalhe)."""
        with socket.create_connection(("127.0.0.1", self.porta), timeout=120) as s:
            s.sendall(b"zINSTREAM\0")
            for p in pedacos:
                if p:
                    s.sendall(struct.pack("!L", len(p)) + p)
            s.sendall(struct.pack("!L", 0))
            partes = []
            while True:
                d = s.recv(4096)
                if not d:
                    break
                partes.append(d)
        self.amb.base.mkdir(parents=True, exist_ok=True)
        self.amb.ultimo_uso.write_text(str(time.time()), encoding="ascii")
        return interpreta(b"".join(partes).decode("utf-8", "replace"))

    def para_se_ocioso(self, agora=None, ocioso=OCIOSO_S):
        agora = time.time() if agora is None else agora
        try:
            ultimo = float(self.amb.ultimo_uso.read_text(encoding="ascii"))
        except (OSError, ValueError):
            ultimo = 0.0
        if agora - ultimo < ocioso or not self.vivo():
            return False
        try:
            self._fala(b"zSHUTDOWN\0", 3)
        except OSError:
            pass
        registra(self.amb, "motor-desligado")
        return True


def le_eventos(buffer):
    """Lista de (acao, nome relativo) do bloco que o ReadDirectoryChangesW devolve (FILE_NOTIFY_INFORMATION)."""
    saida, pos = [], 0
    while pos + 12 <= len(buffer):
        proximo, acao, tamanho = struct.unpack_from("<III", buffer, pos)
        fim = pos + 12 + tamanho
        if fim > len(buffer):
            break
        saida.append((acao, buffer[pos + 12:fim].decode("utf-16-le", "replace")))
        if proximo == 0:
            break
        pos += proximo
    return saida


ACOES_DE_ARQUIVO_NOVO = {1, 3, 5}  # criado, alterado, novo nome


def vigia_pasta(pasta, aviso, sobrecarga):
    """Bloqueia sem gastar CPU. Pasta que ainda nao existe: tenta de novo em 60 s."""
    import ctypes
    from ctypes import wintypes

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateFileW.restype = wintypes.HANDLE
    k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k.ReadDirectoryChangesW.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID, wintypes.LPVOID]
    invalido = wintypes.HANDLE(-1).value
    while True:
        h = k.CreateFileW(str(pasta), 1, 7, None, 3, 0x02000000, None)
        if h == invalido:
            time.sleep(60)
            continue
        buf = ctypes.create_string_buffer(64 * 1024)
        lidos = wintypes.DWORD()
        try:
            while k.ReadDirectoryChangesW(h, buf, len(buf), True, 0x1 | 0x8 | 0x10, ctypes.byref(lidos), None, None):
                if lidos.value == 0:
                    sobrecarga(pasta)
                    continue
                for acao, nome in le_eventos(buf.raw[:lidos.value]):
                    if acao in ACOES_DE_ARQUIVO_NOVO:
                        aviso(pasta / nome)
        finally:
            k.CloseHandle(h)
        time.sleep(5)


def ignorar(caminho):
    nome = Path(caminho).name.lower()
    if nome.startswith("mapao_") and nome.endswith(".xlsx"):  # regra do Rafael: planilha de notas nunca e aberta, nem para varrer
        return True
    return nome in IGNORAR_NOME or nome.endswith(IGNORAR_FIM)


class Fila:
    """So entrega o arquivo que parou de mudar por QUIETO_S (o navegador grava aos poucos)."""

    def __init__(self, quieto=QUIETO_S):
        self.quieto = quieto
        self.itens = {}
        self.trava = threading.Lock()

    def aviso(self, caminho, agora=None):
        if ignorar(caminho):
            return
        agora = time.time() if agora is None else agora
        with self.trava:
            atual = self.itens.get(str(caminho))
            self.itens[str(caminho)] = {"marca": None, "desde": agora, "tentativas": atual["tentativas"] if atual else 0, "depois": 0}

    def adia(self, caminho, agora, espera):
        """Devolve False quando ja tentou demais."""
        with self.trava:
            atual = self.itens.get(str(caminho)) or {"tentativas": 0}
            tentativas = atual["tentativas"] + 1
            if tentativas >= TENTATIVAS:
                self.itens.pop(str(caminho), None)
                return False
            self.itens[str(caminho)] = {"marca": None, "desde": agora, "tentativas": tentativas, "depois": agora + espera}
            return True

    def espera_memoria(self, caminho, agora, espera):
        """Falta de memoria nao gasta tentativa: o arquivo espera o tempo que for."""
        with self.trava:
            atual = self.itens.get(str(caminho)) or {"tentativas": 0}
            self.itens[str(caminho)] = {"marca": None, "desde": agora, "tentativas": atual["tentativas"], "depois": agora + espera}

    def prontos(self, agora=None):
        agora = time.time() if agora is None else agora
        saida = []
        with self.trava:
            for caminho, item in list(self.itens.items()):
                if agora < item["depois"]:
                    continue
                try:
                    st = os.lstat(caminho)
                except OSError:
                    del self.itens[caminho]
                    continue
                marca = (st.st_size, st.st_mtime)
                if marca != item["marca"]:
                    item["marca"], item["desde"] = marca, agora
                elif agora - item["desde"] >= self.quieto:
                    saida.append(caminho)
                    item["depois"] = agora + 3600  # em andamento: o processamento tira ou adia
        return saida

    def conclui(self, caminho):
        with self.trava:
            self.itens.pop(str(caminho), None)

    def __len__(self):
        with self.trava:
            return len(self.itens)


def _nome_seguro(nome):
    return re.sub(r"[^\w.\- ]", "_", nome)[:120] or "arquivo"


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for p in iter(lambda: f.read(PEDACO), b""):
            h.update(p)
    return h.hexdigest()


def le_json(caminho, padrao):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def grava_json(caminho, dados):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(caminho.name + ".novo")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, caminho)


def poe_em_quarentena(amb, caminho, ameaca, agora=None):
    agora = time.time() if agora is None else agora
    caminho = Path(caminho)
    amb.quarentena.mkdir(parents=True, exist_ok=True)
    resumo = sha256(caminho)
    ident = time.strftime("%Y%m%d-%H%M%S", time.localtime(agora)) + "-" + resumo[:8]
    destino = amb.quarentena / f"{ident}-{_nome_seguro(caminho.name)}.quarentena"
    os.replace(caminho, destino)
    grava_json(destino.with_name(destino.name + ".json"), {"id": ident, "origem": str(caminho), "ameaca": ameaca, "sha256": resumo, "arquivo": destino.name})
    return ident


def lista_quarentena(amb):
    itens = []
    for j in sorted(amb.quarentena.glob("*.quarentena.json")) if amb.quarentena.is_dir() else []:
        d = le_json(j, None)
        if d and (amb.quarentena / str(d.get("arquivo", ""))).is_file():
            itens.append(d)
    return itens


def devolve(amb, ident):
    """Volta ao lugar de origem e marca este conteudo como liberado, para o vigia nao levar de novo."""
    for d in lista_quarentena(amb):
        if d["id"] == ident:
            origem = Path(d["origem"])
            if origem.exists():
                raise ValueError("ja existe um arquivo com esse nome na origem; nada foi mudado")
            liberados = le_json(amb.liberados, [])
            if d["sha256"] not in liberados:
                grava_json(amb.liberados, liberados + [d["sha256"]])
            origem.parent.mkdir(parents=True, exist_ok=True)
            os.replace(amb.quarentena / d["arquivo"], origem)
            (amb.quarentena / (d["arquivo"] + ".json")).unlink()
            registra(amb, "devolvido", id=ident)
            return origem
    raise ValueError("nao ha esse id na quarentena")


def avisa(amb, titulo, texto, roda=subprocess.Popen):
    """Balao no PC e recado ao celular pelo KDE Connect, que ja esta pareado. Falha de aviso nunca derruba a vigia."""
    registra(amb, "aviso", titulo=titulo, texto=texto)
    if os.name != "nt":
        return
    sem_janela = 0x08000000
    limpo = lambda s: re.sub(r"[^\w .,:()\-]", "_", s)[:180]
    script = ("Add-Type -AssemblyName System.Windows.Forms;$n=New-Object System.Windows.Forms.NotifyIcon;$n.Icon=[System.Drawing.SystemIcons]::Warning;"
              f"$n.Visible=$true;$n.ShowBalloonTip(20000,'{limpo(titulo)}','{limpo(texto)}','Warning');Start-Sleep 21;$n.Dispose()")
    try:
        roda(["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script], creationflags=sem_janela, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass
    cli = amb.local / "Programs" / "KDE Connect" / "bin" / "kdeconnect-cli.exe"
    if cli.is_file():
        threading.Thread(target=_recado_kde, args=(cli, f"{limpo(titulo)}: {limpo(texto)}"), daemon=True).start()


def _recado_kde(cli, texto):
    sem_janela = 0x08000000
    try:
        ids = subprocess.run([str(cli), "-a", "--id-only"], capture_output=True, text=True, timeout=20, creationflags=sem_janela).stdout.split()
        for i in ids:
            subprocess.run([str(cli), "-d", i, "--ping-msg", texto], capture_output=True, timeout=20, creationflags=sem_janela)
    except (OSError, subprocess.SubprocessError):
        pass


def le_pedacos(caminho):
    with open(caminho, "rb") as f:
        for p in iter(lambda: f.read(PEDACO), b""):
            yield p


def processa(amb, motor, caminho, avisar=avisa):
    """Devolve limpo, infectado, liberado, grande, ignorado ou erro. SemMemoria e MotorFora sobem para quem chamou adiar."""
    if ignorar(caminho):
        return "ignorado"
    st = os.lstat(caminho)
    if not os.path.isfile(caminho) or os.path.islink(caminho) or st.st_size == 0:
        return "ignorado"
    if st.st_size > MAX_ARQUIVO:
        registra(amb, "grande-demais", arquivo=str(caminho), mb=st.st_size // (1024 * 1024))
        return "grande"
    motor.garante()
    estado, detalhe = motor.varre(le_pedacos(caminho))
    if estado == "limpo":
        registra(amb, "limpo")  # sem o nome: o registro nao vira lista do que voce baixa
        return "limpo"
    if estado != "infectado":
        registra(amb, "erro-do-motor", arquivo=str(caminho), detalhe=detalhe)
        return "erro"
    if sha256(caminho) in le_json(amb.liberados, []):
        registra(amb, "liberado", arquivo=str(caminho), ameaca=detalhe)
        return "liberado"
    ident = poe_em_quarentena(amb, caminho, detalhe)
    registra(amb, "quarentena", arquivo=str(caminho), ameaca=detalhe, id=ident)
    if not detalhe.startswith(ASSINATURA_TESTE):  # o clamd acrescenta .UNOFFICIAL ao nome de assinatura propria
        avisar(amb, "Guarda: arquivo isolado", f"{Path(caminho).name} ({detalhe})")
    return "infectado"


def trata_fila(amb, motor, fila, agora=None, avisar=avisa):
    agora = time.time() if agora is None else agora
    for caminho in fila.prontos(agora):
        try:
            resultado = processa(amb, motor, caminho, avisar)
        except SemMemoria as e:
            registra(amb, "esperando-memoria", arquivo=caminho, detalhe=str(e))
            fila.espera_memoria(caminho, agora, ESPERA_SEM_MEMORIA_S)
            continue
        except FileNotFoundError:
            fila.conclui(caminho)
            continue
        except (OSError, MotorFora) as e:  # arquivo preso por outro programa ou motor fora: tenta de novo e, no fim, registra sem fingir que varreu
            if not fila.adia(caminho, agora, 30):
                registra(amb, "nao-varrido", arquivo=caminho, detalhe=str(e)[:120])
            continue
        if resultado == "erro":
            if not fila.adia(caminho, agora, 30):
                registra(amb, "nao-varrido", arquivo=caminho, detalhe="erro do motor")
            continue
        fila.conclui(caminho)


def arquivos_recentes(pastas, desde):
    """O que chegou com a vigia parada. Sem seguir atalho de pasta."""
    for pasta in pastas:
        for raiz, dirs, nomes in os.walk(pasta, followlinks=False):
            for n in nomes:
                c = os.path.join(raiz, n)
                try:
                    st = os.lstat(c)
                    if max(st.st_mtime, st.st_ctime, getattr(st, "st_birthtime", 0)) > desde:  # ctime no Windows = quando chegou aqui, mesmo com data antiga
                        yield c
                except OSError:
                    continue


def analisa_portas(netstat, processos):
    """Saida do netstat -ano e {pid: nome} viram {(processo, porta)} so do que escuta FORA do proprio PC. Porta alta (dinamica) conta so pelo processo."""
    achadas = set()
    for linha in netstat.splitlines():
        p = linha.split()
        if len(p) < 5 or p[0] != "TCP" or p[3] not in ("LISTENING", "ESCUTANDO"):
            continue
        endereco, _, porta = p[1].rpartition(":")
        if endereco in ("127.0.0.1", "[::1]") or not porta.isdigit():
            continue
        nome = processos.get(p[4], f"pid{p[4]}").lower().removesuffix(".exe")
        achadas.add(f"{nome}:{'dinamica' if int(porta) >= 49152 else porta}")
    return achadas


def portas_agora(roda=subprocess.run):
    sem_janela = {"creationflags": 0x08000000} if os.name == "nt" else {}
    net = roda(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=30, **sem_janela).stdout
    net6 = roda(["netstat", "-ano", "-p", "TCPv6"], capture_output=True, text=True, timeout=30, **sem_janela).stdout
    lista = roda(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=30, **sem_janela).stdout
    processos = {}
    for linha in lista.splitlines():
        m = re.match(r'"([^"]+)","(\d+)"', linha)
        if m:
            processos[m.group(2)] = m.group(1)
    return analisa_portas(net + "\n" + net6, processos)


def compara_portas(amb, agora):
    """Na primeira vez guarda a referencia. Depois devolve o que apareceu de novo (uma vez so por porta)."""
    base = le_json(amb.portas_base, None)
    if base is None:
        grava_json(amb.portas_base, sorted(agora))
        return []
    novas = sorted(p for p in agora if p not in set(base) and p.split(":")[0] not in PROCESSOS_DO_SISTEMA)
    if novas:
        grava_json(amb.portas_base, sorted(set(base) | set(novas)))
    return novas


def compara_pares(amb, dados):
    """Aparelho novo na tailnet e o que mais importa para a VPN: ele alcancaria a saida de internet e as portas do PC. Na primeira vez guarda a referencia."""
    pares = {str(p.get("PublicKey", "")): str(p.get("HostName", "?")) for p in (dados.get("Peer") or {}).values()}
    arquivo = amb.base / "pares-base.json"
    base = le_json(arquivo, None)
    if base is None:
        grava_json(arquivo, sorted(pares))
        return []
    novos = sorted(nome for chave, nome in pares.items() if chave not in set(base))
    if novos:
        grava_json(arquivo, sorted(set(base) | set(pares)))
    return novos


def problemas_da_vpn(dados):
    """O que deixaria o celular sem saida ou mandaria o trafego do PC para outro aparelho."""
    ruins = []
    if dados.get("BackendState") != "Running":
        ruins.append("Tailscale do PC nao esta ligada")
        return ruins
    eu = dados.get("Self") or {}
    if "0.0.0.0/0" not in (eu.get("AllowedIPs") or []):
        ruins.append("o PC nao esta aprovado como saida de internet")
    for p in (dados.get("Peer") or {}).values():
        if p.get("ExitNode"):
            ruins.append(f"o PC esta mandando a propria internet por {p.get('HostName', '?')}")
    return ruins


def dados_tailscale(roda=subprocess.run):
    sem_janela = {"creationflags": 0x08000000} if os.name == "nt" else {}
    return json.loads(roda(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=30, **sem_janela).stdout)


def confere_rede(amb):
    """Leve (netstat, tasklist e tailscale, sem PowerShell): roda de 30 em 30 min na vigia. Devolve textos de aviso que ainda nao foram dados."""
    avisos = []
    novas = compara_portas(amb, portas_agora())
    if novas:
        avisos.append("porta nova aberta: " + ", ".join(novas))
    d = dados_tailscale()
    novos = compara_pares(amb, d)
    if novos:
        avisos.append("aparelho novo na VPN: " + ", ".join(novos))
    ruins = problemas_da_vpn(d)
    anteriores = le_json(amb.base / "vpn-avisos.json", [])
    avisos += [r for r in ruins if r not in anteriores]
    grava_json(amb.base / "vpn-avisos.json", ruins)
    return avisos


def pastas_da_varredura(amb, tudo=False):
    if tudo:
        return [amb.perfil]
    return [p for p in amb.vigiadas() if p.is_dir()]


PASTAS_FORA_DA_VARREDURA = {"backups", "node_modules", ".git", "__pycache__", "temp", "inetcache", "onedrive", "packages"}


def arquivos_da_varredura(pastas):
    for pasta in pastas:
        for raiz, dirs, nomes in os.walk(pasta, followlinks=False):
            dirs[:] = [d for d in dirs if d.lower() not in PASTAS_FORA_DA_VARREDURA]
            for n in nomes:
                yield os.path.join(raiz, n)


def varredura(amb, pastas, motor=None, memoria=memoria_livre_mb, dorme=time.sleep, escreve=print):
    """Varredura completa, sob demanda, com prioridade baixa. Com a memoria acabando ela espera em vez de atrapalhar. Devolve o resumo."""
    motor = motor or Motor(amb, memoria=memoria)
    conta = {"limpo": 0, "infectado": 0, "liberado": 0, "grande": 0, "ignorado": 0, "erro": 0}
    for caminho in arquivos_da_varredura(pastas):
        while memoria() < MEMORIA_MIN_MB // 2:
            dorme(60)
        try:
            conta[processa(amb, motor, caminho)] += 1
        except SemMemoria:
            dorme(60)
            conta["erro"] += 1
        except OSError:  # preso por outro programa, ou sumiu: nao conta como limpo
            conta["erro"] += 1
        except MotorFora:
            conta["erro"] += 1
            break
    registra(amb, "varredura", **conta)
    escreve(f"Varredura: {conta['limpo']} limpos, {conta['infectado']} isolados, {conta['liberado']} liberados por voce, "
            f"{conta['grande']} grandes demais, {conta['ignorado']} ignorados, {conta['erro']} sem varrer.")
    return conta


def _atende_trava(trava):
    """Sem aceitar, a fila da porta enche depois de poucas consultas e o `status` passa a dizer que a vigia esta desligada (visto no PC em 04/11)."""
    while True:
        try:
            c, _ = trava.accept()
            c.close()
        except OSError:
            return


def vigiar(amb, motor=None):
    trava = socket.socket()
    try:
        trava.bind(("127.0.0.1", PORTA_TRAVA))
        trava.listen(8)
    except OSError:
        print("A vigia ja esta rodando.")
        return 0
    threading.Thread(target=_atende_trava, args=(trava,), daemon=True).start()
    motor = motor or Motor(amb)
    fila = Fila()
    acorda = threading.Event()
    pastas = amb.vigiadas()

    def aviso(c):
        fila.aviso(c)
        acorda.set()

    def sobrecarga(pasta):
        for c in arquivos_recentes([pasta], time.time() - 120):
            aviso(c)

    for pasta in pastas:
        threading.Thread(target=vigia_pasta, args=(pasta, aviso, sobrecarga), daemon=True).start()
    estado = le_json(amb.estado, {})
    registra(amb, "vigia-ligada", pastas=len(pastas))
    for c in arquivos_recentes([p for p in pastas if p.is_dir()], float(estado.get("ultimo", 0))):
        aviso(c)
    while True:
        agora = time.time()
        trata_fila(amb, motor, fila, agora)
        motor.para_se_ocioso(agora)
        if agora - float(estado.get("atualizado", 0)) > ATUALIZA_S:
            estado["atualizado"] = agora
            threading.Thread(target=atualiza, args=(amb,), daemon=True).start()
        if agora - float(estado.get("rede", 0)) > REDE_S:
            estado["rede"] = agora
            try:
                for texto in confere_rede(amb):
                    avisa(amb, "Guarda: rede", texto)
            except (OSError, ValueError, subprocess.SubprocessError) as e:
                registra(amb, "rede-falhou", detalhe=str(e)[:120])
        if not len(fila):  # so avanca sem nada pendente: o que ficou preso e revisto ao religar
            estado["ultimo"] = agora - 5
        grava_json(amb.estado, estado)
        acorda.wait(2 if len(fila) else 60)
        acorda.clear()


def atualiza(amb, roda=subprocess.run):
    sem_janela = {"creationflags": 0x08000000} if os.name == "nt" else {}
    try:
        r = roda([str(amb.clam / "freshclam.exe"), f"--config-file={amb.clam / 'freshclam.conf'}"], capture_output=True, text=True, timeout=900, **sem_janela)
        registra(amb, "assinaturas", codigo=r.returncode)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError) as e:
        registra(amb, "assinaturas-falhou", detalhe=str(e)[:120])
        return False


def vigia_viva():
    s = socket.socket()
    s.settimeout(1)
    try:
        s.connect(("127.0.0.1", PORTA_TRAVA))
        return True
    except OSError:
        return False
    finally:
        s.close()


def ultimos(amb, n=200):
    try:
        linhas = amb.registro.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []
    saida = []
    for l in linhas:
        try:
            saida.append(json.loads(l))
        except ValueError:
            pass
    return saida


def cmd_status(amb):
    motor = Motor(amb)
    print(f"Vigia: {'ligada' if vigia_viva() else 'DESLIGADA'} | motor: {'carregado' if motor.vivo() else 'parado (sobe quando chega arquivo)'}")
    main = amb.clam / "database" / "daily.cvd"
    if main.is_file():
        dias = (time.time() - main.stat().st_mtime) / 86400
        print(f"Assinaturas: de {time.strftime('%d/%m %H:%M', time.localtime(main.stat().st_mtime))} ({dias:.1f} dias)" + (" DESATUALIZADAS" if dias > 7 else ""))
    else:
        print("Assinaturas: NAO encontradas")
    print("Pastas: " + "; ".join(str(p) for p in amb.vigiadas() if p.is_dir()))
    print(f"Quarentena: {len(lista_quarentena(amb))} arquivo(s)")
    ev = ultimos(amb)
    print(f"Ultimos registros: {sum(e['evento'] == 'limpo' for e in ev)} limpos, {sum(e['evento'] == 'quarentena' for e in ev)} isolados, "
          f"{sum(e['evento'] in ('nao-varrido', 'grande-demais') for e in ev)} sem varrer")
    return 0


def cmd_varrer(amb, arquivo):
    motor = Motor(amb)
    try:
        resultado = processa(amb, motor, arquivo)
    except SemMemoria as e:
        print(f"Pouca memoria para ligar o motor agora ({e}). Nada foi varrido.")
        return 2
    print(f"{arquivo}: {resultado}")
    return 1 if resultado == "infectado" else (2 if resultado in ("erro", "grande") else 0)


def cmd_quarentena(amb):
    itens = lista_quarentena(amb)
    if not itens:
        print("Quarentena vazia.")
    for d in itens:
        print(f"{d['id']} | {d['ameaca']} | {d['origem']}")
    return 0


def cmd_provar(amb, espera=240):
    """Caminho inteiro de verdade: grava um arquivo inofensivo numa pasta vigiada e confere que ele foi isolado. Usa assinatura propria, sem disparar o Defender."""
    if not vigia_viva():
        print("A vigia esta desligada.")
        return 2
    Motor(amb).garante_assinatura_teste()
    alvo = amb.perfil / "Downloads" / f"guarda-prova-{int(time.time())}.txt"
    inicio = time.time()
    alvo.write_bytes(TEXTO_TESTE)
    while time.time() - inicio < espera:
        for d in lista_quarentena(amb):
            if d["origem"] == str(alvo):
                print(f"PROVADO: isolado em {time.time() - inicio:.0f} s como {d['ameaca']}.")
                (amb.quarentena / d["arquivo"]).unlink()
                (amb.quarentena / (d["arquivo"] + ".json")).unlink()
                return 0
        time.sleep(1)
    print("FALHOU: o arquivo de prova nao foi isolado.")
    if alvo.exists():
        alvo.unlink()
    return 1


def regras_rdp():
    script = (
        "Get-NetFirewallPortFilter -Protocol TCP | Where-Object { $_.LocalPort -eq '3389' } | ForEach-Object { $r = $_ | Get-NetFirewallRule; "
        "if ($r.Enabled -eq 'True' -and $r.Direction -eq 'Inbound' -and $r.Action -eq 'Allow') { [pscustomobject]@{ perfil = \"$($r.Profile)\"; remoto = (($r | Get-NetFirewallAddressFilter).RemoteAddress -join ',') } } } | ConvertTo-Json -Compress"
    )
    r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=120)
    dados = json.loads(r.stdout or "[]")
    return dados if isinstance(dados, list) else [dados]


def rdp_exposto(regras):
    """Em rede publica (escola, hotel), o RDP so pode aceitar quem vem da tailnet."""
    ruins = []
    for r in regras:
        perfil, remoto = str(r.get("perfil", "")), str(r.get("remoto", ""))
        if ("Public" in perfil or "Any" in perfil) and not remoto.startswith("100.64.0.0"):
            ruins.append(remoto or "qualquer")
    return ruins


def cmd_rede(amb, aceitar=False):
    """So leitura: confere se a parte de rede segue como foi decidida. Nao muda nada."""
    falhas = 0
    agora = portas_agora()
    if aceitar:
        grava_json(amb.portas_base, sorted(agora))
        print("Lista de portas aceita como referencia.")
    novas = compara_portas(amb, agora)
    print(f"Portas abertas para fora: {', '.join(sorted(agora))}")
    if novas:
        falhas += 1
        print(f"AVISO: novas desde a referencia: {', '.join(novas)}")
    for nome, porta in (("Ollama", 11434), ("Painel do AdGuard", 3000), ("clamd", PORTA)):
        if any(p.endswith(f":{porta}") for p in agora):
            falhas += 1
            print(f"AVISO: {nome} ({porta}) esta aberto para fora")
    try:
        ruins = rdp_exposto(regras_rdp())
        print(f"RDP em rede publica: {'so pela tailnet' if not ruins else 'ABERTO a ' + ', '.join(ruins)}")
        falhas += bool(ruins)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        print(f"RDP: nao deu para conferir ({str(e)[:80]})")
        falhas += 1
    try:
        d = dados_tailscale()
        print(f"Tailscale: {d.get('BackendState')} | aparelhos na VPN: {len(d.get('Peer') or {})}")
        novos = compara_pares(amb, d)
        if novos:
            falhas += 1
            print(f"AVISO: aparelho novo na VPN: {', '.join(novos)}")
        for r in problemas_da_vpn(d):
            falhas += 1
            print(f"AVISO: {r}")
    except (OSError, ValueError, subprocess.SubprocessError):
        print("Tailscale: nao respondeu")
        falhas += 1
    print("Tudo como decidido." if not falhas else f"{falhas} ponto(s) para olhar.")
    return 1 if falhas else 0


# ------------------------------------------------- menu do PC: so texto, verde puro com sombras em verde escuro (o mesmo jeito do `antivirus` do celular)
VERDE, MEDIO, ESCURO, SOMBRA = "\x1b[38;2;0;255;0m", "\x1b[38;2;0;175;0m", "\x1b[38;2;0;105;0m", "\x1b[38;2;0;60;0m"
SEL, NEGRITO, Z = "\x1b[48;2;0;255;0m\x1b[38;2;0;0;0m\x1b[1m", "\x1b[1m", "\x1b[0m"
LIMPA = "\x1b[H\x1b[2J\x1b[3J"
LARGURA = 62
LOGO = [
    " ██████╗ ██╗   ██╗ █████╗ ██████╗ ██████╗  █████╗ ",
    "██╔════╝ ██║   ██║██╔══██╗██╔══██╗██╔══██╗██╔══██╗",
    "██║  ███╗██║   ██║███████║██████╔╝██║  ██║███████║",
    "██║   ██║██║   ██║██╔══██║██╔══██╗██║  ██║██╔══██║",
    "╚██████╔╝╚██████╔╝██║  ██║██║  ██║██████╔╝██║  ██║",
    " ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝",
]


def logo_colorido():
    """Bloco cheio em verde puro e as bordas em verde escuro: da o efeito de relevo (3D) so com texto."""
    saida = []
    for linha in LOGO:
        partes, cor = [], None
        for ch in linha:
            nova = VERDE if ch == "█" else (SOMBRA if ch != " " else cor)
            if nova != cor and nova:
                partes.append(nova)
                cor = nova
            partes.append(ch)
        saida.append("  " + "".join(partes) + Z)
    return saida


def traduz(t):
    mapa = {"\xe0H": "cima", "\x00H": "cima", "\xe0P": "baixo", "\x00P": "baixo", "\r": "ok", "\n": "ok", "\x1b": "sair",
            "q": "sair", "Q": "sair", "k": "cima", "j": "baixo", "w": "cima", "s": "baixo"}
    if t in mapa:
        return mapa[t]
    return t if len(t) == 1 and t.isdigit() else "nada"


def le_tecla():
    import msvcrt
    c = msvcrt.getwch()
    if c in ("\x00", "\xe0"):
        c += msvcrt.getwch()
    return traduz(c)


def caixa(linhas):
    """Painel com borda em verde escuro e sombra embaixo e a direita."""
    largura = LARGURA - 4
    saida = [f"  {ESCURO}┌{'─' * largura}┐{Z}"]
    for l in linhas:
        saida.append(f"  {ESCURO}│{Z} {VERDE}{l[:largura - 2].ljust(largura - 2)}{Z} {ESCURO}│{SOMBRA}▌{Z}")
    saida.append(f"  {ESCURO}└{'─' * largura}┘{SOMBRA}▌{Z}")
    saida.append(f"   {SOMBRA}{'▀' * (largura + 2)}{Z}")
    return saida


def situacao(amb):
    motor = Motor(amb)
    linhas = [("● proteção em tempo real LIGADA" if vigia_viva() else "○ proteção em tempo real DESLIGADA")
              + ("   ◆ motor carregado" if motor.vivo() else "   ◇ motor em repouso")]
    base = amb.clam / "database" / "daily.cvd"
    if base.is_file():
        dias = (time.time() - base.stat().st_mtime) / 86400
        linhas.append(f"◆ assinaturas de {time.strftime('%d/%m %H:%M', time.localtime(base.stat().st_mtime))} ({dias:.1f} dia)"
                      + ("  DESATUALIZADAS" if dias > 7 else "") + f"   ◆ quarentena {len(lista_quarentena(amb))}")
    else:
        linhas.append(f"◆ assinaturas NÃO encontradas   ◆ quarentena {len(lista_quarentena(amb))}")
    return linhas


def desenha(pergunta, itens, i, topo):
    out = [LIMPA, ""] + logo_colorido()
    out.append(f"  {MEDIO}  antivírus · motor ClamAV · o mesmo no PC e no celular{Z}")
    out.append("")
    out += caixa(topo)
    out.append("")
    out.append(f"  {VERDE}{NEGRITO}{pergunta}{Z}")
    out.append("")
    for k, t in enumerate(itens):
        n = "0" if t.startswith("Sair") else str(k + 1)
        texto = f" ► {n}  {t}".ljust(LARGURA - 4)  # ❯ nao existe na fonte do cmd (vira quadrado)
        out.append(f"  {SEL}{texto}{Z}{SOMBRA}▌{Z}" if k == i else f"  {MEDIO}   {n}  {VERDE}{t}{Z}")
    out.append("")
    out.append(f"  {ESCURO}─ ↑↓ escolher · Enter confirma · número direto · Esc sai ─{Z}")
    return "\n".join(out)


def escolhe(pergunta, itens, topo, tecla=le_tecla, escreve=None):
    """Devolve o indice escolhido ou -1. O ultimo item pode ser 'Sair', que responde ao 0."""
    escreve = escreve or (lambda s: (sys.stdout.write(s + "\n"), sys.stdout.flush()))
    i, n = 0, len(itens)
    while True:
        escreve(desenha(pergunta, itens, i, topo))
        t = tecla()
        if t == "cima":
            i = (i - 1) % n
        elif t == "baixo":
            i = (i + 1) % n
        elif t == "ok":
            return i
        elif t == "sair":
            return -1
        elif t == "0":
            return n - 1 if itens[-1].startswith("Sair") else -1
        elif t.isdigit() and 1 <= int(t) <= n:
            return int(t) - 1


def recentes(pastas, quantos=7):
    achados = []
    for p in pastas:
        for c in (p.iterdir() if p.is_dir() else []):
            try:
                if c.is_file() and not ignorar(c):
                    achados.append((c.stat().st_mtime, c))
            except OSError:
                continue
    return [c for _, c in sorted(achados, reverse=True)[:quantos]]


class Painel:
    """Liga o menu as acoes. `roda` executa o proprio guarda.py (ou outro programa) e mostra a saida em verde."""

    def __init__(self, amb, tecla=le_tecla, escreve=None, pergunta_texto=input, roda=None):
        self.amb, self.tecla, self.pergunta_texto = amb, tecla, pergunta_texto
        self.escreve = escreve or (lambda s: (sys.stdout.write(s + "\n"), sys.stdout.flush()))
        self.roda = roda or self._roda

    def _roda(self, titulo, cmd):
        self.escreve(LIMPA + "\n" + "\n".join(logo_colorido()) + f"\n\n  {VERDE}{NEGRITO}{titulo}{Z}\n")
        abaixo_do_normal = 0x00004000 if os.name == "nt" else 0  # varredura longa nao atrapalha jogo nem aula
        p = None
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                 errors="replace", creationflags=abaixo_do_normal, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            for linha in p.stdout or []:
                self.escreve(f"  {VERDE}{linha.rstrip()}{Z}")
            p.wait()
        except KeyboardInterrupt:
            if p:
                p.terminate()
            self.escreve(f"  {MEDIO}Interrompido. Nada do que faltava foi dado como limpo.{Z}")
        except OSError as e:
            self.escreve(f"  {MEDIO}Não deu para rodar: {e}{Z}")
        self.escreve(f"\n  {ESCURO}── Enter para voltar ──{Z}")
        while self.tecla() not in ("ok", "sair"):
            pass

    def guarda(self, titulo, *args):
        self.roda(titulo, [sys.executable, "-B", os.path.abspath(__file__), *args])

    def escolhe(self, pergunta, itens):
        return escolhe(pergunta, itens, situacao(self.amb), self.tecla, self.escreve)

    def confirma(self, pergunta, sim, nao="Não, voltar", sim_primeiro=True):
        itens = [sim, nao] if sim_primeiro else [nao, sim]
        return self.escolhe(pergunta, itens) == itens.index(sim)

    def digita(self, pergunta):
        self.escreve(f"\n  {VERDE}{pergunta}{Z} ")
        try:
            return self.pergunta_texto("").strip().strip('"')
        except EOFError:
            return ""

    def varredura_completa(self):
        if self.confirma("Varredura completa da sua pasta de usuário (sem Backups, OneDrive e temporários). Pode levar mais de uma hora.",
                         "Sim, iniciar agora"):
            self.guarda("Varredura completa (Ctrl+C interrompe)", "varredura", "--tudo")

    def outras(self):
        escolha = self.escolhe("Qual varredura?", ["Rápida: só as pastas vigiadas", "Uma pasta", "Um arquivo",
                                                  "O celular pelo cabo (apps e Download, ~4 GB, ~50 min)", "Voltar"])
        if escolha == 0:
            self.guarda("Varredura rápida", "varredura")
        elif escolha == 1:
            pastas = [self.amb.perfil / n for n in ("Downloads", "Desktop", "Documents", "Pictures", "Videos")]
            pastas = [p for p in pastas if p.is_dir()]
            e = self.escolhe("Qual pasta?", [p.name for p in pastas] + ["Digitar o caminho", "Voltar"])
            alvo = str(pastas[e]) if 0 <= e < len(pastas) else (self.digita("Caminho da pasta:") if e == len(pastas) else "")
            if alvo:
                self.guarda(f"Varrendo {alvo}", "varredura", alvo)
        elif escolha == 2:
            arqs = recentes([self.amb.perfil / "Downloads", self.amb.perfil / "Desktop"])
            e = self.escolhe("Qual arquivo? (os mais novos primeiro)", [a.name for a in arqs] + ["Digitar o caminho", "Voltar"])
            alvo = str(arqs[e]) if 0 <= e < len(arqs) else (self.digita("Caminho do arquivo:") if e == len(arqs) else "")
            if alvo:
                self.guarda(f"Varrendo {Path(alvo).name}", "varrer", alvo)
        elif escolha == 3:
            if self.confirma("Ligue o celular no cabo com a depuração USB. Os apps e a pasta Download vêm para o PC, são varridos e a cópia é apagada.",
                             "Sim, varrer o celular agora"):
                self.roda("Celular pelo cabo", ["pwsh", "-NoProfile", "-File", str(Path(__file__).with_name("antivirus-pc.ps1")), "-Celular"])

    def quarentena(self):
        itens = lista_quarentena(self.amb)
        if not itens:
            self.guarda("Quarentena", "quarentena")
            return
        e = self.escolhe("Quarentena: escolha um arquivo", [f"{Path(d['origem']).name}  ({d['ameaca']})" for d in itens] + ["Voltar"])
        if 0 <= e < len(itens) and self.confirma(f"Devolver {Path(itens[e]['origem']).name} ao lugar de origem? O guarda não vai mais acusar este mesmo conteúdo.",
                                                 "Sim, devolver", "Não, deixar isolado", sim_primeiro=False):
            self.guarda("Devolver", "devolver", itens[e]["id"])

    def liga_desliga(self):
        if vigia_viva():
            if self.confirma("Desligar? Arquivos novos ficam sem varredura até ligar de novo.", "Sim, desligar", "Não, manter ligada", sim_primeiro=False):
                self.roda("Desligar", ["powershell.exe", "-NoProfile", "-Command", "Stop-ScheduledTask -TaskName Guarda; 'Proteção em tempo real desligada.'"])
                Motor(self.amb).para_se_ocioso(ocioso=0)
        else:
            self.roda("Ligar", ["powershell.exe", "-NoProfile", "-Command", "Start-ScheduledTask -TaskName Guarda; Start-Sleep 3; 'Proteção em tempo real ligada.'"])

    def laco(self):
        acoes = [
            ("Ver a situação da proteção", lambda: self.guarda("Situação", "status")),
            ("Iniciar varredura completa do computador", self.varredura_completa),
            ("Outras varreduras: rápida, pasta, arquivo, celular", self.outras),
            ("Quarentena: ver e devolver", self.quarentena),
            ("Atualizar as assinaturas de vírus", lambda: self.guarda("Atualizando as assinaturas (alguns minutos)", "atualizar")),
            ("Conferir a rede e a VPN", lambda: self.guarda("Rede e VPN", "rede")),
            (None, self.liga_desliga),
            ("Testar a proteção (arquivo inofensivo)", lambda: self.guarda("Teste com arquivo inofensivo (até 4 min)", "provar")),
            ("Ver o registro", lambda: self.roda("Registro", [sys.executable, "-B", "-c",
                                                             f"import sys;sys.stdout.reconfigure(encoding='utf-8');print(open(r'{self.amb.registro}',encoding='utf-8',errors='replace').read()[-6000:])"])),
        ]
        while True:
            nomes = [n or ("Desligar a proteção em tempo real" if vigia_viva() else "Ligar a proteção em tempo real") for n, _ in acoes] + ["Sair"]
            e = self.escolhe("O que fazer?", nomes)
            if e < 0 or e == len(acoes):
                self.escreve(Z + LIMPA)
                return 0
            acoes[e][1]()


def liga_cores():
    """Windows: liga as cores ANSI e o UTF-8 no console (cmd e PowerShell antigos nao ligam sozinhos)."""
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        modo = ctypes.c_ulong()
        if k.GetConsoleMode(h, ctypes.byref(modo)):
            k.SetConsoleMode(h, modo.value | 0x0004)
        k.SetConsoleOutputCP(65001)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def principal(argv=None):
    p = argparse.ArgumentParser(description="Vigia de arquivos com o motor ClamAV.")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("status")
    sub.add_parser("vigiar")
    sub.add_parser("quarentena")
    sub.add_parser("provar")
    sub.add_parser("atualizar")
    sub.add_parser("menu")
    a = sub.add_parser("varrer")
    a.add_argument("arquivo")
    a = sub.add_parser("varredura")
    a.add_argument("pasta", nargs="?")
    a.add_argument("--tudo", action="store_true")
    a = sub.add_parser("devolver")
    a.add_argument("id")
    a = sub.add_parser("rede")
    a.add_argument("--aceitar", action="store_true")
    args = p.parse_args(argv)
    amb = Ambiente()
    if args.cmd == "vigiar":
        return vigiar(amb)
    if args.cmd == "menu":
        liga_cores()
        sys.stdout.write("\x1b[?25l")
        try:
            return Painel(amb).laco()
        except KeyboardInterrupt:
            return 0
        finally:
            sys.stdout.write("\x1b[?25h" + Z)
    if args.cmd == "varrer":
        return cmd_varrer(amb, args.arquivo)
    if args.cmd == "varredura":
        conta = varredura(amb, [Path(args.pasta)] if args.pasta else pastas_da_varredura(amb, args.tudo))
        return 1 if conta["infectado"] else 0
    if args.cmd == "quarentena":
        return cmd_quarentena(amb)
    if args.cmd == "provar":
        return cmd_provar(amb)
    if args.cmd == "atualizar":
        return 0 if atualiza(amb) else 1
    if args.cmd == "rede":
        return cmd_rede(amb, args.aceitar)
    if args.cmd == "devolver":
        try:
            print(f"Devolvido a {devolve(amb, args.id)}")
            return 0
        except ValueError as e:
            print(e)
            return 1
    return cmd_status(amb)


if __name__ == "__main__":
    sys.exit(principal())
