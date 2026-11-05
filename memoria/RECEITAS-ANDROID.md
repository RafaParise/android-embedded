# RECEITAS-ANDROID: como o Matrix opera o Galaxy A12 (Android 12, One UI 4)

O Claude escreve; chega ao Matrix como `pc-receitas-android` e vale sem internet (`memoria buscar ...`).
Tudo pelo `cel` (porta 5555 do adb: qualquer rede). Marcas: [Conferido 05/11] = o comando existe neste aparelho
(consulta, sem mudar nada); [Sem conferir] = documentação do Android, testar antes de confiar.

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

## Voz (ditado offline, desde 05/11)
- Ditar: abra o campo de texto e toque no microfone do HeliBoard; ou `cel sh "ime set org.woheller69.whisper/com.whispertflite.WhisperInputMethodService"` e o Rafael segura o botão enquanto fala; volte ao teclado com `cel sh "ime set helium314.keyboard/.latin.LatinIME"`.
- Ver se está pronto: `cel sh "settings get secure voice_recognition_service"` deve mostrar `org.woheller69.whisper/...WhisperRecognitionService`.
- Microfone: só `cel microfone status`; não troque o modo para ditar (o `sempre` estraga o som do JBL). Detalhes: `memoria ler pc-voz-offline`.

## Apps e arquivos
- Lista: `cel apps texto`. Abrir: `cel abrir-app PACOTE`. Fechar à força: `cel sh "am force-stop PACOTE"` (reversível: só fecha).
- Instalar: peça ao Claude (F-Droid com hash conferido); o Matrix não instala APK por conta própria. Desinstalar: nunca (bloqueado).
- Procurar arquivo: `cel procurar TEXTO`; nos projetos do cartão: `memoria buscar TEXTO` (o índice tem o texto de todos os arquivos).
- Cartão SD: `/storage/1A2B-3C4D` (exFAT, 477 GB); a memória do Matrix fica em `Android/data/com.termux/files/matrix-memoria`.

## Interface do Rafael (05/11)
- Tela inicial da Samsung em "Apenas a Tela inicial" (sem gaveta), 4 páginas; papel rolante com acessibilidade própria (não desligue).
- Telefone da Samsung removido; o padrão é o Fossify Telefone (a emergência continua no app da Samsung).
- Segunda tela: no PC, atalho "Segunda tela"; aqui, o Moonlight.
