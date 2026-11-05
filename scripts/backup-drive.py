#!/usr/bin/env python3
"""Backup dos projetos do PC no Google Drive do Rafael, com o rclone. So COPIA: nada no Drive e apagado nem sobrescrito por pasta vazia.

Uso (no PC):
  python scripts\\backup-drive.py status          ultima rodada, cota do Drive e agenda (so leitura)
  python scripts\\backup-drive.py simular         mostra o que seria enviado, sem enviar
  python scripts\\backup-drive.py rodar           envia: primeiro os projetos, depois os jogos
  python scripts\\backup-drive.py conferir        compara PC e Drive arquivo a arquivo (--md5 le tudo e demora horas)
  python scripts\\backup-drive.py agendar         tarefa BackupDrive: todo dia as 03:00, ao entrar no Windows e depois de cada envio ao GitHub
  python scripts\\backup-drive.py tirar-agenda    tira a tarefa
  python scripts\\backup-drive.py filtros         mostra o que fica de fora

O que fica de fora: planilhas MAPAO (nome e nota de aluno), arquivos de segredo pelo nome (.env, chaves, acesso.json do AdGuard, rclone.conf)
e sobras do sistema. A chave de login do Google fica em %APPDATA%\\rclone\\rclone.conf, fora das pastas copiadas.
Parar uma rodada: crie diagnostico\\backup-drive\\PARAR; na proxima vez ela continua de onde parou. Decisoes e medidas: memoria/BACKUP-DRIVE.md.
Saida: 0 = ok; 1 = rodou com erro; 2 = nao deu para rodar.
"""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
RCLONE = os.environ.get("BACKUP_RCLONE", r"C:\Projetos\ferramentas\rclone\rclone.exe")
REMOTO = os.environ.get("BACKUP_REMOTO", "gdrive:")
DESTINO = "Backup-PC"
ORIGENS = [(r"C:\Projetos", "Projetos"), (r"C:\Android Embeeded", "Android Embeeded")]
TAREFA = "BackupDrive"
# Nome de arquivo basta aqui: a varredura por conteudo de 03/11 achou segredo so em acesso.json (memoria/BACKUP-DRIVE.md).
FORA_SEMPRE = [  # sem "/" no comeco: vale em qualquer nivel (regra do rclone); testado de verdade em 03/11
    "*MAPAO*", "*mapao*", "*Mapao*", "*MAPÃO*", "*mapão*", "*Mapão*",
    ".env", ".env.*", "*.pem", "*.key", "*.pfx", "*.p12", "*.kdbx",
    "id_rsa*", "id_ed25519*", "a12_termux*", "rclone.conf", ".claude.json",
    "/adguard-home/**",
    "~$*", "Thumbs.db", "desktop.ini", "*.tmp", "__pycache__/**",
    "diagnostico/backup-drive/**",  # o registro da propria rodada muda durante a copia: dava "corrupted on transfer" a cada rodada (04/11)
    "diagnostico/pytest-lib/**",  # biblioteca dos testes, sem leitura para o rclone: em 04/11 fez a medida falhar e os jogos nao foram
]
JOGOS = ["/Criador De Apps Pedagógicos/arena-console/jogos/**"]  # 149 GB: vao por ultimo, para os projetos nao esperarem por eles
PROIBIDOS_NO_RCLONE = {"sync", "move", "moveto", "delete", "deletefile", "purge", "rmdir", "rmdirs", "dedupe", "cleanup"}


class Erro(Exception):
    pass


def pasta_estado():
    p = RAIZ / "diagnostico" / "backup-drive"
    p.mkdir(parents=True, exist_ok=True)
    return p


def filtros(sem_jogos=False):
    return ["- " + x for x in FORA_SEMPRE + (JOGOS if sem_jogos else [])]


def comando_copia(origem, destino, arq_filtro, log, simular=False, banda=None):
    """A unica forma de enviar. copy nunca apaga no destino."""
    cmd = [RCLONE, "copy", origem, destino, "--filter-from", arq_filtro, "--skip-links", "--transfers", "3", "--checkers", "8",
           "--drive-chunk-size", "64M", "--drive-stop-on-upload-limit", "--retries", "3", "--low-level-retries", "10",
           "--log-file", log, "--log-level", "INFO", "--stats", "60s", "--stats-one-line"]
    if simular:
        cmd.append("--dry-run")
    if banda:
        cmd += ["--bwlimit", banda]
    return cmd


