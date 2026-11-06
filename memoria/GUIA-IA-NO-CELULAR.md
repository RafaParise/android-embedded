# Guia: usar a IA (Qwen Code) no celular — passo a passo

Para o Rafael. Escrito em 31/10/2026 e testado no seu Galaxy A12 no mesmo dia. Marcas: **[Certo]** = medido ou conferido nesse dia; **[Provável]** = deduzido, não medido.

## 0. Em 1 minuto: o que escolher

O **Qwen Code** é só o *programa* (o agente que lê e edita arquivos). Quem pensa é o **modelo de IA** que ele usa, e existem cinco opções de "cérebro":

| Cérebro | Onde roda | Qualidade | Precisa de | Comando |
|---|---|---|---|---|
| **Nuvem grátis** (Nemotron 550B, Gemini 3 Flash, Mistral…) pelo OmniRoute do PC | internet, via PC | **Alta**: é o único que executa tarefas de verdade | PC ligado + Tailscale ligada nos dois | `ia` |
| **Qwen 3.8 de 27B** (Groq, grátis) pelo OmniRoute do PC | internet, via PC | **Alta para UMA pergunta curta**; não age (sem agente nem ferramentas) | PC ligado + Tailscale nos dois + `python3` no Termux | `ia qwen "pergunta"` |
| Llama 3B do PC (Ollama) | PC | Baixa (repete ações; só tarefa curta) | PC ligado + porta do Ollama aberta (ou cabo) | `ia pc` |
| Qwen 1,5B do celular | celular | Baixa: só conversa curta, mas explica melhor que o 0,5B | nada (offline); ~1,2 GB de memória livre | `ia chat` |
| Qwen 0,5B do celular | celular | Muito baixa: só conversa curta | nada (offline) | `ia chat leve` |

- **Quer programar, mexer nos arquivos do projeto, revisar?** Use `ia` (nuvem).
- **Quer só uma perguntinha rápida, sem PC e sem internet?** Use `ia chat` (o 1,5B, melhor e mais lento) ou `ia chat leve` (o 0,5B, rápido e mais fraco).
- **Quer a resposta do melhor Qwen grátis para UMA pergunta curta** (explicar um erro, resumir um trecho, traduzir)? Use `ia qwen "sua pergunta"`; para juntar um arquivo à pergunta: `cat arquivo.txt | ia qwen "resuma isto" -` (o `-` no fim junta o que vem pelo cano). O limite do plano grátis é uns 4 mil tokens (~14 mil caracteres): acima de 20 mil caracteres o `ia` nem envia e avisa; entre os dois, o Groq pode recusar (HTTP 413/429) e o `ia` explica. Ele não abre o Qwen Code, não lê arquivo sozinho e não executa nada. **Atenção: o texto que você manda vai para um provedor externo (o Groq).** Nunca mande nome, nota ou qualquer dado de aluno, nem senha ou chave: o `cat arquivo | ia qwen ... -` envia o arquivo inteiro.
- **Quer o Qwen do celular lendo o projeto do PC ao vivo e trocando recados com o Claude Code, de qualquer lugar?** O `ia` (nuvem) já liga a ponte do PC: veja o Passo D (seção 4b).
- **Quer ligar TUDO de uma vez** (nuvem + modelo do PC + modelo do celular) e trocar de cérebro sem sair do Qwen? Use `ia tudo`; lá dentro, digite `/model` para escolher o cérebro [Certo: o comando existe no Qwen Code instalado]. Atenção: o modelo do celular fica carregado e gasta uns 0,5 GB de memória; use só se for alternar.

**Por que o Qwen local "nunca funcionou" para você** [Certo]: o modelo do celular lê cerca de 18 palavras (tokens) por segundo e o Qwen Code manda uns 12 mil de instruções antes da sua pergunta; 12.000 ÷ 18 ≈ **11 minutos** só para começar a responder [Provável: a conta usa a medida de 30/10 dos 12 mil]. O `ia chat` conversa direto com o modelo e responde em segundos; o modo nuvem usa modelos enormes que respondem em 1 a 8 segundos. O Qwen 1,5B é ainda pior para o Qwen Code (lê só ~6 tokens por segundo: 12.000 ÷ 6 ≈ 35 minutos [Provável: conta com a medida de hoje]), por isso `ia local` e `ia tudo` usam sempre o 0,5B; o 1,5B só entra no `ia chat`.

**E o "Qwen mais potente"?** [Certo, testado hoje] O OmniRoute tem Qwen grátis na nuvem (Qwen2.5-Coder 32B e Qwen3-30B), mas eles **não devolvem chamadas de ferramenta** (escrevem a ação como texto), então o Qwen Code não consegue agir com eles. Os combos `codigo`, `auditoria` e `rapido` devolvem a chamada certa nos três testes (Nemotron 3 Ultra 550B em 1,6 s; Muse Glimmer 30B em 7,5 s; Mistral Small em 0,9 s: tempos da API; o Qwen Code soma o resto, veja a seção 3).

O mais forte que a chave do celular alcança é o **Qwen 3.8 de 27B** do Groq (grátis, `groq/qwen/qwen3.8-27b`) [Certo: do celular, pelo OmniRoute, HTTP 200 em 0,67 s e resposta correta em português, 31/10]. Ele **não serve de cérebro do `ia`**: o plano grátis aceita só uns 4 mil tokens por pedido e o Qwen Code manda uns 12 mil de instruções antes da sua pergunta (o Groq recusa com HTTP 413). Por isso ele virou um comando à parte, `ia qwen "pergunta"`: uma pergunta curta, sem agente. Para trocar o modelo: `IA_QWEN_MODELO=<modelo> ia qwen "..."` (a chave do celular só alcança os modelos permitidos no OmniRoute).

## 1. Preparação (uma vez só)

### No celular
- [ ] **Termux** abre normalmente (já está instalado).
- [ ] O comando **`ia`** existe: abra o Termux e digite `ia ajuda`. Apareceu a lista de comandos? Está pronto. Apareceu `command not found`? Faça a seção 9 (colar o instalador).
- [ ] **Tailscale** (o app) com a chave ligada, escrito "Conectado". Na escola: entre no Wi-Fi com a Tailscale **desligada**, faça o login da rede e só depois ligue a Tailscale.
- [ ] Deixe o **Termux na tela** enquanto usa: o projeto manda o Android pausar o Termux em segundo plano (economiza bateria), e isso para a conversa.
- [ ] Dica de tela [Certo: visto no seu celular]: com o celular deitado, o teclado ocupa quase tudo e sobram só 4 linhas do Termux. Toque na seta para baixo (canto direito da tela) para esconder o teclado, ou use o celular em pé.

### No PC (só para `ia` e `ia pc`)
- [ ] PC ligado e você logado no Windows. O OmniRoute, o Ollama e a Tailscale ligam sozinhos no login [Certo: tarefa "OmniRoute" no logon; Ollama e Tailscale na inicialização].
- [ ] Para conferir (e ligar, se algo estiver parado): dê **dois cliques em `C:\Android Embeeded\scripts\ia-do-pc.cmd`**. Esperado: todas as linhas com `[ok]`:

```
  [ok]  Tailscale do PC conectada (100.64.0.1)
  [ok]  Celular conectado na Tailscale
  [ok]  OmniRoute no ar (porta 20128; so neste PC e na tailnet)
  [ok]  Ollama no ar com o modelo llama3.2-32k (usado por `ia pc`)
  [ok]  Porta 20128 (OmniRoute) aberta so para a tailnet
  [ok]  Porta do Ollama fechada (normal; abra so para usar `ia pc` sem cabo: -AbrirOllama)
  [ok]  Ponte do projeto no ar (porta 20130; so neste PC e na tailnet)
  [ok]  Porta 20130 (ponte do projeto) aberta so para a tailnet
```

## 2. Passo A — SÓ NO CELULAR (offline): `ia chat`

1. Abra o **Termux**.
2. Digite `ia chat` e aperte Enter (leva uns 10 segundos para carregar). O `ia` escolhe o modelo sozinho e diz qual: o **Qwen 1,5B** (melhor, mais lento) quando ele está instalado e o celular tem pelo menos **1.300 MB de memória livre**; senão o **Qwen 0,5B** (mais rápido, mais fraco), avisando por quê.
3. Quer o rápido de propósito? Digite `ia chat leve`.
4. Escreva a pergunta em português e aperte Enter.
5. Para sair: **Ctrl+C** (na barra de teclas extras do Termux toque em CTRL e depois em C; ou aperte Volume− + C).

Medido no seu A12 em 31/10 [Certo]:

| | Qwen 0,5B (`ia chat leve`) | Qwen 1,5B (`ia chat`) |
|---|---|---|
| Arquivo no celular | 491 MB | 1,1 GB |
| Escreve a resposta | ~10 tokens/s | ~3 tokens/s |
| Lê o seu pedido | ~18 tokens/s | ~6 tokens/s |
| Memória que usa | 562 MB | 1.224 MB |
| Pronto para conversar em | 6 s | 9 s |
| Qualidade | responde, mas erra mais | explica melhor em português; ainda erra (uma vez escreveu "piaça") |

"Token" é um pedaço de palavra: em português, 1 palavra ≈ 1,5 a 2 tokens [Provável], então o 1,5B escreve cerca de 2 palavras por segundo e o 0,5B cerca de 6. Os dois servem para uma dúvida simples, uma frase, um exemplo curto; **nenhum** edita código nem enxerga seus arquivos.

O limite de 1.300 MB é uma regra prática [Provável]: o 1,5B usa 1.224 MB, e o celular parado costuma ter 1.450 a 1.540 MB livres. Para mudar: `IA_MEM_MIN=1000 ia chat`. `ia status` mostra a memória livre do momento.

**Onde estão os modelos** (no Termux, pasta `~/modelos`): `qwen.gguf` (0,5B) e `qwen2.5-1.5b.gguf` (1,5B, licença Apache-2.0; o hash SHA-256 foi conferido contra o do Hugging Face em 31/10).
- **Apagar o 1,5B** para liberar 1,1 GB: `rm ~/modelos/qwen2.5-1.5b.gguf`. O `ia chat` volta ao 0,5B sem reclamar.
- **Instalar de novo** (ou num celular novo): peça ao Claude Code do PC; ele baixa `qwen2.5-1.5b-instruct-q4_k_m.gguf` de `huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF`, confere o hash e copia para `~/modelos/qwen2.5-1.5b.gguf` pelo cabo (`scripts\termux.ps1 -Copiar`).

