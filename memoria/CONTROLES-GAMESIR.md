# Dois GameSir Nova Lite no A12: latência, Wi-Fi e controle do celular (04/11/2026)

Pedido do Rafael: os dois controles configurados no app GameSir, menor atraso possível, o melhor no celular e no ARENA, e poder controlar o telefone pelo controle, tudo sem instalar nada.

## O achado principal: os dois controles sufocam o Wi-Fi

O A12 está em Wi-Fi 2,4 GHz (2422 MHz) e o Bluetooth usa a mesma faixa. Medido no aparelho em 03 e 04/11 [Certo], com ping ao roteador e **sem o fone no Bluetooth**:

| Bluetooth | Wi-Fi até o roteador |
|---|---|
| Nenhum aparelho | 5 a 40 ms, sem perda |
| Só o Preto (2 amostras) | cerca de 25 ms, sem perda |
| Preto e Roxo | 100 a 340 ms; depois 50 a 100% de perda e até 1,5 s |
| Preto, Roxo e JBL (situação da queda) | a varredura achou 0 redes; a internet caiu e o guarda suspendeu a saída pelo PC |
| Bluetooth desligado na mesma hora | conectou em menos de 10 s, 0% de perda |

Não isolei o papel do fone: a queda total foi com ele, e sem ele a rede já quase não funciona. Causa [Provável]: rádio e antena divididos entre Wi-Fi e Bluetooth; sem root não há ajuste disso.

**Na ordem inversa, o Wi-Fi atrapalha pouco o controle** [Certo: cerca de 370 pacotes por fase, com o Preto em movimento e o Roxo parado, sem tráfego de Wi-Fi]:

| Wi-Fi | Mediana | p90 | p99 | Pior |
|---|---|---|---|---|
| Ligado | 19,5 ms | 20,6 ms | 24,6 ms | 30 ms |
| Desligado | 15,6 ms | 20,8 ms | 24,9 ms | 29 ms |

O número é o intervalo entre pacotes do controle (cerca de 50 a 60 por segundo), não o atraso total até a tela. Esse eu não medi: precisaria de câmera lenta.

**Na prática:**
- **Para jogar:** Wi-Fi desligado no painel rápido. Ganho no controle pequeno; o maior efeito é parar a Tailscale, que chegou a 121% de CPU tentando reconectar sem rede [Certo: `top`].
- **Fone:** cabo P2 durante o jogo; tira um aparelho do Bluetooth.
- **Internet com os dois controles ligados:** 4G, que não disputa a faixa [Certo: funcionou com os dois ligados]. Gasta o plano.
- **Depois de jogar:** desligue os controles (Mode por 5 s). **O Wi-Fi não volta sozinho:** depois de sufocado, ele não reconectou em 2 minutos sem nenhum controle, e voltou em 6 s ao ser desligado e religado no painel rápido, com 2 a 20 ms e 0% de perda [Certo: 04/11]. Não conte com o desligamento automático: os dois ficaram ligados e parados por mais de 25 minutos, e o Wi-Fi seguiu sem IP. Celular sem internet: é a primeira coisa a conferir.
- 5 GHz resolveria em tese, mas o celular só viu redes de 2,4 GHz e não confirmei se o roteador ou o aparelho têm 5 GHz.

**5 GHz não é saída (04/11):** o SM-A125M é só de 2,4 GHz [Provável: Vodafone, Devicebeast e Wikipédia; sem ficha oficial da Samsung], e nas leituras de hoje o aparelho não mostrou nenhuma frequência de 5 GHz. Não é defeito. Com dois controles: dados móveis, ou Wi-Fi desligado.

## Controle pelo cabo USB-C (pedido do Rafael, 04/11)

**O celular tem tudo o que precisa [Certo: lido no aparelho]:** recurso `usb.host`, porta que alterna entre os dois papéis, e no kernel os drivers `xpad` (Xbox) e `usbhid`/`hid-generic`. **Não foi testado:** a única porta estava no cabo do PC. O manual da GameSir só cita Android por Bluetooth, sem falar de cabo nem de OTG, então é suporte do Android, e não do fabricante. O cabo é o caminho sem rádio, e sem disputa com o Wi-Fi.

