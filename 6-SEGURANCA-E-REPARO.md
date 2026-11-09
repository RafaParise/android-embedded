# 6. Segurança e reparo

## As regras de ouro (aprendidas no aparelho)

| Nunca | Por quê | O que fazer no lugar |
|---|---|---|
| `pm move-package` ou `pm move-primary-storage` | No A12 derrubou o sistema e corrompeu 1.412 arquivos, mesmo dizendo "Success" | App na memória interna: `pm uninstall --user 0` + `adb install -r` |
| Confiar em "Success", `du` ou contagem de arquivos | Nada disso prova integridade | md5 contra o backup, com o cache descartado (`teste-gravacao.py`) |
| Desligar as Opções do desenvolvedor pela tela | Desliga também a depuração USB | `settings put global development_settings_enabled 0` (esconde e mantém o ADB) |
| Formatar o cartão, apagar dados ou resetar sem conferir | Não tem volta | Olhar o alvo, bateria acima de 3% e carregando, e só então |
| Rodar script de outra IA sem ler | Já apareceu script que apagava pastas e reinstalava tudo | Ler, conferir pacote por pacote e testar a parte que dá |
| Root, Magisk ou desbloquear o bootloader | Apaga o celular e não tem volta simples | Não é assunto deste projeto |

## Antivírus `guarda`

Analogia: um **porteiro** que olha cada pacote que chega (Download, Documentos, apps novos) e manda para o
raio-X do PC (ClamAV) só o que precisa. O que for suspeito vai para a **quarentena**, que nunca apaga.

- PC: `guarda.cmd` (menu) ou `python scripts\guarda.py varredura`.
- Celular: `antivirus` (menu) ou `guarda status`, `guarda varrer ARQUIVO`, `guarda quarentena`.
- Com o PC desligado, nada é varrido e nada é dado como limpo.

Detalhes: [`memoria/ANTIVIRUS.md`](memoria/ANTIVIRUS.md).

## Conferir tudo

```
python scripts\auditoria.py     # mais de 150 itens; só lê; rode depois de qualquer mudança
python scripts\saude.py         # o painel; --online confere atualização de sistema e dos apps
```

## Cópia e restauração

`copia-a12.cmd` faz uma cópia local em duas partes (o que dá para copiar sem root) e `restaurar-a12.cmd`
devolve. A cópia tem mensagens e contatos: guarde fora da nuvem e não abra com IA de terceiros.
O que volta e o que não volta: [`memoria/COPIA-E-RESTAURAR.md`](memoria/COPIA-E-RESTAURAR.md).

## Desfazer

| Mudou | Desfaz com |
|---|---|
| Lote de apps | `python scripts\lote-pacotes.py LOTE --restaurar` |
| Modo economia | `python scripts\modos.py economia desligar` |
| Papel rolante | `python scripts\papel-rolante.py desfazer` |
| Saída pelo PC | `saida desligar` (Termux) ou o app da Tailscale > Exit node > None |
| Voz offline | `memoria/VOZ-OFFLINE.md`, seção "Desfazer" |
| Kit do parise-core | `pwsh scripts\ponte-pc.ps1 -Desinstalar` e `-NovoToken` (revoga o acesso) |

## Recuperar arquivos apagados

`recuperar-arquivos.cmd` abre o PhotoRec (CGSecurity) no cartão ligado ao PC
([`memoria/WEBCAM-E-RECUPERACAO.md`](memoria/WEBCAM-E-RECUPERACAO.md)).