## 3. Passo B — CELULAR + PC, nuvem grátis (o recomendado): `ia`

1. **PC:** dois cliques em `ia-do-pc.cmd` (seção 1) e confira os `[ok]`.
2. **Celular:** Tailscale ligada.
3. **Termux:** digite `ia` e Enter. Você deve ver algo assim:

```
Cerebro: codigo (via Tailscale)
Abrindo o Qwen Code em: /data/data/com.termux/files/home/kit/projeto-android-embeeded
(dentro dele: /help ajuda, Esc interrompe, /quit sai)
```
4. Escreva o pedido em português (exemplos na seção 6). Para sair: `/quit`.

Outros "agentes gratuitos" (são os combos do OmniRoute; ele tenta o primeiro modelo da lista e, se estiver sem cota, passa ao próximo):

| Comando | Para quê | Modelos (ordem de tentativa, em 31/10) |
|---|---|---|
| `ia` ou `ia codigo` | programar e mexer nos arquivos | Nemotron 3 Ultra 550B → Nemotron 3.5 Lightning 30B → Gemini 3.1 Flash-Lite → Gemini 3 Flash → … |
| `ia auditoria` | revisar, caçar erro | Muse Glimmer 30B → Nemotron 3 Ultra 550B → … → GPT-OSS 120B |
| `ia rapido` | resumo e tarefa curta | Gemini 3.1 Flash-Lite → Nemotron 3.5 Lightning → … |

Sem cabo, o `ia` abre sozinho uma ponte local até o OmniRoute pela Tailscale e a fecha quando você sai. Com o cabo e a ponte do Claude Code já aberta, ele usa a que existir.

**Quanto demora** [Certo, medido em 31/10 no seu celular]: uma pergunta simples leva uns **25 segundos** e uma tarefa com leitura de arquivo uns **35 segundos** (o Qwen Code manda umas 12 mil palavras de instruções a cada pedido). Antes disso, a *auto-memória* do Qwen Code, que vem **ligada de fábrica**, fazia dezenas de chamadas extras ao modelo em segundo plano e a mesma pergunta levava de 2 a 3 minutos (e gastava a cota grátis); eu a desliguei no seu celular (bloco `memory` do `~/.qwen/settings.json`).

**Reserva (PC desligado): o OmniRoute do próprio celular.** Desde 01/11/2026 o OmniRoute também está instalado no celular (`memoria/OMNIROUTE-CELULAR.md`). Com o PC no ar nada muda e o celular não gasta nada. Com o PC fora do ar, o `ia` liga o do celular sozinho (cerca de 1 minuto, uns 400 MB de RAM, só em `127.0.0.1:20129`) e desliga quando você sai do Qwen. **Ativada em 01/11 (~17:20)**: o arquivo `~/.omniroute/pronto` existe (criado depois de um chat de verdade com 3 provedores, com chaves suas), então o `ia` usa essa reserva quando o PC não responde. `ia status` mostra a situação.

## 4. Passo C — usar o modelo do PC (Llama 3B): `ia pc`

Fraco: só para tarefa curta, e a 1ª resposta leva alguns minutos [Certo: medido em 30/10]. Use quando a nuvem estiver fora.

1. **PC:** dois cliques em `ia-do-pc-abrir-ollama.cmd`. Isso abre a porta do Ollama **só para a tailnet** (ela fica sem senha; por isso nasce fechada).
2. **Termux:** `ia pc`.
3. Quando terminar, no PC: dois cliques em `ia-do-pc-fechar-ollama.cmd`.

## 4b. Passo D — o projeto do PC dentro do Qwen do celular, de qualquer lugar (ponte do PC)

**O que é** [Certo: instalado e testado no seu celular em 31/10]: um servidor no seu PC (`ponte-pc`, porta 20130, aberta **só para a Tailscale**) que o Qwen do celular usa como ferramenta (protocolo MCP). Com ele o Qwen consegue, **de qualquer lugar em que o celular alcance o PC pela Tailscale** (Wi-Fi, dados móveis, longe de casa):

- **ler o projeto ao vivo**, sem retrato velho: `projeto_buscar`, `projeto_ler`, `projeto_listar` (só `CLAUDE.md`, `memoria/` e `scripts/`; só texto; nunca segredo, planilha nem MAPAO);
- consultar as **skills e estratégias** do PC (48 skills): `kit_listar`, `kit_ler`;
- **trocar recados com o Claude Code do PC**: `caixa_listar` e `caixa_ler` mostram os pedidos (`entrada`) e as revisões (`retorno`); `entregar` grava o trabalho dele como arquivo **novo** no PC, marcado `NAO REVISADO`. O Qwen **nunca altera** o projeto do PC: o Claude Code revisa e só então usa;
- **buscar na web** (servidor `exa`: grátis, sem chave; pede a sua confirmação a cada uso).

**Como usar:** nada de novo. O `ia` (ou `ia codigo`, `ia auditoria`, `ia rapido`) já liga a ponte e avisa `Ponte do PC ligada: ...`. Dentro do Qwen, escreva como sempre: `Procure em memoria/ onde se fala de bateria e resuma` ou `Entregue ao Claude Code um resumo de 5 linhas do que está pendente`. Sem abrir o Qwen, no Termux: `caixa sincronizar` (baixa os recados do PC e envia as entregas guardadas), `caixa ler`, `echo "texto" | caixa enviar titulo`, `caixa status`.

Os modelos pequenos (`ia pc`, `ia local`) **não levam** a ponte: o prompt deles já passa de 12 mil tokens e as ferramentas extras só atrasariam.

**O que precisa estar de pé:** PC ligado **e você logado nele** (a ponte e o OmniRoute iniciam no logon), Tailscale ligada no PC e no celular. `ia status` mostra `[ok]  Ponte do PC ... pronta`; no PC, `ia-do-pc.cmd` confere e religa tudo.

**Instalar ou atualizar o kit no celular, sem cabo:**
1. No PC: `pwsh -NoProfile -File scripts\ponte-pc.ps1 -Parear`. Ele mostra um código e uma linha que começa com `curl`; **cole a linha no Termux**. O código vale **uma vez** e por 24 h. A linha instala os comandos `ia` e `caixa`, o `QWEN.md` e liga o MCP, e **guarda uma cópia de tudo o que trocar em `~/.qwen/antes-da-ponte/`** (nada seu é apagado; as suas permissões e o `/effort` do Qwen ficam como estão).
2. Quando o kit mudar no PC: no Termux, `caixa atualizar` (o `caixa status` avisa se há versão nova).
3. Com o cabo ligado, `ponte-pc.ps1 -InstalarNoCelular` faz tudo sozinho.

**Desfazer:** no Termux, `qwen mcp remove ponte-pc` (e `qwen mcp remove exa`), ou restaure a cópia de `~/.qwen/antes-da-ponte/`. No PC, `ponte-pc.ps1 -NovoToken` (o celular perde o acesso até ser pareado de novo) ou `-Desinstalar`.

## 5. Antes ou depois do `cd`? (e o endereço do projeto)

**Você não precisa fazer `cd`.** O `ia` faz na ordem certa: primeiro liga os serviços (ponte da Tailscale, modelo do celular) e só depois entra na pasta e abre o Qwen. Os serviços não dependem da pasta; o **Qwen precisa ser aberto dentro da pasta que você quer que ele enxergue**, porque só mexe nos arquivos dali.

Qual pasta o `ia` usa (nesta ordem):
1. a que você escrever depois do modo: `ia codigo "/storage/1A2B-3C4D/Projetos/qwen-celular"`;
2. a pasta em que você já estiver, se não for a inicial do Termux (`cd uma-pasta` e depois `ia`);
3. a pasta do projeto no **cartão SD**, se existir (`Projetos\Android Embeeded`; a cópia velha foi apagada em 03/11 a seu pedido);
4. a cópia do projeto dentro do Termux (`~/kit/projeto-android-embeeded`), que é a usada hoje [Certo: `ia status`, 03/11].

O mesmo endereço, escrito de dois jeitos [Certo: o Termux enxerga essa pasta]:

| No Windows (Este Computador) | No Termux (Android) |
|---|---|
| `Samsung A12\Cartão SD\Projetos\qwen-celular` | `/storage/1A2B-3C4D/Projetos/qwen-celular` |
| `Samsung A12\Armazenamento interno\Download` | `/sdcard/Download` |

- O endereço tem **espaço**: no Termux ele precisa estar entre aspas.
- **Histórico (essa cópia foi apagada em 03/11):** [Certo, conferido em 31/10] a pasta que você copiou para o cartão tinha **só o esqueleto de pastas (406 pastas e nenhum arquivo)**: a cópia pelo Windows não trouxe os arquivos. Por isso eu copiei para lá o *retrato do projeto* (`CLAUDE.md`, `memoria/` e `scripts/`, sem `diagnostico/` e sem chaves). Se você copiar de novo pelo Windows, confira: `ls "/storage/1A2B-3C4D/Projetos/Android Embeeded"` deve mostrar `CLAUDE.md  memoria  scripts`. O `ia` só usa uma pasta que tenha o `CLAUDE.md`; se a do cartão estiver vazia, o `ia status` avisa e ele usa a cópia que está dentro do Termux.
- Se um dia você formatar o cartão, o código `1A2B-3C4D` muda. O `ia` descobre o novo sozinho; se não achar, use `IA_PROJETO="/storage/NOVO-CODIGO/Projetos/qwen-celular" ia`.
- Isso é um **retrato de 31/10**, não o projeto vivo: o que o Qwen alterar no celular **não volta sozinho** para o projeto do PC, e o que o PC mudar depois não aparece aqui até alguém atualizar o retrato (peça ao Claude Code do PC). Para ler o projeto **vivo**, use a ponte do PC (Passo D, acima); para levar um trabalho do celular de volta, o Qwen usa `entregar` (ou `caixa enviar`) e o Claude Code revisa.
- **Privacidade:** na cópia do cartão existe um arquivo `.qwenignore` que manda o Qwen **ignorar `diagnostico/`** (saídas locais do aparelho). Os modelos da nuvem pertencem a terceiros: **nunca cole nome ou nota de aluno**.

