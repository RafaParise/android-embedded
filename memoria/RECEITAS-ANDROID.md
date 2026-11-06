# RECEITAS-ANDROID: como o Matrix opera o Galaxy A12 (Android 12, One UI 4)

O Claude escreve; chega ao Matrix como `pc-receitas-android` e vale sem internet (`memoria buscar ...`).
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

## Câmera de viagem: FadCam em segundo plano + Organic Maps na tela [Provado no A12 em 06/11 ~13:00–14:16]
Por que o FadCam: o Open Camera FECHA a câmera ao sair da tela (código atual dele, `Preview.onPause` -> `closeCamera`); só grava em tela dividida.
O FadCam (F-Droid, GPL-3.0, 3.0.1, hash conferido com o índice assinado) grava como serviço, com o aviso na barra.
- Ativar: `cel viagem iniciar` (abre o FadCam, espera 7 s porque frio ele TRAVA se mandar gravar na hora, grava, abre o Organic Maps).
  Parar: `cel viagem parar` ou "Stop" no aviso do FadCam (barra de cima > aviso FadCam > Stop). Estado: `cel viagem status`.
- Onde ficam: cartão SD, pasta `Viagens` (`/storage/1A2B-3C4D/Viagens`), partes de 500 MB (~4 min a 16 Mbps): um travamento perde no máximo uma parte.
- Ajustes feitos (06/11): traseira (a única lente que o Android entrega a apps), 1080p, 30 qps (máximo real do A12: `aeAvailableTargetFpsRanges` até 30),
  H.264 a 16 Mbps (o A12 não grava HEVC; 16 é a dica do próprio app para 1080p), deitado, data e hora no vídeo, local (GPS) no arquivo,
  foco contínuo (não há foco fixo no infinito), sem redução de ruído (experimental), sem busca de atualização. App em inglês (não tem português).
- Medido: 3 min 9 s, 1920x1080, 15,9 Mbps, 0 erro ao decodificar; gravação seguiu com o Organic Maps em tela cheia, girando a tela e abrindo a barra de avisos.
- Calor: o `cel viagem` vigia a bateria a cada minuto e só AVISA (42 °C: aviso; 45 °C: aviso com vibração). Nada é fechado por ele.
- Quedas do FadCam [Certo: registro de falhas, 06/11]: reabrir o app durante a gravação às vezes o derruba. CONSERTO (06/11 ~15:10): a vigia
  do `cel viagem` (a cada 15 s) RETOMA sozinha a gravação e reabre o mapa (provado: queda forçada 15:08:11, nova parte 15:08:41, aviso
  "VOLTOU sozinha"); até 3 retomadas em 10 min, depois avisa "PAROU". A parte interrompida NÃO se perde: o FadCam grava MP4 fragmentado
  (moof), conferido: a parte cortada abriu com 20,5 s. O "Stop" do aviso do FadCam foi ESCONDIDO: parar = botão "Parar" do aviso
  "Gravando a viagem" (testado) ou o Matrix; qualquer outra parada é tratada como queda. (2) Lanterna durante a gravação: o FadCam acende, mas ao apagar TRAVA:
  `cel viagem lanterna` só explica. (3) O FadCam cria um arquivo vazio de ~1 KB ao começar pelo comando; o `cel viagem parar` apaga só esses.
- Precisa: `termux-am` (pkg) e o Termux com "Sobrepor a outros apps" (appops SYSTEM_ALERT_WINDOW allow, dado em 06/11; desfaz: `appops set com.termux SYSTEM_ALERT_WINDOW default`).

## Calor: por que a câmera fechava e o mapa ficava [Certo: código do SDHMS do próprio aparelho, decompilado em 06/11]
- O serviço térmico da Samsung (`com.sec.android.sdhms`, desativado desde 30/10 mas o Android o mantém rodando por ser persistente) tem o
  "Overheat App Kill": fecha à força (`forceStopPackageAsUser`) o app VISÍVEL na tela e apaga a tela. Poupa: tela inicial, apps de
  navegação (lista "Navigation", por isso o Organic Maps fica), a lista "except_ovt" e pacotes protegidos. Também tem `flash_led_disable`
  (o flash pisca/apaga no calor) e `camera_recording_disable`. Remover ou desligar exige root (decidido não fazer).
- Saída: gravar com o FadCam em segundo plano (`cel viagem`), que não é "visível" e por isso não entra na regra; o aviso de calor fica com o `cel viagem`.

## O celular reiniciou sozinho [06/11 08:05]
- Ver o motivo: `cel sh "getprop sys.boot.reason"`. `kernel_panic,...watchdog_timer...100s` = o sistema ficou 100 s sem responder.
- 06/11 (teste de estresse do Rafael: ScreenStream transmitindo, hotspot ligado e troca para o Wi-Fi da SEDUC): uns 100 s antes, netd, o
  serviço de ancoragem e outros tinham acabado de reiniciar (o Android caiu e recomeçou); depois ficaram parados esperando memória/disco e o
  driver de tela preso numa trava [Provável: registro do kernel]. Sem root não há conserto; diminui o risco: memória folgada antes de estressar
  (fechar o Organic Maps, 572 MB, e o Matrix), não trocar de Wi-Fi com hotspot + ScreenStream ligados.

