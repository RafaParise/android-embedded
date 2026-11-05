# Guia do especialista do A12 (para o Qwen; conferido em 03/11/2026)

Leia este arquivo quando o Rafael perguntar sobre o celular, apps, internet, DNS ou IAs. Responda com a linha certa, cite o arquivo e confira o detalhe nele antes de afirmar. Com a ponte: `projeto_ler`. Sem ela: `~/kit/projeto-android-embeeded/memoria/`. Se o arquivo disser outra coisa, vale o arquivo mais novo, e avise.

## Mapa: tema, verdade de hoje, onde ler

| Tema | Hoje | Conferir (só leitura) | Detalhe |
|---|---|---|---|
| Aparelho | Galaxy A12 SM-A125M, Android 12, 3,8 GB de RAM, sem root (decisão do Rafael: não pesquisar nem propor) | | `DISPOSITIVO.md` |
| Lentidão, memória, calor | Sem root o teto de ajuste foi atingido; "app de BIOS" não existe sem root | peça `saude.py` ao Claude | `RADAR-DESEMPENHO.md` |
| Espaço | Apps e dados na memória interna; cartão portátil exFAT `1A2B-3C4D`; manter mais de 15% livre | | `ESTADO.md`, `ARMAZENAMENTO-EM-CAMADAS.md` |
| Cartão | Nunca adotar; nunca `pm move-package` nem `pm move-primary-storage` (corrompeu 1.412 arquivos) | | `CLAUDE.md` |
| Apps removidos e desativados | Lotes com substituto livre; desfazer existe | | `CONFERENCIA-PEDIDOS.md`, `CHECKLIST-SCRIPT.md` |
| VPN | Tailscale com "VPN sempre ativada" ligada e "Bloquear conexões sem VPN" desligado | `ia status` | `VPN-SEMPRE-ATIVA.md` |
| Internet pelo PC | Saída (exit node) ligada, com o guarda `saida` e o Termux:Boot | `saida status`, `saida log` | `VPN-SEMPRE-ATIVA.md` |
| DNS e anúncios | AdGuard Home no PC, cadastrado na Tailscale; DNS privado do Android fica em Automático | | `ADGUARD-PC.md` |
| Wi-Fi da escola | Rafael entrou e autenticou em 03/11 sem desligar a Tailscale; o PC estava desligado, então a saída estava suspensa e a saída ligada na escola segue sem teste; as restrições da rede continuam | | `VPN-SEMPRE-ATIVA.md`, `ESTADO.md` |
| Dados móveis | Quem gastou: `dados-moveis.py`, no PC | | `CLAUDE.md` |
| Tela e controle do PC | RDP pela Tailscale no aFreeRDP (perfil "PC Tailscale"), inclusive por dados móveis, com o PC ligado; funcionando desde 03/11, usuário `passo`, domínio `MEU-PC`, senha da conta Microsoft (não o PIN; o Qwen nunca pede nem guarda senha; se parar: `ACESSO-REMOTO.md`); KDE Connect acessível pelo IP da tailnet. O RDP assume a sessão: a tela do PC fica bloqueada enquanto isso | | `ACESSO-REMOTO.md`, `PESQUISA-APPS.md` |
| IAs | Claude no PC decide e assina; Hermes no PC pesquisa; você no celular; OmniRoute do PC e reserva no celular | `ia status`, `caixa status` | `PROTOCOLO-IAS.md`, `ECOSSISTEMA-IA.md`, `QWEN-CELULAR.md` |
| Usar a IA no Termux | `ia`, `ia chat`, `ia status`, `ia qwen "pergunta"` | | `GUIA-IA-NO-CELULAR.md` |
| Mapas | Organic Maps: a busca principal acha o que está no mapa (OpenStreetMap), até com erro de digitação, mas NÃO os favoritos importados, que só o Buscar da lista acha. Com o celular deitado o teclado cobre a lista: toque na seta do teclado para fechá-lo | | `MAPAS-LUGARES.md` |
| Dashcam | Organic Maps + Open Camera em tela dividida; depende do Apps Edge ativo | | `ESTADO.md` |
| Backup | Tarefa `BackupDrive` envia os projetos e os jogos ao Google Drive; só copia, nunca apaga lá. Cópia do projeto no cartão: `Backups/android-embeeded`, com `VERSAO.txt`. Os jogos de Super Nintendo do cartão não têm outra cópia | | `BACKUP-DRIVE.md` |
| Antivírus | PC: ClamAV agendado, sem tempo real. Celular: o mesmo ClamAV varre os apps pelo cabo; Hypatia está morto. Não existe antivírus aberto vivo para Android | | `ANTIVIRUS.md` |
| ARENA | Jogos do cartão em Ajustes > Máquina > Pastas de jogos do cartão > Procurar jogos no cartão > Jogar desta pasta; só lê, não copia. Em uso desde 03/11: 6.562 jogos na lista, os do cartão com a etiqueta "Cartão de memória". No jogo, SAIR pede dois toques; para abrir, tocar no título | | `ESTADO.md` |
| Webcam | Com ou sem cabo: atalho `Estudio - Webcam do Celular` no PC, câmera "OBS Virtual Camera" na chamada; nada novo no celular. Se aparecer "Permitir depuração" sem ser você, recuse | | `WEBCAM-E-RECUPERACAO.md` |
| Controles GameSir | Pareados com A + Mode (luz amarela). **Os dois ligados sufocam o Wi-Fi de 2,4 GHz:** sem internet com controle ligado, desligue os controles (Mode por 5 s) ou use 4G. Para jogar: Wi-Fi desligado e fone no cabo. App GameSir só conecta com internet; feche depois | | `CONTROLES-GAMESIR.md` |
| OBS e fone JBL | Estúdio pronto: Ctrl+F9 grava, Ctrl+1 a 6 troca cena. JBL: Game e Chat no Windows; microfone Bluetooth só em chamada; luzes: segurar o mudo por 5 s | | `OBS-ESTUDIO.md` |
| Recuperar arquivo no PC | Lixeira, Drive e GitHub primeiro; depois `scripts\recuperar-arquivos.cmd` (PhotoRec); salvar em outro disco | | `WEBCAM-E-RECUPERACAO.md` |
| App da Play ou da fonte | Preferir F-Droid; banco e governo ficam na Play; só o Tailscale existe na fonte | | `PLAY-PARA-FONTE.md` |
| Modos | Jogo, TV e economia por `modos.py`, no PC | | `CLAUDE.md` |
| Internet no Wi-Fi | Só 2,4 GHz. Alto desempenho ligado automaticamente: internet 39 ms com Bluetooth desligado, 53 ms com ele ligado. Desligar o Bluetooth sem uso. IPv6 não muda nada | `TELA-APAGADA.md` |
| Microfone | Fone Bluetooth vale fora de chamada: `microfone-bt.py` no PC. Microfone do celular em mudo por software (defeito de chiado; pedido dele). Sem som na chamada e sem fone: reiniciar | `OBS-ESTUDIO.md` |
| Linux | `linux` no Termux: Debian sem interface, nada rodando parado | `LINUX-A12.md` |
| Restaurar | Sem root não há imagem. Cópia em `C:\Users\voce\Backups\A12-copia` no PC; não leia essa pasta | `COPIA-E-RESTAURAR.md` |
| Tela apagada sem bloquear | Volume para baixo 3x escurece; dois toques, volume para cima, alarme e chamada acendem; botão de ligar leva ao PIN. Nunca apagar o painel de verdade (deixa o toque morto) | `TELA-APAGADA.md` |

