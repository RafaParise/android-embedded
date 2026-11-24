# RECEITAS-ANDROID: como o Univo opera o Galaxy A12 (Android 12, One UI 4)

O Claude escreve; chega ao Univo como `pc-receitas-android` e vale sem internet (`memoria buscar ...`).
Tudo pelo `cel` (porta 5555 do adb: qualquer rede). Marcas: [Conferido 05/11] = o comando existe neste aparelho
(consulta, sem mudar nada); [Sem conferir] = documentação do Android, testar antes de confiar.

## Pedido direto = comando direto (regra do Rafael, 05/11: "ativar apenas falando, sem ficar procurando")
Se o pedido bate com uma linha daqui, rode o comando NA HORA, sem buscar antes, e mostre a saída real.
| Ele fala | Você roda |
|---|---|
| "câmera do celular na aula", "vira webcam do PC" | `cel obs camera` (selfie: `cel obs frontal`); no site: "OBS Virtual Camera" |
| "grava a câmera", "grava um vídeo no PC" | `cel obs gravar` |
| "grava a minha tela" | `cel obs gravar-tela` |
| "para de gravar", "salva" | `cel obs parar-gravacao` |
| "começa a live" / "para a live" | `cel obs tela` (ou `camera`) e `cel obs live` / `cel obs parar-live` |
| "desliga a câmera do PC", "desliga tudo do OBS" | `cel obs desligar` |
| "o que está ligado no PC?" | `cel obs status` |
| "manda minha tela para a TV/aluno", "compartilha esse arquivo/app" | `link tela` / `link arquivo CAMINHO` / `link app PACOTE`; `link parar` |
| "tela com som", "o som não sai na TV/notebook" | `link tela --som` (ScreenStream no modo RTSP; receita no `link`) |
| "internet livre no notebook", "o notebook no hotspot não abre os sites" | `link internet` (proxy; ele configura o proxy no notebook) |
| "grava a viagem", "câmera do carro", "grava enquanto uso o mapa" | `cel viagem iniciar` · `cel viagem parar` · `cel viagem status` |
| "faixa preta na câmera do OBS" | `cel obs verificar` |
| "faixas cinza no navegador", "não fica tela cheia na TV/notebook" | `link tela --preencher` (celular deitado) |
| "o hotspot tirou a VPN", "pausa a saída com o hotspot" | `saida hotspot status` / `saida hotspot manter` / `saida hotspot pausar` |
| "manda essa foto/vídeo/arquivo pro PC" | `cel enviar-pc /sdcard/CAMINHO` (chega em Downloads do PC; últimas fotos: `ls -t /sdcard/DCIM/Camera \| head -3`) |
| "celular como monitor do PC", "segunda tela" | `cel abrir-app com.limelight` e diga: RafaParise > Desktop; para sair de vez: segurar o Desktop > "Sair do Jogo" > SIM |
| "acha a TV", "controla a TV da sala" | `controle-tv procurar` e depois `controle-tv N volume+` / `mudo` / `ok` / `youtube` (sem N: a última TV); a TV precisa estar na mesma rede |
| "o que falta dos meus pedidos?", "organiza meus pedidos" | `pedidos` / `pedidos revisar` (todo pedido novo: `pedidos novo "..."` antes de começar) |
| "desliga o Wi-Fi e os dados", "modo avião" | RECUSADO pelo `cel` (você ficaria sem internet e pararia no meio): diga a ele para usar o painel rápido |
| "liga/desliga a lanterna" | `cel lanterna ligar` / `cel lanterna desligar` |
| "apaga/acende a tela" | `cel tela apagar` / `cel tela acender` |
| "tela acesa no carregador" | `cel acordado ligar` / `desligar` |

## Celular no OBS do PC: aula, gravação e live [Provado 05/11 ~22:15, pedido pelo próprio celular]
- Faixa preta (06/11): ao ligar, o PC mede a tarja na janela do scrcpy (cropdetect), corta, põe a fonte do celular "cobrindo" a tela inteira do OBS e confere a câmera virtual (provado 06/11: "camera virtual SEM faixa"). Avulso: `cel obs verificar` (pelo PC: `webcam-celular.py verificar`). Celular em pé numa tela deitada sempre corta um pouco.
- O que é: a câmera OU a tela do celular entram no OBS do PC (scrcpy; cabo, Wi-Fi ou dados móveis pela Tailscale), e o OBS
  as entrega como "OBS Virtual Camera" (site da aula, Meet, Teams), grava em `D:\Vídeos\Celular OBS` (MP4) ou faz live.
- Do celular: `cel obs camera|frontal|tela|gravar|gravar-tela|parar-gravacao|live|parar-live|desligar|status` (vai pela ponte do PC).
- Do PC ou pelo aFreeRDP: atalho "Celular no OBS" na área de trabalho (menu de 1 a 9).
- A câmera virtual liga SOZINHA, mesmo com o OBS do Estúdio já aberto, e a cena no ar passa para a da webcam
  (05/11: na aula ela estava desligada e o site só mostrava o logo do OBS com a câmera riscada).
- Site sem câmera ou sem "compartilhar tela": o Windows estava NEGANDO câmera e captura de tela (o microfone, permitido,
  funcionava). Liberado em 05/11; se voltar, `cel obs status` avisa e o Claude roda `pc-permissoes-aula.ps1 -Aplicar`.
- Nos dados móveis a câmera gasta ~900 MB por hora: avise antes. Modo câmera escurece a tela do celular (a câmera continua).
- `gravar-tela` leva o som do celular; o microfone do celular fica MUDO sem fone (privacidade, `cel microfone status`).
- Live: o destino e a chave ficam no OBS do PC (o Rafael configura uma vez); nunca peça nem grave a chave.

## Câmera de viagem: Open Camera em janela flutuante sobre o Organic Maps [Provado no A12 em 06/11 ~21:10–21:30]
O Rafael tirou o FadCam (06/11 à noite) e prefere o Open Camera ("dessa vez não fechou e nem esquentou muito", em 720p). O Open Camera
só grava VISÍVEL; por isso o `cel viagem` o abre numa JANELA FLUTUANTE (pop-up da Samsung) no canto de cima, por cima do mapa em tela cheia.
- Ativar: `cel viagem iniciar` (abre o Organic Maps, abre o Open Camera com `am start --windowingMode 5`, põe a janela no canto com
  `am task resize`, toca na barra da janela para dar o foco e aperta volume para cima: no Open Camera isso começa/para a gravação; o volume
  de mídia não muda). `--sem-mapa` não abre o mapa. Parar: botão "Parar" do aviso "Gravando a viagem" ou `cel viagem parar` (para pelo
  volume, confere que o arquivo parou de crescer e só então fecha a janela). Estado: `cel viagem status`. Precisa da conexão do `cel` (5555).
