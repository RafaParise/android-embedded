"""Passo 2: atribui a cada lugar o MUNICIPIO por poligono (malha municipal do IBGE, SP_Municipios_2025) e junta os dois extratos sem repetir id.
Metodo:
  1) ponto dentro do poligono de algum dos 645 municipios de SP  -> metodo 'poligono';
  2) ponto fora de todos (mar, estuario, praia, ilha pequena que a malha generalizada nao cobre) e a no maximo TOL_M metros de um dos 9
     municipios da Baixada -> o mais proximo, metodo 'proximidade';
  3) o resto fica sem municipio (mun = NULL) e nao entra em nenhuma lista.
Taxa de acerto: concordancia com o campo de localidade do endereco (addresses[1].locality) quando ele e o nome de um municipio de SP.
Uso: python -I recorte.py <pasta_dados_overture> <shapefile_ibge.shp> [TOL_M]
Saida: <pasta>/places-recorte.parquet e <pasta>/recorte-estatisticas.json
Entradas sao dados externos: so leitura."""
import json
import math
import pathlib
import sys
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pyarrow as pa  # noqa: E402
import shapely  # noqa: E402

import comum as C  # noqa: E402

C.utf8_stdout()

LAT0, LON0 = -23.9, -46.4
KX = 111320.0 * math.cos(math.radians(24.0))
KY = 110574.0


def para_metros(coords):
    return np.column_stack(((coords[:, 0] - LON0) * KX, (coords[:, 1] - LAT0) * KY))


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower().strip()


