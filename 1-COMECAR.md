# 1. Começar

Analogia: antes de mexer no motor, o mecânico **liga o scanner** e lê o painel. É isso que este guia
faz: prepara o PC, conecta o celular e tira um retrato do aparelho **sem mudar nada**.

## O que instalar no PC (uma vez, tudo grátis)

| Programa | Para quê | Como |
|---|---|---|
| Python 3.11+ | roda os scripts | `winget install Python.Python.3.12` |
| PowerShell 7 | roda os `.ps1` | `winget install Microsoft.PowerShell` |
| ADB (platform-tools) | a "porta de oficina" do Android | `winget install Google.PlatformTools` |
| Git (opcional) | baixar e atualizar pelo GitHub | `winget install Git.Git` |

Depois de instalar, feche e abra o terminal e confira: `python --version`, `pwsh --version` e `adb version`.

## Ligar a depuração USB no celular

1. **Configurações > Sobre o telefone > Informações do software** e toque **7 vezes** em
   **Número de compilação**. Aparece "Modo de desenvolvedor ativado".
2. **Configurações > Opções do desenvolvedor > Depuração USB**: ligue.
3. Ligue o cabo no PC e rode `adb devices`. No celular, aceite **"Permitir depuração USB?"**
   (marque "Sempre permitir deste computador" só no **seu** PC).
4. `adb devices` deve mostrar o aparelho com a palavra `device`. Se aparecer `unauthorized`, olhe a tela
   do celular; se aparecer `offline`, tire e ponha o cabo e rode `adb kill-server`.

> Dica: o app `gov.br` (e alguns de banco) recusa abrir com as Opções do desenvolvedor **visíveis**.
> Esconda-as sem desligar o ADB: `adb shell settings put global development_settings_enabled 0`.

## Primeiro diagnóstico (só leitura)

Na pasta do projeto:

```
python scripts\sonda-a12.py        # retrato do aparelho: modelo, versão, memória, apps
python scripts\saude.py            # painel: bateria, temperatura, RAM, quem pesa, espaço
python scripts\auditoria.py        # confere mais de 150 itens; nada é mudado
```

Os três **só leem**. As saídas ficam em `diagnostico\` (essa pasta não vai para o GitHub: tem dados do
seu aparelho).

## Seus valores pessoais

Alguns scripts precisam saber o endereço do seu PC na Tailscale (guia 4). Os valores que vêm no código
são **exemplos neutros** (`100.64.0.1` para o PC, `100.64.0.2` para o celular). Troque pelos seus:

- no PC: variáveis `IA_PC_IP`, `ADGUARD_IP` e afins (cada script diz qual lê, no comentário do topo);
- no celular (Termux): `IA_PC_IP` e `PONTE_URL` no `~/.bashrc`.

Para descobrir os seus: `tailscale ip -4` no PC e o app da Tailscale no celular.

## Problemas comuns

| O que aparece | O que fazer |
|---|---|
| `adb: command not found` | Feche e abra o terminal depois do winget; ou use o caminho completo do `adb.exe` |
| `unauthorized` | Aceite o aviso na tela do celular; se sumiu, revogue as autorizações nas Opções e ligue de novo |
| `offline` depois de recolocar o cabo | `adb kill-server` e `adb start-server`; feche o aviso "Permitir acesso aos dados" com Voltar |
| Script diz "simulação" e não muda nada | É o padrão. Leia o que ele faria e rode de novo com `--aplicar` |

Próximo: [2-DEIXAR-RAPIDO.md](2-DEIXAR-RAPIDO.md).
