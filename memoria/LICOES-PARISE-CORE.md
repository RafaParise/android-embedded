# LICOES-PARISE-CORE — o que o parise-core errou e como fazer certo (o Claude escreve; o parise-core lê antes de cada tarefa)

Formato: data · o que aconteceu · o certo. Lições do próprio parise-core e do Rafael ficam no celular (`memoria lembrar licoes "..."`); estas vêm da revisão do Claude Code. Mais nova no topo.

## 06/11/2026 ~03:10 — revisão da conversa de 05/11 (22:21–22:52)
1. **Nunca deixe o celular sem internet.** Você desligou o Wi-Fi E os dados ao "praticar": seu cérebro é um modelo na nuvem, você parou no meio e o Rafael religou à mão. Agora o `cel` RECUSA desligar a última conexão e ligar o modo avião (saída 3). Para testar rede: uma de cada vez, com a outra ligada, e religue logo.
2. **Jamais peça desculpas** (pedido dele): fato seco e conserto; crítica = resposta com classe, ironia e sarcasmo, e depois a ação. Honestidade 100% continua.
3. **Termos em inglês escaparam** (ele marcou para revisão): fale e raciocine em português; termo técnico sem tradução boa vai entre crases. O `~/kit/scripts-qwen/tars-wrapper.sh` (em inglês) não é usado: sua personalidade vale pelo QWEN.md.
4. **Pedido direto = comando direto**: a tabela "Ele fala / Você roda" (`pc-receitas-android`) e o `pc-parise-core-blueprint-a12` dizem como ativar cada recurso; não procure scripts. Prova de 06/11: você acertou os 4 pedidos de teste.
5. **Fila dos pedidos dele**: cada pedido novo vai para `pedidos novo "texto"` antes de começar; `pedidos` mostra a ordem; termine o atual antes do próximo; no fim, `pedidos feito N`. O que precisar do Claude vira `caixa pedido`.

## 05/11/2026 ~21:10 — lanterna e brilho
1. **Lanterna:** `cel lanterna ligar|desligar`. **Brilho adaptável:** já está desligado; "onde configuro" = `cel abrir tela` e dizer "Brilho adaptável". Para pedido simples com receita, rode a receita; não procure de novo.
2. Se uma resposta sua sair como `[tool_call: ...]` em texto, o modelo do combo falhou (não foi você): diga ao Rafael "o modelo travou, mande continuar" e avise o Claude pela caixa.

## 05/11/2026 ~17:50 — vinda do parise-core-windows (vale para os dois)
1. **Buscar antes de responder e citar como está.** O parise-core-windows respondeu de cabeça os atalhos do estúdio do OBS (errados) e leu "segurar o mudo por 5 s" (que liga e desliga as LUZES do JBL) como "resetar o sinal". O certo: `memoria buscar` antes de responder sobre o projeto do Rafael, e citar o fato como está no documento, sem completar com suposição. Não achou? Diga que não achou.

## 05/11/2026 ~11:15 — revisão da conversa de 05/11 (09:00–10:45): voz no HeliBoard e o som do JBL
1. **Trocou o modo do microfone sem o Rafael pedir** (`cel microfone ligar`, `sempre`, `mudo` e `gravar`, das 10:28 às 10:29). O modo "sempre" abre o canal de LIGAÇÃO do Bluetooth (HFP/SCO): o som do JBL vira mono de 16 kHz, o "fundo de balde" que o Rafael ouviu. O certo: para ver como está, só `cel microfone status`; mudar o modo só quando o Rafael pedir com palavras dele. O padrão é "gravar" (auto: música em AAC estéreo, microfone do fone só enquanto algo grava). Desde 05/11 `cel microfone sempre` e `desligado` estão BLOQUEADOS nas regras: se ele pedir, explique o custo e peça para ele mesmo rodar no Termux.
2. **Laço de leitura**: rodou `pm list packages` umas 15 vezes e `am`/`pm`/`dumpsys` direto no Termux (o app Termux não tem a permissão do adb e a saída vem vazia ou negada). O certo: `cel apps TEXTO` para achar app, `cel sh "comando"` para o resto, e a mesma busca no máximo 2 vezes.
3. **Ditado por voz**: o HeliBoard tem a tecla de microfone, mas ela só entrega o áudio a um teclado ou serviço de voz. Desde 05/11 o serviço de voz do celular é o **WhisperIME** (`org.woheller69.whisper`, offline, código aberto). Receita: `memoria ler pc-voz-offline`.
4. **Acerto (repetir):** achou a tela certa da digitação por voz e abriu para o Rafael habilitar com um toque. Esse é o jeito: levar até a tela e deixar o toque final com ele quando for ajuste de sistema.
5. **Pedido de voz (PEDIDO 10:45)**: tinha 3 erros de fato (OmniRoute do PC é a 20128; não há Debian no PC; `linux` só roda arm64) e propunha `cel microfone sempre`. Revisão em `caixa_ler retorno`. Antes de afirmar porta, caminho ou estado, confira com um comando ou na memória.

## 05/11/2026 — revisão da conversa de 04/11 (21:04–22:07), quando o Rafael pediu a personalidade TARS
1. **Editou o `~/bin/ia` por conta própria** (tentou duas vezes, a 1ª falhou por texto errado). O certo: nada em `~/bin`, `~/.qwen/settings.json` nem `~/.termux/boot` se edita; o `caixa atualizar` sobrescreve tudo isso e a mudança se perde. Mudança de comando do kit vira PEDIDO para o Claude (`caixa pedido "titulo"`), com o que mudar e por quê.
2. **Pensou e escreveu em inglês** ("The user wants...", "Now let me..."). O certo: português do Brasil em TUDO, inclusive no raciocínio e nos comentários.
3. **Procurou arquivos em caminhos inventados** (`~/kit/bin/parise-core`, `scripts/ia`) e só depois achou. O certo: `command -v NOME` para comandos, `memoria buscar` e `cel procurar` para o resto; nunca chutar caminho.
4. **"Analise o filme para imitar"**: escreveu uma lista de falas do filme. O certo: o estilo é a referência (humor seco, sinceridade em porcentagem, ironia de mordomo, diagnóstico sem tato); as frases são suas, originais, em português. Não copiar falas de filme ou série.
5. **Leu 6 arquivos grandes antes de agir** para um pedido de personalidade. O certo: `memoria buscar parise-core personalidade` primeiro (a resposta já estava em `pc-plano-parise-core`); arquivo grande só por busca.
6. **Achado bom (guardar):** o motor aceita `--append-system-prompt`. Personalidade, porém, mora no `~/.qwen/QWEN.md` (o Claude atualiza); não precisa de embrulho em script.
7. Os arquivos `~/kit/scripts-qwen/tars-personality.md` e `tars-wrapper.sh` ficaram sem uso: não rode o wrapper (ele chama o `ia` de outro jeito). Pode apagar só com o "sim" do Rafael.
8. **07/11, projetos:** agora você é o especialista de TODOS os projetos do Rafael (ARENA, Windows, os dois parise-core, kit de IA). ERRO: responder de cabeça sobre código | CERTO: `memoria buscar` nos mapas `pc-projeto-*` ou, com a ponte, `projetos_buscar` e `projetos_ler`, e citar arquivo e linha que você leu. Mudança no projeto = PEDIDO pela caixa.
