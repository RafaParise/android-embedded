# Lugares no Organic Maps: achar loja, escola e serviço pelo nome (31/10 a 01/11/2026)

**03/11/2026, busca principal testada no aparelho:** "terminal rodoviario tatico", "tatico", "terminal tatico" e até "rodoviaria tactico" acham o Terminal Rodoviário e Urbano Tatico (Praia Grande), que existe no OpenStreetMap [Certo: 2.ª tela de teste]. Com o celular deitado o teclado cobre quase toda a lista [Certo: captura]; na tela dividida do dashcam deve ser pior [Palpite]. Favorito importado na busca principal segue impossível: pedido aberto no projeto ([#808](https://github.com/organicmaps/organicmaps/issues/808)).

Pedido do Rafael: "um pacote de mapas do Organic Maps que o torne com um funcionamento semelhante ao Maps", com "todas as lojas, estabelecimentos e tudo que tem na Baixada Santista".

## O que é e o que NÃO é
- O mapa do Organic Maps é **OpenStreetMap** (região São Paulo–Santos: capital, Baixada, Embu e Ribeirão Pires). A barra de busca principal só acha o que está nele. Não existe "pacote do Organic Maps" com todos os lugares.
- O que foi feito: listas de **favoritos OCULTOS** (KML) com lugares de bases abertas, **já importadas no A12 na manhã de 01/11**. Elas **não aparecem na barra principal** [Certo: testado no aparelho em 31/10 e 01/11, Organic Maps 2026.09.29].
  Para achar: **Marcadores → (a lista) → lupa (Buscar) → digitar → tocar no resultado → PARA** (rota até lá) ou **ROTA DE** (rota a partir de lá). Com o teclado aberto os resultados ficam escondidos na tela deitada: toque em Voltar uma vez para fechá-lo e ver a lista inteira.
- Rota a partir de onde você está exige a **localização do aparelho ligada** (em 01/11 estava ligada: a rota da posição do aparelho, em Itanhaém, até um ponto perto de Santos calculou: 66 km, 58 min).
- Não é o Google: sem avaliações, fotos, horário de funcionamento nem trânsito. O dado é aberto e tem lugar fechado, endereço velho e coordenada aproximada.
- **A busca da lista casa só o NOME do lugar** [Certo: 01/11, "Governador" só achou nomes com a palavra; o endereço da descrição não conta]. Por isso as listas foram geradas com `--categoria-no-nome`: se a palavra da categoria não está no nome, o nome ganha "(Categoria)". Exemplo testado: buscar "camping" acha "Recanto Caiçara (Camping)" e "Clube do jet (Camping)". Categoria vem do Overture e erra (viu-se "Camping Beira Mar (Academia)").
- Não toque em **Mostrar** nas listas grandes com o mapa afastado: são dezenas de milhares de pinos. Para ver os pinos de uma cidade só, use a lista dela (arquivos `por-municipio` no PC; peça que eu importe).

## Listas no aparelho (todas ocultas)
| Lista (como aparece em Marcadores) | Lugares | Fonte |
|---|---|---|
| Escolas — Baixada Santista | 1.233 | INEP/IPEA geobr, Censo Escolar 2020; a escola usada no teste está aqui [Certo: achada pelo Buscar da lista, com ROTA DE e PARA] |
| Escolas — São Paulo capital | 6.737 | idem |
| Escolas estaduais — resto de SP | 4.546 | idem |
| Lugares — Baixada Santista | 52.155 | Overture Maps, release 2026-10-21.0 (confiança ≥ 0,5, ou categoria do dia a dia com ≥ 0,2) |
| Lugares — Baixada Santista (menos certos) | 22.241 | idem (o que ficou abaixo desses cortes) |
| Lugares — São Paulo, zona Centro / Norte / Leste / Sul / Oeste | 13.197 / 13.122 / 29.578 / 28.450 / 26.261 (110.608) | idem (confiança ≥ 0,9; essenciais ≥ 0,7) |

Só no PC (`diagnostico\mapas-lugares\kml-overture\por-municipio\`): as mesmas 52.155 da lista principal divididas em Bertioga 2.587, Cubatão 2.022, Guarujá 8.008, Itanhaém 3.442, Mongaguá 1.836, Peruíbe 2.647, Praia Grande 9.697, Santos 15.466 e São Vicente 6.450 (plano B se a lista única pesar ou para ver os pinos de uma cidade).

Cortes na Baixada (75.828 lidos → 74.396): 1.284 escolas de educação básica (já estão nas listas do INEP, com nome oficial; faculdades, idiomas, autoescolas, música e escolas técnicas ficam), 140 duplicados (mesmo nome a até 40 m), 5 nomes genéricos, 2 nomes só em alfabeto não latino (tailandês, árabe, chinês...) e 1 sem letra.
Limpeza dos nomes: e-mail nunca entra; TUDO MAIÚSCULO vira Capitalizado; **letra "estilizada" (negrito matemático, largura total, versalete) vira letra comum**, senão a busca não acha ("𝗦𝗔𝗣𝗔𝗧𝗔𝗥𝗜𝗔" não casa com "sapataria"); "º", "ª", "½" e "–" ficam como estão; 259 categorias que vinham em inglês ("Notary public") foram traduzidas ("Cartório").

Os KML prontos ficam em `diagnostico\mapas-lugares\` (fora do git, de propósito: são dados de terceiros): `kml-overture\` (lojas e serviços, com `manifesto.json`) e `kml-inep\` (escolas); o recorte inteiro do Overture (760 mil lugares, sem e-mail) está em `places-overture-2026-10-21.0.jsonl.gz` (74 MB): `python scripts\mapas-lugares.py overture <esse .gz> <pasta> --release 2026-10-21.0 --categoria-no-nome` regera as listas em ~1 minuto, sem baixar nada.

## Como importar ou trocar uma lista (PC; celular no cabo com a depuração USB)
```powershell
python scripts\om-lugares.py importar diagnostico\mapas-lugares\kml-overture\lugares-baixada-santista.kml            # simulação: valida e mostra o plano
python scripts\om-lugares.py importar diagnostico\mapas-lugares\kml-overture\lugares-baixada-santista.kml --aplicar  # copia e abre no Organic Maps (um por vez)
python scripts\om-lugares.py medir                                                                  # abertura a frio x3 e memória (FECHA o app)
python scripts\om-lugares.py limpar-copias lugares-baixada-santista.kml --aplicar                   # apaga a cópia em Download (a lista fica no app)
```
O script não consegue ver dentro do Organic Maps (área privada, sem root): **confira em Marcadores** se a lista apareceu. Para apagar uma lista: Marcadores → ⋮ da lista → **Apagar** (apague a antiga antes de importar a nova com o mesmo título, senão ficam duas).
Nunca `file://` (falha); o caminho que funciona é `content://media/external/file/<id>` com `--grant-read-uri-permission` (o script faz).

## Custo medido no A12 (`om-lugares.py medir`, 01/11) [Certo, com a ressalva abaixo]
- Só as 3 listas do INEP (12.516 lugares): abertura a frio 498, 406 e 403 ms (mediana 406); PSS do app 272.247 KB = **266 MiB** (Native Heap 178 MiB).
- Com **todas** as listas (≈ 197 mil favoritos: Baixada 74.396 + capital 110.608 + INEP 12.516): abertura a frio 436, 392 e 400 ms (mediana **400**); PSS 335.575 KB = **328 MiB** (Native Heap 234 MiB). Ou seja, ~62 MiB a mais por ~184 mil favoritos e nenhuma diferença na abertura (as listas carregam depois, em segundo plano).
- Ressalva: o PSS do app varia com a parte do mapa que estava aberta (uma medida de 414 MiB com 64 mil favoritos veio logo depois de eu mexer num ponto no centro de Santos). O custo da lista é a diferença entre medidas na mesma situação, não um número solto. Em uso (tela dividida + rota calculada + lista grande aberta + busca) o app chegou a **634 a 643 MiB** de PSS (649.113 e 658.285 KB).
- **Dashcam com tudo carregado** (Organic Maps e Open Camera em tela dividida, gravação de 1 min 45 s, rota de 66 km calculada, lista da zona Leste aberta e busca "padaria"): MP4 íntegro (`ftyp`+`mdat`+`moov`), os dois apps vivos até o fim, MemAvailable entre 778 MB e 1,1 GB, nenhuma morte de processo no log. Teste anterior (só a lista da Baixada, 2 min 30 s): íntegro também. Os dois vídeos de teste foram apagados do cartão; os seus de 31/10 ficaram.
- Limites que usei [Palpite]: abertura a frio acima de ~1,5 s ou memória em repouso acima de ~450 MiB = trocar por listas por município. Não foi preciso.

## Qualidade (o que foi conferido)
- 760.358 lugares únicos nas duas caixas; município por polígono do IBGE concorda com a localidade do endereço do próprio dado em 99,4%; o verificador (que não usa o código do gerador) aprovou as 16 listas, e **243 de 243** lugares sorteados (27 por lista) batem com o município do OpenStreetMap (Nominatim) [Certo: `mapas-lugares.py verificar <pasta> 27`, 01/11].
- A confiança do Overture mede mais a atividade online da página do que a existência do lugar (de 406 hospitais da Baixada, 99 ficam abaixo de 0,5), por isso a lista principal leva "confiança ≥ 0,5 **ou** categoria do dia a dia (hospital, farmácia, mercado, órgão público, praia...) com confiança ≥ 0,2".
- O verificador achou defeitos reais: 9 nomes com e-mail dentro e duplicados de categorias diferentes (corrigidos em 01/11 de madrugada) e, na regeração com a categoria no nome, nomes de mais de 120 caracteres (o sufixo agora nunca passa de 100 no total).
- Lugares com nome estilizado, em alfabeto não latino e categorias em inglês foram achados olhando a lista no aparelho, não pelo verificador.

## Refazer ou atualizar
- Lojas e serviços: `scripts/mapas-overture/LEIAME.md` (baixar → recorte por município → JSONL) e `scripts/mapas-lugares.py overture ...` / `verificar ...`.
- Escolas: `scripts/mapas-lugares.py escolas-inep <schools_2020.gpkg> <saida>` (arquivo de 98 MB: https://www.ipea.gov.br/geobr/data_gpkg/schools/2020/schools_2020.gpkg).
- Testes: `test_mapas_lugares.py` (108; 62 de 62 mutações plantadas pegas) e `test_om_lugares.py` (49).

## Privacidade e licença
- Lista de comércios é dado de **terceiros** (nomes e telefones de estabelecimentos e de profissionais com página pública): os KML ficam fora do repositório e fora de qualquer IA externa; só os scripts e estes textos vão ao GitHub. Nada de aluno. Os favoritos do Rafael ("Meus locais") não foram tocados.
- Atribuição: Overture Maps Foundation (CDLA-Permissive-2.0; Foursquare Apache-2.0; AllThePlaces CC0-1.0 [Certo: campo `sources[].license` do próprio dado]); INEP/IPEA geobr (dados abertos).
