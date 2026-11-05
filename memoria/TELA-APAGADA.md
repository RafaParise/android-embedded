# Tela apagada sem bloquear (04/11/2026)

Pedido do Rafael: volume para baixo 3 vezes só escurece; sem limite de tempo; com ou sem cabo; nunca bloqueia, a não ser que ele bloqueie.

## Como usar
| O que | Como |
|---|---|
| Escurecer, no celular | **Volume para baixo 3 vezes** |
| Acender | **Dois toques** curtos (rápidos ou com até 2 s entre eles), ou **volume para cima** |
| Acende sozinha | **Alarme** tocando ou **chamada** chegando (confere a cada 5 s) |
| Bloquear | **Botão de ligar**: a tela volta no PIN |
| Pelo PC | `scripts\tela-apagada.cmd` alterna; `python scripts\tela-apagada.py iniciar, apagar, acender, parar, status` |

## Como funciona
Camada preta por cima de tudo mais brilho temporário 0 (`Tela.java`, `tela.dex`, com o usuário `shell`). Nenhum ajuste salvo muda. A cada 5 s ele conta como uso do aparelho (`userActivity`), e é isso que impede o Android de dormir sem o cabo. Se o processo morrer, a camada some sozinha e o `tela-vigia.sh` devolve o brilho.

Memória: gesto parado ~4 MB; tela escura ~70 MB, só enquanto escura.

## Limites reais
- **Sobra um brilho quase imperceptível.** É a luz de fundo do LCD no mínimo. Apagar de verdade foi tentado e não dá com o toque vivo (tabela abaixo).
- **O toque continua chegando ao que está por baixo.** No bolso pode abrir app; toque longo e dois dedos não acendem. O `shell` não tem permissão para desligar o toque (`DISABLE_INPUT_DEVICE`). Na tela inicial, dois toques muito rápidos bloqueiam: é o recurso da própria One UI.
- **Reiniciar o celular apaga o gesto.** Volta sozinho ao ligar o cabo no PC, com a tarefa `TelaGesto`.
- **Recolocar o cabo reinicia o `adbd` e mata o gesto** [Provável: `adbd` novo às 07:25:06, e o processo sumiu junto]. Medido: voltou sozinho em 8 s. Em carregador de parede sem PC ele pode ficar desligado até a próxima vez no PC (não testado). Se a tela estava escura nessa hora, a camada some e o brilho pode ficar no 0 até mexer na barra de brilho [Palpite, pelo código].
- **Apertos de volume com a tela já escura mudam a mídia** e não são devolvidos. Os 3 do gesto são devolvidos, menos se a mídia chegar a 0.

## O que foi tentado e por que não ficou
| Caminho | Resultado medido em 04/11 |
|---|---|
| `scrcpy --turn-screen-off` | Tirar o cabo deixou a tela preta sem saída pelos botões. O Rafael reiniciou. |
| `SurfaceControl.setDisplayPowerMode` (painel desligado de verdade) | Apaga, mas **o toque não volta depois de acender**, com o Android dizendo que está tudo normal. O Rafael não conseguiu desligar um alarme. Volta do toque: `input keyevent 223; sleep 1; input keyevent 224`, com a tela de bloqueio. |
| `SurfaceControl.setDisplayBrightness` | O Android recusa (`false`). |
| Arquivo da luz em `/sys/class/leds` | Sem permissão para o `shell`. |
| Só brilho 0 | A imagem continua visível. |
| Camada preta + brilho 0 | **É o que ficou.** Toque vivo e sem bloqueio. |

## Provas no aparelho, com a mão do Rafael (04/11)
- Dois toques com 1 s de intervalo acenderam; volume para cima acendeu.
- Sem cabo: gesto, dois toques e volume para cima funcionaram.
- Botão de ligar com a tela escura: histórico `energia`, tela de PIN.
- Alarme real com a tela escura: histórico `alarme`, sem bloqueio; o som parou 16 s depois e o Rafael aprovou.
- Volume: mídia 6 antes do gesto e 6 depois.
- `lastUserActivityTime` renovado (742 ms) durante o escuro.

Histórico no celular: `python scripts\tela-apagada.py status` (`/data/local/tmp/tela-vigia.historico`, últimas 20 vezes).

## Regra para quem mexer nisso
"On" e "Awake" não provam que o aparelho responde. Qualquer mudança aqui se confere com a mão do Rafael, incluindo o toque depois de acender, o cabo solto e o alarme. Os testes com falsos não pegariam nenhum dos defeitos de 04/11. Nunca `keyevent 26` nem `223` em teste sem avisar: bloqueiam.

