# Instruções para agentes de IA (Claude Code, Codex, Qwen Code, Hermes e outros)

Leia inteiro antes de mudar qualquer coisa. Vale para qualquer agente, não só para o Claude.

## O projeto em uma frase
Scripts do PC (Windows) e um kit para o Termux que deixam um Samsung Galaxy A12 (SM-A125M, Android 12)
mais rápido e automatizado **pelo ADB, sem root**, com cada mudança reversível.

## Regras que não mudam
- **Português do Brasil** em tudo: respostas, comentários, textos da tela, documentos e commits.
- **Simular é o padrão.** Script que muda o aparelho só age com `--aplicar` (ou com o nome da ação).
  Nunca rode `--aplicar`, `--remover` nem nada que mude o celular sem o dono pedir.
- **Root, Magisk e desbloqueio do bootloader: fora do projeto.** Não pesquise, não proponha, não planeje.
- **Nunca `pm move-package` nem `pm move-primary-storage`** (no A12 derrubaram o sistema e corromperam
  arquivos). Operação em massa no armazenamento: backup antes e md5 depois, com o cache descartado.
- **Nunca desativar:** `com.android.*`, serviços do Google (`gms`, `gsf`), Play Store, WebView, Knox,
  a tela inicial, o teclado em uso, telefone e SMS, SystemUI, `com.samsung.android.app.appsedge`,
  `com.samsung.android.kgclient`. A lista `PROTEGIDOS` do `lote-pacotes.py` é a fonte.
- **Irreversível** (formatar, apagar dados, reset) só com o "sim" escrito do dono, depois de olhar o
  alvo, com bateria acima de 3% e carregando.
- **Tela:** nunca `scrcpy --turn-screen-off`, nunca desligar o painel por comando, nunca `keyevent 26`
  ou `223` sem avisar. Use `scripts/tela-apagada.py`.
- **Sem segredos no repositório:** chave, token, senha, e-mail ou IP pessoal não entram em arquivo
  versionado. Cada pessoa põe os próprios valores em variáveis de ambiente.
- **Sem dado de terceiros:** contas, contatos e conversas que aparecem em listas ou capturas do celular
  são mascarados e nunca vão para arquivo, commit ou memória.
- **Script de outra IA não roda como veio:** leia, confira pacote por pacote, teste em simulação.
- **Instalar** só de fonte oficial (F-Droid, GitHub do autor, winget) e com o hash conferido.

## Antes de cada commit
- `python -m pytest scripts/tests -q` (Linux ou WSL; os testes usam um ADB falso e não tocam celular).
  Mudou um script? Rode o teste dele e, se mudou o comportamento, escreva o teste antes.
- `git status` e `git diff --staged`: adicione só os arquivos que você mudou (nunca `git add -A`).
- Commit pequeno, mensagem "Área: assunto" em português.

## Onde está cada coisa
- `scripts/`: um script por tarefa, cada um com o uso e o desfazer no comentário do topo.
- `scripts/celular-kit/`: o que vai para o Termux (`bin/`: `ia`, `cel`, `memoria`, `caixa`, `saida`,
  `guarda`, `linux`; `QWEN.md`: a personalidade e as regras do parise-core; `settings.json`: as travas).
- `scripts/celular-kit/papel/` e `tela/`: código Java dos ajudantes (compilam sem Gradle).
- `scripts/tests/`: a bateria de testes.
- `memoria/`: documentos técnicos, com o que foi medido e o que falhou. Leia o do assunto antes de
  propor algo: muita ideia "óbvia" já foi testada e descartada, com prova (`RADAR-DESEMPENHO.md`).
- Guias para pessoas: `README.md` e `1-COMECAR.md` a `6-SEGURANCA-E-REPARO.md`.

## Como agir
- Leia só trechos de arquivos grandes (busque primeiro).
- Fato que alguém vai repassar (versão, número, preço) leva **[Certo]**, **[Provável]** ou **[Palpite]**
  e a fonte.
- Premissa errada do usuário: diga na primeira frase, com o risco e a alternativa.
- Terminou: diga o que mudou, como testou e como desfazer.
