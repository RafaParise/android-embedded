# Antivírus de código aberto no PC e no celular (atualizado em 04/11/2026)

## O que está ligado desde 04/11: o `guarda`, um programa só para os dois aparelhos
Pedido do Rafael: antivírus aberto, em tempo real, completo, igual no PC e no celular, protegendo as IAs, a troca de dados e a VPN em qualquer rede, leve e sem atrapalhar nada.

**Limite real, dito a ele:** não existe antivírus aberto completo em tempo real para Windows e Android [Certo: on-access do ClamAV é só Linux (`man clamonacc`); Clam Sentinel é beta de terceiro de 2024; Amaru tem 10 estrelas, último envio em 04/2025 e nenhuma versão publicada; Hypatia procura mantenedor e o servidor de assinaturas deu tempo esgotado em 04/11]. O `guarda` percebe e isola **depois de gravar**: não bloqueia programa ao abrir e não tem análise de comportamento. Isso só o Defender faz no PC e o Play Protect no celular, e os dois seguem ligados.

| Camada | PC | Celular |
|---|---|---|
| Arquivo novo, em tempo real | `guarda.py vigiar` (tarefa `Guarda`): aviso do Windows, sem varredura em laço | `guarda` no Termux: `inotifywait` dorme até o Android avisar; sobe com o Termux:Boot |
| Motor | ClamAV 1.5.4 (`clamd`) só em 127.0.0.1 | o mesmo do PC, pela ponte (`POST /v1/varrer`, token, só na tailnet, cifrado pela Tailscale, nada gravado em disco) |
| Pastas | Downloads, Área de Trabalho, Inicializar, entradas e saídas do Qwen, saída do Hermes | Download, Documents, caixa de entrada do Qwen (o que vem do PC) |
| App novo | Defender | pacote base varrido no PC, uma vez; atualização não, para não gastar dados móveis |
| Varredura completa | `guarda.cmd` (dois cliques) ou `guarda.py varredura [PASTA] [--tudo]` | `guarda varredura`; arquivo acima de 64 MB só pelo cabo (`antivirus-pc.ps1 -Celular`) |
| Achou | quarentena em `%LOCALAPPDATA%\Guarda\quarentena`, balão e recado pelo KDE Connect; `guarda.py devolver ID` | `~/.cache/guarda/quarentena`; `guarda devolver ID`; notificação no celular e balão no PC |
| Rede e VPN | a cada 30 min: porta nova aberta, **aparelho novo na tailnet**, PC sem aprovação de saída, PC saindo por outro aparelho. `guarda.py rede` confere também o RDP em rede pública | `saida` (guarda do exit node) continua igual |
| Sites de malware e golpe | AdGuard Home com 3 listas novas (URLHaus, Phishing URL, Dandelion Sprout): `adguard-pc.py seguranca` | o mesmo AdGuard pelo DNS da tailnet, em qualquer rede. PROVADO: domínio real da URLHaus resolve para 127.0.0.1 no A12 |

**Menu (04/11, pedido dele: "verde puro para selecionar"):** no celular, digitar `antivirus` no Termux; no PC, o atalho **Antivírus** da área de trabalho (`scripts\guarda.cmd`). Os dois mostram o mesmo menu em texto, setas e Enter: situação, varrer um arquivo, varredura rápida e completa (pede confirmação com a contagem), quarentena e devolver, provar, rede e VPN, atualizar assinaturas, ligar e desligar. No PC o logo é em relevo, em tons de verde. O Qwen do celular chega aos mesmos recursos por `guarda` (Termux) e pela `acao_pc` (`antivirus-status`, `antivirus-rede`, `antivirus-atualizar`, `antivirus-varredura-rapida`).

**O que nunca faz:** olhar tráfego, mexer em firewall, DNS, VPN, Defender ou configuração do sistema, apagar arquivo, abrir `MAPAO_*.xlsx` (ignorado nos dois lados), guardar nome de arquivo limpo no registro. Jogos, gravações do OBS, backups, o projeto e o OmniRoute ficam fora da vigia: nada disso é lido.

