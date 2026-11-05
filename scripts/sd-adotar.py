#!/usr/bin/env python3
"""Formata o cartao SD como PORTATIL exFAT (APAGA O CARTAO). Sem --confirmo-apagar so faz as checagens.
Uso: python scripts/sd-adotar.py --modo public --uuid <UUID do cartao em sm list-volumes all> [--confirmo-apagar]
Travas: um unico disco removivel, tamanho > 400 GB com flag SD, bateria >= 3% e carregando (regra do Rafael, 29/10).
Os modos private e mixed (adotar) sao RECUSADOS: em 28/10/2026 a adocao corrompeu gravacoes grandes neste A12 (1.412 de 5.006 arquivos no md5) e a decisao e nao adotar de novo
(revisao de 02/11: ate entao so o texto proibia). Nunca rode com --confirmo-apagar sem o "sim" do Rafael na mensagem do dia (apaga o cartao inteiro);
depois de formatar rode scripts/teste-gravacao.py --alvo /storage/<UUID novo>."""
import argparse
import pathlib
import re
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
ADB = shutil.which("adb") or (str(pathlib.Path.home()) + r"\AppData\Local\Microsoft\WinGet\Packages"
                              r"\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe")


def sh(cmd, t=120):
    try:
        p = subprocess.run([ADB, "shell", cmd], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=t)
        return ((p.stdout or "") + (("\n[stderr] " + p.stderr.strip()) if p.stderr.strip() else "")).strip()
    except subprocess.TimeoutExpired:
        return "[timeout]"


def corta(s, n=12, c=170):
    return "\n".join(l[:c] for l in (s or "(vazio)").splitlines()[:n])


ap = argparse.ArgumentParser()
ap.add_argument("--modo", choices=["private", "public", "mixed"], required=True,
                help="public = portatil exFAT; private e mixed sao recusados (adotar corrompeu dados em 28/10)")
ap.add_argument("--razao", type=int, default=50, help="sem uso enquanto mixed for recusado")
ap.add_argument("--confirmo-apagar", action="store_true")
ap.add_argument("--uuid", required=True,
                help="UUID do cartao autorizado como aparece em 'sm list-volumes all' (ve-lo antes: ele e o alvo que sera apagado); "
                     "use '' para ignorar, p.ex. apos formatacao parcial")
a = ap.parse_args()
if a.modo != "public":
    sys.exit(f"ABORTADO: --modo {a.modo} (adotar o cartao) e proibido neste A12: corrompeu 1.412 arquivos em 28/10. So --modo public. Veja memoria/DECISOES.md.")

disks = sh("sm list-disks").split()
print("discos:", disks)
if len(disks) != 1:
    sys.exit("ABORTADO: esperava exatamente 1 disco removivel")
disco = disks[0]
if a.uuid and a.uuid not in sh("sm list-volumes all"):
    sys.exit(f"ABORTADO: o cartao com UUID {a.uuid} nao esta montado (outro cartao?)")
dm = sh(f"dumpsys mount | grep -A1 'DiskInfo{{{disco}}}'")
print(corta(dm, 3))
m = re.search(r"size=(\d+)", dm)
if not (m and int(m.group(1)) > 400_000_000_000 and "SD" in dm):
    sys.exit("ABORTADO: o disco nao parece o cartao SD de ~512 GB")
bat = sh("dumpsys battery | grep -E 'level|powered'")
nivel_m = re.search(r"level:\s*(\d+)", bat)
if not nivel_m:
    sys.exit("ABORTADO: nao consegui ler a bateria (aparelho offline?)")
nivel = int(nivel_m.group(1))
carregando = ("USB powered: true" in bat) or ("AC powered: true" in bat)
print(f"bateria {nivel}% carregando={carregando}")
if nivel < 3 or not carregando:
    sys.exit("ABORTADO: bateria abaixo de 3% ou sem carregar")
if not a.confirmo_apagar:
    sys.exit("SIMULACAO: checagens ok, nada foi alterado. Rode de novo com --confirmo-apagar (apaga o cartao).")

cmd = f"sm partition {disco} {a.modo}" + (f" {a.razao}" if a.modo == "mixed" else "")
print(f"\n>>> {cmd}")
t0 = time.time()
print("saida:", corta(sh(cmd, 540), 8), "| segundos:", int(time.time() - t0))
time.sleep(8)
vols = sh("sm list-volumes all")
print("\nvolumes:\n" + corta(vols))
print("\ndf:\n" + corta(sh("df -h | grep -E 'Filesystem|/data$|/storage|/mnt/expand|/mnt/media_rw'")))
print("\nprimario:", sh("sm get-primary-storage-uuid"), "| has-adoptable:", sh("sm has-adoptable"))
pub = [l for l in vols.splitlines() if l.startswith("public:") and "unmountable" not in l]
if not pub:
    sys.exit("FALHOU: nenhum volume public: montado depois do sm partition (erro, timeout ou cartao ainda sem montar); "
             "confira 'sm list-volumes all' antes de tratar o cartao como portatil")
print("volume portatil:", pub[0])
print("proximo passo: python scripts/teste-gravacao.py --alvo /storage/<UUID novo>")