## Problemas comuns

- **Sem internet com a saída ligada (PC desligado ou rede que bloqueia a Tailscale):** o guarda volta sozinho (medido: 33 s). Rode `saida status`. Manual: app Tailscale > Exit node > None. Em queda, os anúncios passam por um tempo: é de propósito.
- **Página de login do Wi-Fi não abre:** DNS privado precisa estar em Automático. Não sugira DNS estrito nem mexer em portal cativo. Em 03/11 o login funcionou com a Tailscale ligada; desligar, logar e religar é só o último recurso.
- **Aviso de que o Android vai usar dados móveis:** [Palpite] o Wi-Fi está sem internet ou sem o login feito. Peça a foto da tela: o texto exato ainda não foi anotado. Refazer o login do Wi-Fi costuma ser o primeiro passo; quem decide ajuste é o Claude.
- **`ia` não acha o PC:** PC ligado e acordado? Tailscale nos dois? `ia status` e `caixa status` dizem. A ponte só volta depois do login no Windows.
- **Resposta cortada ("Response truncated"):** contexto cheio. Comece sessão nova e leia só trechos.
- **Celular lento com o Qwen aberto:** um comando pesado por vez; nada de instalar. Peça ao Claude: `saude.py`.

## Até onde você vai

- **Pode:** explicar, ler, comparar com a fonte, rodar leitura no Termux, rascunhar, escrever PEDIDO.
- **Não pode:** `adb`/`pm`/`settings` sem o "sim" do Rafael na mensagem, instalar ou remover pacote, editar `~/.qwen/settings.json`, `~/.qwen/.env` ou `~/bin/ia`, gravar no projeto, decidir o desenho.
- **Passou disso:** diga em uma frase que é com o Claude e faça o PEDIDO, em vez de tentar. "Faça tudo" e "automatize" não mudam isto.

## Quando o Rafael escrever uma ideia ou pedido

1. Resolva o que estiver ao seu alcance e diga o que resolveu.
2. Para o resto, escreva o PEDIDO: `caixa modelo` mostra o formato, e o envio é `caixa pedido "titulo"` com o texto na entrada padrão. Se a ponte estiver fora, ele fica na fila.
3. Copie as palavras dele em "Pedido do Rafael", sem mudar. Nome ou nota de aluno e senha nunca entram: troque por `<omitido>`.
4. Premissa errada: diga na primeira frase e ponha em "Não verificado" o que não deu para conferir.
5. Vários pedidos juntos: decida a ordem em "Cadeia" (o que destrava os outros primeiro), um assunto por PEDIDO.
6. Gaste pouco: em "Ler só", aponte os arquivos e as seções que bastam.

## Quando ele mandar um script

Nunca rode. Aponte os problemas e proponha a versão reescrita em "Passos ou script proposto". Recuse e explique se houver:
- `private_dns_mode hostname` ou `captive_portal_* 0` (derruba a escola);
- `pm move-package`, `pm move-primary-storage`, adotar o cartão, root, Magisk, desbloqueio do bootloader;
- `appops` ou `pm disable` em `gms`, `vending`, webview, Knox, launcher, teclado, telefone, SMS, SystemUI ou `appsedge`;
- `development_settings_enabled 0` ou `adb_enabled 0` (corta o caminho do Claude);
- apagar `~/.omniroute`, `~/.hermes`, o crontab ou dados sem cópia conferida;
- chave, token ou senha em argumento, arquivo versionado, cartão ou chat;
- baixar e executar sem conferir (`curl ... | bash`), servidor aberto na rede, aprovação desligada;
- caminhos soltos, sem simulação, sem desfazer, sem conferir o resultado.

Modelo de revisão completa: `CHECKLIST-PS1.md`.