## Arquivos
`scripts/tela-apagada.py`, `.cmd`, `scripts/tela-vigia.sh`, `scripts/celular-kit/tela/` (`Tela.java`, `compilar.ps1`, `tela.dex`), `scripts/tests/test_tela_apagada.py`. Compilar exige `C:\Projetos\ferramentas\compilar-dex` (JDK e R8 oficiais, com hash conferido; nada instalado no Windows).

## Wi-Fi 2,4 GHz, medido em 04/11
Média de 4 rodadas alternadas de 30 pings cada (cabo ligado, sem controles conectados, sinal −44 dBm):

| Internet: média / oscilação | Normal | Trava de alto desempenho |
|---|---|---|
| Bluetooth desligado | 53,7 / 20,8 ms | **39,2 / 1,8 ms** |
| Bluetooth ligado, nada conectado | 63,6 / 38,6 ms | 52,8 / 19,5 ms |
| Roteador, Bluetooth desligado | 15,9 / 12,0 ms | **3,8 / 2,3 ms** |

- **Ficou ligado:** `Tela wifi-turbo` segura a trava enquanto a tela estiver em uso e solta com o aparelho dormindo; religado com o gesto (`tela-apagada.py iniciar`). Desliga: `turbo-desligar`. Custa ~26 MB de memória residente (12:30; pouco depois de iniciar chegou a 69 MB); o gasto de bateria não foi medido. Provado: encerrar o processo solta a trava ("Locks held" vazio em `dumpsys wifi`). Não provado: soltar com o aparelho dormindo (a lógica é simples, mas sem medida).
- **Primeira medida enganou:** uma rodada com Bluetooth ligado não mostrou ganho. Só a repetição alternada separou o efeito do Bluetooth.
- **Bluetooth ligado piora o Wi-Fi mesmo sem aparelho conectado.** Desligar o Bluetooth quando não usar é o maior ganho que depende só dele.
- **Sem ganho, descartados:** trava de baixa latência (15 ms, igual ao normal); `set-fixed-performance-mode-enabled` (carga de 2,1 s nos dois, freq. igual); desativar IPv6: com `curl`, conectar sem forçar levou 0,03 s e forçando IPv4 0,02 s, então nenhuma demora de IPv6; o IPv6 público nem responde daqui, e a Microsoft não recomenda desativar (`learn.microsoft.com/troubleshoot/windows-server/networking/configure-ipv6-in-windows`).
- **Canal:** rede no canal 9, e só uma vizinha visível (canal 3, −82 dBm). Nada a trocar no roteador.
- **5 GHz:** o aparelho é só 2,4 GHz [Provável].

## BIOS, desempenho e temperatura (pedido de 03 e 04/11)
Sem root não existe "BIOS" nem app que mude frequência ou limite térmico neste celular: os arquivos de frequência não abrem para o `shell` [Certo: `-rw-rw----`, lido em 04/11], e root foi descartado. Em uso leve o aparelho fica frio: status térmico 0, processador 33 °C, bateria 29 °C. Teto de fábrica: 2,3 GHz em 4 núcleos e 1,8 GHz nos outros 4 [Certo: `cpuinfo_max_freq`].

Carga máxima nos 8 núcleos, em 04/11, 12:30, no cabo, com 100% de bateria [Certo, medido uma vez]:

| Tempo | Processador | Status térmico | Núcleos rápidos | Bateria |
|---|---|---|---|---|
| Antes | 33 °C | 0 | até 2,3 GHz | 29,4 °C |
| 1 min | 49 °C | 0 | 2,3 GHz | 29,5 °C |
| 3 min | 53 °C | 1 | **1,88 GHz** | 29,5 °C |
| 6 min | 55 °C | 2 | 1,88 GHz | 29,5 °C |
| 11 min | 58 °C | 3 (parei aqui) | 1,88 GHz | 30 °C |
| 2 min depois | 39 °C | 1 | livre | 30,2 °C |

Com carga pesada, os núcleos rápidos perdem cerca de 18% em 3 minutos, enquanto os outros seguem em 1,8 GHz, e o aparelho esfria rápido. O calor vem do processador, não da bateria. O que sobra: tirar a capinha e deixar o aparelho em superfície fria ou com ventilação em jogo longo [Provável: física, não medido aqui]; `python scripts\saude.py` quando esquentar. `scripts\proteger-bateria.cmd` (quem roda é ele; limita a carga a 85%) poupa a bateria, mas não esfria o processador.

## Dois toques com a tela bloqueada
Separado deste recurso, e FUNCIONA: em 04/11 o Rafael testou dois toques na tela inicial (bloqueia) e dois toques na tela apagada (acende no PIN). O EnforceDoze ficou como estava. O que falhou antes não se repetiu, e eu não medi a causa.
