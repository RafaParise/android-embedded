# Divisão de trabalho: Claude Code × Hermes × Rafael (28/10/2026)

**Propósito comum:** deixar o Galaxy A12 (SM-A125M) rápido, privado e útil como aparelho de teste, de forma reversível e documentada, com a memória do projeto em arquivos.
**Regra de ouro: nenhum espera pelo outro.** Cada um tem faixa, fila e instruções próprias e só se encontram nos arquivos. Se a cota do Claude Code acabar (sessão ou semana) ou a conta emprestada sumir, o projeto segue: a memória está em `memoria/` e no GitHub privado, não numa conta.

## 1. Quem faz o quê
| Tarefa | Claude Code (ou `claude-livre`) | Hermes | Rafael |
|---|---|---|---|
| Celular (adb, pm, settings, apps) | sim; simulação primeiro | só pela porta `celular.cmd`: leitura e reaplicação reversível | pode, com `PLANO-DE-ACAO.md` e os scripts |
| Editar o projeto (`memoria/`, `scripts/`, `CLAUDE.md`) e GitHub | sim (`sync-memoria.ps1`) | **nunca**: só propõe | pode (mesmo script) |
| Pesquisa na web com fontes, comparar opções | revisa | **principal** | pede |
| Resumos, índices, relatórios, folhas de decisão, rascunho de passo a passo | revisa e aplica | **principal** (rascunho) | lê e decide |
| Auditar texto ou script alheio (só leitura) | confirma o que for aplicar | primeiro passe | |
| Decidir desenho, revisar entregas, aprovar | sim | não | o irreversível é só dele |
| Medir, testar, `auditoria.py`, atualizar `ESTADO.md` | sim | não | pode rodar os scripts |

**Autorização do Rafael (28/10, ~21:15, na mensagem dele):** os dois agentes podem acessar o celular e implementar, tomando as melhores decisões. Cobre trabalho reversível. Passo irreversível novo (formatar, apagar dados, reset de fábrica, remover conta; **root/bootloader está decidido NÃO desde 29/10**) ainda pede o "sim" dele para aquele passo, porque Knox 0x1 e apagar `/data` não têm volta. O Hermes entra só pela `celular.cmd` (lista fechada: leitura e reaplicação reversível): em 28/10 o orquestrador dele desfez decisões do projeto no celular [Certo: `AUDITORIA-HERMES-28-10.md`]. Escrita mais ampla pelo Hermes: o Rafael pede e a lista da `celular.cmd` cresce.

