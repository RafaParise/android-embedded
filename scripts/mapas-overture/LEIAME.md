# Pipeline do Overture Maps (lojas e serviços) para o Organic Maps

Gera as listas KML de lugares da Baixada Santista e da capital paulista a partir do **Overture Maps Places** (dados abertos, CDLA-Permissive-2.0; fontes Meta,
Microsoft, Foursquare em Apache-2.0, AllThePlaces em CC0-1.0 [Certo: campo `sources[].license` do próprio dado, release 2026-10-21.0]).
Os scripts desta pasta precisam de um venv com `duckdb`, `pyarrow`, `shapely` e `numpy` e de internet; **não têm teste** (baixam dado de verdade).
O que é testado (`scripts/tests/test_mapas_lugares.py`) é o `scripts/mapas-lugares.py`, que só usa a biblioteca padrão.
Nada gerado entra no git: lista de comércios é dado de terceiros (fica fora do repositório, como as planilhas).

## Refazer tudo (uma pasta de trabalho FORA do repositório, por exemplo `D:\mapas`)

```powershell
python -m venv D:\mapas\venv ; D:\mapas\venv\Scripts\pip install duckdb pyarrow shapely numpy
$py = 'D:\mapas\venv\Scripts\python.exe'; $dados = 'D:\mapas\dados-overture'
# 1) malha municipal do IBGE (SP_Municipios_2025.zip; ~35 MB) e descompactar em $dados\ibge\malha-2025\extraido
New-Item -ItemType Directory -Force $dados\ibge\malha-2025 | Out-Null
Invoke-WebRequest https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2025/UFs/SP/SP_Municipios_2025.zip -OutFile $dados\ibge\malha-2025\SP_Municipios_2025.zip
# 2) lugares do Overture dentro das duas caixas (a release mais recente vem do catálogo STAC; ~90 MB)
& $py -I scripts\mapas-overture\baixar.py $dados todas
# 3) município de cada lugar por polígono do IBGE (fora dos polígonos, até 300 m do município da Baixada mais próximo)
& $py -I scripts\mapas-overture\recorte.py $dados $dados\ibge\malha-2025\extraido\SP_Municipios_2025.shp
# 4) JSONL (uma linha por lugar; sem e-mail nem redes sociais); o mapas-lugares.py também lê .jsonl.gz (guardado em diagnostico\mapas-lugares\)
& $py -I scripts\mapas-overture\exportar-jsonl.py $dados
# 5) KML (só biblioteca padrão; qualquer Python 3) e conferência
python -I scripts\mapas-lugares.py overture $dados\places.jsonl D:\mapas\kml-overture --categoria-no-nome --release (Get-Content $dados\release.json | ConvertFrom-Json).release
python -I scripts\mapas-lugares.py verificar D:\mapas\kml-overture 8
```

## Medido em 31/10/2026 (release 2026-10-21.0)

- 760.358 lugares únicos nas duas caixas; 99,4% do município atribuído por polígono concorda com a localidade do endereço do próprio dado; fora de qualquer polígono (praia, ilha),
  só 21 lugares, 20 deles a até 300 m de um município da Baixada.
- Baixada Santista: 75.828 lugares; 96% com endereço, 85% com telefone, 42% com site. A confiança do Overture mede mais a atividade online da página do que a existência do lugar
  (de 406 hospitais, 99 ficam abaixo de 0,5), por isso a lista principal leva "confiança >= 0,5 **ou** categoria do dia a dia com confiança >= 0,2".
- Capital: 483.577 lugares: grande demais para uma lista só no Organic Maps do A12 (3,8 GB de RAM): só confiança >= 0,9 (e essenciais >= 0,7), por zona.
- Verificação independente (`mapas-lugares.py verificar 8`): 72 de 72 lugares sorteados batem com o município do OpenStreetMap (Nominatim, 1 pedido por segundo).
