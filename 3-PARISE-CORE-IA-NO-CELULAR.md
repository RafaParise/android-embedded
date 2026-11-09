# 3. parise-core, a IA no celular

Analogia: o Qwen Code é um **carro sem motor**: o programa que lê arquivos, roda comandos e conversa.
Quem pensa é o **modelo** (o motor). No celular cabe só um motor de moto (modelos de 0,5 a 1,5 bilhão de
parâmetros, que conversam mas não trabalham). Por isso o parise-core pega carona no motor grande da nuvem,
pelo PC, e cai para o motor pequeno quando está sem internet.

## Como as peças se encaixam

```
 Celular (Termux)                        PC (Windows)
 ┌──────────────────────┐   Tailscale   ┌──────────────────────────────┐
 │ parise-core / ia          │ ────────────► │ OmniRoute :20128 (IA grátis) │
 │ cel (lê e toca)      │               │ Ponte do projeto :20130      │
 │ memoria (SQLite, SD) │ ◄──────────── │ Ollama :11434 (reserva)      │
 └──────────────────────┘   adb :5555   └──────────────────────────────┘
```

- **OmniRoute** (no PC): junta vários provedores de IA grátis numa porta só e troca de provedor
  sozinho quando um acaba a cota. Os "combos" `codigo`, `auditoria` e `rapido` escolhem o tipo de modelo.
- **Ponte do projeto** (`scripts/ponte-pc.py`): deixa o parise-core ler a documentação do projeto ao vivo e
  pedir ao PC as ações de uma **lista fechada** (`acao_pc`), sem comando livre.
- **Ollama** (opcional): modelo local do PC, reserva quando a nuvem falha.

## Instalar

1. **No celular:** Termux, Termux:API e Termux:Boot pelo **F-Droid** (a versão da Play Store está parada).
   No Termux: `pkg install nodejs python git curl socat`.
2. **No PC:** OmniRoute e Tailscale (guia 4); depois `pwsh scripts\ia-do-pc.ps1` liga tudo e confere.
3. **Levar o kit ao celular:** com o cabo, `pwsh scripts\ponte-pc.ps1 -InstalarNoCelular`; sem cabo,
   `pwsh scripts\ponte-pc.ps1 -Parear` mostra um código de uso único para colar no Termux.
   O kit instala os comandos `ia`, `parise-core`, `cel`, `memoria`, `caixa`, `saida`, `guarda` e `linux`, e as
   regras de segurança do Qwen Code.

Passo a passo completo, com cada mensagem esperada: [`memoria/GUIA-IA-NO-CELULAR.md`](memoria/GUIA-IA-NO-CELULAR.md).

## Usar

| Comando (no Termux) | O que faz |
|---|---|
| `parise-core` | Abre a IA completa, com o visual verde e a personalidade (humor seco, sinceridade 100%) |
| `ia status` | Mostra quais "motores" estão ao alcance |
| `ia chat` | Conversa só no celular, sem internet |
| `cel ler` | Lista numerada do que está na tela (textos, botões, campos) |
| `cel tocar 3` / `cel tocar "Salvar"` | Toca no item; **recusa** botões sem volta (desinstalar, apagar, pagar, Pix) |
| `cel tela apagar` | Escurece sem bloquear (guia 5) |
| `memoria buscar wifi` | Busca na memória local (SQLite FTS5, no cartão SD, funciona offline) |

Receitas prontas (alarme, Não Perturbe, volume, discar, mapa, voz): [`memoria/RECEITAS-ANDROID.md`](memoria/RECEITAS-ANDROID.md).

## As travas (por que dá para confiar)

O parise-core roda sem pedir licença a cada passo (modo "yolo", a pedido do dono), mas uma lista de **negados**
no `settings.json` do Qwen Code bloqueia o que não tem volta: desinstalar, apagar com `rm -r`, `pm clear`,
reiniciar, `npm`/`pip install`, ADB direto e mudar o microfone do fone para o modo de ligação. Os
negados são conferidos antes do modo, então nem o "yolo" passa por cima.

Quando erra, ele anota a lição na memória, e o revisor (o Claude Code do PC) escreve as lições dele em
[`memoria/LICOES-PARISE-CORE.md`](memoria/LICOES-PARISE-CORE.md), que chegam ao celular pelo `memoria atualizar --pc`.

Próximo: [4-SEM-CABO.md](4-SEM-CABO.md).
