# Voz offline (ditado) no celular e no PC — 05/11/2026

Pedido do Rafael e do parise-core (PEDIDO 20261105-104547): digitar por voz sem Google, sem nuvem, código aberto.
Escolhidos programas prontos no lugar dos scripts do pedido (servidor STT no PC e cliente no celular): menos peças, funciona sem rede.

## Celular: WhisperIME
- App `org.woheller69.whisper` 3.8 (F-Droid oficial, código aberto, autor woheller69), hash do APK conferido antes de instalar.
- Roda o Whisper no próprio celular (TensorFlow Lite). Internet só uma vez, para baixar o modelo (~435 MB, Hugging Face).
- Habilitado pelo Claude em 05/11 ~11:05:
  - teclado de voz: `ime enable org.woheller69.whisper/com.whispertflite.WhisperInputMethodService`
  - serviço de voz do sistema: `settings put secure voice_recognition_service org.woheller69.whisper/com.whispertflite.WhisperRecognitionService` (antes: o do Google)
  - microfone: `pm grant org.woheller69.whisper android.permission.RECORD_AUDIO`
  - no app: "Traduzir para inglês" e "Texto-para-fala" DESMARCADOS (vinham marcados; com a tradução o texto sairia em inglês).
- Uso: tecla de microfone do HeliBoard (troca para o teclado de voz) ou segurar o botão do WhisperIME enquanto fala; solta e o texto entra no campo.
- Tecla fixa (05/11 ~11:37, pedido do Rafael: "um ícone no meu teclado ... como o Google faz"): HeliBoard > Barra de Ferramentas > Selecionar teclas FIXADAS > "Entrada de voz" ligada. O microfone fica sempre no canto direito da barra de sugestões, em qualquer app. Toque nele: abre o teclado do Whisper; segure o microfone roxo enquanto fala; o botão de teclado (no meio, em cima) volta ao HeliBoard [Certo: ida e volta conferidas no aparelho]. O Rafael confirmou: "o whisper está funcionando muito bem", e o JBL no PC pelo receptor não se cruza com o celular.
- No teclado do Whisper há um botão "EN": se o texto sair em inglês, é ele (tradução); deixe desligado.
- O app mostra, ao abrir, um aviso do autor sobre a exigência de identidade de desenvolvedor do Google em 2026/2027 ("o aplicativo deixará de funcionar em dispositivos certificados") [Certo: texto da tela; o efeito real no A12 não foi verificado]. Reserva, se parar: Sayboard (`com.elishaazaria.sayboard` 4.2.1, Vosk, F-Droid; APK já baixado e conferido no PC, não instalado).
- Desfazer: `settings put secure voice_recognition_service com.google.android.tts/com.google.android.apps.speech.tts.googletts.service.GoogleTTSRecognitionService`; `ime disable org.woheller69.whisper/com.whispertflite.WhisperInputMethodService`; desinstalar o app.

## PC: Handy
- Handy 0.10.0 (cjpais, licença MIT, Whisper local), instalado só para o usuário em `%LOCALAPPDATA%\Handy` (instalador assinado, SHA-256 d4c02386… conferido). O winget falhou porque a dependência Vulkan Runtime não tem instalador por usuário; o Vulkan já vem com o driver de vídeo (`vulkan-1.dll` presente).
- Uso: atalho de teclado do Handy; fala e o texto entra no cursor de qualquer programa. O Rafael confirmou em 05/11: "no pc o handy está funcionando muito bem".
- Desfazer: Configurações > Aplicativos > Handy > Desinstalar.

## Microfone e som do JBL (o que NÃO fazer para ditar)
- `cel microfone sempre` abre o canal de ligação do Bluetooth (HFP/SCO): som do fone mono de 16 kHz, o "fundo de balde". Em 05/11 o parise-core fez isso sem pedido e o Rafael ouviu. Padrão: `gravar` (auto). O parise-core tem `sempre` e `desligado` bloqueados nas regras.
- Microfone do JBL no celular será sempre qualidade de ligação (limite do Bluetooth HFP) [Provável: perfil HFP com mSBC = 16 kHz]. Para ditar com mais qualidade: microfone do próprio celular, ou o JBL no PC pelo receptor USB (Handy).