- Sem a conexão: à mão, abra o Organic Maps, depois o Open Camera em janela pop-up (Recentes > ícone do app > Abrir em visualização pop-up) e grave.
- Onde ficam: cartão SD, pasta `Dashcam` (a pasta do Open Camera), `VID_*.mp4` + `.srt` (data, hora e GPS).
- Ajustes do vídeo para viagem, dia e noite (06/11 ~21:10; cópia antes: Open Camera > Configurações > Settings manager > Restore settings >
  `BACKUP_OC_20261106_210930`): 1280x720 (escolha dele: esquenta menos), estabilização ligada, MP4/H.264, taxa de bits padrão (medido ~9 Mbps),
  quadros "Padrão" (à noite a câmera pode baixar os quadros para clarear; o A12 vai até 30), partes de 20 min com "Repetir 10x" (até 3h40
  seguidas; era 1 h), reinício no tamanho máximo ligado, "Travar tela enquanto filma" LIGADO (um toque sem querer não para; deslize para
  destravar), lanterna durante a filmagem desligada, aviso de bateria crítica ligado, legendas .srt ligadas. Foto e detecção de rosto: não mexidos.
- Calor: só AVISO (42 °C aviso; 45 °C aviso com vibração). O SDHMS da Samsung pode fechar a câmera no calor e sem root isso NÃO sai
  (código decompilado em 06/11: só poupa tela inicial, apps de navegação, listas embutidas e da Samsung, Gear VR e modo VR, que o A12 não tem
  — `cmd vr` não existe). Contorno provado: se a câmera cair, a vigia (15 s) acende a tela, espera o desbloqueio se precisar e reabre a
  câmera gravando (queda forçada às 21:24:55, novo arquivo às 21:25:26); o pedaço já gravado NÃO se perde (quem grava é o serviço de mídia do
  Android: o arquivo cortado à força abriu inteiro, 28 s, ffmpeg sem erro). Desiste só depois de 40 tentativas em 10 min.
- Parou pelo próprio Open Camera (ou acabaram as 11 partes)? A vigia respeita e avisa "Gravação parada no Open Camera".
- Lanterna com a câmera gravando: o Android não libera (a câmera está em uso); `cel viagem lanterna` só explica.

## Calor: por que a câmera fechava e o mapa ficava [Certo: código do SDHMS do próprio aparelho, decompilado em 06/11]
- O serviço térmico da Samsung (`com.sec.android.sdhms`, desativado desde 30/10 mas o Android o mantém rodando por ser persistente) tem o
  "Overheat App Kill": fecha à força (`forceStopPackageAsUser`) o app VISÍVEL na tela e apaga a tela. Poupa: tela inicial, apps de
  navegação (lista "Navigation", por isso o Organic Maps fica), a lista "except_ovt" e pacotes protegidos. Também tem `flash_led_disable`
  (o flash pisca/apaga no calor) e `camera_recording_disable`. Remover ou desligar exige root (decidido não fazer).
- Saída (06/11 noite, com o Open Camera): a câmera que o calor fecha VOLTA sozinha pelo `cel viagem` e o que já foi gravado fica salvo (seção acima).

## O celular reiniciou sozinho [06/11 08:05]
- Ver o motivo: `cel sh "getprop sys.boot.reason"`. `kernel_panic,...watchdog_timer...100s` = o sistema ficou 100 s sem responder.
- 06/11 (teste de estresse do Rafael: ScreenStream transmitindo, hotspot ligado e troca para o Wi-Fi da SEDUC): uns 100 s antes, netd, o
  serviço de ancoragem e outros tinham acabado de reiniciar (o Android caiu e recomeçou); depois ficaram parados esperando memória/disco e o
  driver de tela preso numa trava [Provável: registro do kernel]. Sem root não há conserto; diminui o risco: memória folgada antes de estressar
  (fechar o Organic Maps, 572 MB, e o Univo), não trocar de Wi-Fi com hotspot + ScreenStream ligados.

## Univo em potência máxima: frase → ação, troca de cérebro e RAM [Provado no A12 em 06/11 ~16:30–17:30]
- **Frase do jeito dele → comando:** `cel faz "frase"` (normaliza acento e caixa e roda o comando certo; `--lista` mostra as frases;
  `--mostra` só diz o que faria). "falta um detalhe" (saída 3) = perguntar só esse detalhe; "Nao reconheci" (saída 4) = procurar no
  Catálogo do QWEN.md. É a REGRA 1 no topo do QWEN.md: o Univo roda `cel faz` antes de tudo. Conferido no aparelho: "libera a memoria
  do celular" → `cel otimizar`; "grava a viagem" → `cel viagem iniciar`. 27 frases nos testes.
- **Cérebro que troca sozinho (PC ↔ celular):** com a reserva pronta, o `ia`/`univo` põe o CHAVEADOR em 127.0.0.1:20128 (no lugar da
  ponte fixa). Cada pedido vai ao OmniRoute do PC se ele responder; se o PC cair NO MEIO da conversa, vai ao OmniRoute do celular
  (o chaveador o liga sozinho, troca a chave pela local, avisa na barra "PC fora: o Univo seguiu com o OmniRoute do celular"); quando o
  PC volta, volta a ele e desliga a reserva parada há 5 min. O Univo não fecha. Ver qual está valendo: `ia status` (linha "Cerebro agora").
  Medido no A12: PC no ar = rota ao PC; "PC fora" (porta fechada) = 1º pedido respondido pela reserva em 77 s (a reserva sobe em ~70 s,
  precisa de ~800 MB livres: se recusar, `cel otimizar`); ao fechar, chaveador e reserva saem sozinhos. Desligar a troca: `IA_CHAVEADOR=0 ia`.
  Segurança: o chaveador só atende quem manda a chave do Univo (a do `~/.qwen/.env`, comparada em tempo constante); outro app do celular
  que abra a 20128 recebe 401, sem repasse e sem ligar a reserva (provado no A12: certa 200, errada 401, sem chave 401).
  Por que a reserva não fica ligada SEMPRE: custa ~400 MB de RAM o tempo todo (de 3,8 GB), contra o pedido de RAM livre; ela liga sozinha
  quando precisa e a vigia do chaveador a liga assim que o PC some, antes do próximo pedido.
