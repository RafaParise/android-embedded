#!/usr/bin/env python3
"""Persona do Univo: uma fonte só para o celular e o PC (17/11/2026).

Fonte (edite SÓ aqui):
  scripts/celular-kit/persona/UNIVO-PERSONA.md          completa: Qwen Code e OpenCode (QWEN.md) e Hermes (SOUL.md)
  scripts/celular-kit/persona/UNIVO-PERSONA-COMPACTA.txt compacta: modelos locais pequenos (ia chat) e pergunta avulsa (ia qwen)

Destinos (o bloco entre os marcadores é reescrito; o resto do arquivo fica como está):
  scripts/celular-kit/QWEN.md                 <!-- UNIVO-PERSONA:INICIO ... --> ... <!-- UNIVO-PERSONA:FIM -->
  C:\\Projetos\\univo-windows\\hermes\\SOUL.md    os mesmos marcadores (pula se o projeto não estiver nesta máquina)
  scripts/celular-kit/bin/ia                  # UNIVO-PERSONA-COMPACTA:INICIO ... # UNIVO-PERSONA-COMPACTA:FIM

Uso: python scripts/persona.py conferir      (saída 0 = tudo igual à fonte; 1 = algum destino diferente)
     python scripts/persona.py sincronizar   (reescreve os blocos que mudaram e mostra quais)
     --soul CAMINHO troca o SOUL.md procurado.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
KIT = RAIZ / "scripts" / "celular-kit"
FONTE = KIT / "persona" / "UNIVO-PERSONA.md"
FONTE_COMPACTA = KIT / "persona" / "UNIVO-PERSONA-COMPACTA.txt"
SOUL_PADRAO = (Path(r"C:\Projetos\univo-windows\hermes\SOUL.md"), Path("/mnt/c/Projetos/univo-windows/hermes/SOUL.md"))

INICIO = ("<!-- UNIVO-PERSONA:INICIO (fonte: scripts/celular-kit/persona/UNIVO-PERSONA.md da casa-mãe "
          "C:\\Android Embeeded; mude lá e rode: python scripts\\persona.py sincronizar) -->")
FIM = "<!-- UNIVO-PERSONA:FIM -->"
INICIO_C = ("# UNIVO-PERSONA-COMPACTA:INICIO (fonte: scripts/celular-kit/persona/UNIVO-PERSONA-COMPACTA.txt; "
            "mude la e rode: python scripts/persona.py sincronizar)")
FIM_C = "# UNIVO-PERSONA-COMPACTA:FIM"

_RE_MD = re.compile(r"<!-- UNIVO-PERSONA:INICIO[^\n]*-->\r?\n.*?\n<!-- UNIVO-PERSONA:FIM -->", re.S)   # aceita CRLF
_RE_SH = re.compile(r"# UNIVO-PERSONA-COMPACTA:INICIO[^\n]*\n.*?\n# UNIVO-PERSONA-COMPACTA:FIM", re.S)


def _ler(p: Path) -> str:
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


def bloco_completo() -> str:
    return f"{INICIO}\n{_ler(FONTE).replace(chr(13), '').strip()}\n{FIM}"


def compacta() -> str:
    texto = " ".join(_ler(FONTE_COMPACTA).split())
    if "'" in texto:   # vai entre aspas simples no bash
        raise ValueError("a persona compacta não pode ter aspas simples (vai dentro de '...' no bin/ia)")
    if len(texto) > 1200:   # o 0,5B/1,5B do celular roda com 4096 tokens e ainda leva o resumo da memória
        raise ValueError(f"a persona compacta passou de 1200 caracteres ({len(texto)}): o modelo pequeno não aguenta")
    return texto


def bloco_compacto() -> str:
    return f"{INICIO_C}\nPERSONA_COMPACTA='{compacta()}'\n{FIM_C}"


def destinos(soul: Path | None) -> list[tuple[Path, re.Pattern, str]]:
    lista = [(KIT / "QWEN.md", _RE_MD, bloco_completo()), (KIT / "bin" / "ia", _RE_SH, bloco_compacto())]
    candidatos = (soul,) if soul else SOUL_PADRAO
    achado = next((c for c in candidatos if c and c.is_file()), None)
    if achado:
        lista.append((achado, _RE_MD, bloco_completo()))
    return lista


def processa(gravar: bool, soul: Path | None = None) -> list[str]:
    """Devolve a lista de problemas (vazia = tudo igual à fonte depois da chamada)."""
    problemas = []
    for arq, padrao, bloco in destinos(soul):
        texto = _ler(arq)
        achados = padrao.findall(texto)
        if len(achados) != 1:
            problemas.append(f"{arq}: esperava 1 bloco da persona, achei {len(achados)} (ponha os marcadores à mão)")
            continue
        crlf = "\r\n" in texto
        alvo = bloco.replace("\n", "\r\n") if crlf else bloco
        if achados[0] == alvo:
            continue
        if not gravar:
            problemas.append(f"{arq}: a persona está diferente da fonte (rode: python scripts/persona.py sincronizar)")
            continue
        novo = padrao.sub(lambda _: alvo, texto)
        tmp = arq.with_name(arq.name + ".persona-novo")
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(novo)
        try:
            os.chmod(tmp, os.stat(arq).st_mode)
        except OSError:
            pass
        os.replace(tmp, arq)
        print(f"  [ok] persona atualizada: {arq}")
    return problemas


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Persona do Univo: conferir ou sincronizar os destinos com a fonte única.")
    ap.add_argument("acao", nargs="?", default="conferir", choices=["conferir", "sincronizar"])
    ap.add_argument("--soul", type=Path, help="SOUL.md do univo-windows (padrão: C:\\Projetos\\univo-windows\\hermes\\SOUL.md)")
    a = ap.parse_args(argv)
    for fluxo in (sys.stdout, sys.stderr):   # o console do Windows (cp1252) estragava o "à"
        reconf = getattr(fluxo, "reconfigure", None)
        if reconf:
            try:
                reconf(encoding="utf-8")
            except ValueError:
                pass
    try:
        problemas = processa(a.acao == "sincronizar", a.soul)
    except (OSError, ValueError) as e:
        print(f"Persona: {e}", file=sys.stderr)
        return 2
    for p in problemas:
        print("  [--] " + p, file=sys.stderr)
    if not problemas:
        print(f"Persona do Univo: {len(destinos(a.soul))} destino(s) iguais à fonte.")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
