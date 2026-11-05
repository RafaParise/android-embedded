# Cópia local do A12 e como restaurar (04/11/2026)

Script: `scripts\copia-a12.py`. A cópia fica em `C:\Users\voce\Backups\A12-copia`, fora do git e do Drive, porque tem SMS, contatos e chamadas. Não abrir essa pasta com IA externa.

## O que é e o que não é
Não é uma imagem do aparelho, como no iPhone [Certo, medido em 04/11]: o `dd` nas partições dá "Permission denied", e a memória é criptografada por arquivo. O modo Download só aceita firmware assinado pela Samsung [Provável: inicialização verificada, com o bootloader travado]. Root segue decidido NÃO.

Por isso a restauração tem duas partes: o firmware original da Samsung, e depois o script, que refaz o aparelho.

| Volta | Não volta |
|---|---|
| 64 apps (APKs conferidos por md5), com o instalador de origem | Dados internos de apps sem backup próprio: logins, bancos, ajustes de cada app |
| Remoções e desativações (lotes) | Contas Google e demais logins |
| Apps padrão, teclado, permissões, isenções de bateria | Redes Wi-Fi e pareamentos Bluetooth |
| Ajustes do projeto, gesto da tela e Wi-Fi em alto desempenho | Organização da tela inicial |
| Arquivos da memória interna | SMS, contatos e chamadas: ficam só para consulta em `pessoais\` |
| Termux, sem chaves e sem modelos de IA | Chaves do OmniRoute do celular: copiar de novo |

O cartão SD não entra na cópia: ele não depende do sistema. O WhatsApp volta pelo backup dele, se estiver ativado.

## Parte 1: o celular não liga (modo Download)
A depuração USB só existe com o Android funcionando, então nenhum script por cabo conserta este caso.

1. Instale o Samsung Smart Switch para PC, do site da Samsung. Hoje ele não está instalado.
2. Abra `MORE > Emergency Software Recovery and Initialization` [Certo: guia da Samsung, `update.kies.samsung.com/SmartSwitchPC_recovery_guide/firmware/emergencyrecovery`].
3. Se a atualização falhou, escolha "Emergency recovery". Se não aparecer nada, use "Device Initialization", que pede o modelo e o número de série (estão em `aparelho.json`) e **apaga tudo** [Provável: relatos; não testado aqui].
4. Com o celular desligado, segure volume para cima + volume para baixo e ligue o cabo: entra no modo Download [Provável: não testado neste aparelho].

Não instale firmware de site de terceiros. Antes de apagar: se o aparelho ainda entra no Android, rode a cópia.

Nada desta parte foi testado aqui: testar apagaria o único aparelho dele.

## Parte 2: o celular liga
1. Termine a configuração inicial e entre na conta Google.
2. Ligue as Opções do desenvolvedor (Número de compilação, 7 toques) e a Depuração USB; ligue o cabo e autorize.
3. Dê dois cliques em `scripts\restaurar-a12.cmd`: ele mostra o plano e só aplica se você digitar `RESTAURAR`.

## Parte 3: o que fica com a sua mão
Contas e login de cada app · Tailscale (login, VPN sempre ativada, `saida`) · Termux: `termux-setup-storage`, depois `cd ~; tar xzf ~/storage/downloads/termux-copia.tgz` e `pkg install $(cut -f1 termux-pacotes.txt)`; Termux:Boot aberto uma vez · chaves do OmniRoute: `omniroute-celular.ps1 -Ativar` · ponte: `ponte-pc.ps1 -Parear` · pasta do Open Camera e do NewPipe no cartão · Wi-Fi e Bluetooth · sons e tela inicial.

## Manter a cópia em dia
Dois cliques em `scripts\copia-a12.cmd`: só traz o que mudou. Rode depois de instalar app ou mudar ajuste importante.

`python scripts\copia-a12.py conferir` compara o celular com a cópia, só lendo. `--so apps` (ou `papeis`, `lotes`, `permissoes`, `ajustes`, `arquivos`, `termux`) restaura só uma parte.

`copiar --aplicar --dados-apps` tenta também o `adb backup`, que pede toque no celular. Apps feitos para Android 12 ou mais novo ficam de fora [Certo: `developer.android.com/about/versions/12/behavior-changes-12`].

## Provas e limites
Medidas da cópia: ver `ESTADO.md`. A restauração nunca rodou num aparelho apagado; o `conferir` mostra que o plano sai vazio no aparelho atual, e isso prova a leitura, não a reinstalação inteira. A restauração nunca apaga arquivo nem tira app instalado depois da cópia.