def confere_seguro(cmd):
    if cmd[1] in PROIBIDOS_NO_RCLONE or any(x.startswith("--delete") or x == "--backup-dir" for x in cmd):
        raise Erro("comando recusado, poderia apagar no Drive: " + cmd[1])
    return cmd


def roda(cmd, **kw):
    """Roda o rclone. Separado para os testes trocarem."""
    if os.name == "nt":  # a tarefa roda com pythonw: sem isto, cada rclone abriria uma janela preta na tela do Rafael
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(confere_seguro(cmd), capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def cota():
    r = roda([RCLONE, "about", REMOTO, "--json"], timeout=120)
    if r.returncode != 0:
        raise Erro("o Drive nao respondeu (login vencido? rode: rclone config reconnect gdrive:): " + r.stderr.strip()[-200:])
    return json.loads(r.stdout)


def tamanho(alvo, arq_filtro=None):
    cmd = [RCLONE, "size", alvo, "--json", "--skip-links"] + (["--filter-from", arq_filtro] if arq_filtro else [])
    r = roda(cmd, timeout=3600)
    if r.returncode != 0:
        if "directory not found" in r.stderr.lower():
            return {"bytes": 0, "count": 0}
        raise Erro("nao consegui medir " + alvo + ": " + r.stderr.strip()[-200:])
    return json.loads(r.stdout)


def ja_rodando(trava):
    """Outra rodada viva? Trava de processo morto nao segura ninguem."""
    if not trava.exists():
        return False
    try:
        pid = int(trava.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return False
    if pid == os.getpid():
        return False
    if os.name == "nt":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, errors="replace")
        return str(pid) in r.stdout
    return pathlib.Path(f"/proc/{pid}").exists()


def escreve_filtro(pasta, sem_jogos):
    f = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", dir=pasta, delete=False, newline="\n")
    f.write("\n".join(filtros(sem_jogos)) + "\n")
    f.close()
    return f.name


def grava_estado(pasta, **campos):
    arq = pasta / "estado.json"
    atual = {}
    if arq.exists():
        try:
            atual = json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            atual = {}
    atual.update(campos)
    tmp = arq.with_suffix(".tmp")
    tmp.write_text(json.dumps(atual, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, arq)


def agora():
    return datetime.datetime.now().strftime("%d/%m/%Y %H:%M")


def rodar(simular=False, banda=None):
    pasta = pasta_estado()
    if (pasta / "PARAR").exists():
        print("Existe o arquivo PARAR em", pasta, "- nada foi enviado. Apague-o para voltar.")
        return 0
    trava = pasta / "rodando.lock"
    if ja_rodando(trava):
        print("Ja ha uma rodada em andamento. Nada a fazer.")
        return 0
    if not pathlib.Path(RCLONE).exists():
        raise Erro("nao encontrei o rclone em " + RCLONE)
    trava.write_text(str(os.getpid()), encoding="ascii")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log = str(pasta / f"rodada-{stamp}.log")
    leve = escreve_filtro(pasta, True)
    tudo = escreve_filtro(pasta, False)
    try:
        c = cota()
        livre = c.get("free")
        erros = 0
        grava_estado(pasta, inicio=agora(), fim=None, codigo=None, erro=None, simulado=simular, log=log)
        for rotulo, arq_filtro in (("projetos", leve), ("jogos e o resto", tudo)):
            if (pasta / "PARAR").exists():
                print("PARAR encontrado: fica para a proxima rodada.")
                break
            if rotulo != "projetos" and livre is not None and not simular:
                local = sum(tamanho(o, arq_filtro)["bytes"] for o, _d in ORIGENS)
                la = tamanho(f"{REMOTO}{DESTINO}")["bytes"]
                falta = max(0, local - la)
                atual = cota().get("free", livre)
                if falta > atual:
                    print(f"Nao cabe: faltam {falta // 1024**3} GB e o Drive tem {atual // 1024**3} GB livres. Os projetos foram; os jogos nao.")
                    erros += 1
                    break
            for origem, nome in ORIGENS:
                if not pathlib.Path(origem).exists():
                    print("Nao existe, pulei:", origem)
                    continue
                print(f"{rotulo}: {origem}")
                r = roda(comando_copia(origem, f"{REMOTO}{DESTINO}/{nome}", arq_filtro, log, simular, banda))
                if r.returncode != 0:
                    erros += 1
                    print(f"  o rclone terminou com o codigo {r.returncode} (detalhe em {log})")
        grava_estado(pasta, fim=agora(), codigo=1 if erros else 0)
        print("Rodada terminada" + (f" com {erros} erro(s). Uma nova rodada continua de onde parou." if erros else " sem erro."), "Registro:", log)
        return 1 if erros else 0
    except Erro as e:
        grava_estado(pasta, fim=agora(), codigo=2, erro=str(e)[:300])  # na tarefa nao ha tela: sem isto a rodada parecia nao ter terminado
        raise
    finally:
        for f in (leve, tudo):
            pathlib.Path(f).unlink(missing_ok=True)
        trava.unlink(missing_ok=True)


def conferir(md5=False):
    pasta = pasta_estado()
    arq = escreve_filtro(pasta, False)
    falhas = 0
    try:
        for origem, nome in ORIGENS:
            cmd = [RCLONE, "check", origem, f"{REMOTO}{DESTINO}/{nome}", "--one-way", "--skip-links", "--filter-from", arq, "--checkers", "8"]
            if not md5:
                cmd.append("--size-only")
            r = roda(cmd)
            print(origem, "=>", (r.stderr.strip().splitlines() or ["(sem saida)"])[-1][:170])
            falhas += 1 if r.returncode else 0
    finally:
        pathlib.Path(arq).unlink(missing_ok=True)
    print("PC e Drive conferem." if not falhas else "Ha diferencas: uma nova rodada envia o que falta.")
    return 1 if falhas else 0


def status():
    pasta = pasta_estado()
    arq = pasta / "estado.json"
    print("Ultima rodada:", arq.read_text(encoding="utf-8") if arq.exists() else "nenhuma")
    print("Rodando agora:", "sim" if ja_rodando(pasta / "rodando.lock") else "nao")
    print("PARAR:", "sim" if (pasta / "PARAR").exists() else "nao")
    c = cota()
    print(f"Drive: {c.get('used', 0) // 1024**3} GB usados, {c.get('free', 0) // 1024**3} GB livres de {c.get('total', 0) // 1024**3} GB")
    return 0


def executavel_sem_janela():
    p = pathlib.Path(sys.executable)
    w = p.with_name("pythonw.exe")
    return str(w if w.exists() else p)


def agendar():
    script = str(pathlib.Path(__file__).resolve())
    texto = f"""
$a = New-ScheduledTaskAction -Execute '{executavel_sem_janela()}' -Argument '"{script}" rodar'
$t = @((New-ScheduledTaskTrigger -Daily -At 03:00), (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME))
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Days 3) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName '{TAREFA}' -Action $a -Trigger $t -Settings $s -Principal $p -Force | Out-Null
(Get-ScheduledTask -TaskName '{TAREFA}').State
"""
    r = subprocess.run(["pwsh", "-NoProfile", "-Command", texto], capture_output=True, text=True, errors="replace")
    print((r.stdout + r.stderr).strip()[-300:])
    return 0 if r.returncode == 0 else 1


def tirar_agenda():
    r = subprocess.run(["pwsh", "-NoProfile", "-Command", f"Unregister-ScheduledTask -TaskName '{TAREFA}' -Confirm:$false"], capture_output=True, text=True, errors="replace")
    print("Tarefa tirada." if r.returncode == 0 else r.stderr.strip()[-200:])
    return r.returncode and 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Backup dos projetos no Google Drive (so copia, nunca apaga no Drive).")
    ap.add_argument("acao", choices=["status", "simular", "rodar", "conferir", "agendar", "tirar-agenda", "filtros"])
    ap.add_argument("--banda", help="limite de envio do rclone, por exemplo 2M ou '06:00,2M 23:00,off'")
    ap.add_argument("--md5", action="store_true", help="conferir: compara o conteudo, lendo os 175 GB")
    a = ap.parse_args(argv)
    try:
        if a.acao == "status":
            return status()
        if a.acao == "simular":
            return rodar(simular=True, banda=a.banda)
        if a.acao == "rodar":
            return rodar(banda=a.banda)
        if a.acao == "conferir":
            return conferir(a.md5)
        if a.acao == "agendar":
            return agendar()
        if a.acao == "tirar-agenda":
            return tirar_agenda()
        print("\n".join(filtros()))
        return 0
    except Erro as e:
        print("ABORTADO:", e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
