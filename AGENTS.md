# Instruções para agentes

Este arquivo existe para os agentes que procuram `AGENTS.md` (Codex, Hermes, Qwen Code e outros).
**As instruções do projeto ficam no [`CLAUDE.md`](CLAUDE.md)**: leia o arquivo inteiro antes de mudar
qualquer coisa. Ele vale para qualquer agente.

O essencial, que nunca muda:

- Tudo em português do Brasil.
- Sem root. Simular é o padrão: nada muda o celular sem `--aplicar` e sem o dono pedir.
- Nunca `pm move-package` nem `pm move-primary-storage`; nunca desativar a lista `PROTEGIDOS`.
- Sem segredos nem dados pessoais em arquivo versionado.
- Antes do commit: `python -m pytest scripts/tests -q`, `git status`, e `git add` só do que você mudou.

## Configurar num computador novo (para o agente fazer pelo usuário)

1. Conferir o que já existe: `python --version`, `pwsh --version`, `adb version`.
2. Instalar o que faltar com o winget (`Python.Python.3.12`, `Microsoft.PowerShell`,
   `Google.PlatformTools`), sem senha de administrador quando houver opção por usuário.
3. Pedir ao usuário para ligar a depuração USB e aceitar o aviso no celular (o agente não consegue
   tocar nessa tela pela primeira vez).
4. Rodar só leitura: `python scripts/sonda-a12.py`, `python scripts/saude.py`, `python scripts/auditoria.py`.
5. Mostrar o resultado e perguntar o que o usuário quer fazer, apontando o guia certo (1 a 6).