- **Um processo só:** o Univo abria dois `node` (um "supervisor" de ~30 MB); desde 06/11 `QWEN_CODE_NO_RELAUNCH=true` no `ia`
  (no Linux o Qwen 0.26.5 já liga o `gc` no próprio processo; conferido no `cli-entry.js`). Provado: um processo. `IA_RELANCAR=1` volta.
- **Liberar RAM e CPU:** `cel otimizar` (fecha com `am kill` os apps PARADOS em cache, que continuam recebendo avisos; `force-stop` só nos
  utilitários parados (CPU Info, Binary Eye, LocalSend); nada visível, nada com serviço, nenhum `com.android.*`, gms,
  teclado, telefone, SMS, relógio, tela inicial, papel, Termux, Tailscale, KDE Connect, EnforceDoze). Mostra a RAM antes e depois.
  Medido: 1190 → 1584 MB (+393 MB, 17 apps). `cel otimizar --tudo` encerra também o ScreenStream transmitindo à toa (se nenhum `link` estiver no ar).
- **O que fica rodando sempre e por quê (revisado em 06/11):** vigia da tela (`app_process Tela`, 24 MB: o gesto de apagar e o Wi-Fi turbo),
  guarda da `saida` (23 s de CPU em 8 h; espaçar os testes atrasaria a volta da internet quando o PC cai, hoje 33 s: mantido), `guarda`
  (inotifywait, só acorda com arquivo novo), Termux:Boot. Nenhum deles vale trocar: o custo medido é quase zero.
- **Papel de parede:** sem faixa preta em pé e deitado, e deitado ele fica FIXO ao arrastar entre as páginas (app `br.embeeded.papel`, 06/11).

## Regra de ouro para operar qualquer app (o "olho e dedo")
1. `cel abrir-app PACOTE` (ache o pacote: `cel apps texto`), ou `cel abrir TELA` para Configurações.
2. `cel ler` lista o que há na tela, numerado, com o centro de cada item. `cel ler TEXTO` filtra.
3. `cel tocar N` ou `cel tocar "texto"`; campo de texto: tocar nele e `cel digitar "texto"` (sem acento).
4. `cel ler` DE NOVO para conferir que mudou. Nunca encadeie 3 toques sem ler.
5. Mais itens: `cel rolar baixo`; voltar: `cel tecla voltar`; tela inicial: `cel tecla inicio`.
- O `cel tocar` RECUSA botão sem volta (apagar, desinstalar, pagar, Pix, transferir, desligar, reiniciar, permitir depuração).
  Esses ficam com a mão do Rafael: diga a ele o que tocar.
- O `cel ler` mascara e-mail e número longo. Não leia conversas (WhatsApp, SMS) sem ele pedir. Nada da tela vai para a memória.
- O `uiautomator` às vezes falha em tela que ainda anima ("não parou de mexer"): espere 2 s e leia de novo.

## Hora, alarme e timer [Conferido 05/11: Relógio Fossify atende]
- Alarme: `cel sh "am start -a android.intent.action.SET_ALARM --ei android.intent.extra.alarm.HOUR 6 --ei android.intent.extra.alarm.MINUTES 30 --es android.intent.extra.alarm.MESSAGE 'Escola'"` (abre o Relógio já preenchido; confira com `cel ler` e toque em salvar).
- Timer: `cel sh "am start -a android.intent.action.SET_TIMER --ei android.intent.extra.alarm.LENGTH 600"` (segundos).

## Som, Não Perturbe e tela
- Não Perturbe: `cel sh "cmd notification set_dnd priority"` (só prioridade), `alarms` (só alarmes), `on` (silêncio total), `off` [Conferido 05/11].
- Volume da mídia: `cel sh "cmd media_session volume --stream 3 --set 8"` (0 a 15; `--get` lê) [Conferido 05/11: o comando existe].
- Brilho: `cel sh "settings put system screen_brightness_mode 0; settings put system screen_brightness 120"` (0 a 255; modo 1 = automático). Estava em 66 em 05/11.
- Brilho automático (adaptável): JÁ ESTÁ DESLIGADO (`screen_brightness_mode` = 0, conferido em 05/11 21:05). "Onde configuro?": `cel abrir tela` (Configurações > Visor) e diga a ele "Brilho adaptável" lá dentro; não precisa buscar mais nada.
- Lanterna: `cel lanterna ligar` / `cel lanterna desligar` (Termux:API; funciona sem a depuração sem fio). Não procure outra receita.
- Rotação: `cel sh "settings put system accelerometer_rotation 1"` (1 = automática; o Rafael usa automática).
- Escurecer sem bloquear: `cel tela apagar` / `cel tela acender`. NUNCA `keyevent 26`/`223` nem `SurfaceControl` (regras do projeto).
- Foto da tela: `cel sh "screencap -p /sdcard/Pictures/Screenshots/univo-$(date +%H%M%S).png"`.
- Gravar a tela: `cel sh "screenrecord --time-limit 30 /sdcard/Movies/univo.mp4"` (até 180 s).

## Bateria, rede e localização
- Economia de energia: `cel sh "settings put global low_power 1"` (0 desliga) [Sem conferir o efeito na One UI; `cmd power set-mode` também existe].
- Economia de dados: `cel economia-dados ligar|desligar|status`.
- Wi-Fi, Bluetooth, dados, modo avião: `cel wifi|bluetooth|dados|aviao ligar|desligar`. Desligar o Wi-Fi não derruba mais o `cel` (a 5555 segue pelos dados), mas avise antes.
- Localização: `cel sh "cmd location set-location-enabled true"` (`is-location-enabled` lê) [Conferido 05/11].
- Painel de notificações: `cel sh "cmd statusbar expand-notifications"`; atalhos rápidos: `expand-settings`; fechar: `collapse`.

## Ligar, mensagem, navegador e mapas (abrem; quem confirma é o Rafael)
- Ligação: `cel sh "am start -a android.intent.action.DIAL -d tel:NUMERO"` só DISCA (abre o Telefone Fossify com o número). Ligar de verdade só com o pedido dele.
- SMS: `cel sh "am start -a android.intent.action.SENDTO -d sms:NUMERO --es sms_body 'texto'"` abre a conversa no Fossify Mensagens [Conferido 05/11]; o envio é com ele.
- Página: `cel sh "am start -a android.intent.action.VIEW -d https://exemplo.com"` (abre no Fennec).
- Mapa: `cel sh "am start -a android.intent.action.VIEW -d 'geo:0,0?q=escola estadual'"` (Organic Maps; a busca principal não acha favoritos importados).
- Câmera: `cel abrir-app net.sourceforge.opencamera` (a intenção de captura não tem app neste aparelho, conferido 05/11).

