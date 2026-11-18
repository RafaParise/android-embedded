#!/usr/bin/env python3
"""Mensagens de status do Univo: espelha o catalogo e a logica da casa-mae no Hermes do PC (18/11/2026).

Fonte (edite SO aqui):  scripts/celular-kit/status/frases-status.json  (frases e palavras-chave)
                        scripts/celular-kit/status/status_univo.py     (logica; espelho JS: status_univo.cjs)
Destinos no univo-windows (C:\\Projetos\\univo-windows; pula se o projeto nao estiver nesta maquina):
  hermes/plugins/univo-status/status_univo.py e frases-status.json   (copias identicas)
  hermes/skins/univo.yaml                                             (gerada: as mesmas frases no spinner padrao)
O celular recebe os 3 arquivos pelo instalador do kit (ponte-pc.py), direto da fonte.

Uso: python scripts/status_sync.py conferir      (saida 0 = tudo igual a fonte; 1 = algum destino diferente)
     python scripts/status_sync.py sincronizar   (valida o catalogo, reescreve o que mudou e mostra o que foi)
     --windows CAMINHO troca a pasta do univo-windows procurada.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FONTE = RAIZ / "scripts" / "celular-kit" / "status"
WINDOWS_PADRAO = (Path(r"C:\Projetos\univo-windows"), Path("/mnt/c/Projetos/univo-windows"))


def _logica():
    spec = importlib.util.spec_from_file_location("status_univo_fonte", FONTE / "status_univo.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def destinos(windows: Path) -> dict[Path, bytes]:
    su = _logica()
    plugin = windows / "hermes" / "plugins" / "univo-status"
    return {
        plugin / "status_univo.py": (FONTE / "status_univo.py").read_bytes(),
        plugin / "frases-status.json": (FONTE / "frases-status.json").read_bytes(),
        windows / "hermes" / "skins" / "univo.yaml": su.hermes_skin(su.carregar(FONTE / "frases-status.json")).encode("utf-8"),
    }


def processa(gravar: bool, windows: Path | None = None) -> list[str]:
    """Os destinos diferentes da fonte (e, com gravar, ja reescritos). Catalogo invalido: SystemExit."""
    erros = _logica().validar()
    if erros:
        raise SystemExit("catalogo invalido (nada foi copiado):\n" + "\n".join(erros))
    windows = windows or next((p for p in WINDOWS_PADRAO if p.is_dir()), None)
    if windows is None:
        return []
    mudou = []
    for alvo, dados in destinos(windows).items():
        if not alvo.is_file() or alvo.read_bytes() != dados:
            mudou.append(str(alvo))
            if gravar:
                alvo.parent.mkdir(parents=True, exist_ok=True)
                alvo.write_bytes(dados)
    return mudou


def principal(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("acao", choices=("conferir", "sincronizar"))
    ap.add_argument("--windows")
    a = ap.parse_args(argv)
    mudou = processa(a.acao == "sincronizar", Path(a.windows) if a.windows else None)
    if a.acao == "conferir":
        print("status: tudo igual a fonte" if not mudou else "status FORA de sincronia:\n  " + "\n  ".join(mudou))
        return 1 if mudou else 0
    print("status: nada a mudar" if not mudou else "status reescrito:\n  " + "\n  ".join(mudou))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
