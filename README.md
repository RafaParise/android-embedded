<h1 align="center">Android Embedded — o Galaxy A12 turbinado sem root</h1>

<p align="center">
  Um celular de entrada transformado em <b>aparelho de trabalho, de aula e de teste</b>.<br>
  Mais rápido, mais limpo e com uma IA que <b>opera o próprio celular</b>, tudo pelo cabo ou pela internet,<br>
  <b>sem root, sem desbloquear nada e com volta para cada passo</b>.
</p>

<p align="center">
  <a href="https://github.com/RafaParise/android-embedded/releases/latest"><b>⬇️ Baixar o pacote pronto</b></a>
  &nbsp;·&nbsp; <a href="1-COMECAR.md">Primeiros passos</a>
  &nbsp;·&nbsp; <a href="#os-guias">Os guias</a>
  &nbsp;·&nbsp; <a href="#perguntas-frequentes">Perguntas frequentes</a>
</p>

---

## O que é

Pense no celular como um **carro popular**. Dá para trocar o motor (root), mas isso
anula a garantia, apaga tudo e, se der errado, o carro não liga mais. Este projeto faz
o contrário: **regula o carro que já existe**. Tira o peso do porta-malas (apps que vêm
de fábrica e ninguém usa), calibra os pneus (ajustes escondidos do Android), instala um
painel que mostra o que está acontecendo e coloca um **copiloto** no banco do lado: uma IA
que entende português, lê a tela e toca nos botões por você.

Tudo é feito com o **ADB** (a "porta de oficina" oficial que todo Android tem) a partir de um
PC com Windows, e cada mudança tem o seu **desfazer**.

Ele nasceu do trabalho de um professor do curso técnico de **Desenvolvimento de Sistemas**
(Ensino Médio, rede estadual de São Paulo), que precisava de um celular de teste rápido e
confiável. Tem dois papéis:

1. **Um kit que funciona:** foi usado e medido todos os dias num Galaxy A12 de verdade
   (SM-A125M, Android 12, 4 GB de RAM).
2. **Material de estudo:** scripts curtos, comentados em português, com testes automáticos,
   para quem quer aprender Android, redes, automação e IA na prática.

## O que ele faz

| | |
|---|---|
| 🧹 **Faxina segura** | Desativa os apps de fábrica em lotes, com um substituto livre declarado para cada função e uma lista do que **nunca** se toca (telefone, Play Store, câmera...). Simula antes, aplica só quando você manda, desfaz com um comando |
| 🩺 **Painel de saúde** | `saude.py` mostra bateria, temperatura, memória, quem está pesando e o espaço livre, e guarda o histórico. `auditoria.py` confere mais de 150 itens do aparelho de uma vez |
| 🤖 **Matrix, a IA do celular** | O Qwen Code no Termux, com personalidade própria, memória local no cartão SD e o comando `cel` para **ler a tela e tocar nos botões** de qualquer app (e recusar sozinho os botões sem volta, como "Desinstalar" ou "Pagar") |
| 🌍 **Sem cabo, de qualquer lugar** | Pela Tailscale (VPN grátis), o celular alcança o PC e o PC alcança o celular, no Wi-Fi ou nos dados móveis: a IA do PC, a ponte do projeto e o ADB pela porta 5555 |
| 🖥️ **Segunda tela** | O PC mostra e comanda o celular, abre uma tela **extra** do celular numa janela, ou usa o celular como monitor do PC |
| 🎙️ **Ditado sem nuvem** | Voz para texto no próprio celular (WhisperIME, com a tecla de microfone do teclado) e no PC (Handy), sem mandar o áudio para ninguém |
| 🌄 **Papel de parede rolante** | Um app próprio de 21 KB: a imagem anda com as páginas da tela inicial e aparece inteira com o celular deitado, como nos Samsung antigos |
| 🌑 **Tela apagada sem bloquear** | Escurece a tela de verdade (para economizar e para gravar), mas o toque e a depuração continuam vivos. Volume para baixo 3 vezes liga e desliga |
| 🛡️ **Antivírus sob demanda** | `guarda`: vigia os downloads em tempo real e manda o arquivo ao ClamAV do PC só quando precisa, com quarentena que nunca apaga |
| 🔐 **Saída de internet pelo PC** | O celular pode navegar pela internet de casa (exit node da Tailscale), com um guarda que desliga sozinho se o PC sumir |
| 📷 **E mais** | Celular como webcam do PC, cópia e restauração locais, teste de gravação do cartão com md5, mapas offline com listas de lugares, estúdio do OBS |

