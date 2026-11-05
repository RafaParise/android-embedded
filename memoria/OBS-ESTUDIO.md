# Estúdio do OBS e o JBL Quantum 810 (03/11/2026)

Pedido do Rafael: "tudo pronto, só para conectar e usar", como estúdio profissional, com nomes organizados e "sempre desempenho acima de qualidade, melhor sempre fluido do que bonito". Script: `scripts/obs-estudio.py`.

## Como usar

Atalhos na área de trabalho:
- **Estudio - Gravar Jogos**: abre o OBS na bandeja, pronto. Abra o jogo e aperte **Ctrl+F9** para começar e para parar.
- **Estudio - Webcam do Celular**: câmera para chamadas ("OBS Virtual Camera"), com ou sem cabo. Com o OBS do estúdio já aberto, só liga a câmera nas cenas.
- **Recuperar Arquivos**: abre o PhotoRec (`WEBCAM-E-RECUPERACAO.md`).

| Atalho | Faz |
|---|---|
| Ctrl+F9 | Liga e desliga a gravação |
| Ctrl+F10 | Liga e desliga o microfone na gravação |
| Ctrl+1 a Ctrl+6 | 1 Jogo · 2 Jogo com Webcam · 3 Só Webcam · 4 Tela do PC · 5 Tela com Webcam · 6 Volto Já |

Vídeos em `C:\Users\voce\Videos\Estudio\Jogos`. Depois de jogar: `python scripts\obs-estudio.py relatorio` diz se perdeu quadros e por quê.

## O que foi escolhido, e por quê

Máquina [Certo: registro do OBS]: Ryzen 5 5600G sem placa dedicada, 12 GB úteis de RAM, monitor 1440x900 a 60 Hz. **Jogo e OBS dividem o mesmo chip gráfico**: é o limite que define tudo.

| Item | Valor | Motivo |
|---|---|---|
| Quadro | 1440x900 a 60 fps | Tamanho do monitor: sem reescala, que gastaria chip gráfico |
| Codificador | H.264 no chip da AMD, modo `speed`, sem quadros B | Circuito próprio; o menor atraso das opções |
| Taxa | VBR 25 Mbit/s | Boa para ação nesse tamanho; 11 GB por hora |
| Formato | MP4 híbrido | Não perde o vídeo se o PC cair |
| Cor | NV12, Rec.709, faixa limitada | Padrão de vídeo: abre igual em qualquer programa |
| Áudio | 48 kHz, AAC 192 kbit/s, 4 faixas | Tudo, Jogo, Microfone e Chamada, separadas para editar |
| Microfone | RNNoise, compressor, limitador | Só áudio: quase não pesa [Provável: não medi isolado] |
| Prioridade | Acima do normal | Já estava assim no OBS |
| Transição | Corte | Sem custo |

Sem filtro de imagem na webcam (nitidez, cor): gastam o chip gráfico, e a regra dele é fluidez.

**Medido em 03/11 [Certo: registro do OBS]:** 20 s da tela com 1.223 e 1.231 quadros: 0,6% a 0,7% perdidos ao codificar e 0% ao desenhar. O atalho Ctrl+F9 foi testado de verdade. **Não testado com jogo pesado rodando:** é aí que o chip é disputado. Rodar `relatorio` depois da primeira partida.

**Prova com jogo real em 04/11 [Certo]:** `C:\Need For Speed Underground 2` (DXVK, Vulkan), iniciado pelo mesmo modo do atalho: 60 s, 3.624 quadros, **0,2% perdidos ao codificar e 0% ao desenhar**, 183 MB (25 Mbit/s), 1440x900 a 60 fps, som do jogo na faixa Jogo. O quadro conferido mostra corrida a 106 mph: era a corrida de demonstração do jogo, sem entrada no controle; uma partida de verdade pode pesar diferente. Saves conferidos por md5, iguais. A fonte "Jogo em Tela Cheia" é a que captura (`vulkan shared texture capture successful`); "Jogo em Janela" fica tentando e registra `init_pipe: failed` enquanto a outra está ativa: é só ruído no registro.

**Perda baixa não prova imagem.** Em outra cópia do jogo, parada em "Please insert Disc 2", o vídeo saiu preto com 0,2% de perda. Por isso o `relatorio` mede o último vídeo e avisa quando ele está preto do começo ao fim.

**Se engasgar:** no perfil, Saída Reescalada para 1280x800 ou 48 fps; ou limitar o FPS do próprio jogo, o que mais libera o chip quando ele e o OBS disputam [Provável].

**Disco:** `C:` tem 50 GB livres, cerca de 4 horas de gravação.

**Desfazer:** `python scripts\obs-estudio.py desfazer`. O OBS antigo está inteiro: coleção e perfil `Sem nome` intactos, e cópia em `%APPDATA%\obs-studio\copia-antes-do-estudio.zip`.

