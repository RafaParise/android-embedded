# 2. Deixar rápido

Analogia: um celular de entrada é uma **mochila pequena**. Ele não fica rápido com "turbo", fica rápido
quando você **tira o que não usa** e para de carregar peso morto. Este guia faz a faxina com segurança
e mostra o que vale e o que não vale a pena.

## Antes de tudo: medir

```
python scripts\medir.py              # números de desempenho (abertura de apps, memória livre)
python scripts\saude.py              # painel de saúde; guarda histórico em diagnostico\
```

Rode antes e depois de cada mudança. Sem medida, "ficou mais rápido" é só impressão.

## A faxina dos apps (lotes)

Os apps de fábrica estão agrupados em **lotes** em `scripts/lotes-bloatware.json` (por exemplo, `A1`,
`B`, `S1`, e os `FOSS-*`, em que cada função ganha um substituto livre do F-Droid).

```
python scripts\lote-pacotes.py A1             # SIMULA: mostra o que faria
python scripts\lote-pacotes.py A1 --aplicar   # desativa (pm disable-user --user 0)
python scripts\lote-pacotes.py A1 --restaurar # desfaz
```

- **Desativar não é apagar:** o app para de rodar e de ocupar memória, mas continua no sistema, e volta
  com `--restaurar`. É como tirar o fusível, não arrancar o fio.
- **Remover de verdade** (`--remover`, `pm uninstall -k --user 0`) só vale para o que já está desativado
  e tem substituto declarado. Mesmo assim volta com `--restaurar` (`cmd package install-existing`).
- **Lista de protegidos:** o script recusa sozinho o que quebra o celular (Play Store, serviços do Google,
  WebView, telefone e SMS, teclado em uso, Knox, a tela inicial, Configurações, `appsedge`, que faz a
  tela dividida, e outros que a comunidade do UAD-ng marcou como perigosos).
- **Bateria:** o script para abaixo de 3%.

Para trocar os apps da Samsung pelos livres: `python scripts\fdroid-baixar.py --pasta baixados org.fossify.phone`
baixa do F-Droid oficial e confere o hash (`--instalar` instala pelo cabo); `memoria/PLAY-PARA-FONTE.md` diz o que dá para trocar.

## Ajustes que valem (e o porquê)

| Ajuste | Efeito real | Como |
|---|---|---|
| Animações em 0 | O celular para de "desenhar" a transição: tudo responde na hora | `modos.py` ou as 3 escalas em `settings put global ... 0` |
| Remover animações (Samsung) | Mantém sem animação mesmo com as Opções do desenvolvedor escondidas | `settings put system reduce_animations 1` |
| Reduzir transparência | Menos desfoque na barra e no painel: menos trabalho para a placa de vídeo | `settings put system accessibility_reduce_transparency 1` |
| Busca de Wi-Fi sempre ligada **desligada** | Menos rádio acordado sem motivo | `settings put global wifi_scan_always_enabled 0` |
| Modo economia completo | Cinza, economia de energia e de dados, brilho e tela em 15 s; guarda e devolve tudo | `python scripts\modos.py economia ligar` / `desligar` |

## Ajustes que NÃO valem (testados ou conferidos)

| Ajuste | Por que não |
|---|---|
| Forçar 4x MSAA | Mais trabalho para a GPU (Mali-G52) numa tela 720p; deixa jogos mais lentos |
| Mostrar a taxa de atualização | A tela do A12 é fixa em 60 Hz: o contador só mostra "60" |
| "Wi-Fi seguro" da Samsung | Serviço com conta e VPN próprias; briga com a Tailscale (só uma VPN por vez no Android) |
| Mover app ou o armazenamento para o cartão adotado | **Nunca.** No A12, `pm move-package` derrubou o sistema e `pm move-primary-storage` corrompeu 1.412 arquivos (conferido por md5). Ver guia 6 |
| Apps "otimizadores" e "limpadores" da loja | Gastam mais do que economizam; o `cel otimizar` faz o que existe de útil |

O que já foi investigado a fundo, com prova (o "teto" sem root): [`memoria/RADAR-DESEMPENHO.md`](memoria/RADAR-DESEMPENHO.md).

Próximo: [3-PARISE-CORE-IA-NO-CELULAR.md](3-PARISE-CORE-IA-NO-CELULAR.md).