## Baixar e usar

1. Baixe **`android-embedded-AAAA.MM.DD.zip`** na página
   [**Releases**](https://github.com/RafaParise/android-embedded/releases/latest) e descompacte numa
   pasta sem espaço no nome (por exemplo, `C:\android-embedded`). Quem usa git pode clonar o repositório:
   é o mesmo conteúdo, menos os dois arquivos compilados que só vêm no pacote.
2. Siga o [**1-COMECAR.md**](1-COMECAR.md): instalar o Python e o ADB (grátis, sem conta), ligar a
   depuração USB e rodar o primeiro diagnóstico, que **só lê** o aparelho.
3. Escolha o que quer fazer nos guias abaixo. Cada script, rodado **sem** a opção `--aplicar`,
   mostra o que faria e não muda nada.

### O que vem no pacote

- `scripts/`: os scripts do PC (Python e PowerShell) e o `celular-kit/` (o que vai para o Termux).
- `memoria/`: os documentos técnicos (o que foi medido, o que funcionou e o que não funcionou).
- `binarios/papel-rolante.apk`: o app do papel de parede, compilado e assinado a partir do código
  em `scripts/celular-kit/papel/`.
- `scripts/celular-kit/tela/tela.dex`: o ajudante da tela apagada, compilado de `Tela.java`.

### O que NÃO vem (e por quê)

- **Nenhum app de terceiros, firmware ou ferramenta da Samsung.** Os scripts baixam o que precisam
  das fontes oficiais (F-Droid, GitHub dos autores, winget) e conferem o hash antes de instalar.
- **Nada de root, Magisk ou desbloqueio.** Foi uma decisão: desbloquear apaga o celular e não tem volta
  simples. O teto do que dá para fazer sem root está medido em
  [`memoria/RADAR-DESEMPENHO.md`](memoria/RADAR-DESEMPENHO.md).
- **Chaves, senhas e dados pessoais.** Cada pessoa usa as próprias contas (todas grátis).
- **Listas de lugares dos mapas e ícones de outros apps.** São dados e marcas de terceiros: os scripts
  geram no seu computador, a partir das fontes abertas.

## Requisitos

| Peça | O mínimo | Observação |
|---|---|---|
| Celular | Samsung Galaxy A12 (SM-A125M), Android 12 | Outros Android 11 a 14 aceitam boa parte; a lista de apps e as telas são do A12 |
| PC | Windows 10 ou 11 | Python 3.11 ou mais novo, PowerShell 7 (`pwsh`), ADB (platform-tools do Google) |
| Cabo | USB com dados | Depois da primeira vez, dá para trabalhar sem cabo pela Tailscale |
| Internet | Só para baixar e para a IA de nuvem | A faxina, o painel e a auditoria funcionam offline |
| Contas | Nenhuma paga | Tailscale, OmniRoute e os provedores de IA têm plano grátis; nada aqui pede cartão |

## Os guias

| Guia | Para quê |
|---|---|
| [1-COMECAR.md](1-COMECAR.md) | Instalar, ligar a depuração e fazer o primeiro diagnóstico |
| [2-DEIXAR-RAPIDO.md](2-DEIXAR-RAPIDO.md) | Faxina dos apps, ajustes que valem e os que não valem, medir antes e depois |
| [3-MATRIX-IA-NO-CELULAR.md](3-MATRIX-IA-NO-CELULAR.md) | A IA no Termux: instalar, conversar, operar apps, memória e limites |
| [4-SEM-CABO.md](4-SEM-CABO.md) | Tailscale, ADB pela rede, segunda tela, webcam e saída de internet pelo PC |
| [5-TELA-SOM-E-VOZ.md](5-TELA-SOM-E-VOZ.md) | Papel rolante, tela apagada, ditado sem nuvem, microfone e fone Bluetooth |
| [6-SEGURANCA-E-REPARO.md](6-SEGURANCA-E-REPARO.md) | Antivírus, auditoria, cópia e restauração, o que nunca fazer e como desfazer |

## Para quem programa

- **Cada script é independente** e começa com um comentário que explica, em português, o que ele faz,
  como usar e como desfazer.
- **Simular é o padrão.** O que muda o aparelho só age com `--aplicar` (ou o nome da ação, como `ligar`).
- **Testes automáticos:** mais de 1.600 testes em `scripts/tests/`, com um ADB falso (nenhum teste toca
  um celular de verdade). Rodam no Linux e no WSL: `python -m pytest scripts/tests -q`.
  O GitHub roda a mesma bateria a cada envio.
- **Agentes de IA** (Claude Code, Codex, Qwen Code, Hermes...): leiam o [`AGENTS.md`](AGENTS.md) e o
  [`CLAUDE.md`](CLAUDE.md) antes de mudar qualquer coisa.

## Perguntas frequentes

**Preciso de root?** Não. E o projeto não ajuda a fazer root: tudo aqui é com o ADB oficial.

**Vou perder a garantia ou os meus dados?** Não. Desativar um app com o ADB é como tirar o fusível de um
aparelho da casa: ele para, mas continua lá, e volta com um comando (`lote-pacotes.py --restaurar`).
O que apaga dados (formatar o cartão, por exemplo) pede confirmação escrita e mostra o alvo antes.

**O app do banco ou do governo reclama de "modo de desenvolvedor".** O `gov.br` se recusa a abrir com as
Opções do desenvolvedor visíveis. Dá para escondê-las sem desligar o ADB:
`adb shell settings put global development_settings_enabled 0` (testado: o `gov.br` abre e o ADB segue
funcionando). Não desligue pela tela de Configurações: isso desliga também a depuração.

**Funciona no meu celular, que não é um A12?** A maioria dos scripts usa comandos comuns a todo Android.
O que é específico do A12 (a lista de apps da Samsung, as coordenadas de tela, o deslocamento do papel de
parede) está marcado no próprio script. Rode a auditoria, que só lê, e veja o que ela diz.

**Por que a IA às vezes erra?** Os modelos grátis são pequenos perto dos pagos. Por isso o projeto tem
travas: a IA não desinstala, não apaga, não toca em botão sem volta e anota as próprias lições para não
repetir o erro ([`memoria/LICOES-MATRIX.md`](memoria/LICOES-MATRIX.md)).

**Com dois controles Bluetooth ligados, a internet cai.** É limite do A12, que só tem Wi-Fi de 2,4 GHz,
a mesma faixa do Bluetooth. Medido: o roteador passa a responder em 3 a 5 segundos. Use os dados móveis
enquanto joga e, depois, desligue e ligue o Wi-Fi uma vez ([`memoria/CONTROLES-GAMESIR.md`](memoria/CONTROLES-GAMESIR.md)).

## Licença

[GPL-3.0](LICENSE), a mesma do [ARENA](https://github.com/RafaParise/arena-console): pode usar, estudar,
mudar e redistribuir, desde que a versão modificada continue aberta. Os programas de terceiros que os
scripts baixam têm as licenças deles ([`TERCEIROS.md`](TERCEIROS.md)).

## Créditos

Projeto de Rafael Parise Passos, professor do técnico em Desenvolvimento de Sistemas (SEDUC-SP), com
Claude Code como parceiro de programação e revisão. Novidades de cada versão: [`NOVIDADES.md`](NOVIDADES.md).