Como testar:
1. Cabo **USB-C para USB-C com dados**, ou adaptador OTG com o cabo do controle. Um cabo só de carga não serve.
2. Plugue com o controle desligado. Se a luz não indicar Android: **Menu + View por 2 s** alterna XInput, NS Pro e Android; o manual diz que isso vale em cabo e no receptor.
3. O ARENA aceita "Bluetooth ou cabo". Para medir e comparar, com o sem fio aberto: `python scripts\controle-medir.py`, que mostra o tipo de ligação.

**Limites:** só um controle por vez, porque há só uma porta; o outro fica no Bluetooth, situação em que o Wi-Fi ficou bem nas duas amostras. O celular alimenta o controle, então não carrega e a bateria desce mais rápido: comece com carga. A taxa de pacotes por cabo o manual não informa.

## App GameSir (`com.xiaoji.xtouch`, versão da China)

- Mostrar "Not Connected" era falta de internet: com rede, **Connect Now** vira "Connected" [Certo]. Pareamento no modo certo: **A + Mode, luz amarela** é o Android por Bluetooth; B + Mode, azul, é PC [Certo: manual].
- Menu do Nova Lite: Gamepad Test, Connection Tutorial, Product Manual, Feedback e Firmware Upgrade [Certo: telas]. **Nada de latência, zona morta ou mapeamento.** Firmware 7000 nos dois desde 31/10.
- O app gasta um núcleo inteiro (97% medido) quando fica sem rede: **fechar depois de usar**. Não aceitei a atualização 5.9.20 oferecida (pedido: não instalar nada), nem entrei em Firmware Upgrade, que desemparelha o controle.
- V-Touch (toques simulados) não foi ativado: exige depuração sem fio e sobreposição em app fechado da China, e o ARENA lê o controle direto, sem precisar disso.

## Atalhos físicos (só o Rafael pode acionar; não testados)

Manual oficial da GameSir, em cada controle; valem depois de reiniciar e desfazem com o mesmo atalho:
- **M + LT** e **M + RT** por 2 s: gatilho curto. Bom para ação; perde a pressão gradual, e o manual avisa que pode parecer defeito.
- **M + LS** e **M + RS** por 2 s: zona morta zero. Responde antes; se o personagem andar sozinho, desfaça.
- M + direcional cima ou baixo: força da vibração, em 5 níveis, do desligado a 100% (padrão 75%).
- M + A por 2 s: troca A com B e X com Y.
- M + botão: turbo de 20 Hz nesse botão, com o Home piscando em vermelho; o mesmo atalho desfaz, e dois toques em M limpam todos.
- Se o analógico ou o gatilho falhar: View + Logo + Menu até o branco piscar devagar; LT e RT até o fim 3 vezes, analógicos em círculo 3 vezes, A [Certo: manual; a FAQ da GameSir descreve outra ordem].
- Menu + View por 2 s troca o modo só no receptor ou no cabo: não vale no Bluetooth do celular.

## ARENA

Já estava no melhor para este aparelho, sem mudar nada [Certo: telas de Ajustes]: perfil Desempenho, leitura do controle no último instante (2), fila de imagens no mínimo (2), sincronia rígida ligada, espera antes de desenhar desligada. Não liguei a espera nem a resposta instantânea: gastam CPU, e a regra é fluido acima de tudo. Som tem mínimo de 64 ms no Android (`plataforma.py`).

- Jogador 1 é o primeiro controle conectado, depois o segundo [Certo: `arena-controles.patch`; não observado em jogo]. Ligue o Preto antes, se quiser ele como 1.
- Sem botão de tela com controle ligado, o menu do jogo abre com **L3 + R3** [Certo: `docs/ANDROID.md`]. O ajuste "Botões na tela" não foi visto na tela; o padrão do código é Automático.
- O repositório do ARENA não foi alterado.

## Controlar o telefone pelo controle (nativo)

Mapa do Android [Certo: `/system/usr/keychars/Generic.kcm`, e os botões chegaram ao aparelho]:

| Controle | Faz |
|---|---|
| Direcional e analógico esquerdo | Move a seleção |
| A, L3, R3, Menu | Confirmar |
| B | Voltar |
| View | Menu |
| X / Y | Apagar / Espaço |
| Captura | Foto da tela (`KEY_SYSRQ`; não conferi o arquivo) |