## Opcionais que o Rafael pediu (05/11): só quando ele pedir
- Permanecer acordado enquanto carrega: `cel acordado status|ligar|desligar` (7 = ligado no cabo, no carregador e sem fio; 0 = desligado; desde 05/11 ~17:35, testado no aparelho). Esquenta a tela se ficar horas ligado: lembre isso a ele.
- Contador de taxa de atualização: a tela do A12 é fixa em 60 Hz; o contador só mostraria 60. Explique e não ligue.
- Opções do desenvolvedor: ficam ESCONDIDAS (`development_settings_enabled 0`) para o gov.br abrir; a depuração continua. Nunca religue o menu sem ele pedir.

## Voz (ditado offline, desde 05/11)
- Ditar: abra o campo de texto e toque no microfone do HeliBoard; ou `cel sh "ime set org.woheller69.whisper/com.whispertflite.WhisperInputMethodService"` e o Rafael segura o botão enquanto fala; volte ao teclado com `cel sh "ime set helium314.keyboard/.latin.LatinIME"`.
- Ver se está pronto: `cel sh "settings get secure voice_recognition_service"` deve mostrar `org.woheller69.whisper/...WhisperRecognitionService`.
- Microfone: só `cel microfone status`; não troque o modo para ditar (o `sempre` estraga o som do JBL). Detalhes: `memoria ler pc-voz-offline`.

## Apps e arquivos
- Lista: `cel apps texto`. Abrir: `cel abrir-app PACOTE`. Fechar à força: `cel sh "am force-stop PACOTE"` (reversível: só fecha).
- Instalar: peça ao Claude (F-Droid com hash conferido); o Univo não instala APK por conta própria. Desinstalar: nunca (bloqueado).
- Procurar arquivo: `cel procurar TEXTO`; nos projetos do cartão: `memoria buscar TEXTO` (o índice tem o texto de todos os arquivos).
- Cartão SD: `/storage/1A2B-3C4D` (exFAT, 477 GB); a memória do Univo fica em `Android/data/com.termux/files/univo-memoria`.

## Compartilhar com qualquer pessoa, de qualquer celular ou PC: `link` [Provado 05/11 ~21:55]
Para quê: mandar a TELA, um ARQUIVO ou um APP para quem não tem nenhum app (celular de aluno nos dados móveis, smart TV,
notebook no Wi-Fi da escola, iPhone, Xiaomi). Abre em qualquer navegador. O Quick Share da Samsung NÃO volta (pedido dele).
- Tela: o Rafael abre o ScreenStream e toca "Iniciar transmissão" (o Android pede confirmação, é a mão dele); depois `link tela`.
  Mostra o link https (Cloudflare, grátis, sem conta), o QR no Termux e copia o link. `--minutos N` (padrão 120, máx. 720);
  `--local` = só os endereços da mesma rede ou do hotspot, sem internet. Sem PIN no ScreenStream, quem tiver o link vê a tela:
  avise; com PIN, um aluno que errar o PIN bloqueia o link para todos (todos chegam pelo mesmo intermediário).
- Arquivo: `link arquivo CAMINHO [CAMINHO...]` (foto, vídeo, PDF); quem abre o link baixa. Recusa senha, chave, `.env`, `.ssh`, MAPAO.
- App: `link app PACOTE` (ache com `cel apps texto`); vira `pacote-versão.apk`. App dividido (split) é recusado: aí use o LocalSend.
- `link status` mostra o que está no ar; `link parar` derruba tudo (o link morre na hora). Ele também para sozinho no fim do tempo.
- No fim, lembre o Rafael de tocar em "Parar" no ScreenStream (a transmissão segue até ele parar).
- Falhou "o túnel não saiu": a internet do celular caiu ou a Cloudflare recusou; o link local (`--local`) continua valendo.
- **Tela COM SOM (06/11): `link tela --som`.** O modo de sempre (Local, MJPEG) NÃO tem som [Certo: README do ScreenStream]. Com som: no ScreenStream, Modo = RTSP (Servidor; padrão porta 8554, caminho `screen` [Certo: `RtspSettings.kt`]), em Áudio ligar "Áudio do dispositivo" (vem desligado), Vídeo = H.264, Iniciar; depois `link tela --som`. O ffmpeg do Termux (`pkg install ffmpeg`, uma vez) copia o vídeo sem recodificar e passa o som para AAC, em HLS; a página toca em qualquer navegador (hls.js 1.5.20, Apache-2.0, baixado uma vez e conferido por SHA-256; sem ele só Safari e algumas TVs). Quem abre toca em "Toque para ouvir o som" (o navegador não toca som sozinho). Atraso: alguns segundos. O comando avisa se veio H.265 ou sem som. O RTSP do ScreenStream não tem senha no modo servidor: quem está na mesma rede consegue abrir `rtsp://IP:8554/screen`. Feito sem o celular (06/11): falta provar no aparelho.
- **Tela cheia no navegador (06/11):** todo `link tela` passa pelo intermediário: fundo PRETO (era cinza, cor do ScreenStream) e dois toques/cliques = tela cheia. `link tela --preencher`: a página diz ao celular o tamanho da tela de quem assiste e o celular desenha nessa proporção (mesma regra do `segunda-tela.py`: 16:9 -> `wm size 720x1280`); precisa do celular DEITADO e da depuração sem fio do `cel`; `link parar` devolve o tamanho normal. Trocou de rede? O link público (https) segue o mesmo e o intermediário acha o ScreenStream no endereço novo; o local muda.
- **Internet para o notebook do hotspot (06/11): `link internet`** — receita em `VPN-SEMPRE-ATIVA.md` (proxy na porta 3128; ele configura o proxy no Windows e DESATIVA ao terminar).

