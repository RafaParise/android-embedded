#!/usr/bin/env python3
"""Poe no guia memoria/GUIA-IA-NO-CELULAR.md o texto ATUAL de scripts/celular-kit/bin/ia, no bloco que o Rafael cola no Termux
(`cat > ~/bin/ia <<'FIM_DO_IA'` ... `FIM_DO_IA`). Rode depois de QUALQUER mudanca no `ia`: o teste
test_guia_traz_exatamente_o_script_para_colar falha se o guia ficar para tras.

  python scripts/gerar-guia-ia.py          atualiza o guia
  python scripts/gerar-guia-ia.py --ver    so diz se o guia esta em dia (saida 0 = em dia, 1 = desatualizado)

Le e grava BYTES: o Python no Windows trocaria LF por CRLF e o bloco colado no Termux quebraria.
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "celular-kit" / "bin" / "ia"
GUIA = RAIZ / "memoria" / "GUIA-IA-NO-CELULAR.md"
BLOCO = re.compile(r"(cat > ~/bin/ia <<'FIM_DO_IA'\n)(.*?)(\nFIM_DO_IA\n)", re.S)


def main():
    script = SCRIPT.read_bytes().decode("ascii")  # tem que ser ASCII puro (colagem no terminal)
    if "\r" in script:
        sys.exit("ERRO: o script tem CR (CRLF); converta para LF antes.")
    guia = GUIA.read_bytes().decode("utf-8")
    if not BLOCO.search(guia):
        sys.exit("ERRO: nao achei o bloco `cat > ~/bin/ia <<'FIM_DO_IA' ... FIM_DO_IA` no guia.")
    novo = BLOCO.sub(lambda m: m.group(1) + script.rstrip("\n") + m.group(3), guia, count=1)
    if "--ver" in sys.argv:
        print("guia em dia" if novo == guia else "guia DESATUALIZADO (rode: python scripts/gerar-guia-ia.py)")
        sys.exit(0 if novo == guia else 1)
    if novo == guia:
        print("guia ja estava em dia")
        return
    GUIA.write_bytes(novo.encode("utf-8"))
    print(f"guia atualizado: {GUIA}")


if __name__ == "__main__":
    main()