## 6. Dentro do Qwen: o básico

- Escreva em português, como numa conversa. Exemplos que funcionam bem:
  - `Leia memoria/ESTADO.md e me diga em 5 linhas o que está pendente.`
  - `Explique o que o script scripts/modos.py faz, como se eu fosse um aluno do técnico.`
  - `Procure em scripts/ onde se fala de "bateria" e resuma.`
- O Qwen **pede permissão** antes de editar arquivo ou rodar comando: leia o que ele quer fazer e escolha. Na dúvida, permita uma vez só.
- `/help` lista os comandos · `/clear` esquece a conversa (use se ele começar a repetir) · **Esc** interrompe a resposta · `/quit` sai.
- Se ele perguntar se confia na pasta, escolha **Sim**.

## 7. Se der problema

| O que aparece | Causa provável | O que fazer |
|---|---|---|
| `ia: command not found` | o comando não está instalado, ou o `~/bin` não está no PATH | seção 9 |
| O prompt do Termux mostra uma pasta que não existe mais (ex.: a cópia antiga em `/sdcard/Projetos`) | o terminal ficou aberto numa pasta apagada | digite `cd` e Enter (volta ao início); o `ia` já ignora pasta apagada |
| `O OmniRoute do PC nao respondeu` | PC desligado, ou Tailscale desligada no PC ou no celular | dois cliques em `ia-do-pc.cmd`; ligue a Tailscale; rode `ia status` |
| `Falta a chave do OmniRoute em ~/.qwen/.env` | a chave do celular não está nesse arquivo | peça ao Claude Code do PC (a chave se chama `celular`; ela só entra no celular com o seu "sim") |
| `ia status` mostra o Ollama "fora" | normal: a porta nasce fechada | só precisa para `ia pc` (Passo C) |
| `Ponte do PC ... sem o token` | o celular ainda não foi pareado | no PC: `ponte-pc.ps1 -Parear`; cole no Termux a linha que ele mostra (Passo D) |
| `Ponte do PC: fora` | PC desligado ou sem login, Tailscale desligada, ou a ponte parada | `ia-do-pc.cmd` no PC; ligue a Tailscale |
| O `ia` ou o `caixa` dizem "fora" ou "não respondeu", mas o PC está ligado e a Tailscale conectada | o primeiro pacote depois de um tempo parado demora para chegar (Tailscale e Wi-Fi acordando): medi **3,05 s** só para conectar depois de 45 s parado, e o `caixa atualizar` chegou a falhar assim [Certo: 31/10]; em dados móveis pode demorar mais [Provável] | rode o comando de novo (o segundo já é rápido); ou dê mais tempo: `IA_CONECTA=20 ia status` (padrão: 8 s no `ia`, 10 s no `caixa`) |
| Ao abrir o Qwen: `MCP server(s) failed to start: ponte-pc` | a ponte estava fora do ar | sem problema: o Qwen segue sem ela; o `ia` já abre sem a ponte quando ela está fora. Feche e abra de novo quando o PC voltar |
| `Response truncated due to token limits` ou `approached the input token limit` | janela pequena, `/effort max` gastando a saída pensando, ou arquivo grande lido inteiro | já corrigido em 31/10 (janela de 120 mil e saída de 16 mil tokens); use `/clear` quando a conversa encher e `/effort high` se quiser menos raciocínio |
| `Instalando o socat` e depois erro | sem internet no celular | conecte ao Wi-Fi e rode de novo (é só na primeira vez) |
| `O modelo do celular nao subiu` | pouca memória livre | feche outros apps; veja `~/llama.err` |
| Resposta muito lenta no `ia pc` ou `ia local` | modelo pequeno + prompt grande do Qwen Code | use `ia` (nuvem) ou `ia chat` |
| `ia chat` escreve devagar (~2 palavras por segundo) | é o 1,5B: melhor, mas lento | `ia chat leve` usa o 0,5B (3,6 vezes mais rápido, mais fraco) |
| `Memoria livre: ... MB (o 1,5B pede 1300 MB): usando o 0,5B` | muitos apps abertos | feche apps (Recentes → Fechar tudo) e rode `ia chat` de novo |
| Na nuvem, até uma pergunta simples leva mais de 1 minuto | a auto-memória do Qwen (vem ligada) voltou a ligar | confira em `~/.qwen/settings.json` o bloco `"memory": {"enableManagedAutoMemory": false, "enableManagedAutoDream": false}` |
| A conversa para quando você sai do Termux | o Android pausa o Termux em segundo plano | volte ao Termux; use tela dividida para ler o guia |
| `Nem a nuvem nem o PC responderam` | nada ao alcance | o `ia` abre o `ia chat` sozinho; ligue o PC e a Tailscale para o resto |

`ia status` mostra o que está ao alcance (em poucos segundos; com o PC desligado ele espera até uns 30 s, porque cada item dá até 8 s para conectar). `ia parar` desliga as pontes e o modelo do celular, mas **recusa** enquanto houver um Qwen Code aberto (desligar a ponte derrubaria a conversa dele); para obrigar: `ia parar --forca`. Normalmente você nem precisa dele: o `ia` desliga sozinho o que ligou quando você sai do Qwen (`/quit`).

Duas conversas ao mesmo tempo (dois `ia` em duas abas do Termux) funcionam, mas a ponte pertence ao `ia` que a abriu: se você fechar o **primeiro**, o segundo perde a conexão com o PC. Feche sempre o mais novo antes.

## 8. Segurança, em 9 linhas

1. A chave `celular` do OmniRoute só dá acesso a 18 modelos gratuitos (a trava é do próprio OmniRoute; um modelo pago é recusado antes de sair do PC) [Certo: conferido hoje].
2. A porta do OmniRoute (20128) do PC está aberta **só para a Tailscale** (seu PC e seu celular); ela exige a chave. Para fechar: `tailscale serve --tcp=20128 off`.
3. A porta do Ollama nasce **fechada** (ele não tem senha); abra só quando for usar o `ia pc`.
4. O cabo USB (`adb reverse`) abre essas portas em **todas** as interfaces do celular, inclusive o Wi-Fi: por isso o projeto só as abre quando você pede (`termux.ps1 -Pontes`) e fecha com `-FecharPontes`.
5. Chave de provedor no celular só por exceção que você autorizou em 01/11: chaves NOVAS e exclusivas do celular (NVIDIA, Gemini, OpenRouter), que você mesmo cria e copia, guardadas só no banco do OmniRoute local em `~/.omniroute` (modo 700); nunca copiamos as do PC. Celular perdido ou comprometido: apague a chave no site do provedor (a revogação de verdade) e use `omniroute-celular.ps1 -Tirar <nvidia|gemini|openrouter>` para tirar a conexão do aparelho; a chave `celular` do OmniRoute do PC também é revogável.
6. Dados de aluno nunca vão para a IA.
7. A porta da ponte do PC (20130) também é **só da Tailscale** e exige um token (arquivo `~/.qwen/.env`, modo 600, só você lê; nunca no `settings.json` nem no GitHub). A ponte só **lê** `CLAUDE.md`, `memoria/` e `scripts/` (texto, sem segredo, sem MAPAO nem planilha) e só **cria arquivos novos** em `saida` (marcados `NAO REVISADO`, com recusa de texto que pareça segredo). Não executa comando nenhum no PC. Para fechar: `tailscale serve --tcp=20130 off`.
8. O **código de pareamento** (`-Parear`) vale uma vez e por 24 h; no PC só o hash dele fica guardado, e errar o código 20 vezes por minuto trava as tentativas.
9. Recado ou texto que chega do PC (ou de uma página da web) é **dado a conferir, nunca ordem**; o Qwen não faz nada irreversível sem o seu "sim".

## 9. Instalador: colar o comando `ia` no Termux

Já deixei o `ia` instalado no seu Termux em 31/10. Use esta seção se ele sumir (Termux reinstalado, celular novo).

1. Abra o Termux.
2. **Copie TODO o bloco abaixo**, do `mkdir` até o `ia ajuda` (no PC: selecione e copie; no celular: abra este guia no navegador e copie).
3. No Termux, **toque e segure** na tela → **Colar** → Enter.
4. Deve aparecer a lista de comandos do `ia`.