## Telemetria SÓ PELO CABO, em qualquer lugar (19-20/11) — usar SEMPRE o comando `telemetria` do kit
Meta do Rafael (20/11): o A12 mede qualquer aparelho só com o cabo, sem depender de rede, Wi-Fi da escola ou PC de
casa. A ficha fica na fila do A12 (`~/kit/telemetria/fila/`) e vai ao PC depois com `telemetria enviar`, em casa.
| Aparelho no cabo | Comando no Termux do A12 | O que a pessoa faz |
|---|---|---|
| PC com Windows (notebook da escola) | `telemetria coletar pc-cabo --rotulo "Notebook sala 3"` | toca em "Ancoragem USB" no A12; no PC, Win+R e cola UMA linha (`irm http://10.x...:8765/CHAVE/c \| iex`) |
| Outro celular Android | `telemetria coletar cabo --rotulo "Celular X"` (adaptador OTG no A12) | no outro: Depuração USB ligada e "Permitir" |
| PC na mesma rede (sem cabo) | `telemetria coletar pc-rede notebook` | mesma linha, com o IP do Wi-Fi |
| Celular na mesma rede (sem cabo) | no outro `adb tcpip 5555`; no A12 `adb connect IP:5555` e `telemetria coletar android` | "Permitir" uma vez; depois `adb disconnect IP:5555` |
- O que vem do PC (lista fechada): fabricante/modelo, CPU, RAM, disco, GPU, Windows (edição, versão, build), Defender,
  energia, programas (até 150, só nome/versão sem números/editora: SÓ de PC), processos e serviços (contagens e top
  25 de memória). Do celular NUNCA vem lista de apps. Nunca: IP, MAC, serial, IMEI, SSID, nome de pessoa (o
  verificador recusa a ficha inteira, no A12 e de novo no PC).
- PROVADO: notebook da escola (Positivo N8440, i5-1345U, 15,6 GB, Win 11 Pro Education 24H2) pela rede em 20/11;
  Redmi 9i pelo A12 pela rede (adb) em 19/11. Falta: celular no OTG de verdade; PC com Linux/macOS pelo cabo (o
  servidor do cabo só entrega o coletor PowerShell).
- ERROS de 20/11 (já corrigidos): (1) `coletar pc-rede` gravava a ficha e quebrava (`p` inexistente) — a ficha fica
  na fila, `telemetria enviar` resolve; (2) a ponte do PC recusava as seções novas (`sistema`/`apps`/`processos`) e
  passava de 48 KB — atualizada (60 KB, inventário só com alvo pc); ponte reiniciada com `ponte-pc.ps1 -Parar/-Iniciar`;
  (3) ligar a Ancoragem USB troca a rede do A12 e derruba a sessão que o PC abriu por ssh: quando o PC comanda, rodar
  destacado (`setsid nohup bash -lc "telemetria coletar pc-cabo X" > ~/cabo.log 2>&1 &`) e ler o log; nunca `pkill -f`
  com o texto do próprio comando (mata a própria sessão).
- PROVADO SÓ PELO CABO (20/11 00h15): notebook da escola -> A12 pela Ancoragem USB (origem `cabo-usb`), ficha no PC.
  Se a janela do Win+R fecha rápido demais para ler o erro: Win+R `powershell`, colar a linha DENTRO dela; conferir
  `ipconfig | findstr 10.179` (sem resposta = o notebook não pegou a rede do cabo: driver ou bloqueio da escola).
  PowerShell de 32 bits só via os programas do WOW6432Node (17 de 46): o coletor lê as duas visões pelo .NET
  (Registry64/Registry32). O nome da ficha vem de `--rotulo "..."` (o texto solto depois do pc-cabo é ignorado).
- Dizer "funciona" só depois de testar o caso pedido (OUTRO aparelho no cabo), não o próprio A12.
- TODAS as entradas do FortiGate versáteis (20/11): `scripts/fortigate-portas.cmd` (o Rafael aplica, 2 senhas): internet
  (ALL, NAT, sem registro/inspeção = aceleração; nunca para a rede de casa) para a faixa do DHCP das portas 1 e 3-7
  (10.0.20.50-150), da DMZ (10.0.10.50-60) e da porta 2 (10.0.30.10-150); PC gerencia porta 2 e DMZ; DMZ alcança os
  apps de projeto do PC (8000-8099, 8780); DNS com BLOQUEIA_TELEMETRIA nas três. Qualquer aparelho, antigo ou novo:
  DHCP + IPv4. Sem UPnP (FortiOS 5.4 e CGNAT da operadora): console/TV que pede "NAT aberto" fica em NAT restrito.
- Anúncios bloqueados na casa toda, sem instalar nada (20/11): AdGuard DNS (94.140.14.14 / 94.140.15.15; IPv6
  2a10:50c0::ad1:ff / ::ad2:ff; DoH https://dns.adguard-dns.com/dns-query). FortiGate: `config system dns` (as LANs
  usam o DNS dele); ONT Huawei: DNS do DHCP da LAN (o Rafael, no 192.168.1.1); PC: Wi-Fi com DoH do AdGuard (feito).
  Testado: doubleclick/googleadservices = 0.0.0.0, globoplay e google normais. YouTube não sai por DNS. Se um app de
  vídeo travar esperando anúncio: DNS manual só naquele aparelho. Pedido de furar bloqueio de site pirata
  (RedeCanais): recusado; não montar VPN/proxy para isso.
- Porta 2 do FortiGate (switch da bancada, internal2, LAN2 10.0.30.x): sem internet e sem acesso do PC até o Rafael
  aplicar `scripts/fortigate-bancada.cmd` (20/11: internet para a faixa do DHCP .10-.150 (as reservas dos controles
  estão vazias: .10/.11 são faixa comum), nunca para a rede de casa; PC gerencia por ping/SSH/RDP/WinRM/adb/HTTP(S); DNS com BLOQUEIA_TELEMETRIA). Comando de FortiGate é texto
  para o Rafael; ele digita a senha.

## Ligar o PC desligado e teclado no Termux/RDP (19/11)
- PC SUSPENSO (atalho "Suspender PC (Moonlight acorda)" ou Iniciar > Energia > Suspender): o Wi-Fi do PC fica de
  guarda (WoWLAN armado em 19/11, só pacote mágico) e acorda pelo botão do próprio Moonlight ou pelo `ligar-pc`, sem
  passar pelo FortiGate. DESLIGADO de vez: só a placa de cabo, que depende da regra do FortiGate (senha do admin
  esquecida em 19/11; `scripts/fortigate-wol.cmd` aplica quando ele tiver a senha).
- PELOS DADOS MÓVEIS (19/11, ADIADO pelo Rafael: "deixa para lá"): não há aparelho sempre ligado em casa e a senha
  do FortiGate foi esquecida. Caminhos registrados: (a) ponte com celular/tablet Android velho na tomada + Tailscale
  (recomendado, grátis); (b) recuperar a senha: no 60D o console É a porta MGMT USB (mini-USB) e só fala com o
  FortiExplorer (cadastro grátis na Fortinet); a conta maintainer por ela costuma perder a janela de ~15 s (teste da
  própria Fortinet); `scripts/fortigate-recuperar-senha.ps1` serve só para console serial; reset de fábrica apaga a
  configuração (só com o sim). Mesmo com a senha, o 4G depende de a operadora não usar CGNAT (não confirmado).