**Limites:** o **Mode não apareceu nas duas capturas**, então não conte com ele para ir à tela inicial; volte com B. Não há atalho nativo para Recentes, notificações nem volume. Telas feitas só para toque não respondem. Sem root não dá para trocar o mapa de teclas.

Rejeitados, com motivo: remapeador próprio pelo adb (`getevent` em pipe só entrega em blocos, e rodar um processo por evento pesa no jogo; morre ao reiniciar) e Universal Switch da Samsung, serviço de acessibilidade que ficaria entre o controle e o jogo [Palpite: atraso não medido].

## Desligamento automático

Sem ajuste [Certo: manual]: 10 min sem uso conectado, 3 min tentando reconectar, 1 min em pareamento. Por software não dá para mantê-los ligados. Testes com os controles: esperar o movimento em vez de marcar hora.

## G7 HE no PC e Need for Speed Underground 2 (04/11)
- Controle: só com fio, `USB\VID_3537&PID_1065`, XInput. Parado: 0,00% nos 4 eixos e gatilhos em 0 [Certo: medido com xinput1_4].
- FAQ oficial [Certo: gamesir.com]: firmware V6.40; zona morta 3 a 5, modo Raw, 250 Hz recomendados; gatilho curto M+LT ou M+RT; reset Xbox+Menu por 5 s ou M+Y. Atualizador manual oficial, sem Nexus: zip `G7_HE_and_SE_file_and_instruction` no CDN da GameSir (link no FAQ).
- Jogo, fora do git: `C:\Need For Speed Underground 2\scripts\NFSU_XtendedInput.ini` (cópia `.antes-g7he-0411`). Mapeamento: o Rafael pediu de volta como era (04/11), e voltou: nitro RT, freio de mão LT, olhar para trás B. Só a precisão mudou: analógicos 2% no jogo (eram 12%, porque o controle já tira 5%) e nitro e freio de mão só a partir de 85% do gatilho (`DeadzonePercent_AnalogTriggerDigital`, era 12%: antes disparavam ao encostar). Jogador 2 (`_P2`) segue 12%. NÃO testado dentro do jogo. Se o T4 Nova Lite for ao PC como jogador 1, medir o repouso dele: 2% pode ser pouco.
- Nexus 2.5.8, firmware V6.6.4 (o app diz que está atualizado). Perfil NFS (M+X), ajustado em 04/11 com o sim dele; RAW, Batman e GTA não foram tocados: analógicos com zona morta inicial 5 (o app avisa abaixo de 5: retorno incompleto ao centro; estavam em 6 e 3), anti-zona morta 0 (estava 6 e 3), curva linear, trajetória Bruto; gatilhos com zona morta inicial 3, curva linear e modo ultrassensível DESATIVADO (estava adaptativo, que tira a dosagem de acelerador e freio). 500 Hz, como já estava: o FAQ recomenda 250 só por causa de áudio em fone, e 1000 é apontado como instável. L4 e R4 e as vibrações ficaram como ele deixou. Repouso medido depois: 0,00% nos 4 eixos. Para jogo de tiro ou corrida digital, os outros perfis seguem como eram.
- Nexus: pacote da Loja com integridade quebrada (`Modified, NeedsRemediation`; eventos 54, 59 e 8104); reparar e re-registrar não resolveram. A GameSir só publica o Nexus pela Loja [Certo: gamesir.com/support/downloads]. `scripts\reinstalar-nexus.cmd` (quem roda é ele, porque há termos a aceitar) guarda os dados, tira o pacote e reinstala pelo winget, do servidor da Microsoft, sem abrir a Loja. Se falhar: atualizador manual acima e ajustes pelos atalhos do controle.
- G7 HE no celular: o manual em espanhol cita Android; as lojas citam só Xbox e PC. Falta ele confirmar no USB-C.
- T4 Nova Lite no PC: não medido; está com ele no celular.

## Falta testar

Jogo real com os dois controles e o Wi-Fi desligado; fone e dois controles sem o Wi-Fi; os atalhos físicos; o controle no USB-C. Tela escura sem bloquear: `TELA-APAGADA.md`.
