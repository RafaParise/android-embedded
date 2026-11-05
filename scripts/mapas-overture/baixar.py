"""Passo 1: baixa do Overture Maps (Places) SO os lugares dentro do bbox de cada regiao, gravando um Parquet local.
Filtro de bbox no proprio Parquet (colunas bbox.xmin/xmax/ymin/ymax -> poda de row groups; nunca baixa o planeta).
Uso: python -I baixar.py <pasta_dados_overture> [baixada|capital|todas]
Saida: <pasta>/places-<regiao>-bbox.parquet  (colunas ja achatadas; e-mail NAO e gravado, so a quantidade)
Esquema real da release 2026-10-21.0: NAO existe mais `categories`; ficam `taxonomy` (primary/hierarchy/alternates) e `basic_category`."""
import json
import pathlib
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import comum as C  # noqa: E402

C.utf8_stdout()


def descobre_release(pasta: pathlib.Path) -> str:
    with urllib.request.urlopen("https://stac.overturemaps.org/catalog.json", timeout=60) as r:
        cat = json.load(r)
    return cat["latest"]


def grava_release(pasta: pathlib.Path, release: str) -> None:
    arq = pasta / "release.json"
    arq.write_text(json.dumps({"release": release, "glob": C.glob_places(release), "fonte": "https://stac.overturemaps.org/catalog.json (campo latest)"}, indent=1), encoding="utf-8")


SELECT = """
SELECT
  id,
  names.primary                                     AS nome,
  confidence,
  operating_status,
  basic_category,
  taxonomy.primary                                  AS cat,
  taxonomy.hierarchy                                AS cat_hier,
  taxonomy.alternates                               AS cat_alt,
  ST_X(geometry)                                    AS lon,
  ST_Y(geometry)                                    AS lat,
  (ST_GeometryType(geometry) = 'POINT')             AS eh_ponto,
  addresses[1].freeform                             AS end_livre,
  addresses[1].locality                             AS localidade,
  addresses[1].postcode                             AS cep,
  addresses[1].region                               AS uf,
  addresses[1].country                              AS pais,
  len(addresses)                                    AS n_end,
  phones[1]                                         AS tel,
  len(phones)                                       AS n_tel,
  websites[1]                                       AS site,
  len(websites)                                     AS n_site,
  len(emails)                                       AS n_email,
  len(socials)                                      AS n_social,
  brand.names.primary                               AS marca,
  brand.wikidata                                    AS marca_wikidata,
  list_distinct(list_transform(sources, lambda s: s.dataset)) AS fontes,
  sources[1].update_time                            AS atualizado,
  version
FROM read_parquet('{glob}', hive_partitioning=1)
WHERE bbox.xmin >= {x0} AND bbox.xmax <= {x1} AND bbox.ymin >= {y0} AND bbox.ymax <= {y1}
"""


def baixa(pasta: pathlib.Path, release: str, nome: str, bbox):
    x0, y0, x1, y1 = bbox
    saida = pasta / f"places-{nome}-bbox.parquet"
    tmp = pasta / f"places-{nome}-bbox.parquet.parcial"
    if tmp.exists():
        tmp.unlink()
    con = C.abre_duckdb(spatial=True)  # ST_X/ST_Y: o bbox do Parquet e float32 (xmin != xmax mesmo em ponto), nao serve de coordenada
    sql = SELECT.format(glob=C.glob_places(release), x0=x0, x1=x1, y0=y0, y1=y1)
    t = time.time()
    con.execute(f"COPY ({sql}) TO '{str(tmp).replace(chr(92), '/')}' (FORMAT parquet, COMPRESSION zstd)")
    n = con.execute(f"SELECT count(*) FROM read_parquet('{str(tmp).replace(chr(92), '/')}')").fetchone()[0]
    nao_ponto = con.execute(f"SELECT count(*) FROM read_parquet('{str(tmp).replace(chr(92), '/')}') WHERE NOT eh_ponto").fetchone()[0]
    if saida.exists():
        saida.unlink()
    tmp.rename(saida)
    print(f"[{nome}] bbox={bbox} linhas={n} nao_ponto={nao_ponto} arquivo={saida.stat().st_size/1e6:.1f} MB em {time.time()-t:.0f}s")
    return {"regiao": nome, "bbox_baixado": list(bbox), "linhas": n, "nao_ponto": nao_ponto, "bytes": saida.stat().st_size,
            "sha256": C.sha256_arquivo(saida), "segundos": round(time.time() - t, 1)}


def main():
    pasta = pathlib.Path(sys.argv[1])
    quais = sys.argv[2] if len(sys.argv) > 2 else "todas"
    regs = {"baixada": C.BBOX_BAIXADA_BAIXAR, "capital": C.BBOX_CAPITAL_BAIXAR}
    if quais != "todas":
        if quais not in regs:
            sys.exit(f"regiao desconhecida: {quais!r} (use baixada, capital ou todas)")
        regs = {quais: regs[quais]}
    pasta.mkdir(parents=True, exist_ok=True)
    release = descobre_release(pasta)
    print("release mais recente:", release)
    info = {}
    for nome, bbox in regs.items():
        info[nome] = baixa(pasta, release, nome, bbox)
    # release.json so depois de TODOS os downloads; baixando so uma regiao o outro parquet pode ser de outra release
    grava_release(pasta, release)
    if len(regs) < 2:
        print("AVISO: so uma regiao baixada; se o outro parquet for de outra release, baixe 'todas' antes do recorte.")
    (pasta / f"baixados-{'-'.join(regs)}.json").write_text(json.dumps({"release": release, "regioes": info}, indent=1), encoding="utf-8")


main()