- "liga o PC" / "acorda o computador": no Termux, `ligar-pc` (manda o pacote mágico à wan1 do FortiGate e espera o
  Sunshine responder até 3 min; `--sem-esperar`, `--status`). Só na rede de casa; pelos dados móveis não alcança. Só
  funciona depois de o Rafael aplicar `diagnostico/fortigate-wol-pc-19-11.cli` no console e ligar o WoL no BIOS.
  O botão de acordar do Moonlight não serve aqui (manda o MAC do Wi-Fi para a rede errada).
- Teclado não volta no Termux: dentro do Qwen Code era o mouse do Qwen (`ui.mouseTracking: false` resolve ao reabrir
  o `ia`); em qualquer programa, a tecla do teclado na barra de teclas extras (canto direito) reabre sem sair do app.
- RDP (aFreeRDP) trocando "/" por ";": na sessão remota, Win+Espaço até "POR ENG (Estados Unidos)"; voltar ao ABNT2
  no teclado físico do PC. Quando o F-Droid tiver o aFreeRDP 3.33.1, ligar "Use Android keyboard layout".

## Dados móveis, hotspot e o PC de longe [Provado 05/11]
- Pelos dados, o PC responde pela Tailscale (100.64.0.1): RDP 3389 (aFreeRDP), ponte 20130, OmniRoute 20128.
- Hotspot ligado (desde 06/11): a saída pelo PC CONTINUA (o celular segue sem filtro). O hotspot em si sai pela rede em uso: com o Wi-Fi da escola, o notebook pega o filtro (use `link internet`); com os dados móveis, sai livre. `saida hotspot pausar` volta ao jeito antigo.
- Escola (06/11): SEDUC-MAQ (notebooks) e SEDUC-ALUNOS (celulares) não se enxergam; o notebook na SEDUC-MAQ não abre `http://10.x...:8080` do celular. Para mostrar a tela no notebook da escola: notebook no hotspot do celular e o endereço do hotspot, ou o link público do `link tela`.
- ScreenStream pela Tailscale: `http://100.64.0.2:8080` (filtros VPN e Público ligados no app). KDE Connect acha o PC pelo IP da Tailscale.

## Doze, compilação e bateria (06/11)
- **Doze profundo mais cedo (ligado):**
  - Com o celular parado, sem cabo e de tela apagada, entra em cerca de 20 min, em vez de cerca de 1 h.
  - Conferir: `cel sh "device_config get device_idle inactive_to"`. O valor 600000 indica ligado.
  - Desfazer: `device_config delete device_idle inactive_to` e `device_config delete device_idle idle_after_inactive_to`.
  - Quem está na lista do Doze (Termux, Tailscale, SED, Relógio) não é afetado.
- **Não sugerir `compile -m speed`:** medido em 06/11, deixa os apps de 15% a 55% mais lentos para abrir neste A12. O padrão é `speed-profile`.
- **Saúde da bateria:** `saude.py` (no PC) mostra a estimativa da Samsung (ASOC, 86% em 06/11). Abaixo de 80% vira atenção.

## Interface do Rafael (05/11)
- Tela inicial da Samsung em "Apenas a Tela inicial" (sem gaveta), 5 páginas (a 5ª vazia, para o papel rolante mostrar a imagem inteira); papel rolante com acessibilidade própria (não desligue). Nunca mude a ordem dos ícones.
- Telefone da Samsung removido; o padrão é o Fossify Telefone (a emergência continua no app da Samsung).
- Segunda tela: no PC, atalho "Segunda tela"; aqui, o Moonlight.

## Repasse do ARENA: partida entre casas (10/11) [Provado 10/11 na rede de casa]
- O que é: o A12 passa os dados de uma casa para a outra quando dois alunos jogam juntos pelo ARENA ("Estamos em casas diferentes"), por um código de 6 números, sem lista pública. O PC é só mais um jogador.
- No Termux: `repasse ligar | desligar | estado | registro | testar`. Sobe sozinho quando o celular liga (linha no `iniciar-a12`). Porta 55440 TCP; parado, perto de 0% de CPU; não grava endereço de ninguém.
- Instalar ou atualizar (do PC, com o cabo): `python C:\Projetos\univo-sync\scripts\repasse_a12.py instalar` (copia o `repasse_proprio.py` do ARENA para `~/arena-repasse/`).
- Para a internet chegar nele: FortiGate (VIP e regra 6 no `provisionar_rede.py` do univo-sync) e porta 55440 encaminhada no roteador da operadora. Explicação das decisões: `C:\Projetos\arena-console\docs\REPASSE-PROPRIO.md`.

## Modelos locais da IA no cartão SD (13/11) [Provado 13/11 no A12]
- `~/modelos/qwen.gguf` e `qwen2.5-1.5b.gguf` (1,5 GB) foram para `/storage/1A2B-3C4D/Android/data/com.termux/files/modelos`;
  em `~/modelos` ficam atalhos (o `ia chat` e o `ia local` não mudaram). Abre do cartão em ~9 s, 14 tokens/s no 0,5B.
- Programa não roda do cartão (o Android não deixa executar de lá): Qwen Code, OmniRoute, glibc e OpenCode ficam na
  memória interna. A memória do Univo (`memoria`) já mora no cartão desde 05/11.

## IA sem o PC: `ia glm` (OpenCode + GLM 5.3 Flash grátis) (13/11) [Provado 13/11 no A12]
- O que é: o agente OpenCode com o GLM 5.3 Flash grátis do OpenCode Zen, direto do celular, só com internet: sem PC, sem OmniRoute, sem conta. Substitui o Ollama do PC (removido em 13/11).
- Usar: `ia glm` (abre na pasta do projeto), `ia glm "pedido"` (já com o pedido). No `ia` automático, se a nuvem do PC estiver fora, ele vem antes do modelo do celular. `ia status` mostra se está pronto.
- Instalar ou atualizar: `ia glm instalar` (glibc-runner do repositório oficial do Termux + binário oficial 1.19.5, SHA-256 conferido; fica em `~/opt/opencode`).
- Configuração em `~/.config/opencode/opencode.jsonc`: personalidade do `~/.qwen/QWEN.md` e as mesmas travas (deny) do Qwen; o `ia` só completa o que falta.
- Medido: ~21 s por resposta curta, ~0,5 GB de memória no pico. O grátis é "por tempo limitado"; sem retenção nem treino pela doc. Nunca mande dado de aluno.

