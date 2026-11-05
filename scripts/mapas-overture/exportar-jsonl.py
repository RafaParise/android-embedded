"""Passo 3: exporta o recorte (places-recorte.parquet) para JSONL, um lugar por linha, so com os campos que o scripts/mapas-lugares.py usa.
Campos: id, nome, conf, status, cat, lon, lat, end, cep, tel, site, mun. NAO exporta e-mail nem redes sociais. Linhas em ordem de id (saida repetivel).
Uso: python -I exportar-jsonl.py <pasta_dados_overture> [saida.jsonl]   (saida padrao: <pasta>/places.jsonl)
Entrada = dado externo: so leitura."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import duckdb  # noqa: E402

import comum as C  # noqa: E402

C.utf8_stdout()


def main():
    pasta = pathlib.Path(sys.argv[1])
    saida = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pasta / "places.jsonl"
    arq = (pasta / "places-recorte.parquet").as_posix()
    if saida.exists():
        saida.unlink()
    con = duckdb.connect()
    con.execute(f"""COPY (SELECT id, nome, confidence AS conf, operating_status AS status, cat, lon, lat, end_livre AS "end", cep, tel, site, mun
                         FROM read_parquet('{arq}') WHERE mun IS NOT NULL ORDER BY id)
                    TO '{saida.as_posix()}' (FORMAT json)""")
    n = con.execute(f"SELECT count(*) FROM read_parquet('{arq}') WHERE mun IS NOT NULL").fetchone()[0]
    print(f"{n} lugares com municipio -> {saida} ({saida.stat().st_size / 1048576:.0f} MB); release {C.le_release(pasta)}")


main()