## JBL Quantum 810 no PC

- O Windows está como a JBL manda [Certo: lido por Core Audio, e guia oficial]: saída padrão = Game; comunicação e microfone = Chat. O OBS grava cada canal na sua faixa.
- O nó do fone que mistura jogo e chat muda o que você ouve, e também o que cada canal entrega [Palpite: não medi].
- **Se o dongle sair:** essas fontes ficam mudas no OBS até ele voltar.
- **No app QuantumENGINE, para não brigar com o OBS** (eu não controlo a interface dele; ajustes para o Rafael):
  - Filtro de ruído do microfone, se houver no app: deixar **só um**. Dois juntos deixam a voz robótica [Provável]. O do OBS só vale para a gravação; em chamada vale o que estiver no fone.
  - Ganho do microfone no app: ajustar falando normal até o medidor do OBS ficar perto de -12 dB.
  - Som surround: só no canal Game, e ele entra na gravação como está.
- Fora do jogo, o QuantumENGINE usa cerca de 440 MB somados [Certo: 3 processos medidos]. Fechar a janela depois de configurar ajuda [Palpite: não sei se ajustes seguem sem ele].

## JBL no celular

- **App da JBL no celular: não instalei.** O guia oficial dá o QuantumENGINE só para Windows, e não achei fonte confirmando outro app para o 810 [Provável]. No guia, o celular é "Stereo" por Bluetooth e por cabo, e o 2.4G é "não compatível" [Certo: tabela do guia]. Não achei app aberto que controle o 810 [Provável: F-Droid e HeadsetControl sem menção].
- **Microfone no Bluetooth (04/11, funciona, aprovado por ele com o canal aberto):** `scripts\microfone-bt.py`. No modo `auto` (padrão), o canal de voz abre só enquanto um app grava, e fecha 3 s depois; no resto, a música fica em AAC. O modo `fixo` deixa aberto, sem atraso no começo da gravação, mas com todo o som em qualidade de telefone: é limite do Bluetooth deste fone, que não tem voz e música em alta ao mesmo tempo [Provável]. Roda dentro do processo do Wi-Fi em alto desempenho, sem processo a mais: 0,3% de CPU medido. Reconhece conectar e desconectar sozinho. Em `auto`, o primeiro 1 a 2 s da gravação pode faltar: comece a falar depois disso, ou use `fixo`. O reconhecimento com o fone real falta provar. **Desde 04/11 ~19:00 fica em `fixo` (sempre ativo), a pedido dele**: o fone já tem trava de mudo ao levantar a haste e botão de mudo. Voltar ao padrão: `python scripts\microfone-bt.py auto`.
- **Música:** já está no melhor codec que o fone aceita: AAC, 44,1 kHz, 16 bits [Certo: `dumpsys`; só AAC e SBC aparecem como selecionáveis]. Nada a ganhar aí.
- **Voz:** `microfone-bt.py medir` grava pelo PC, mede nível, ruído e faixa, e apaga a gravação. Faixa até 4 kHz = voz estreita; até 8 kHz = voz larga. Ainda não medido com o fone. Equalizador, cancelamento de ruído e firmware do fone só existem no QuantumENGINE, no PC.
- **Microfone do celular:** `microfone-bt.py celular-mudo` silencia sem fone nem fio: -33 dB (chiado) para -91 dB [Certo: medido]. Sem root, o hardware não desliga: é mudo por software. Em toque e em chamada, ele volta sozinho em até 1 s. **O mudo sobrevive se o processo morrer** [Certo: medido]; o vigia religa em 30 s, mas recolocar o cabo longe do PC mata os dois. Nesse caso: reiniciar o celular libera. Desfazer: `celular-ligado`.
- Dongle no PC e Bluetooth no celular ao mesmo tempo é previsto: o manual mostra atender chamada pelo botão Bluetooth [Certo: guia].

## Luzes e chiado

**Luzes (logo e laterais):** o guia diz que segurar o **botão de mudo do microfone por mais de 5 s** liga e desliga a iluminação [Certo: "Button command"]. Testar isso primeiro. Depois, o QuantumENGINE com brilho no máximo. Sem luz nos dois, com o fone carregado no modo 2.4G, a falha é provavelmente física [Provável]. Eu não consigo ver a luz nem mexer no app.

**Chiado depois do som:** medido [Certo]: depois de um bipe, a gravação do canal Game cai para -91 dB, silêncio digital, em todos os trechos. O chiado **não vem do PC nem do OBS**: nasce no fone ou no dongle. Chiado leve que some em segundos costuma ser o circuito de áudio ficando ligado e desligando [Palpite]. Para separar: repetir com ANC desligado (botão ANC, 1 toque); pelo Bluetooth; e pelo cabo. Se some no cabo, é o rádio ou o dongle; se fica nos três, é o circuito do fone.