## Relatorio de acompanhamento do estudante (pedido do professor, 17/11) [Ordoc; testado com aluno ficticio]
- O que e: o documento "tudo o que o estudante fez e o que falta nas plataformas" (EP + Tarefa SP), para coordenacao, conselho e responsaveis.
- Quem faz: o app Ordoc, no aparelho (tela "Relatorio do aluno"). O Univo NUNCA recebe nem guarda o nome, a nota ou a tela do aluno.
- Passo a passo: abrir o Ordoc nessa tela -> o professor digita nome, turma e escola -> "Gerar" (marca "Ler a EP de novo" se faz tempo que nao le; leva minutos) -> confere -> "Copiar o documento".
- Precisa: Sala do Futuro logada dentro do Ordoc (a EP e o Tarefa SP entram por ela). Login e do professor.
- Homonimos na turma: o Ordoc nao chuta, pede o nome completo. Fonte que falhou aparece como NAO LIDA, nunca como "nao fez".
- Nome nao encontrado: escreva como esta na chamada (17/11: 'y' em vez de 'i' e sem o sobrenome do cadastro nao achou); o Ordoc mostra os nomes parecidos da turma para o professor tocar no certo. A 1a leitura da EP leva ~40 min; as proximas usam a leitura guardada.

## Aula pratica a partir do pacote da semana (pedido do professor, 18/11) [repositorio aulas-praticas; feito com S24 e S25]
- O que e: o Registro da Aula (atividade que vai para o AVA) com plano, roteiro do professor, guia e um script de demonstracao.
- Fonte da verdade: o pacote da semana na plataforma EP = Material da Aula + Roteiro/Material de Apoio + enunciado do Registro + Pause e Responda (perguntas e respostas). Os tres falam a mesma lingua.
- Quem coleta: o Ordoc (script de leitura `ep_pacote_semana`), no PC pelo `pacote_semana.ps1`; a EP e logada pelo professor. Uma pagina por vez, com pausa.
- Quem escreve: o Claude no PC (modulo + script + `gerar_aulas.py`). O Univo explica o caminho, lembra a semana que falta (`memoria\ESTADO.md` do projeto) e nunca inventa objetivo ou habilidade: copia do slide.
- Cuidado: material da CDN com o mesmo codigo pode ser de outro assunto; roteiro oficial pode ter comando errado; vale o Registro e o slide, e o professor e avisado.
- Caso real variado: ARENA, Univo-Sync (bancada) ou Android Embedded; em Logica, o modelo usa outro tema para nao entregar a resposta.

## Mensagens de status do Univo (spinner), 18/11 [celular e PC, catalogo unico]
- O que e: enquanto o Univo pensa, a 1a frase reage ao assunto do pedido e as seguintes giram (troca a cada 8 s) ate a resposta.
- Ele fala: "as frases de carregamento estao repetindo" / "troca aquela frase" -> Voce: nao edite nada; abra pedido na caixa
  (`caixa pedido "frase de status: ..."`). O catalogo e do Claude: `scripts/celular-kit/status/frases-status.json` (casa-mae).
- Ele fala: "a primeira frase sumiu" -> Voce roda: `python3 ~/.qwen/univo-status/status_univo.py qwen-patch conferir`
  (desligada = o Qwen Code foi atualizado; peca ao Claude reinstalar o kit). Desligar de proposito: `... qwen-patch desfazer`.
- `ia qwen "pergunta"`: o mesmo spinner no terminal (some antes da resposta; Ctrl+C tambem o encerra).
- PC (Hermes): plugin `univo-status` + skin `univo`; desfazer pelo `instalar.ps1 -Desfazer` do univo-windows.


## Otimização completa de Xiaomi/Redmi com MIUI 12.5 (Redmi 9i Sport, 19/11/2026)
- Antes: listas `pm list packages -s/-3/-d` e `settings list global/secure/system` em `diagnostico/<aparelho>-<data>/`
  (fora do git). Nunca tocar em app da Play Store (`pm list packages -3 -i`: instalador `com.android.vending`) nem em
  APK que a pessoa instalou (ex.: app da SED); pré-instalado da Xiaomi que aparece como "-3" (instalador
  `com.xiaomi.discover`, ex.: Glance `com.miui.android.fashiongallery`, WPS lite) pode sair.
- Remoção reversível: `pm uninstall -k --user 0 <pacote>`; desfazer com `cmd package install-existing <pacote>` (gerar
  o DESFAZER.sh na hora). Saíram: telemetria e anúncios (analytics, msa.global, daemon, bugreport, cit, loggerui,
  engineermode/ygps/lbs), quick apps (hybrid), GetApps/Discover, Cleaner, Mi Pay, ShareMe, Mi Connect/Cast, Música,
  Clima, Notas, Agenda Xiaomi, Quick Ball, Scanner, RCS, teclado Mint (o padrão era o Gboard), Facebook de sistema,
  impressão, Google One/Pay Índia/Assistente Go/Lens/Android Auto/Bem-estar digital/Feedback/Turbo/YouTube/Maps/app
  Google/TalkBack. FICAM: Play Store, GMS/GSF, WebView, Chrome (login gov.br), Gmail, Gboard, câmera, galeria (+
  mediaeditor, gallery.player), telefone/contatos, SMS (com.android.mms), rádio FM (miui.fm, fmservice,
  android.fmradio), relógio, calculadora, arquivos, securitycenter (permissões do MIUI), powerkeeper, home,
  thememanager (tirar quebra papel de parede).
- Ajustes: animações 0.5; `wifi_scan_always_enabled 0`, `ble_scan_always_enabled 0`, `mobile_data_always_on 0`; DNS
  privado `dns.adguard-dns.com` (corta rastreador e anúncio; conferido que gov.br, Sala do Futuro, Play e Microsoft
  resolvem); `pm trim-caches 999G`; compilação ART com `setsid sh -c 'cmd package bg-dexopt-job ...' &` (a sessão do
  adb cai e mataria o job). Resultado: RAM livre 1,1 -> 1,8 GB.
- Conta Xiaomi: a PESSOA sai da conta antes (Configurações > Mi Account > Sair, com a senha); só depois remover
  account/finddevice/cloud/xmsf. Com o "Encontrar dispositivo" ligado, o bloqueio fica no servidor da Xiaomi e um
  reset pediria a senha.
- Cabo que cai (o adb reconecta com outro transport_id): comandos curtos com `timeout`, e o que é longo roda destacado
  no aparelho.
