# Scripts do PC no A12: o que vai, o que vira comando do celular e o que fica no PC (01/11/2026)

Pedido do Rafael: integrar ao Samsung A12 os scripts de sincronização, nuvem e kit, o `CLAUDE.md`, o `RELATORIO-KIT-TURBO.md` e os dois `.sh` de unificação; o que não couber no telefone vira base para algo equivalente que caiba no Android.

## Regras que decidem o que cabe
- O Termux do A12 tem node 26, Python 3.14, git, jq, socat e curl, e **não tem PowerShell** [Certo: `command -v pwsh` = não, 01/11]. Os `.ps1` não rodam lá.
- **Nada de token do GitHub, chave de provedor, `~/.claude.json` nem chave de cliente do OmniRoute em arquivo no celular** (regra do projeto). Por isso o celular não faz `git push`: quem versiona é o PC. O celular só tem o token da ponte do PC (`~/.qwen/.env`, modo 600, autorizado em 31/10).
- Sem root: o Termux só enxerga os próprios dados. O limite de processos fantasma do Android 12 já está liberado (`max_phantom_processes` = 2147483647).
- Reiniciar o aparelho derruba o sshd e a Tailscale do Termux; não havia Termux:Boot em 01/11 (só o pacote `com.termux`) [Certo: `pm list packages`, 01/11]; **hoje há Termux:Boot (02/11)**, que sobe o sshd e a guarda `saida` depois do reboot (`celular-kit/boot/iniciar-a12`).
- RAM de 3,8 GB: o Qwen local de 1,5B só roda se couber (`ia status` mostra a memória livre).

## Cada arquivo
| Arquivo | No celular | Equivalente ou motivo |
|---|---|---|
| `CLAUDE.md` | cópia de LEITURA em `~/kit/projeto-android-embeeded/` e as regras curtas em `~/.qwen/QWEN.md` | o Qwen pequeno carrega só o `QWEN.md`; o resto ele consulta quando precisa |
| `scripts/sync-memoria.ps1` | só leitura | NÃO roda lá (pede token do GitHub e o git do PC). Equivalente: `caixa enviar` grava a entrega no celular e `caixa sincronizar` a manda ao PC como arquivo novo "NAO REVISADO"; o Claude do PC revisa e versiona |
| `scripts/teste-nuvem.ps1` | só leitura | PC. São 150 verificações em repositórios temporários. Os comandos do celular são testados no PC, com curl, qwen e socat falsos (`test_ia_comando_termux.py`, `test_caixa_termux.py`) |
| `scripts/kit-celular.ps1` | só leitura | É o instalador: roda NO PC e manda o kit ao Termux pelo cabo. Sem cabo: `caixa atualizar` baixa do PC os comandos, o `QWEN.md` e a ponte MCP |
| `scripts/nuvem-comum.ps1`, `nuvem-configurar.ps1`, `nuvem-iniciar.ps1`, `nuvem-integrar.ps1` | só leitura | PC. Cuidam do repositório B, da sessão na nuvem e da integração de branches. No celular a sessão na nuvem abre pelo navegador [Provável]; nada a portar |
| `RELATORIO-KIT-TURBO.md` | não vai | relatório do plugin kit-turbo do Claude Code do PC. O que serve ao celular já está no kit: skills do kit-turbo e do kit-professor em `~/kit/skills-extras` e o `kit-turbo-README.md` em `~/kit/estrategias` |
| `unificar_hermes_claude_code.sh`, `claude_code_unification_script.sh` | **não vão** | são blocos para colar no terminal do PC: gravam a chave do OmniRoute em `~/.claude/settings.local.json` com campos que parecem inventados [Provável: não conferi na documentação] e mandam usar `--dangerously-skip-permissions`. Um agente no celular poderia tentar executá-los |

## Novos de 02/11
| Arquivo | Onde roda | Como chega |
|---|---|---|
| `scripts/celular-kit/bin/saida` | Termux | kit da ponte (`caixa atualizar`) |
| `scripts/celular-kit/boot/iniciar-a12` | Termux:Boot (`~/.termux/boot/`) | kit da ponte |
| `scripts/navegador.py` | PC; o Qwen usa pela ferramenta `navegador_ler` da ponte, o Hermes por `navegador.cmd` | não vai ao celular (pede um Chromium) |
| `scripts/navegador-a12.py` | PC, pelo cabo: comanda o Fennec | não vai ao celular |
| `scripts/adguard-pc.py`, `.ps1` | PC | não vai ao celular (é serviço do PC) |

## O que os dois `.sh` queriam e onde isso já existe no celular
| Função do `.sh` | No celular |
|---|---|
| `h2c` / `hermes-to-claude` (arquivo + pedido para o modelo) | `cat arq \| ia qwen "pedido" -` (até 20 mil caracteres; vai a um provedor externo: nunca dado de aluno) |
| `c2h` / `claude-to-hermes` (devolver só o diff) | `cat arq \| ia qwen "devolva só o diff para ..." -`; para entregar ao PC: `caixa enviar "titulo"` |
| `check-models` / `check-local-models` | `ia status` (nuvem, PC, ponte e modelos do celular) |
| `test-integration` | `ia status` e `caixa status` (a ponte responde? o kit está em dia?) |
| `sync-workspace` | `git status` na pasta do projeto no celular |
| `export OMNIROUTE_KEY_HERMES=...` | não existe no celular, de propósito: `ia codigo` usa a ponte e o token dela |

## Como atualizar a cópia de leitura
- Com cabo, no PC: `pwsh -NoProfile -File scripts\kit-celular.ps1 -Enviar` (varre segredos antes e aborta se achar algum). Atualiza `~/.agents/skills`, `~/kit/skills-extras`, `~/kit/estrategias` e `~/kit/projeto-android-embeeded`.
- O `caixa status` mede só o kit da ponte (comandos e `QWEN.md`): **não avisa se a cópia do projeto está velha**. Em 01/11 ela estava de 31/10 07:58 e foi renovada.
- Com a ponte no ar o Qwen do celular lê o projeto AO VIVO pelo MCP; a cópia local só importa sem o PC.

## O que ainda poderia ser feito (só se o Rafael quiser)
1. `caixa atualizar` trazer também a cópia do projeto, sem cabo (pede uma rota nova e somente leitura na ponte).
2. ~~Instalar o Termux:Boot para religar o sshd depois de reiniciar.~~ FEITO em 02/11 (`celular-kit/boot/iniciar-a12`).
3. `caixa status` mostrar a idade da cópia do projeto.
Nada de GitHub no celular.
