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
| "liga/desliga a lanterna" | `cel lanterna ligar` / `cel lanterna desligar` |
| "apaga/acende a tela" | `cel tela apagar` / `cel tela acender` |
| "tela acesa no carregador" | `cel acordado ligar` / `desligar` |

## Celular no OBS do PC: aula, gravação e live [Provado 05/11 ~22:15, pedido pelo próprio celular]
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

## Dados móveis, hotspot e o PC de longe [Provado 05/11]
- Pelos dados, o PC responde pela Tailscale (100.64.0.1): RDP 3389 (aFreeRDP), ponte 20130, OmniRoute 20128.
- Hotspot ligado: o `saida` PAUSA sozinho a saída de internet pelo PC (para o hotspot funcionar) e religa ao desligar.
- ScreenStream pela Tailscale: `http://100.64.0.2:8080` (filtros VPN e Público ligados no app). KDE Connect acha o PC pelo IP da Tailscale.

## Interface do Rafael (05/11)
- Tela inicial da Samsung em "Apenas a Tela inicial" (sem gaveta), 5 páginas (a 5ª vazia, para o papel rolante mostrar a imagem inteira); papel rolante com acessibilidade própria (não desligue). Nunca mude a ordem dos ícones.
- Telefone da Samsung removido; o padrão é o Fossify Telefone (a emergência continua no app da Samsung).
- Segunda tela: no PC, atalho "Segunda tela"; aqui, o Moonlight.