**Claude-nuvem (sessão do Claude Code na nuvem, créditos do Rafael):** o mesmo Claude, sem celular, PC, Hermes nem PowerShell. Revisa (entregas do Hermes pelo espelho `memoria/hermes-espelho/`), pesquisa com fontes, escreve código e testes Python e entrega **em branch** num repositório SEPARADO (o B, `android-embedded-nuvem`, espelho da `main`: o principal fica fora do alcance dela); o Claude local revisa o diff e integra a ponta revisada (`scripts/nuvem-integrar.ps1 -Aplicar '<ref>' -Sha <ponta de 40 caracteres>`; sem `-Confirmo` só passam os `.md` de `memoria/nuvem/` com nome simples, e `scripts/tests/`, qualquer código e as revisões para o Hermes exigem leitura linha a linha; arquivos que mandam em agentes, histórico cruzado, segredos e blobs grandes nunca entram). Manual dela: `NUVEM.md`; como o Rafael inicia: `NUVEM-INICIAR.md`; memória dela entre sessões: `memoria/nuvem/DIARIO.md`. A frase-chave é a mesma (seção 8). **Qwen do celular (31/10, `memoria/QWEN-CELULAR.md`):** o Qwen Code do Termux (comando `ia`, modelos de nuvem) alcança o PC de qualquer lugar pela Tailscale (porta 20130, serviço `PontePC`): LÊ o projeto ao vivo e as skills e TROCA recados pela caixa `C:\Projetos\qwen-celular\{entrada,saida,retorno}`. Ele só entrega rascunho (arquivo novo `NAO REVISADO` em `saida\`); o Claude Code revisa (`retorno\<nome>-revisao.md` com `Veredito:`) e é o único que grava no projeto. Cabe a ele: triar e resumir memória, rascunhar guias e planos de aula, revisar script só comentando, explicar erro. Não cabe: adb/pm no aparelho sem o "sim" do Rafael, decisão de arquitetura, segredo, dado de aluno. A `hermes-fila.ps1` lista as entregas dele sem revisão.

## 2. Quem escreve onde
- `C:\Android Embeeded\` (git privado): Claude Code e Rafael.
- `C:\Projetos\hermes-trabalho\android-embeeded\` (fora de git): `entrada\` pedidos (Claude e Rafael; o Hermes nunca), `retorno\` revisões (Claude e Rafael), `saida\` e `trava\` (só o Hermes). `AGENTS.md`, `ROTINA.txt`, `LEIA-ME.md`, `COMANDO.txt` e o iniciador são somente leitura (mudar: `attrib -R`, editar, `attrib +R`).
- Fatos do aparelho: `ESTADO.md` e `DISPOSITIVO.md`. Decisões: `DECISOES.md`. O que falta ele fazer: `PLANO-DE-ACAO.md`. Um assunto, um arquivo dono.

## 3. Fluxo (nada depende de quem está online)
1. **Pedido**: arquivo `entrada\NN-assunto.md` (modelo: `entrada\_modelo-de-pedido.md`) ou frase direta no chat do Hermes (ele grava `saida\R-AAAA-MM-DD-assunto.md`).
2. **Fila vazia**: o Hermes faz as tarefas permanentes `entrada\permanente\P1..P4` que estiverem vencidas ou, se nenhuma, grava `saida\PROPOSTAS.md` (até 3 ideias, sem executar). Nunca para perguntando "o que faço?".
3. **Entrega** sempre com: `Status: NÃO REVISADO`, Resumo para o Rafael, fatos [Certo]/[Provável]/[Palpite] com fonte, Risco se estiver errado, Como fazer sozinho (passo a passo copiável, com desfazer), Não verificado, Autoconferência (≥5 afirmações reabertas na fonte) e `Para o Claude Code:` (1 a 3 linhas: o que revisar, aplicar ou decidir a partir dela).
4. **Revisão**: Claude Code (ou `claude-livre`) lê, confere ≥5 afirmações e grava `retorno\NN-*.md` com `Veredito: APROVADO | COM CORREÇÕES | REPROVADO`. Entrega **revisada** = existe `retorno\NN-*.md`.
5. **Aplicação**: só o que passou na revisão vai para `memoria/`, `scripts/`, celular ou GitHub. Para mudar a memória o Hermes grava a proposta em `saida\memoria-proposta\<arquivo>.md`.
6. **Dúvida do Hermes**: `saida\PERGUNTA-NN-assunto.md` e segue para o próximo item. Quem responde (Claude ou Rafael) grava `retorno\NN-resposta.md`.

## 4. Modos de operação
| Situação | O que fazer | Limite honesto |
|---|---|---|
| Normal | Claude Code opera, decide, escreve pedidos e revisa; Hermes consome a fila | |
| **Claude Code sem cota** | (a) Hermes: colar o comando de `COMANDO.txt`; (b) Claude em modelos gratuitos: `claude-livre` iniciado dentro de `C:\Android Embeeded` (lê este `CLAUDE.md`; usa o combo `codigo` do OmniRoute [Certo: `kit-ia-professor\scripts\claude-livre.cmd`]); (c) Rafael com `PLANO-DE-ACAO.md` | `claude-livre` é mais fraco: só leitura, simulação e texto; nada irreversível |
| Claude local sem cota, mas com créditos de nuvem | Sessão na nuvem com a mesma frase (`NUVEM-INICIAR.md`); ela entrega em branch e o trabalho no celular espera o Claude local, o `claude-livre` ou o Rafael | Nuvem não vê o celular nem o PC; créditos acabam em 05/11 04:59 (Brasília) |
| Hermes indisponível (OmniRoute ou cota gratuita) | Claude segue; os pedidos ficam na fila e ninguém trava | |
| Os dois fora | Rafael sozinho: `PLANO-DE-ACAO.md` e scripts (`auditoria.py`, `medir.py`, `sync-memoria.ps1`); o que pede julgamento espera | `claude-livre` e Hermes dividem a mesma cota gratuita do OmniRoute |
| Celular no cabo (ADB) | Hermes usa `celular.cmd`; só interativo e acompanhado: `-Auto` e `-Yolo` seguem recusados pelo iniciador | o `execute_code` do Hermes escapa das regras de terminal [Certo: `approval.py`], então a lista fechada da `celular.cmd` vale como instrução, não como cadeado |

## 5. O que vale uma entrega NÃO REVISADA
- **Serve para** ler, planejar, comparar opções e preparar decisão.
- **Não serve para** rodar comando no celular ou no PC que não esteja em `PLANO-DE-ACAO.md` ou `scripts/`, repassar número, norma ou versão como fato, nem gravar em `memoria/`.
- Por quê [Certo: `retorno\01-revisao-do-claude.md`]: a primeira entrega teve 9 correções; modelo gratuito lê só o começo dos arquivos e completa com suposição.
- Rafael quer agir antes da revisão: usar só comando que também esteja em `PLANO-DE-ACAO.md` ou `scripts/`, em simulação primeiro, e pedir a um `claude-livre` "revise saida\NN-...". Passo **irreversível** (formatar, apagar, cartão) sempre espera revisão e decisão dele no dia; root, bootloader e Magisk estão decididos NÃO.

## 6. Retomada
- **Claude volta**: `pwsh -NoProfile -File scripts\hermes-fila.ps1` (0 token) mostra pendentes, entregas sem `retorno\`, perguntas e travas. Ordem: `ESTADO.md` → entregas sem revisão → `PERGUNTA-*` → `memoria-proposta\` → `ESTADO.md` e sync. Revisar é trabalho de folga: não bloqueia o resto.
- **Hermes volta**: lê `AGENTS.md`, `saida\STATUS.md` ("onde parei") e `retorno\` novo, depois a fila.

## 7. Desvio consciente da política do kit
`C:\Projetos\kit-ia-professor\POLITICA-DIVISAO-TRABALHO.md` (§3–4) deixa o Hermes reconciliar edições e commitar na pasta de um projeto. **Aqui não**: o Hermes nunca toca projeto, celular nem git (incidente de 28/10, ver `AUDITORIA-HERMES-28-10.md`). Vale o resto da política: um só OmniRoute, combos por tipo de tarefa, "modelo gratuito é rascunho", nenhum dado de aluno.

## 8. Frase-chave: ROTINA UNIFICADA
O Rafael cola a **mesma frase** nos dois agentes, quando quiser e em qualquer ordem:

> Rotina unificada (projeto Android Embeeded): leia suas instruções e C:\Android Embeeded\memoria\DIVISAO-DE-TRABALHO.md, veja o que o outro agente fez, faça a fila da sua faixa, deixe o recado "Para o outro agente" e pare.

| | Claude Code | Hermes |
|---|---|---|
| Suas instruções | `CLAUDE.md` (abrir o Claude em `C:\Android Embeeded`) | `AGENTS.md` (abrir com `iniciar-hermes.cmd`) |
| Vê o que o outro fez | `ESTADO.md` e `scripts\hermes-fila.ps1` (STATUS, entregas, perguntas, recado) | `saida\STATUS.md`, `memoria\ESTADO.md` ("Últimas ações" e `Para o Hermes:`) e `retorno\` |
| Fila que faz | UM ciclo: responder PERGUNTA → revisar entregas do Hermes e do Qwen do celular (até 3 por ciclo; `hermes-fila.ps1` lista as duas filas) → aplicar à memória o que passou → 1 pedido novo ao Hermes, se ele estiver ocioso → `auditoria.py` só leitura, se o celular estiver no ADB e a última tiver mais de 7 dias | TODOS: pedidos pendentes → P1 a P4 vencidas → `PROPOSTAS.md` |
| Deixa o recado em | `ESTADO.md`: "Últimas ações" e `Para o Hermes:` (mais `retorno\` e `entrada\`) | `saida\STATUS.md`: `Para o Claude Code:` (e no fim de cada entrega) |
| A frase nunca autoriza | passo irreversível novo (formatar, apagar dados, reset): pede o "sim" do Rafael para aquele passo; root/bootloader está decidido NÃO e nenhum agente propõe | nada fora da `celular.cmd` nem das proibições do `AGENTS.md` |

**Claude-nuvem (terceira faixa, sem coluna própria):** instruções = `CLAUDE.md` e `memoria/NUVEM.md`; vê o que os outros fizeram em `ESTADO.md` (linha `Para a nuvem:`) e `memoria/hermes-espelho/saida/STATUS.md`; fila = `NUVEM.md` seção 1; deixa o recado no topo de `memoria/nuvem/DIARIO.md`, linha `Para o Claude local:` (é o que a frase chama de "Para o outro agente"); a frase nunca autoriza push na `main`, celular, nem editar `ESTADO.md` ou `DECISOES.md`.

Vai-e-vem sem se atropelar: no máximo 1 pedido novo por ciclo; `PROPOSTAS.md` só vira pedido com aprovação do Claude ou do Rafael; quem discorda escreve o motivo em `retorno\` ou `PERGUNTA-`, sem refazer o trabalho do outro; complementar é não repetir, então leia o que o outro fez antes de começar. Autoridade: Rafael > revisão do Claude Code > entrega do Hermes > pesquisa antiga. Frase com "só o próximo" = um item só.

## 9. Independência, conferida em 29/10 (as regras acima NÃO mudaram)
Ninguém espera ninguém. Conferido nos scripts (todos os .ps1 lidos linha a linha; nenhum .py ou .ps1 exige um agente para rodar) e nos documentos:
| Se faltar... | O que continua sozinho | Como retomar |
|---|---|---|
| **Claude** (sem cota, conta emprestada que sumiu) | Hermes: iniciar-hermes.cmd ou hermes-automatico.cmd (pedidos, P1 a P4, PROPOSTAS.md); celular.cmd roda os scripts do projeto (Python e ADB, sem Claude); as entregas ficam "NÃO REVISADO" e nada vai à memória, ao celular ou ao GitHub sem revisão | claude-livre, outra conta, a sessão na nuvem (revisa, não opera) ou o Rafael com PLANO-DE-ACAO.md |
| **Hermes** (OmniRoute ou cota gratuita) | Claude: sync-memoria.ps1 espelha o Hermes só se a pasta existir (senão sai com 0); hermes-fila.ps1 só lê; os pedidos ficam na fila | iniciar-hermes.cmd quando voltar; ele lê retorno\ e o ESTADO.md |
| **Nuvem** (sem crédito, B fora do ar) | Nada depende dela: o sync avisa e segue; o envio ao A nunca espera o B | scripts\nuvem-configurar.cmd refaz o B |
| **Os dois agentes** | Rafael: PLANO-DE-ACAO.md e os scripts (auditoria.py, medir.py, sync-memoria.ps1) | |
Só duas coisas dependem de um agente específico, sem bloquear o resto: a **revisão** das entregas do Hermes (Claude local ou nuvem) e a **integração** de branches da nuvem (só o Claude local). Passo irreversível continua sendo do Rafael com o "sim" do dia; **root está decidido NÃO** (Rafael, 29/10).