## Matrix em potência máxima: frase → ação, troca de cérebro e RAM [Provado no A12 em 06/11 ~16:30–17:30]
- **Frase do jeito dele → comando:** `cel faz "frase"` (normaliza acento e caixa e roda o comando certo; `--lista` mostra as frases;
  `--mostra` só diz o que faria). "falta um detalhe" (saída 3) = perguntar só esse detalhe; "Nao reconheci" (saída 4) = procurar no
  Catálogo do QWEN.md. É a REGRA 1 no topo do QWEN.md: o Matrix roda `cel faz` antes de tudo. Conferido no aparelho: "libera a memoria
  do celular" → `cel otimizar`; "grava a viagem" → `cel viagem iniciar`. 27 frases nos testes.
- **Cérebro que troca sozinho (PC ↔ celular):** com a reserva pronta, o `ia`/`matrix` põe o CHAVEADOR em 127.0.0.1:20128 (no lugar da
  ponte fixa). Cada pedido vai ao OmniRoute do PC se ele responder; se o PC cair NO MEIO da conversa, vai ao OmniRoute do celular
  (o chaveador o liga sozinho, troca a chave pela local, avisa na barra "PC fora: o Matrix seguiu com o OmniRoute do celular"); quando o
  PC volta, volta a ele e desliga a reserva parada há 5 min. O Matrix não fecha. Ver qual está valendo: `ia status` (linha "Cerebro agora").
  Medido no A12: PC no ar = rota ao PC; "PC fora" (porta fechada) = 1º pedido respondido pela reserva em 77 s (a reserva sobe em ~70 s,
  precisa de ~800 MB livres: se recusar, `cel otimizar`); ao fechar, chaveador e reserva saem sozinhos. Desligar a troca: `IA_CHAVEADOR=0 ia`.
  Por que a reserva não fica ligada SEMPRE: custa ~400 MB de RAM o tempo todo (de 3,8 GB), contra o pedido de RAM livre; ela liga sozinha
  quando precisa e a vigia do chaveador a liga assim que o PC some, antes do próximo pedido.
- **Um processo só:** o Matrix abria dois `node` (um "supervisor" de ~30 MB); desde 06/11 `QWEN_CODE_NO_RELAUNCH=true` no `ia`
  (no Linux o Qwen 0.26.5 já liga o `gc` no próprio processo; conferido no `cli-entry.js`). Provado: um processo. `IA_RELANCAR=1` volta.
- **Liberar RAM e CPU:** `cel otimizar` (fecha com `am kill` os apps PARADOS em cache, que continuam recebendo avisos; `force-stop` só nos
  utilitários parados (CPU Info, Binary Eye, LocalSend) e no FadCam parado; nada visível, nada com serviço, nenhum `com.android.*`, gms,
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
- Foto da tela: `cel sh "screencap -p /sdcard/Pictures/Screenshots/matrix-$(date +%H%M%S).png"`.
- Gravar a tela: `cel sh "screenrecord --time-limit 30 /sdcard/Movies/matrix.mp4"` (até 180 s).

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
- Instalar: peça ao Claude (F-Droid com hash conferido); o Matrix não instala APK por conta própria. Desinstalar: nunca (bloqueado).
- Procurar arquivo: `cel procurar TEXTO`; nos projetos do cartão: `memoria buscar TEXTO` (o índice tem o texto de todos os arquivos).
- Cartão SD: `/storage/1A2B-3C4D` (exFAT, 477 GB); a memória do Matrix fica em `Android/data/com.termux/files/matrix-memoria`.

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

## Dados móveis, hotspot e o PC de longe [Provado 05/11]
- Pelos dados, o PC responde pela Tailscale (100.64.0.1): RDP 3389 (aFreeRDP), ponte 20130, OmniRoute 20128.
- Hotspot ligado (desde 06/11): a saída pelo PC CONTINUA (o celular segue sem filtro). O hotspot em si sai pela rede em uso: com o Wi-Fi da escola, o notebook pega o filtro (use `link internet`); com os dados móveis, sai livre. `saida hotspot pausar` volta ao jeito antigo.
- Escola (06/11): SEDUC-MAQ (notebooks) e SEDUC-ALUNOS (celulares) não se enxergam; o notebook na SEDUC-MAQ não abre `http://10.x...:8080` do celular. Para mostrar a tela no notebook da escola: notebook no hotspot do celular e o endereço do hotspot, ou o link público do `link tela`.
- ScreenStream pela Tailscale: `http://100.64.0.2:8080` (filtros VPN e Público ligados no app). KDE Connect acha o PC pelo IP da Tailscale.

## Interface do Rafael (05/11)
- Tela inicial da Samsung em "Apenas a Tela inicial" (sem gaveta), 5 páginas (a 5ª vazia, para o papel rolante mostrar a imagem inteira); papel rolante com acessibilidade própria (não desligue). Nunca mude a ordem dos ícones.
- Telefone da Samsung removido; o padrão é o Fossify Telefone (a emergência continua no app da Samsung).
- Segunda tela: no PC, atalho "Segunda tela"; aqui, o Moonlight.