**Medidas (04/11):**
- PC parado: vigia 26 MB e 0,3 s de CPU depois de varrer 67 arquivos; motor **fora da memória**. Com arquivo novo: motor sobe em ~12 s, ~960 MB (985 MB privados), prioridade abaixo do normal, 2 linhas; desce depois de 5 a 7 min sem uso (medido: 6,6 min; livre de 3,4 para 5,3 GB). Livre menos de 2,5 GB: não sobe, o arquivo espera e nada é dado como limpo.
- Celular parado: `bash` 3,5 MB + `inotifywait` 2,1 MB, 0 s de CPU. O motor não roda nele: 3,75 GB de RAM com 62 MB livres + 1,4 GB de cache não comportam 1 GB.
- `provar` (arquivo inofensivo, assinatura própria `guarda-teste.hdb`, sem disparar o Defender): PC isolou em 3 s com o motor de pé; celular em 5 s; arquivo com data de 100 dias atrás vindo de outro usuário por `adb push -a` (caso do Bluetooth) também foi isolado.
- AdGuard: 62 para 82 MB com as 3 listas (194.842 para 231.273 regras).

**Limites para não esquecer:**
- PC desligado ou fora do alcance: o arquivo do celular espera. Não há varredura sem o PC.
- WhatsApp e Telegram guardam mídia em pasta privada que o Termux não lê: só o que for salvo em Download ou Documents entra.
- O ClamAV pega menos que antivírus comercial: 59,94% num estudo da Splunk de 2022 [Provável: citado abaixo, não refeito].
- Aviso no celular: notificação pelo app Termux:API (F-Droid, 0.53.0, 4 MB, hash conferido; instalado com o sim dele em 04/11; só roda quando chamado). Com o PC ligado sai também o balão.
- `caixa atualizar` leva o `guarda`; desligar: `guarda desligar` no celular, `pwsh -File scripts\guarda.ps1 -Desinstalar` no PC.
- A saída pelo PC contorna o filtro da rede onde ele estiver. Regra da SEDUC sobre isso: não verifiquei; decisão dele.

Pedido do Rafael: antivírus aberto "no PC e no celular ao mesmo tempo", e o Defender desativado quando o outro estivesse pronto, para "acabar para sempre com os rastreios do Windows".

**Premissas a corrigir:** (1) o aberto disponível não substitui o Defender, porque não tem proteção em tempo real no Windows; (2) o Defender não se remove num Windows cliente; (3) o rastreio que ele poderia causar já está desligado neste PC.

## Decisão anterior de 04/11 (substituída pelo `guarda` acima): pausado até existir um de tempo real
O Rafael: varredura sem tempo real "é só consumo de recursos"; quando vier, tem de ser de tempo real, ótimo e de código aberto. As 3 tarefas `ClamAV-*` foram desativadas (desfaz: `Enable-ScheduledTask`, ou `-Agendar`). O ClamAV fica instalado, sem rodar sozinho. O Defender fica como está, sem enviar à nuvem. Até onde se conferiu, não existe aberto com tempo real no Windows: o tempo real do ClamAV é só no Linux [Provável: documentação do ClamAV, não reconferida hoje]. Reabrir só com fonte nova.

## O que está pronto

**Defeito corrigido em 04/11:** a rotina de uma pasta só varria o disco C: inteiro (o caminho era separado letra por letra). Medido depois de corrigir: 8 arquivos dos Downloads em 17 s, 0 infectados. Arquivo acima de 200 MB não é lido por dentro (limite escolhido).