def main():
    pasta = pathlib.Path(sys.argv[1])
    shp = pathlib.Path(sys.argv[2])
    tol_m = float(sys.argv[3]) if len(sys.argv) > 3 else 300.0
    fb = (pasta / "places-baixada-bbox.parquet").as_posix()
    fc = (pasta / "places-capital-bbox.parquet").as_posix()

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    # uniao dos dois extratos sem repetir id + flags dos bbox LITERAIS da tarefa
    bx = C.BBOX_BAIXADA_LITERAL
    cx = C.BBOX_CAPITAL_LITERAL
    con.execute(f"""
        CREATE TABLE p AS
        SELECT * FROM read_parquet('{fb}')
        UNION ALL
        SELECT * FROM read_parquet('{fc}') WHERE id NOT IN (SELECT id FROM read_parquet('{fb}'))
    """)
    con.execute(f"""
        ALTER TABLE p ADD COLUMN in_bbox_baixada BOOLEAN;
        ALTER TABLE p ADD COLUMN in_bbox_capital BOOLEAN;
        UPDATE p SET in_bbox_baixada = (lon >= {bx[0]} AND lon <= {bx[2]} AND lat >= {bx[1]} AND lat <= {bx[3]}),
                     in_bbox_capital = (lon >= {cx[0]} AND lon <= {cx[2]} AND lat >= {cx[1]} AND lat <= {cx[3]});
    """)
    n = con.execute("SELECT count(*) FROM p").fetchone()[0]
    print("lugares unicos (uniao dos 2 extratos):", n)

    # ---- poligonos
    s = shp.as_posix()
    linhas = con.execute(f"SELECT CD_MUN, NM_MUN, ST_AsWKB(geom) FROM ST_Read('{s}') ORDER BY CD_MUN").fetchall()
    cods = [r[0] for r in linhas]
    nomes = [r[1] for r in linhas]
    polys = shapely.from_wkb([bytes(r[2]) for r in linhas])
    polys_m = shapely.transform(polys, para_metros)
    print("municipios na malha:", len(polys))

    dados = con.execute("SELECT id, lon, lat FROM p").fetchnumpy()
    ids = dados["id"]
    lon = dados["lon"].astype("float64")
    lat = dados["lat"].astype("float64")
    pts = shapely.points(np.column_stack(((lon - LON0) * KX, (lat - LAT0) * KY)))

    tree = shapely.STRtree(polys_m)
    ent, alvo = tree.query(pts, predicate="within")
    idx_mun = np.full(len(ids), -1, dtype="int64")
    # se um ponto cair em 2 poligonos (sobreposicao da malha), vale o primeiro
    idx_mun[ent[::-1]] = alvo[::-1]
    # dtype=object: com o dtype '<U8' que o np.where cria, "proximidade" (11 letras) seria truncada para "proximid"
    metodo = np.array(["poligono" if i >= 0 else "" for i in idx_mun], dtype=object)
    dist = np.zeros(len(ids))
    print("dentro de algum poligono:", int((idx_mun >= 0).sum()), " fora de todos:", int((idx_mun < 0).sum()))

    # ---- fora de todos: municipio da Baixada mais proximo
    cod_baixada = [i for i, nm in enumerate(nomes) if nm in C.BAIXADA_MUNICIPIOS]
    assert len(cod_baixada) == 9, [nomes[i] for i in cod_baixada]
    tree_b = shapely.STRtree(polys_m[cod_baixada])
    fora = np.where(idx_mun < 0)[0]
    estat_dist = {}
    if len(fora):
        tgt, d = tree_b.query_nearest(pts[fora], max_distance=max(2000.0, float(tol_m)), return_distance=True, all_matches=False)
        # tgt: [indices_entrada, indices_arvore]
        d = np.asarray(d)
        for lim in (50, 100, 200, 300, 500, 1000, 2000):
            estat_dist[f"<= {lim} m"] = int((d <= lim).sum())
        sel = d <= tol_m
        idx_mun[fora[tgt[0][sel]]] = np.array(cod_baixada)[tgt[1][sel]]
        dist[fora[tgt[0][sel]]] = d[sel]
        metodo[fora[tgt[0][sel]]] = "proximidade"
    print("fora de todos os poligonos, por distancia ao mais proximo da Baixada:", estat_dist)

    mun_cod = np.array([cods[i] if i >= 0 else None for i in idx_mun], dtype=object)
    mun_nome = np.array([nomes[i] if i >= 0 else None for i in idx_mun], dtype=object)
    metodo_o = np.array([m if m else None for m in metodo], dtype=object)
    tab = pa.table({"id": ids, "mun_cod": pa.array(mun_cod, pa.string()), "mun": pa.array(mun_nome, pa.string()),
                    "mun_metodo": pa.array(metodo_o, pa.string()), "mun_dist_m": pa.array(dist, pa.float64())})
    con.register("atrib", tab)
    saida = (pasta / "places-recorte.parquet")
    if saida.exists():
        saida.unlink()
    con.execute(f"COPY (SELECT p.*, a.mun_cod, a.mun, a.mun_metodo, a.mun_dist_m FROM p JOIN atrib a USING (id)) TO '{saida.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")

    # ---- estatisticas e taxa de acerto
    est = {"unicos": int(n), "dentro_poligono": int((metodo == 'poligono').sum()), "por_proximidade": int((metodo == 'proximidade').sum()),
           "sem_municipio": int((idx_mun < 0).sum()), "tolerancia_m": tol_m, "fora_dos_poligonos_por_distancia": estat_dist}
    pm = {}
    for nm in C.BAIXADA_MUNICIPIOS + [C.CAPITAL_MUNICIPIO]:
        pm[nm] = con.execute("SELECT count(*), sum((mun_metodo='proximidade')::INT) FROM read_parquet(?) WHERE mun = ?", [saida.as_posix(), nm]).fetchone()
    est["por_municipio"] = {k: {"total": int(v[0]), "por_proximidade": int(v[1] or 0)} for k, v in pm.items()}

    # concordancia com a localidade do endereco (so quando a localidade e o nome de um municipio de SP)
    mapa = {sem_acento(n): n for n in nomes}
    loc = con.execute("SELECT localidade, mun FROM read_parquet(?) WHERE mun IS NOT NULL AND localidade IS NOT NULL", [saida.as_posix()]).fetchall()
    comp = conc = 0
    por_mun = {}
    for l, m in loc:
        mm = mapa.get(sem_acento(l))
        if mm is None:
            continue
        comp += 1
        ok = (mm == m)
        conc += ok
        a = por_mun.setdefault(m, [0, 0])
        a[0] += 1
        a[1] += ok
    est["acerto_vs_localidade"] = {"comparaveis": comp, "concordam": conc, "taxa": round(conc / comp, 4) if comp else None,
                                  "por_municipio": {k: {"comparaveis": v[0], "taxa": round(v[1] / v[0], 4)} for k, v in sorted(por_mun.items()) if k in C.BAIXADA_MUNICIPIOS + [C.CAPITAL_MUNICIPIO]}}
    (pasta / "recorte-estatisticas.json").write_text(json.dumps(est, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in est.items() if k != 'acerto_vs_localidade'}, ensure_ascii=False)[:2500])
    print(json.dumps(est["acerto_vs_localidade"], ensure_ascii=False)[:2500])


main()
