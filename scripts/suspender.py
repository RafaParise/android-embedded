#!/usr/bin/env python3
"""Suspende (pm suspend/unsuspend) apps que o Rafael usa de vez em quando, sem desativar: o app para
de gastar fundo/RAM enquanto suspenso (fica com o icone acinzentado, nao abre), mas volta exatamente
como estava ao desuspender -- nao perde estado, nao precisa reinstalar nem reconfigurar. Mais forte que
appops RUN_IN_BACKGROUND (que so bloqueia 2o plano, o app ainda abre normal) e mais leve que
pm disable-user (que exige reativar manualmente e pode pedir verificacao de novo em alguns apps).

Pedido do Rafael, 30/10 ("otimizacao quase nivel de kernel sem root"): "pm suspend"/"pm unsuspend" sao
comandos PUBLICOS do Android (PackageManager.setPackagesSuspended, usados por apps de controle parental/MDM
de verdade) -- nao e truque, nao precisa de app como o Shizuku pra isso: o ADB deste projeto ja fala com
o shell, que ja tem a permissao.

Reusa a lista PROTEGIDOS de lote-pacotes.py: nunca suspende nada da lista "nunca desativar" do CLAUDE.md.
O proprio Android tambem recusa suspender o launcher atual, o teclado/IME ativo, o instalador/verificador
de pacotes e apps com device admin -- isso nao depende do script, e uma trava do PROPRIO SO.
--aplicar/--restaurar sempre tentam pm suspend/unsuspend nos pacotes dados: repetir e seguro.

CONFIRMADO NO APARELHO (Claude local, 30/10, A12 com Android 12, app Teams): "pm suspend <pkg>" responde
"Package <pkg> new suspended state: true"; "dumpsys package <pkg>" traz "User 0: ... suspended=true ..." (e, com o
pacote suspenso, "suspendingPackage=com.android.shell"); "pm unsuspend" volta a "suspended=false". O regex de
esta_suspenso() bate nos dois estados (teste: test_esta_suspenso_le_a_linha_real_do_dumpsys_do_android_12).
Ao tentar ABRIR o app suspenso (31/10, mesmo aparelho): abre a SuspendedAppActivity do Android com "O app nao esta
disponivel / O app Teams nao esta disponivel no momento. Isso e gerenciado pelo app Shell." e um botao OK; o app nao abre.

  python scripts/suspender.py <pacote> [<pacote> ...]              mostra o estado (leitura)
  python scripts/suspender.py <pacote> [<pacote> ...] --aplicar     suspende os pacotes dados
  python scripts/suspender.py <pacote> [<pacote> ...] --restaurar   desuspende os pacotes dados
"""
import argparse
import importlib.util
import pathlib
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def sh(cmd, timeout=60):
    r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def protegidos():
    spec = importlib.util.spec_from_file_location("lote_pacotes", RAIZ / "scripts" / "lote-pacotes.py")
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return [re.compile(x, re.I) for x in mod.PROTEGIDOS]


def em_uso_no_aparelho():
    """Teclado em uso e donos dos papeis telefone, SMS e tela inicial, lidos do aparelho (a lista
    PROTEGIDOS nao casa com helium314.keyboard nem com org.fossify.phone, por exemplo)."""
    nomes = set()
    ime = sh("settings get secure default_input_method").split("/", 1)[0].strip()
    nomes.add(ime)
    for papel in ("DIALER", "SMS", "HOME"):
        nomes.update(sh(f"cmd role get-role-holders --user 0 android.app.role.{papel}").split())
    return {n for n in nomes if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+", n)}


def instalados():
    return {l.split(":", 1)[1].strip() for l in sh("pm list packages").splitlines() if l.startswith("package:")}


def esta_suspenso(pkg):
    """Le o "suspended=true" do dumpsys (confirmado neste Android em 30/10, ver docstring do modulo)."""
    saida = sh(f"dumpsys package {pkg}")
    return bool(re.search(r"\bsuspended\s*=\s*true\b", saida, re.I))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pacotes", nargs="+")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--restaurar", action="store_true")
    a = ap.parse_args()
    if a.aplicar and a.restaurar:
        sys.exit("ABORTADO: use --aplicar ou --restaurar, nao os dois")

    # o nome vai direto para o shell do aparelho (pm suspend {p}, dumpsys package {p}): so nome de pacote de verdade
    invalidos = [p for p in a.pacotes if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+", p)]
    if invalidos:
        sys.exit("ABORTADO: nome de pacote invalido (so letras, numeros, _ e pontos): " + ", ".join(invalidos))

    prot = protegidos()
    ruins = [p for p in a.pacotes if any(r.search(p) for r in prot)]
    if ruins:
        sys.exit("ABORTADO: pacote protegido (lista de lote-pacotes.py, nunca desativar/suspender): " + ", ".join(ruins))

    if "SM-A125" not in sh("getprop ro.product.model"):
        sys.exit("ABORTADO: aparelho nao encontrado ou inesperado")

    antes = {p: esta_suspenso(p) for p in a.pacotes}
    print("estado atual:")
    for p, s in antes.items():
        print(f"  {'suspenso' if s else 'normal  '} {p}")

    if not (a.aplicar or a.restaurar):
        print("SIMULACAO: nada foi alterado. Use --aplicar ou --restaurar.")
        return

    ausentes = [p for p in a.pacotes if p not in instalados()]
    if ausentes:
        sys.exit("ABORTADO: pacote nao instalado (erro de digitacao?): " + ", ".join(ausentes))
    if a.aplicar:
        em_uso = em_uso_no_aparelho()
        ruins = [p for p in a.pacotes if p in em_uso]
        if ruins:
            sys.exit("ABORTADO: teclado em uso ou app padrao de telefone/SMS/tela inicial (nunca suspender): " + ", ".join(ruins))

    verbo = "unsuspend" if a.restaurar else "suspend"
    for p in a.pacotes:
        saida = sh(f"pm {verbo} {p}")
        print(f"  pm {verbo} {p}: {saida[:160]}")

    depois = {p: esta_suspenso(p) for p in a.pacotes}
    alvo = not a.restaurar
    falhas = [p for p in a.pacotes if depois[p] != alvo]
    print(f"RESULTADO: {len(a.pacotes) - len(falhas)} ok, {len(falhas)} falhou" + (": " + ", ".join(falhas) if falhas else ""))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