- **PC:** ClamAV 1.5.4 em `%LOCALAPPDATA%\Programs\ClamAV`, SHA-256 oficial conferido, com 3.628.245 assinaturas [Certo: `-Provar`]. Tarefas `ClamAV-Atualizar` e `ClamAV-Downloads` (todo dia) e `ClamAV-Semanal` (domingo: Downloads, Área de Trabalho, Documentos e `C:\Projetos`, sem `jogos`), em prioridade baixa e só com o PC parado há 10 minutos, para não disputar com jogo ou gravação. Achou algo: mensagem na tela e registro em `diagnostico\antivirus\`. Nada é apagado.
- **Celular:** o mesmo motor. `pwsh -File scripts\antivirus-pc.ps1 -Celular` copia os apps de terceiros e a pasta Download pelo cabo, varre no PC e apaga a cópia.
  Primeira varredura em 03-04/11 [Certo]: 151 arquivos, 3,74 GB lidos, **0 infectados**, 48 min. Num caso de 6 avisos, uma assinatura antiga para Android (`Exploit.Andr-2`) estourou o tempo: esses arquivos passaram pelas demais, não por ela. Limite: não vê apps do sistema nem dados privados, e arquivos acima de 300 MB ficam de fora.
- **Comandos:** `scripts\antivirus-pc.ps1 -Status | -Atualizar | -Varrer <pasta> | -Provar | -Agendar | -Celular`.

## Defender: o que cabe ao Rafael

O Claude não desliga proteção do sistema; a decisão e o clique são dele. Hoje [Certo: `Get-MpPreference`, 04/11]: tempo real ligado, proteção contra adulteração ligada, **MAPS 0 (nuvem desligada) e amostras 2 (nunca enviar)**.

**Recomendação: deixar ligado.** Ele já não manda dados nessa configuração, e o ClamAV só varre em horário: não barra o arquivo ao abrir, e um estudo da Splunk de 2022 mediu 59,94% de detecção em cerca de 400 mil amostras [Provável: dado antigo, via [Wikipedia](https://en.wikipedia.org/wiki/ClamAV)].

**Se decidir desligar mesmo assim**, ficará sem proteção em tempo real:
1. Segurança do Windows > Proteção contra vírus e ameaças > Gerenciar configurações.
2. Desligar **Proteção contra adulterações** e, depois, **Proteção em tempo real**.
3. Pela chave, o Windows religa depois de pouco tempo [Certo: [Microsoft](https://learn.microsoft.com/defender-endpoint/microsoft-defender-security-center-antivirus)]. Para valer, o caminho é a política "Desativar proteção em tempo real" no `gpedit.msc`, em Componentes do Windows > Microsoft Defender Antivirus > Proteção em tempo real; a Microsoft [não recomenda](https://learn.microsoft.com/defender-endpoint/configure-real-time-protection-microsoft-defender-antivirus), e com a adulteração ligada ela é ignorada.
4. A política "Desativar o Microsoft Defender Antivirus" a Microsoft diz que [pode causar comportamento não suportado](https://learn.microsoft.com/windows/client-management/mdm/policy-csp-admx-microsoftdefenderantivirus#disableantispywaredefender). Ferramentas de terceiros para "matar" o Defender não são recomendadas aqui.

O Defender só se desliga sozinho quando outro antivírus se registra no Windows [Certo: Microsoft]; o ClamAV não se registra.

Telemetria do Windows em geral não acaba "para sempre" enquanto for Windows: dá para reduzir, e é assunto do projeto `Windows 10 Embeeded`. As 10 pastas e os 4 processos excluídos da varredura do Defender seguem como estavam (`jogos`, `Windows 10 Embeeded`...).

## Celular: por que nenhum app

- **Hypatia testado e REMOVIDO em 03/11:** o único aberto no F-Droid, com repositório arquivado e servidor de assinaturas respondendo 511, também pelo PC. O app diz "atualizados" mesmo com tudo falhando [Certo]: daria falsa segurança.
- ClamAV no Termux não cabe: o banco carregado usa cerca de 1,3 GB de RAM [Provável] e o aparelho tem cerca de 1,1 GB disponível [Certo: `free`].
- O que já protege: Play Protect ligado, apps vindos da Play e do F-Droid, DNS do AdGuard quando o PC está no ar, e bem menos apps nativos.
