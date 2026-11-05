#!/usr/bin/env python3
"""Testa se uma gravacao no celular chega INTEIRA ao disco (a conferencia de md5 logo apos gravar NAO prova nada).
O cache de paginas do Linux guarda o dado recem-gravado na RAM; se a midia corromper a gravacao, o erro so aparece depois que o
cache e descartado. O teste grava dados aleatorios no alvo e numa copia de controle na memoria interna (/data/local/tmp), confere
na hora, forca o descarte do cache lendo varios GB de /system, /vendor e /product (nao toca no alvo) e confere de novo.
Foi o que revelou, em 28/10, que o cartao ADOTADO corrompe gravacoes grandes neste A12 (interna OK). Apaga tudo no fim.

  python scripts/teste-gravacao.py                            alvo = armazenamento principal (/storage/emulated/0)
  python scripts/teste-gravacao.py --alvo /storage/5E6F-7A8B  alvo = cartao portatil
  python scripts/teste-gravacao.py --mb 128                   tamanho do arquivo de teste (padrao 64)

Saida 0 = alvo integro | 1 = alvo CORROMPIDO no disco | 2 = nao foi possivel testar (controle diferente, sem ADB, alvo ausente).
So leitura e escrita de um arquivo temporario; nao altera ajustes. Rode com o celular carregando (a leitura dura alguns minutos).
"""
import argparse
import hashlib
import os
import pathlib
import subprocess
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

PASTA_TESTE = ".teste-gravacao"
CONTROLE = "/data/local/tmp/teste-gravacao-controle.bin"


def adb(args, timeout=300):
    r = subprocess.run(["adb"] + args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).replace("\r", "").strip()


def md5_celular(caminho):
    partes = adb(["shell", f"md5sum '{caminho}' 2>&1"], timeout=600).split()
    return partes[0] if partes and len(partes[0]) == 32 else "ERRO"


def executa(a):
    destino = f"{a.alvo.rstrip('/')}/{PASTA_TESTE}/teste.bin"
    # confere o alvo ANTES de criar qualquer coisa: mkdir -p criaria um alvo digitado errado (ex.: /sdcard/<UUID>) e aprovaria a midia errada
    if "No such" in adb(["shell", f"ls -d '{a.alvo}' 2>&1"]):
        print(f"Alvo inexistente: {a.alvo}")
        return 2
    adb(["shell", f"mkdir '{a.alvo.rstrip('/')}/{PASTA_TESTE}' 2>&1"])

    dados = os.urandom(a.mb << 20)
    esperado = hashlib.md5(dados).hexdigest()
    with tempfile.TemporaryDirectory() as d:
        arq = pathlib.Path(d) / "teste.bin"
        arq.write_bytes(dados)
        adb(["push", str(arq), destino], timeout=900)
        adb(["push", str(arq), CONTROLE], timeout=900)
    h_alvo, h_controle = md5_celular(destino), md5_celular(CONTROLE)
    if "ERRO" in (h_alvo, h_controle):  # sem isto, alvo cheio ou so de leitura apareceria como "corrompido" (saida 1), e o certo e "nao deu para testar"
        print(f"Nao consegui gravar o arquivo de teste (alvo {'ERRO' if h_alvo == 'ERRO' else 'ok'} | controle {'ERRO' if h_controle == 'ERRO' else 'ok'}): cheio, so de leitura ou sem permissao?")
        return 2
    print(f"logo apos gravar (pode vir do cache):   alvo {'OK' if h_alvo == esperado else 'DIFERENTE'} | controle {'OK' if h_controle == esperado else 'DIFERENTE'}")

    adb(["shell", "sync"])
    t0 = time.time()
    adb(["shell", "find /system /vendor /product /system_ext -type f -size +512k -exec cat {} + > /dev/null 2>&1; echo feito"],
        timeout=1800)
    print(f"cache forcado a girar: {time.time() - t0:.0f} s de leitura de outras areas")

    h_alvo2, h_controle2 = md5_celular(destino), md5_celular(CONTROLE)
    if h_alvo2 == "ERRO":  # cartao desmontado no meio do teste nao e corrupcao: nao deu para ler
        print("Nao foi possivel ler o alvo depois de descartar o cache (desmontado, removido ou sem permissao?): o teste nao vale.")
        return 2
    alvo_ok = h_alvo2 == esperado
    controle_ok = h_controle2 == esperado
    print(f"depois de descartar o cache (le do disco): alvo {'OK' if alvo_ok else 'DIFERENTE (CORROMPIDO NO DISCO)'} | "
          f"controle {'OK' if controle_ok else 'DIFERENTE'}")
    if not controle_ok:
        print("O controle (memoria interna) tambem falhou: o teste nao vale. Repita com o celular carregando e sem outro uso do ADB.")
        return 2
    return 0 if alvo_ok else 1


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--alvo", default="/storage/emulated/0", help="volume a testar (padrao: armazenamento principal)")
    ap.add_argument("--mb", type=int, default=64, help="tamanho do arquivo de teste em MB")
    a = ap.parse_args()

    if not adb(["get-state"]).startswith("device"):
        print("Sem celular no ADB.")
        return 2
    if a.mb < 1:
        print("--mb precisa ser 1 ou mais.")
        return 2
    try:
        return executa(a)
    except subprocess.TimeoutExpired as e:
        print(f"O celular nao respondeu a tempo ({str(e.cmd)[:80]}): o teste nao vale.")
        return 2
    finally:  # em qualquer saida: nao deixa 64 MB esquecidos no aparelho
        pasta = f"{a.alvo.rstrip('/')}/{PASTA_TESTE}"
        try:
            adb(["shell", f"rm -rf '{pasta}' '{CONTROLE}'"])
            # adb() nao olha o codigo de saida (cabo solto responde 'no devices'): confere que os dois sumiram
            restou = adb(["shell", f"ls -d '{pasta}' '{CONTROLE}' 2>&1"]).count("No such") < 2
        except subprocess.TimeoutExpired:
            restou = True
        if restou:
            print(f"Nao consegui apagar os arquivos de teste: {pasta} e {CONTROLE}")


if __name__ == "__main__":
    sys.exit(main())