- NÃO remover no MIUI 12/12.5 (19/11, 23h): `com.xiaomi.finddevice` (o system_server o procura a cada minuto e, sem
  ele, mostra o aviso "FindMyDevice has been destroyed"); e, por segurança de inicialização, `thememanager` (+.module),
  `xiaomi.account`, `powerkeeper`, `guardprovider`, `cloudservice`, `micloud.sdk`, `micloudsync`. Sem a conta Mi eles
  ficam parados. Achar a origem de aviso que "aparece do nada": `logcat -d -b all | grep -i toast` (pkg=android =
  sistema) e o erro que se repete no mesmo minuto.
- Depois do debloat, SEMPRE um reinício de teste com o cabo ligado: ligar `development_settings_enabled 1` antes (garante
  o adb no boot), `adb reboot`, acompanhar `/proc/uptime` e `sys.boot_completed` (uptime que volta = loop), conferir
  `logcat -b crash`, ANR e as configurações; depois esconder o menu de novo e `adb tcpip 5555`. Redmi 9i: 75 s, 0 loop.
- Loop na inicialização depois de a bateria zerar (Redmi 9i, 744 ciclos em `/sys/class/power_supply/battery/cycle_count`):
  bateria gasta, liga com tensão baixa e reinicia. Não deixar zerar; se zerar, 30 min no carregador antes de ligar.
  Conferir o backup (`bmgr enabled`): no Redmi estava desligado e um reset apagou tudo (a pessoa escolhe; aqui só o
  backup do WhatsApp).
- Toque fantasma: medir parado, sem ninguém encostar, `timeout 15 getevent -l /dev/input/eventN | grep -c
  ABS_MT_POSITION_X` (o N do touchscreen em `getevent -p`) COM e SEM o cabo. Redmi 9i: 16 com cabo, 0 sem = ruído do
  carregador/cabo, não a tela.
- Privacidade do Google sem mexer no resto (19/11): ID de anúncio = `am start -a com.google.android.gms.settings.ADS_PRIVACY`
  (zerado = apagado); uso e diagnósticos e "Personalizar usando dados compartilhados" = Configurações > Google > Todos
  os serviços (a atividade não abre pelo adb); Gboard = `am start -n com.google.android.inputmethod.latin/
  com.google.android.apps.inputmethod.latin.preference.SettingsActivity` > Privacidade: desligar SÓ "Compartilhar
  estatísticas de uso" e "Melhorar para todos" (a personalização local fica). Teclado de app de banco (ex.: Next) vem
  dentro do app da Play: fica. Rolar a lista pelo MEIO da tela (do alto abre o seletor de contas, tela protegida).
- Otimização sem remover nada (MIUI 12.5 / Android 11, 19/11 23h40), tudo com desfazer em `diagnostico/`:
  `settings put secure upload_log_pref 0` e `upload_debug_log_pref 0` (programa de experiência e diagnóstico, que
  continuam LIGADOS mesmo com analytics removido); `global com.android.thememanager.preferences.using_theme_show_ad
  false`; `global pref_key_sys_app_auto_update 0`; `device_config put activity_manager use_compaction true` (RAM < 6
  GB); pacotes Xiaomi mantidos por segurança com `cmd appops set P RUN_ANY_IN_BACKGROUND ignore` (+RUN_IN_BACKGROUND)
  e `am set-standby-bucket P rare` (o grupo "restricted" só existe no Android 12+; app de sistema fica "5"=isento, a
  trava de fundo vale); app da Play que não precisa de fundo (Serasa, BlaBlaCar) só `rare`; `sm fstrim` e `pm
  trim-caches 999G`. App Segurança (pela tela): desligar "Verificar após instalação" e "Atualização automática" do
  Avast (o Play Protect já faz), "Receber recomendações", e "Limpar cache quando bloquear" = Nunca (fechar tudo 1 min
  depois de apagar atrasa notificação e força abertura do zero). NÃO dá: congelar apps em cache (kernel 4.19 sem
  cgroup v2 freeze; precisa 5.2+) e `network_recommendations_enabled` (o Google volta para 1). "type=com.xiaomi" no
  `dumpsys account` sem conta = só o autenticador registrado; conta logada aparece como Account{... type=com.xiaomi}.
- Um celular medindo outro pela rede: no outro, `adb tcpip 5555`; no Termux do A12 `adb connect IP:5555`, o outro
  pergunta "Permitir depuração?" (uma vez), `telemetria coletar android`, depois `adb disconnect`.

## Motor nativo a12m (Rust, só lê) — 20/11/2026
- O que é: sensor do A12 que roda como shell (`/data/local/tmp/a12m/a12m`). Não muda ajuste nenhum.
- Usar pelo PC: `adb -s SERIAL shell /data/local/tmp/a12m/a12m status` (ou `status --json --rotulo X` para comparar com
  o medir.py), `... episodios 20`, `... custo`. Pelo Termux, com o adb loopback do `cel`: `sh_ "/data/local/tmp/a12m/a12m status"`.
- Episódio = "o celular sofreu": início com quem usava CPU/RAM e fim com picos e duração. Muitos episódios na hora da
  aula = olhar o culpado; nenhum = o aparelho aguentou.
- Atualizar: `pwsh -File scripts\rotina-a12.ps1 -SemMedir` (confere SHA-256, manda o binário novo, religa o vigia).
- **No Termux, sem o PC (24/11): `a12-daemon`** (= `cel motor`).
  - Ligue a Depuração por Wi-Fi e rode `a12-daemon` (ou `a12-daemon PORTA`, que faz o `adb connect 127.0.0.1:PORTA` antes).
  - Ele liga o vigia, se não estiver rodando, e mostra o custo e a foto: memória, pressão, temperatura de AP e bateria, túneis da VPN.
  - Outras ações: `a12-daemon status`, `a12-daemon episodios 20`, `a12-daemon parar`.
- **Vigia 0.3 (24/11), a cada 15 s.** Além da pressão, grava:
  - `calor_inicio`/`calor_fim`: bateria ≥ 42 °C ou AP ≥ 48 °C; fecha abaixo de 40 °C e 45 °C;
  - `memoria_baixa_inicio`/`_fim`: abaixo de 500 MB disponíveis; fecha a partir de 650 MB;
  - `tuneis`: a VPN caiu ou voltou (`tun0`).
  - A temperatura vem do `dumpsys thermalservice`, porque o kernel é fechado ao shell.
- Não fazer: rodar o binário a partir do Termux direto (o Termux não lê /proc/stat nem os outros apps); pôr o vigia
  para "agir" (matar app, mudar bucket): o projeto mediu que piora (DECISOES 20/11).