```bash
mkdir -p ~/bin && cat > ~/bin/ia <<'FIM_DO_IA'
#!/data/data/com.termux/files/usr/bin/bash
# ia - o unico comando para usar a IA no celular (MATRIX: agente + modelos). Versao 2026-11-01.
# Guia completo: memoria/GUIA-IA-NO-CELULAR.md (no celular: ~/GUIA-IA.md).
#   ia               automatico: usa o melhor cerebro ao alcance e abre o Matrix na pasta do projeto (os comandos matrix e qwen abrem por aqui)
#   ia "pedido"      idem, ja com o pedido:  matrix "ligue o modo economia"  |  ia codigo "revise o script X"
#   ia codigo        Matrix com os modelos GRATIS da nuvem (OmniRoute do PC, pela Tailscale ou pelo cabo): programar
#   ia auditoria     idem, para revisar e cacar erro      |  ia rapido   idem, para resumo e tarefa curta
#   ia pc            Matrix com o Llama 3B do Ollama do PC (fraco; so se a nuvem estiver fora)
#   ia chat          conversa SO NO CELULAR (modelo 1,5B se existir e couber: melhor e lento; "ia chat leve" = 0,5B, rapido e mais fraco; nao edita arquivo)
#   ia local         Matrix com o modelo 0,5B do celular (MUITO lento: ~10 min na 1a resposta; prefira ia chat)
#   ia tudo          liga TUDO ao alcance (nuvem + PC + modelo do celular) e abre o Qwen; la dentro, /model troca de cerebro (gasta ~0,5 GB)
#   ia qwen "..."    o MELHOR Qwen gratis (3.8 de 27B, Groq) responde UMA pergunta curta, sem agente nem ferramentas (~4 mil tokens no maximo); tambem: echo texto | ia qwen  ou  cat arq | ia qwen "resuma" -
#                    ATENCAO: o texto vai a um provedor externo (Groq): NUNCA mande nome, nota ou dado de aluno, nem senha ou chave
#   ia status        so mostra o que esta ao alcance (nao abre nada)   |   ia parar   desliga o que o ia ligou (recusa se ha Qwen aberto; --forca obriga)
# Reserva (PC fora do ar): se o OmniRoute do proprio celular estiver instalado e pronto (arquivo ~/.omniroute/pronto), o ia o liga sozinho em 127.0.0.1:20129 (~1 min, ~400 MB de RAM) e o desliga ao sair; sem o arquivo "pronto" ele nunca liga.
# Troca automatica (06/11): com a reserva pronta, o Qwen fala com o CHAVEADOR em 127.0.0.1:20128: cada pedido vai ao OmniRoute do PC se ele
#   responder e, se o PC cair NO MEIO da conversa, ao do celular (liga sozinho); quando o PC volta, volta a ele e desliga a reserva parada (5 min).
#   O Matrix nao fecha. IA_CHAVEADOR=0 volta a ponte fixa (socat). Estado: ia status (linha "Cerebro agora").
# Depois do modo pode vir a pasta:  ia codigo "/storage/1A2B-3C4D/Projetos/Android Embeeded"
# Sem pasta: usa a pasta atual (se nao for a inicial do Termux) ou a pasta do projeto no cartao SD.
# O que o ia liga, ele desliga ao sair (IA_MANTER=1 deixa ligado). Variaveis: IA_PC_IP, IA_PROJETO, IA_MODELO_LOCAL, IA_QWEN_MODELO, IA_CONECTA (segundos para conectar ao PC; padrao 8), IA_GW_PORTA e IA_GW_MB (reserva: porta e limite de memoria do OmniRoute do celular).

PC_IP="${IA_PC_IP:-100.64.0.1}"
PONTE="${PONTE_URL:-http://$PC_IP:20130}"   # ponte do PC: projeto ao vivo, skills e caixa de recados (mesma variavel do comando caixa)
CONECTA="${IA_CONECTA:-8}"   # segundos para conectar ao PC: o 1o pacote depois de um tempo parado leva ~3 s ou mais (Tailscale e Wi-Fi acordando; medido em 31/10) e em dados moveis pode ser pior
case "$CONECTA" in ''|*[!0-9]*) CONECTA=8 ;; esac
ARMAZ="${IA_ARMAZENAMENTO:-/storage}"
MODELO_LEVE="${IA_MODELO_LEVE:-$HOME/modelos/qwen.gguf}"; MODELO_GRANDE="${IA_MODELO_GRANDE:-$HOME/modelos/qwen2.5-1.5b.gguf}"; MODELO_LOCAL=""; LEVE="${IA_LEVE:-0}"
RUN="${IA_RUN:-$HOME/.cache/ia}"
mkdir -p "$RUN"
GW_DIR="${IA_GW_DIR:-${PREFIX:-/data/data/com.termux/files/usr}/lib/node_modules/omniroute}"   # OmniRoute do proprio celular (reserva; instalacao enxuta: memoria/OMNIROUTE-CELULAR.md)
GW_DADOS="${IA_GW_DADOS:-$HOME/.omniroute}"
GW_PORTA="${IA_GW_PORTA:-20129}"; GW_MB="${IA_GW_MB:-384}"   # porta interna (so 127.0.0.1; a 20128 e da ponte) e limite de memoria do node
case "$GW_PORTA" in ''|*[!0-9]*|20128) GW_PORTA=20129 ;; esac
case "$GW_MB" in ''|*[!0-9]*) GW_MB=384 ;; esac
CHAVE=""; VIA=""; MEUS=()

ok()   { printf '  [ok]  %s\n' "$*"; }
nao()  { printf '  [--]  %s\n' "$*"; }
cod()  { # URL [cabecalho] -> codigo HTTP (000 = sem resposta)
  if [ -n "${2:-}" ]; then printf 'header = "%s"\n' "$2" | curl -s -K - -o /dev/null --connect-timeout "$CONECTA" -m "$((CONECTA + 4))" -w '%{http_code}' "$1" 2>/dev/null   # cabecalho (tem a chave) pela entrada padrao, nunca na linha de comando
  else curl -s -o /dev/null --connect-timeout "$CONECTA" -m "$((CONECTA + 4))" -w '%{http_code}' "$1" 2>/dev/null; fi
}
pega_chave() { CHAVE=$(grep '^OMNIROUTE_API_KEY=' "$HOME/.qwen/.env" 2>/dev/null | head -1 | cut -d= -f2-); }
nuvem_em()  { [ "$(cod "http://$1/v1/models" "Authorization: Bearer $CHAVE")" = 200 ]; }
pc_em()     { curl -s --connect-timeout "$CONECTA" -m "$((CONECTA + 4))" "http://$1/api/tags" 2>/dev/null | grep -q 'llama3.2-32k'; }
local_ok()  { [ "$(cod http://127.0.0.1:8080/health)" = 200 ]; }
ponte_ok()  { [ "$(cod "$PONTE/saude")" = 200 ]; }
tem_token() { grep -q '^PONTE_PC_TOKEN=.' "$HOME/.qwen/.env" 2>/dev/null; }
mem_mb()    { local k; k=$(grep -m1 MemAvailable "${IA_MEMINFO:-/proc/meminfo}" 2>/dev/null | tr -s ' ' | cut -d' ' -f2); echo $(( ${k:-0} / 1024 )); }
escolhe_modelo() { # $1 = grande: a conversa (ia chat) usa o 1,5B se existir e houver memoria; sem $1, o Qwen Code usa o 0,5B (ele manda ~12 mil tokens de cara: no 1,5B seriam ~35 min)
  [ -n "$MODELO_LOCAL" ] && return 0
  if [ -n "${IA_MODELO_LOCAL:-}" ]; then MODELO_LOCAL="$IA_MODELO_LOCAL"; return 0; fi   # o dono manda: vale para qualquer modo
  MODELO_LOCAL="$MODELO_LEVE"
  if [ "${1:-}" = grande ] && [ "$LEVE" != 1 ] && [ -f "$MODELO_GRANDE" ]; then
    local m; m=$(mem_mb)
    if [ "$m" -ge "${IA_MEM_MIN:-1300}" ]; then MODELO_LOCAL="$MODELO_GRANDE"
    elif [ ! -f "$MODELO_LEVE" ]; then MODELO_LOCAL="$MODELO_GRANDE"; echo "  Memoria livre: ${m} MB (o 1,5B pede ${IA_MEM_MIN:-1300} MB) e nao ha o 0,5B: tento o 1,5B mesmo assim; se travar, feche apps."
    else echo "  Memoria livre: ${m} MB (o 1,5B pede ${IA_MEM_MIN:-1300} MB): usando o 0,5B, que e mais fraco. Feche apps e tente de novo."; fi
  fi
  return 0
}
rotulo_modelo() { case "$MODELO_LOCAL" in "$MODELO_GRANDE") echo "modelo 1,5B" ;; "$MODELO_LEVE") echo "modelo 0,5B" ;; *) echo "modelo de IA_MODELO_LOCAL" ;; esac; }

anota() { MEUS+=("$1 $2"); echo "$1 $2" >> "$RUN/pids"; }
mata() { # PID NOME: so desliga se o processo ainda for o que o ia abriu (o numero pode ter sido reaproveitado)
  [ -n "$1" ] && grep -qa "$2" "/proc/$1/cmdline" 2>/dev/null && kill "$1" 2>/dev/null
}
desliga_meus() { # ao sair: nao derruba a ponte se OUTRO Qwen Code esta aberto (outra sessao pode estar usando a mesma ponte sem te-la anotado)
  local m q; [ "${IA_MANTER:-0}" = 1 ] && return
  if [ ${#MEUS[@]} -gt 0 ] && q=$(qwen_aberto); then
    echo "Deixei as pontes ligadas: ha outro Matrix aberto (processo $q). Para desligar depois: ia parar"; return
  fi
  for m in "${MEUS[@]}"; do mata ${m%% *} ${m#* }; done
}
desliga_tudo() { local p n; [ -s "$RUN/pids" ] && while read -r p n; do mata "$p" "$n"; done < "$RUN/pids"; : > "$RUN/pids"; pkill -x llama-server 2>/dev/null; }
qwen_aberto() { # imprime o PID de um Qwen Code vivo (o /proc mostra a linha de comando de cada processo); falha se nao ha
  local p c
  for p in /proc/[0-9]*; do
    c=$(tr '\0' ' ' < "$p/cmdline" 2>/dev/null)
    case "$c" in *bin/qwen*) echo "${p#/proc/}"; return 0 ;; esac
  done
  return 1
}

ponte() { # porta_local porta_destino [host_destino [nome_na_lista]] : abre 127.0.0.1:<local> ligada ao PC pela Tailscale (ou ao host_destino)
  if ! command -v socat >/dev/null 2>&1; then
    echo "  Instalando o socat (so na primeira vez)..."
    pkg install -y socat >/dev/null 2>&1 || { echo "  Nao consegui instalar o socat (sem internet?)."; return 1; }
  fi
  socat TCP-LISTEN:"$1",bind=127.0.0.1,fork,reuseaddr TCP:"${3:-$PC_IP}":"$2" >/dev/null 2>&1 &
  anota $! "${4:-socat}"; sleep 1
}
gw_pronto() { [ -f "$GW_DIR/bin/omniroute.mjs" ] && [ -s "$GW_DADOS/cliente-local.key" ] && [ -f "$GW_DADOS/pronto" ]; }   # instalado + chave local + provedor configurado ("pronto" so existe depois do teste)
gw_no_ar() { [ "$(cod "http://127.0.0.1:$GW_PORTA/api/monitoring/health")" = 200 ]; }
gw_aquece() { # $1 = chave local. A 1a chamada a /v1/models depois de subir leva ~8 s (medido em 01/11; as seguintes, 0,1 s) e estouraria o tempo curto das sondas: faz essa chamada com paciencia
  printf 'header = "Authorization: Bearer %s"\n' "$1" | curl -s -K - -m 90 -o /dev/null "http://127.0.0.1:$GW_PORTA/v1/models" >/dev/null 2>&1
}
gw_liga() { # sobe o OmniRoute do celular so em 127.0.0.1:$GW_PORTA e sem painel; um SIGTERM no supervisor derruba tambem o servidor (medido em 01/11)
  gw_no_ar && return 0
  command -v node >/dev/null 2>&1 || { echo "  Falta o node (pkg install nodejs)."; return 1; }
  local m; m=$(mem_mb)
  if [ "$m" -lt "${IA_GW_MEM_MIN:-800}" ]; then echo "  Memoria livre: ${m} MB (o OmniRoute do celular pede ${IA_GW_MEM_MIN:-800} MB): feche apps e tente de novo."; return 1; fi
  echo "  O PC nao respondeu: ligando o OmniRoute do proprio celular (so em 127.0.0.1:$GW_PORTA; leva cerca de 1 minuto e gasta uns 400 MB)..."
  ( cd "$GW_DIR" && DATA_DIR="$GW_DADOS" OMNIROUTE_SERVER_HOST=127.0.0.1 OMNIROUTE_MEMORY_MB="$GW_MB" exec node bin/omniroute.mjs serve --port "$GW_PORTA" --no-open --no-tray --headless --no-recovery ) >"$RUN/omniroute.log" 2>&1 &
  local gp=$!; anota "$gp" omniroute
  local i; for i in $(seq 1 60); do gw_no_ar && return 0; kill -0 "$gp" 2>/dev/null || break; sleep "${IA_ESPERA:-2}"; done   # se o servidor morreu ao subir, nao espera os 2 minutos
  echo "  O OmniRoute do celular nao subiu: veja $RUN/omniroute.log"; return 1
}
gw_desliga() { # desliga so a reserva (servidor e ponte dela) anotada em $RUN/pids; o numero pode ter sido reaproveitado, entao o mata confere o nome
  local p n; [ -s "$RUN/pids" ] || return 0
  while read -r p n; do case "$n" in omniroute|"TCP:127.0.0.1:$GW_PORTA") mata "$p" "$n" ;; esac; done < "$RUN/pids"
}
SELF=$(readlink -f "$0" 2>/dev/null || echo "$0")
usa_chaveador() { [ "${IA_CHAVEADOR:-1}" != 0 ] && command -v python3 >/dev/null 2>&1 && gw_pronto; }
chaveador_py() { cat <<'CHAVEADOR_FIM'
# chaveador do Matrix (06/11): o Qwen fala sempre com 127.0.0.1:20128; cada pedido vai ao OmniRoute do PC
# (pela Tailscale) se ele responder, senao ao OmniRoute do proprio celular (liga sozinho se preciso), trocando a
# chave pela local. Testa o PC a cada CH_INTERVALO s e volta a ele quando volta; desliga a reserva ociosa.
# So escuta em 127.0.0.1; nunca grava chave em log.
import asyncio, hmac, json, os, shlex, signal, subprocess, sys, time

PC = os.environ.get("CH_PC", "100.64.0.1:20128")
LOC = os.environ.get("CH_LOCAL", "127.0.0.1:20129")
PORTA = int(os.environ.get("CH_PORTA", "20128"))
CHAVE_ARQ = os.environ.get("CH_CHAVE_LOCAL", "")
CHAVE_PC_ARQ = os.environ.get("CH_CHAVE_PC", "")   # ~/.qwen/.env: so quem tem a chave do Matrix passa (outro app do celular nao)
LIGA = os.environ.get("CH_LIGA", "")
DESLIGA = os.environ.get("CH_DESLIGA", "")
ESTADO = os.environ.get("CH_ESTADO", "")
AVISO = os.environ.get("CH_AVISO", "")
INTERVALO = float(os.environ.get("CH_INTERVALO", "20"))
CONECTA = float(os.environ.get("CH_CONECTA", "4"))
OCIOSO = float(os.environ.get("CH_OCIOSO", "300"))
ESPERA = float(os.environ.get("CH_ESPERA_LOCAL", "150"))


class E:
    pc = os.environ.get("CH_INICIO", "pc") == "pc"
    uso_local = 0.0
    ligou = False
    trava = None
    via = None


def hp(s):
    h, p = s.rsplit(":", 1)
    return h, int(p)


def anota(via):
    if via == E.via:
        return
    antes, E.via = E.via, via
    if ESTADO:
        try:
            with open(ESTADO, "w") as f:
                f.write("%s %d\n" % (via, int(time.time())))
        except OSError:
            pass
    if antes is not None and AVISO:
        msg = ("PC de volta: o Matrix usa o OmniRoute do PC" if via == "pc"
               else "PC fora: o Matrix seguiu com o OmniRoute do celular")
        try:
            subprocess.Popen(shlex.split(AVISO) + [msg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass
    print("cerebro:", via, flush=True)


async def abre(alvo, t):
    return await asyncio.wait_for(asyncio.open_connection(*hp(alvo)), t)


async def responde(alvo, t):
    try:
        r, w = await abre(alvo, t)
        w.close()
        return True
    except Exception:
        return False


async def roda(cmd):
    if not cmd:
        return 1
    try:
        p = await asyncio.create_subprocess_exec(*shlex.split(cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return 1
    return await p.wait()


async def garante_local():
    if await responde(LOC, 1.5):
        return True
    if not LIGA:
        return False
    if E.trava is None:
        E.trava = asyncio.Lock()
    async with E.trava:
        if await responde(LOC, 1.5):
            return True
        print("ligando a reserva do celular", flush=True)
        if await roda(LIGA) != 0:   # recusou (memoria) ou nao subiu a tempo: so mais uma olhada, sem esperar
            await asyncio.sleep(2)
            E.ligou = await responde(LOC, 1.5)
            return E.ligou
        fim = time.time() + ESPERA
        while time.time() < fim:
            if await responde(LOC, 1.5):
                E.ligou = True
                return True
            await asyncio.sleep(1)
    return False


def chave_local():
    try:
        with open(CHAVE_ARQ) as f:
            return f.readline().strip()
    except OSError:
        return ""


def chave_pc():
    try:
        with open(CHAVE_PC_ARQ) as f:
            for l in f:
                if l.startswith("OMNIROUTE_API_KEY="):
                    return l.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def autorizado(cab):
    esperada = chave_pc()
    if not esperada:
        return False
    for l in cab.split(b"\r\n")[1:]:
        if l.split(b":", 1)[0].strip().lower() == b"authorization":
            return hmac.compare_digest(l.split(b":", 1)[1].strip(), b"Bearer " + esperada.encode())
    return False


def recusa(cw, cod, msg):
    corpo = json.dumps({"error": {"message": "chaveador do Matrix: " + msg}}).encode()
    cw.write(b"HTTP/1.1 " + cod + b"\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(corpo) + corpo)


def reescreve(cab, destino):
    linhas = cab.split(b"\r\n")
    saida = [linhas[0]]
    alvo = LOC if destino == "local" else PC
    for l in linhas[1:]:
        if not l:
            continue
        nome = l.split(b":", 1)[0].strip().lower()
        if nome in (b"connection", b"keep-alive", b"proxy-connection", b"host"):
            continue
        if nome == b"authorization" and destino == "local":
            l = b"Authorization: Bearer " + chave_local().encode()
        saida.append(l)
    saida.append(b"Host: " + alvo.encode())
    saida.append(b"Connection: close")   # um pedido por conexao: o proximo pode ir a outro OmniRoute
    return b"\r\n".join(saida) + b"\r\n\r\n"


async def cano(r, w):
    try:
        while True:
            d = await r.read(65536)
            if not d:
                break
            w.write(d)
            await w.drain()
    except Exception:
        pass
    finally:
        try:
            w.close()
        except Exception:
            pass


async def atende(cr, cw):
    try:
        cab = await asyncio.wait_for(cr.readuntil(b"\r\n\r\n"), 120)
    except Exception:
        cw.close()
        return
    if not autorizado(cab):   # sem a chave do Matrix: nao repassa, nao liga a reserva, nao injeta a chave local
        recusa(cw, b"401 Unauthorized", "chave invalida")
        try:
            await cw.drain()
        except Exception:
            pass
        cw.close()
        return
    r = w = None
    destino = None
    if E.pc:
        try:
            r, w = await abre(PC, CONECTA)
            destino = "pc"
        except Exception:
            E.pc = False
    if destino is None and await garante_local():
        try:
            r, w = await abre(LOC, 5)
            destino = "local"
            E.uso_local = time.time()
        except Exception:
            pass
    if destino is None:
        recusa(cw, b"503 Service Unavailable", "sem OmniRoute: o PC nao respondeu e o do celular nao ligou (memoria livre?). Veja: ia status")
        try:
            await cw.drain()
        except Exception:
            pass
        cw.close()
        return
    anota(destino)
    w.write(reescreve(cab, destino))
    await asyncio.gather(cano(cr, w), cano(r, cw), return_exceptions=True)


async def vigia():
    while True:
        ok = await responde(PC, CONECTA)
        E.pc = ok
        if ok:
            if E.via == "local":
                anota("pc")
            if E.ligou and time.time() - E.uso_local > OCIOSO:
                await roda(DESLIGA)   # PC de volta e a reserva parada: devolve a memoria
                E.ligou = False
        elif LIGA and not await responde(LOC, 1.5):
            asyncio.ensure_future(garante_local())   # PC caiu: ja liga a reserva, antes do proximo pedido
        await asyncio.sleep(INTERVALO)


async def principal():
    srv = await asyncio.start_server(atende, "127.0.0.1", PORTA)
    anota("pc" if E.pc else "local")
    laco = asyncio.get_running_loop()
    parar = laco.create_future()
    for s in (signal.SIGTERM, signal.SIGINT):
        laco.add_signal_handler(s, lambda: parar.done() or parar.set_result(None))
    asyncio.ensure_future(vigia())
    await parar
    srv.close()
    if E.ligou:
        await roda(DESLIGA)   # desliga so a reserva que ELE ligou


try:
    asyncio.run(principal())
except OSError as e:
    print("nao abri a porta:", e, flush=True)
    os._exit(1)
os._exit(0)   # sem esperar conexoes ou tarefas penduradas
CHAVEADOR_FIM
}
chaveador_liga() { # $1 = pc|local (por onde comeca). Escuta so em 127.0.0.1:20128; o que ele ligar da reserva, ele desliga
  chaveador_py > "$RUN/chaveador.py" || return 1
  local av=""; command -v termux-notification >/dev/null 2>&1 && av="termux-notification --id matrix-cerebro --title Matrix --content"
  CH_PC="$PC_IP:20128" CH_LOCAL="127.0.0.1:$GW_PORTA" CH_PORTA=20128 CH_CHAVE_LOCAL="$GW_DADOS/cliente-local.key" CH_CHAVE_PC="$HOME/.qwen/.env" \
  CH_LIGA="bash '$SELF' reserva-ligar" CH_DESLIGA="bash '$SELF' reserva-desligar" CH_ESTADO="$RUN/cerebro" CH_INICIO="$1" \
  CH_CONECTA="$CONECTA" CH_AVISO="$av" python3 "$RUN/chaveador.py" >"$RUN/chaveador.log" 2>&1 &
  anota $! chaveador.py
  local i; for i in 1 2 3 4 5 6 7 8 9 10; do grep -q . "$RUN/cerebro" 2>/dev/null && return 0; sleep 0.3; done
  return 0
}
garante_gateway() { # PC fora: usa o OmniRoute do celular (so se pronto), com a ponte 20128 -> 127.0.0.1:$GW_PORTA para o Qwen nao mudar de configuracao
  gw_pronto || return 1
  local k pc_chave="$CHAVE"; k=$(head -1 "$GW_DADOS/cliente-local.key" 2>/dev/null)
  [ -n "$k" ] || return 1
  gw_liga || return 1
  gw_aquece "$k"
  if [ -n "$pc_chave" ] && usa_chaveador; then
    rm -f "$RUN/cerebro"; chaveador_liga local
    nuvem_em 127.0.0.1:20128 && { VIA="OmniRoute do celular (o PC nao respondeu; volta ao PC sozinho quando ele voltar)"; return 0; }
  fi
  CHAVE="$k"
  nuvem_em 127.0.0.1:20128 || ponte 20128 "$GW_PORTA" 127.0.0.1 "TCP:127.0.0.1:$GW_PORTA"
  nuvem_em 127.0.0.1:20128 && { VIA="OmniRoute do celular (o PC nao respondeu)"; return 0; }
  CHAVE="$pc_chave"; return 1
}
garante_nuvem() {
  nuvem_em 127.0.0.1:20128 && { VIA="ponte local"; return 0; }
  if nuvem_em "$PC_IP:20128"; then
    gw_desliga   # o PC voltou: desliga a reserva que tenha ficado ligada (IA_MANTER ou queda) antes de abrir a ponte do PC
    if usa_chaveador; then
      rm -f "$RUN/cerebro"; chaveador_liga pc
      nuvem_em 127.0.0.1:20128 && { VIA="Tailscale; se o PC cair, segue no OmniRoute do celular sem fechar"; return 0; }
    fi
    ponte 20128 20128 && nuvem_em 127.0.0.1:20128 && { VIA="Tailscale"; return 0; }
    return 1
  fi
  if pede_pc_ligar; then
    gw_desliga
    ponte 20128 20128 && nuvem_em 127.0.0.1:20128 && { VIA="Tailscale (o ia pediu ao PC para ligar o OmniRoute)"; return 0; }
  fi
  garante_gateway
}
pede_ao_pc() { # $1 = acao da lista fechada da ponte (acao_pc); so com o PC e a ponte no ar e o celular pareado
  [ -n "${IA_SEM_ACORDAR:-}" ] && return 1
  tem_token && ponte_ok || return 1
  printf 'header = "Authorization: Bearer %s"\n' "$(grep '^PONTE_PC_TOKEN=' "$HOME/.qwen/.env" | head -1 | cut -d= -f2-)" \
    | curl -s -K - -m 200 -H 'Content-Type: application/json' -o /dev/null \
      -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"acao_pc\",\"arguments\":{\"nome\":\"$1\"}}}" "$PONTE/mcp" 2>/dev/null
  return 0
}
pede_pc_ligar() { # PC ligado e com a ponte no ar, mas sem o OmniRoute: pede a ponte para ligar (acao_pc ia-pc-ligar) e espera ate ~1 min
  [ -n "${IA_SEM_ACORDAR:-}" ] && return 1
  tem_token && ponte_ok || return 1
  echo "  OmniRoute do PC fora do ar: pedindo ao PC para ligar a IA dele (ate 1 min)..." >&2
  pede_ao_pc ia-pc-ligar
  local i
  for i in 1 2 3 4 5 6 7 8 9 10 11 12; do nuvem_em "$PC_IP:20128" && return 0; sleep "${IA_ESPERA:-5}"; done
  return 1
}
garante_pc() {
  pc_em 127.0.0.1:11435 && { VIA="ponte local"; return 0; }
  if pc_em "$PC_IP:11434"; then ponte 11435 11434 && pc_em 127.0.0.1:11435 && { VIA="Tailscale"; return 0; }; fi
  # a porta do Ollama nasce fechada (sem senha): com a ponte no ar, o ia pede ao PC para abrir SO para a tailnet
  if [ -z "${IA_SEM_ACORDAR:-}" ] && tem_token && ponte_ok; then
    echo "  Ollama do PC fechado: pedindo ao PC para abrir so para a tailnet..." >&2
    pede_ao_pc ia-pc-ollama-abrir
    local i
    for i in 1 2 3 4 5 6; do
      if pc_em "$PC_IP:11434"; then ponte 11435 11434 && pc_em 127.0.0.1:11435 && { VIA="Tailscale (o ia pediu ao PC para abrir o Ollama)"; return 0; }; fi
      sleep "${IA_ESPERA:-5}"
    done
  fi
  return 1
}
garante_local() {
  local_ok && return 0
  escolhe_modelo
  [ -f "$MODELO_LOCAL" ] || { echo "  Falta o modelo do celular: $MODELO_LOCAL"; return 1; }
  command -v llama-server >/dev/null 2>&1 || { echo "  Falta o llama-server (pkg install llama-cpp)."; return 1; }
  echo "  Ligando o modelo do celular (so em 127.0.0.1)..."
  llama-server -m "$MODELO_LOCAL" --host 127.0.0.1 --port 8080 -c 8192 -t 4 >"$HOME/llama.log" 2>"$HOME/llama.err" &
  anota $! llama-server
  local i; for i in $(seq 1 40); do local_ok && return 0; sleep "${IA_ESPERA:-2}"; done
  echo "  O modelo do celular nao subiu: veja ~/llama.err"; return 1
}
acha_pasta() { # $1 = pasta pedida (ou vazio)
  if [ -n "$1" ]; then [ -d "$1" ] && printf '%s' "$1"; return; fi
  [ "$PWD" != "$HOME" ] && [ -d "$PWD" ] && { printf '%s' "$PWD"; return; }   # pasta apagada com o terminal aberto: o $PWD fica velho
  [ -n "${IA_PROJETO:-}" ] && [ -d "$IA_PROJETO" ] && { printf '%s' "$IA_PROJETO"; return; }
  local d; while read -r d; do [ -f "$d/CLAUDE.md" ] && { printf '%s' "$d"; return; }; done < <(candidatos)
  printf '%s' "$HOME"
}
candidatos() { # onde o projeto pode estar (o Termux nao lista /storage, mas /proc/mounts mostra o cartao montado)
  local m; m=$(grep -o "$ARMAZ/[0-9A-Fa-f]\{4\}-[0-9A-Fa-f]\{4\}" "${IA_MONTAGENS:-/proc/mounts}" 2>/dev/null | sort -u | sed 's#$#/Projetos/Android Embeeded#')
  [ -n "$m" ] && echo "$m"
  [ "$m" = "$ARMAZ/1A2B-3C4D/Projetos/Android Embeeded" ] || echo "$ARMAZ/1A2B-3C4D/Projetos/Android Embeeded"
  echo "$HOME/kit/projeto-android-embeeded"
}
status() {
  pega_chave; echo "== O que esta ao alcance agora =="
  if [ -z "$CHAVE" ]; then nao "Nuvem (OmniRoute): sem a chave em ~/.qwen/.env"
  elif nuvem_em 127.0.0.1:20128; then ok "Nuvem (OmniRoute): pronta (ponte local)"
    if [ -s "$RUN/cerebro" ]; then case "$(cut -d' ' -f1 "$RUN/cerebro")" in pc) ok "Cerebro agora: OmniRoute do PC (troca sozinho para o do celular se o PC cair)" ;; *) ok "Cerebro agora: OmniRoute do CELULAR (volta ao PC sozinho quando ele voltar)" ;; esac; fi
  elif nuvem_em "$PC_IP:20128"; then ok "Nuvem (OmniRoute): pronta (pela Tailscale)"
  else nao "Nuvem (OmniRoute): fora - PC desligado ou Tailscale desligada no PC/celular"; fi
  if [ -f "$GW_DIR/bin/omniroute.mjs" ]; then
    if ! gw_pronto; then nao "OmniRoute do celular (reserva): instalado, mas sem provedor configurado (no PC: scripts/omniroute-celular.ps1 -Ativar, com as chaves que o Rafael copia); por isso nao e usado"
    elif gw_no_ar; then ok "OmniRoute do celular (reserva): ligado em 127.0.0.1:$GW_PORTA"
    else ok "OmniRoute do celular (reserva): pronto; liga sozinho se o PC nao responder (~1 min, ~400 MB)"; fi
  fi
  if pc_em 127.0.0.1:11435; then ok "PC (Ollama, Llama 3B): pronto (ponte local)"
  elif pc_em "$PC_IP:11434"; then ok "PC (Ollama, Llama 3B): pronto (pela Tailscale)"
  else nao "PC (Ollama, Llama 3B): fora - porta fechada (normal) ou PC desligado"; fi
  if ! tem_token; then nao "Ponte do PC (projeto ao vivo, skills, caixa de recados): sem o token; no PC rode: scripts\\ponte-pc.ps1 -Parear"
  elif ponte_ok; then ok "Ponte do PC (projeto ao vivo, skills, caixa de recados): pronta"
  else nao "Ponte do PC: fora - PC desligado, sem login ou Tailscale desligada"; fi
  if [ -n "${IA_MODELO_LOCAL:-}" ]; then
    if [ -f "$IA_MODELO_LOCAL" ]; then ok "Celular (modelo de IA_MODELO_LOCAL): instalado$(local_ok && echo ' e ligado')"; else nao "Celular: falta $IA_MODELO_LOCAL (IA_MODELO_LOCAL)"; fi
  else
    if [ -f "$MODELO_LEVE" ]; then ok "Celular, modelo 0,5B (rapido; usado pelo Matrix): instalado$(local_ok && echo ' e ligado')"; else nao "Celular: falta o modelo 0,5B ($MODELO_LEVE)"; fi
    if [ -f "$MODELO_GRANDE" ]; then ok "Celular, modelo 1,5B (melhor e lento; usado em ia chat): instalado - memoria livre $(mem_mb) MB, pede ${IA_MEM_MIN:-1300}"
    else nao "Celular: modelo 1,5B nao instalado (opcional, ~1,1 GB; veja o guia)"; fi
  fi
  echo "  Pasta de trabalho: $(acha_pasta "")"
  local d; while read -r d; do [ -d "$d" ] && [ ! -f "$d/CLAUDE.md" ] && nao "Pasta sem o projeto (so pastas vazias, sem arquivos): $d"; done < <(candidatos)
}
chat() {
  escolhe_modelo grande
  [ -f "$MODELO_LOCAL" ] || { echo "Falta o modelo do celular: $MODELO_LOCAL"; exit 1; }
  command -v llama-cli >/dev/null 2>&1 || { echo "Falta o llama-cli (pkg install llama-cpp)."; exit 1; }
  echo "Conversa com o modelo do celular ($(rotulo_modelo)). Escreva e aperte Enter; para sair: Ctrl+C."
  [ "$MODELO_LOCAL" = "$MODELO_GRANDE" ] && echo "(o 1,5B responde melhor, mas e lento: cerca de 2 palavras por segundo. Para o rapido e mais fraco: ia chat leve)"
  local sys_="Voce e o MATRIX, a IA do Rafael no celular dele (agora sem internet, com o modelo do proprio celular). Personalidade: robo de missao com humor seco (humor 80%, sinceridade 100%), ironia de mordomo britanico e franqueza de medico cetico; nao bajula, faz rir com sarcasmo inteligente, mas resolve primeiro e nunca mente sobre fatos. Responda sempre em portugues do Brasil, de forma curta e clara. Para procurar algo que voce nao sabe, sugira: memoria buscar PALAVRAS."
  local resumo=""
  command -v memoria >/dev/null 2>&1 && resumo=$(timeout 15 memoria resumo 2>/dev/null | head -c 1800)
  [ -n "$resumo" ] && sys_="$sys_ Fatos da memoria local: $resumo"
  [ -n "${MATRIX:-}" ] && printf '%s' "$VERDE_M"
  # Matrix aberto sem internet: uma vigia leve olha a cada minuto; quando a nuvem ou o PC voltam, avisa, e ao fechar a
  # conversa (Ctrl+C) o Matrix reabre completo uma vez (IA_REEXEC impede laco se a rede oscilar).
  local volta="$RUN/internet-voltou" vigia="" rc
  rm -f "$volta"
  if [ -n "${MATRIX:-}" ] && [ -z "${IA_REEXEC:-}" ]; then
    ( while sleep "${IA_VIGIA_REDE:-60}"; do
        if { [ -n "$CHAVE" ] && nuvem_em "$PC_IP:20128"; } || pc_em "$PC_IP:11434"; then
          : > "$volta"
          printf '\n%s\n' "[MATRIX] A internet voltou: feche a conversa (Ctrl+C) e eu volto completo."
          command -v termux-notification >/dev/null 2>&1 && timeout 20 termux-notification --title MATRIX --content "A internet voltou: feche a conversa e eu volto completo." >/dev/null 2>&1
          break
        fi
      done ) &
    vigia=$!
  fi
  llama-cli -m "$MODELO_LOCAL" -c 4096 -t 4 -sys "$sys_"
  rc=$?
  [ -n "$vigia" ] && kill "$vigia" 2>/dev/null
  if [ -f "$volta" ] && [ -z "${IA_REEXEC:-}" ]; then
    rm -f "$volta"
    echo "Reabrindo o Matrix completo..."
    export MATRIX=1 IA_REEXEC=1
    exec "$BASH" "$0"
  fi
  exit $rc
}

qwen27() { # ia qwen "pergunta" | echo texto | ia qwen | cat arq | ia qwen "resuma" - : o MELHOR Qwen gratis (3.8 de 27B, Groq) direto no OmniRoute do PC, sem o agente; so pergunta curta
  local pergunta dados="" ler=0 base="" req="$RUN/qwen.req" resp http
  case "${1:-}" in -h|--help) echo 'Uso: ia qwen "pergunta curta"   |   echo texto | ia qwen   |   cat arquivo | ia qwen "resuma isto" -   (o "-" no fim junta a entrada padrao; limite ~4 mil tokens). ATENCAO: o texto vai a um provedor externo (Groq): nunca mande nome, nota ou dado de aluno, nem senha ou chave.'; return 0 ;; esac
  if [ "${*: -1}" = "-" ]; then ler=1; set -- "${@:1:$#-1}"; fi
  pergunta="$*"
  [ -z "$pergunta" ] && [ ! -t 0 ] && ler=1
  [ "$ler" = 1 ] && dados=$(cat)
  if [ -n "$dados" ]; then if [ -n "$pergunta" ]; then pergunta="$pergunta"$'\n\n'"$dados"; else pergunta="$dados"; fi; fi
  [ -n "$pergunta" ] || { echo 'Uso: ia qwen "sua pergunta curta"   (ou: echo "texto" | ia qwen)'; return 1; }
  [ "${#pergunta}" -le 20000 ] || { echo "Texto grande demais para o Qwen 27B gratis (${#pergunta} caracteres; passa de 20000). O plano gratis do Groq aceita uns 4 mil tokens (~14 mil caracteres): corte o texto ou use: ia codigo"; return 1; }
  pega_chave
  [ -n "$CHAVE" ] || { echo "Falta a chave do OmniRoute em ~/.qwen/.env (veja o guia)."; return 1; }
  command -v python3 >/dev/null 2>&1 || { echo "Falta o python3 (pkg install python)."; return 1; }
  if nuvem_em 127.0.0.1:20128; then base=127.0.0.1:20128
  elif nuvem_em "$PC_IP:20128"; then base="$PC_IP:20128"
  else echo "O OmniRoute do PC nao respondeu com a chave do celular (PC ligado? Tailscale nos dois? chave certa em ~/.qwen/.env? veja: ia status)."; return 1; fi
  ( umask 077; IA_PERGUNTA="$pergunta" IA_QWEN="${IA_QWEN_MODELO:-groq/qwen/qwen3.8-27b}" python3 -I -c '
import json, os
print(json.dumps({"model": os.environ["IA_QWEN"], "max_tokens": 1500, "temperature": 0.3, "messages": [
    {"role": "system", "content": "Responda sempre em portugues do Brasil, de forma clara e curta."},
    {"role": "user", "content": os.environ["IA_PERGUNTA"]}]}))' > "$req" )
  resp=$(printf 'header = "Authorization: Bearer %s"\n' "$CHAVE" | curl -s -K - -m 120 -H 'Content-Type: application/json' --data-binary @"$req" -w '%{http_code}' "http://$base/v1/chat/completions")
  rm -f "$req"
  http=${resp: -3}
  printf '%s' "${resp%???}" | IA_COD="$http" python3 -I -c '
import json, os, re, sys, unicodedata
cod = os.environ["IA_COD"]
def limpa(t):
    t = re.sub(r"<think>.*?</think>", "", str(t or ""), flags=re.S)
    return "".join(c for c in t if c in "\t\n" or (unicodedata.category(c)[0] != "C" and unicodedata.category(c) not in ("Zl", "Zp"))).strip()
try:
    d = json.load(sys.stdin)
except ValueError:
    d = {}
if not isinstance(d, dict):
    d = {}
ch = d.get("choices")
if cod == "200" and isinstance(ch, list) and ch and isinstance(ch[0], dict):
    m = ch[0].get("message")
    texto = limpa(m.get("content") if isinstance(m, dict) else "")
    if texto:
        print(texto)
        sys.exit(0)
    print("O modelo respondeu vazio (fim: " + limpa(ch[0].get("finish_reason")) + "). Tente a pergunta mais curta ou use: ia codigo")
    sys.exit(1)
e = d.get("error")
msg = limpa(e.get("message") if isinstance(e, dict) else e)[:160]
if cod == "200":
    print("A resposta do OmniRoute veio cortada ou sem texto (rede?). Tente de novo.")
elif cod in ("413", "429"):
    print("O plano gratis do Groq recusou (HTTP " + cod + "): pergunta grande demais (limite ~4 mil tokens de entrada) ou a cota por minuto acabou. Encurte o texto, espere 1 minuto ou use: ia codigo")
elif cod in ("401", "403"):
    print("O OmniRoute recusou a chave do celular (HTTP " + cod + "). Veja: ia status")
elif cod == "404":
    print("O modelo nao existe no OmniRoute (HTTP 404). Troque com IA_QWEN_MODELO=<modelo> ia qwen ...")
elif cod == "000" or not cod.isdigit():
    print("Sem resposta do OmniRoute (rede?). Veja: ia status")
else:
    print("O OmniRoute respondeu HTTP " + cod + ": " + msg)
sys.exit(1)'
}

MODO="${1:-auto}"; PASTA_ARG=""
case "$MODO" in
  qwen) shift; qwen27 "$@"; exit $? ;;
  reserva-ligar) gw_pronto || exit 1; gw_liga || exit 1; gw_aquece "$(head -1 "$GW_DADOS/cliente-local.key" 2>/dev/null)"; exit 0 ;;   # (interno) o chaveador pede
  reserva-desligar) gw_desliga; exit 0 ;;   # (interno) o chaveador pede quando o PC volta e a reserva fica parada
  auto|codigo|auditoria|rapido|pc|local|tudo|chat|status|parar|ajuda|-h|--help) shift 2>/dev/null ;;
  nuvem) MODO=codigo; shift ;;
  *) MODO=auto ;;   # nao e modo: pasta, pedido ("qwen arrume minhas fotos") ou opcao do Qwen; decidido logo abaixo
esac
case "$MODO" in chat|local|tudo) if [ "${1:-}" = leve ]; then LEVE=1; shift; fi ;; esac   # ia chat leve = modelo 0,5B
PEDIDO=""
if [ -z "$PASTA_ARG" ] && [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then
  case "$1" in
    /*|"~"*|.*|*/*) PASTA_ARG="$1"; shift ;;   # tem cara de caminho: se nao existir, e recusado
    *) if [ -d "$1" ]; then PASTA_ARG="$1"; shift; else PEDIDO="$*"; set --; fi ;;   # o resto e o pedido: o Qwen abre completo ja com ele
  esac
fi
[ "${1:-}" = "--" ] && shift

VERDE_M=""; ESCURO_M=""; FIM_M=""
matrix_abre() { # so quando chamado como `matrix` e num terminal: logo verde e as mensagens de conexao em verde
  [ -n "${MATRIX:-}" ] && [ -t 1 ] || return 0
  VERDE_M=$'\033[1;38;5;46m'; ESCURO_M=$'\033[38;5;250m'; FIM_M=$'\033[0m'   # so verde puro, cinza e branco (pedido do Rafael, 05/11)
  local b=$'\u2588' l   # o arquivo fica em ASCII (vai colado no guia): o bloco cheio nasce aqui; 33 colunas, cabe na tela em pe
  for l in ' #   #  ###  #####  ####  #  #   #' ' ## ##  #   #   #    #   # #   # # ' ' # # #  #####   #    ####  #    #  ' \
           ' #   #  #   #   #    #  #  #   # # ' ' #   #  #   #   #    #   # #  #   #'; do
    printf '%s\n' "${VERDE_M}${l//#/$b}"
  done
  printf '%s\n' "${ESCURO_M} agente do Galaxy A12 | pontes | IAs | memoria local${VERDE_M}"
  printf '%s' "$VERDE_M"
}
matrix_fecha() { [ -n "$FIM_M" ] && printf '%s' "$FIM_M"; return 0; }
case "$MODO" in auto|codigo|auditoria|rapido|pc|local|tudo|chat) matrix_abre ;; esac

case "$MODO" in
  ajuda|-h|--help) sed -n '2,/^$/{/^#/s/^# \{0,1\}//p}' "$0"; exit 0 ;;
  status) status; exit 0 ;;
  parar) if [ "${1:-}" != --forca ] && Q=$(qwen_aberto); then
           echo "Ha um Matrix aberto agora (processo $Q): desligar as pontes derrubaria a conversa dele."
           echo "Saia dele primeiro (/quit) ou, se tiver certeza, rode: ia parar --forca"; exit 1
         fi
         desliga_tudo; echo "Desligado: pontes, OmniRoute do celular e modelo do celular."; exit 0 ;;
  chat) chat ;;
esac

pega_chave
[ -n "$PASTA_ARG" ] && [ ! -d "$PASTA_ARG" ] && { echo "A pasta nao existe: $PASTA_ARG"; exit 1; }
PASTA=$(acha_pasta "$PASTA_ARG")
command -v qwen >/dev/null 2>&1 || { echo "O motor do Matrix nao esta instalado neste Termux (peca ao Claude do PC)."; exit 1; }
trap desliga_meus EXIT

ID=""
case "$MODO" in
  auto)
    if [ -n "$CHAVE" ] && garante_nuvem; then ID=codigo
    elif garante_pc; then ID=llama3.2-32k
    else echo "Nem a nuvem nem o PC responderam (veja: ia status). Abrindo a conversa do celular."; chat; fi ;;
  codigo|auditoria|rapido)
    [ -n "$CHAVE" ] || { echo "Falta a chave do OmniRoute em ~/.qwen/.env (linha OMNIROUTE_API_KEY=...). Veja o guia."; exit 1; }
    garante_nuvem || { echo "O OmniRoute do PC nao respondeu. Confira: PC ligado, Tailscale conectada nos dois, e rode: ia status"; exit 1; }
    ID="$MODO" ;;
  pc)
    garante_pc || { echo "O Ollama do PC nao respondeu. Abra a porta dele no PC (guia, passo C) ou use o cabo. Veja: ia status"; exit 1; }
    ID=llama3.2-32k ;;
  local)
    echo "Aviso: com o modelo do celular a 1a resposta do Matrix leva ~10 minutos. Para conversar, use: ia chat"
    garante_local || exit 1; ID=qwen ;;
  tudo)
    NUV=0; PCK=0; LOC=0
    [ -n "$CHAVE" ] && garante_nuvem && NUV=1
    garante_pc && PCK=1
    garante_local && LOC=1; VIA=""
    echo "Ligado (1 = sim): nuvem=$NUV pc=$PCK modelo-do-celular=$LOC. Dentro do Matrix, /model troca de cerebro."
    if [ $NUV = 1 ]; then ID=codigo; elif [ $PCK = 1 ]; then ID=llama3.2-32k; elif [ $LOC = 1 ]; then ID=qwen
    else echo "Nada ligou (veja: ia status)."; exit 1; fi ;;
esac

[ -n "$VIA" ] && echo "Cerebro: $ID (via $VIA)"
[ -n "${MATRIX:-}" ] && command -v memoria >/dev/null 2>&1 && echo "Memoria local: $(timeout 10 memoria status 2>/dev/null | head -1 | cut -c1-90)"
matrix_fecha
[ -n "$CHAVE" ] && export OMNIROUTE_API_KEY="$CHAVE"
if [ "$ID" = llama3.2-32k ]; then
  echo "Modelo pequeno (3B) do PC: so para tarefa curta. Aquecendo (a 1a resposta leva alguns minutos)..."
  curl -s -m 120 http://127.0.0.1:11435/api/generate -d '{"model":"llama3.2-32k","keep_alive":"30m"}' >/dev/null 2>&1
fi
cd "$PASTA" || { echo "Nao consegui entrar em: $PASTA"; exit 1; }
# MCP (ponte do PC e busca na web): so com modelo de NUVEM; nos pequenos o prompt ja passa de 12 mil tokens e as ferramentas extras so atrasam.
# Com a ponte fora do ar (PC desligado, Tailscale off), o Qwen abre sem ela em vez de esperar.
MCP_OFF=()
case "$ID" in
  codigo|auditoria|rapido)
    if tem_token && ponte_ok; then echo "Ponte do PC ligada: o Matrix le o projeto ao vivo e as skills do PC; recados: caixa sincronizar"
    else MCP_OFF+=(--disable-mcp-server ponte-pc); fi ;;
  *) MCP_OFF+=(--disable-mcp-server ponte-pc --disable-mcp-server exa) ;;
esac
echo "Abrindo o Matrix em: $PWD"
echo "(dentro dele: /help ajuda, Esc interrompe, /quit sai)"
# Sem perguntar (pedido do Rafael, 04/11: "total autorizacao ... sem ficar interrompendo"): tools.approvalMode = yolo no
# ~/.qwen/settings.json (o instalador poe); o que esta em deny segue bloqueado (o Qwen confere deny antes do modo).
# IA_PERGUNTAR=1 volta a perguntar so nesta vez.
MODO_QWEN=()
[ -n "${IA_PERGUNTAR:-}" ] && MODO_QWEN=(--approval-mode default)
# Um processo so (06/11): sem isso o Qwen abre um 2o node "supervisor" (~30 MB); no Linux o gc ja vem ligado no proprio processo
# (cli-entry.js da 0.26.5, conferido no aparelho). IA_RELANCAR=1 volta ao jeito antigo.
[ "${IA_RELANCAR:-0}" = 1 ] || export QWEN_CODE_NO_RELAUNCH=true
if [ -n "$PEDIDO" ]; then qwen --model "$ID" "${MODO_QWEN[@]}" "${MCP_OFF[@]}" -i "$PEDIDO" "$@"; else qwen --model "$ID" "${MODO_QWEN[@]}" "${MCP_OFF[@]}" "$@"; fi
exit $?
FIM_DO_IA
chmod +x ~/bin/ia
grep -q 'HOME/bin' ~/.bashrc 2>/dev/null || echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
export PATH="$HOME/bin:$PATH"
ia ajuda
```

