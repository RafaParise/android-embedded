"""Constantes e funcoes comuns dos scripts desta pasta (Overture Maps Places -> listas KML do Organic Maps).
Nao e executado sozinho. Com `python -I` o Python NAO poe a pasta do script no sys.path (-I implica -P), entao cada
script insere EXPLICITAMENTE a propria pasta (a pasta \\scripts, que e codigo nosso) antes de `import comum`.
Os dados baixados ficam em outra pasta (dados-overture) e nunca entram no sys.path."""
import hashlib
import json
import pathlib
import sys

# ---------------------------------------------------------------------------------------------
# Regioes (lon_min, lat_min, lon_max, lat_max)
# ---------------------------------------------------------------------------------------------
# Definicao da tarefa (usada para a contagem "literal" da regiao):
BBOX_BAIXADA_LITERAL = (-47.15, -24.45, -45.85, -23.55)
BBOX_CAPITAL_LITERAL = (-46.83, -24.02, -46.36, -23.36)
# Baixada: o bbox literal CORTA a ponta leste de Bertioga (municipio vai ate lon -45,794) e as ilhas de Itanhaem (lat -24,49);
# a capital passa 0,003 grau (330 m) do ymax literal. Por isso baixamos um SUPERCONJUNTO e depois recortamos por poligono do IBGE.
BBOX_BAIXADA_BAIXAR = (-47.15, -24.50, -45.78, -23.55)
BBOX_CAPITAL_BAIXAR = (-46.83, -24.02, -46.36, -23.35)

BAIXADA_MUNICIPIOS = ["Bertioga", "Cubatão", "Guarujá", "Itanhaém", "Mongaguá", "Peruíbe", "Praia Grande", "Santos", "São Vicente"]
CAPITAL_MUNICIPIO = "São Paulo"
PRACA_DA_SE = (-23.5505, -46.6333)  # (lat, lon)

S3_REGIAO = "us-west-2"


def glob_places(release: str) -> str:
    return f"s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*.parquet"


def abre_duckdb(spatial: bool = False, threads: int | None = None):
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"SET s3_region='{S3_REGIAO}'; SET s3_url_style='path';")
    if spatial:
        con.execute("INSTALL spatial; LOAD spatial;")
    if threads:
        con.execute(f"SET threads={int(threads)};")
    return con


def sha256_arquivo(caminho: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def le_release(pasta_dados: pathlib.Path) -> str:
    return json.loads((pasta_dados / "release.json").read_text(encoding="utf-8"))["release"]


def utf8_stdout():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
