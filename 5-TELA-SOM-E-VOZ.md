# 5. Tela, som e voz

## Papel de parede rolante

Analogia: a tela inicial é um **corredor de páginas**; o papel de parede é um **painel comprido** pintado
na parede. Ao andar de uma página para outra, o painel corre junto, como nos Samsung antigos. A tela
inicial da Samsung (One UI) não faz mais isso, então o projeto tem um app próprio de 21 KB que faz.

```
python scripts\papel-rolante.py aplicar --imagem minha-foto.jpg   # instala o app e aplica (tela e bloqueio)
python scripts\papel-rolante.py sincronia ligar                   # o papel segue a página exata
python scripts\papel-rolante.py desfazer                          # volta ao papel comum
```

- Em pé, a imagem anda com o dedo; deitado, aparece inteira, com o fundo desfocado.
- "Sincronia" usa um serviço de **acessibilidade do próprio app**, que só escuta a rolagem da tela inicial
  da Samsung (nada de conteúdo da tela). Ligar é decisão do dono do aparelho.
- O código está em `scripts/celular-kit/papel/` e compila sem Gradle (`compilar.ps1`, com as ferramentas
  oficiais do Android SDK). O APK assinado vem no pacote da versão.

## Tela apagada sem bloquear

Para gravar, ouvir ou deixar a IA trabalhando com a tela escura: `python scripts\tela-apagada.py iniciar`
liga o gesto **volume para baixo 3 vezes** (apaga) e dois toques (acende). É uma camada preta com brilho
zero: o toque, o alarme e a depuração continuam funcionando.

**Não use** `scrcpy --turn-screen-off` nem desligar o painel por comando: no A12, isso deixou o toque morto
e impediu desligar um alarme ([`memoria/TELA-APAGADA.md`](memoria/TELA-APAGADA.md)).

## Ditado sem nuvem

- **Celular:** WhisperIME (F-Droid). Ele vira o serviço de voz do sistema, e a tecla **Entrada de voz** do
  HeliBoard (Barra de ferramentas > teclas fixadas) abre o ditado em qualquer app. Na primeira vez, o app
  baixa o modelo (uns 435 MB); depois, funciona sem internet. **Desmarque "Traduzir para inglês"**.
- **PC:** Handy (`winget install cjpais.Handy`, ou o instalador do GitHub do autor): um atalho de teclado,
  você fala e o texto entra no cursor.

Passo a passo e como desfazer: [`memoria/VOZ-OFFLINE.md`](memoria/VOZ-OFFLINE.md).

## Microfone e fone Bluetooth

Analogia: o fone Bluetooth tem **duas faixas**: a da música (AAC, estéreo, boa) e a da ligação (HFP, mono,
16 kHz). Quando algum app abre o microfone do fone, o celular troca para a faixa da ligação e a música fica
com som de "fundo de balde".

`python scripts\microfone-bt.py auto` (o padrão) abre o microfone do fone só enquanto algo grava; `fixo`
deixa sempre aberto (e o som ruim). No Termux: `cel microfone status`.

## Controles Bluetooth e Wi-Fi

O A12 só tem Wi-Fi de 2,4 GHz, a mesma faixa do Bluetooth. Com dois controles ligados, o Wi-Fi quase
para (medido: 3 a 5 s até o roteador e 25% de perda). Jogue nos dados móveis e, depois de desligar os
controles, desligue e ligue o Wi-Fi uma vez ([`memoria/CONTROLES-GAMESIR.md`](memoria/CONTROLES-GAMESIR.md)).

Próximo: [6-SEGURANCA-E-REPARO.md](6-SEGURANCA-E-REPARO.md).