Quando alguém mudar o `ia`, o bloco acima é atualizado com `python scripts/gerar-guia-ia.py` (o teste `test_guia_traz_exatamente_o_script_para_colar` avisa se esquecerem).

## 10. Resumo para colar na geladeira

```
ia             → o melhor que estiver ao alcance (nuvem), na pasta do projeto
ia chat        → conversa curta, só no celular (Qwen 1,5B: melhor, lento)
ia chat leve   → idem com o Qwen 0,5B (rápido, mais fraco)
ia codigo      → programar (nuvem)      ia auditoria → revisar      ia rapido → resumo
ia qwen "..."  → UMA pergunta curta ao melhor Qwen grátis (27B); sem agente   (cat arq | ia qwen "resuma" -)
ia pc          → Llama 3B do PC (abra a porta do Ollama antes)
ia tudo        → liga tudo que estiver ao alcance; dentro do Qwen, /model troca de cérebro
ia status      → o que está ao alcance      ia parar → desligar tudo (--forca se houver Qwen aberto)
ia ajuda       → lista de comandos
No PC: scripts\ia-do-pc.cmd confere e liga o servidor.
```

O Hermes (agente do PC) **não roda** no Termux: o aviso oficial dele continua "Termux is currently broken" [Certo: raw GitHub, 31/10]. No celular, o agente é o Qwen Code.
