# 4. Sem cabo, de qualquer lugar

Analogia: a **Tailscale** é um corredor particular entre as suas casas. O PC e o celular ganham um
endereço fixo (começa com `100.`) que só os seus aparelhos enxergam, no Wi-Fi de casa, da escola ou nos
dados móveis, sem abrir porta no roteador.

## Tailscale (grátis)

1. Instale no PC (`winget install Tailscale.Tailscale`) e no celular (F-Droid ou Play Store) e entre
   com a **mesma conta** nos dois.
2. `tailscale ip -4` no PC mostra o endereço dele. Guarde: é o `IA_PC_IP` dos scripts (guia 1).
3. No celular, deixe a VPN "sempre ativada", mas **sem** "bloquear conexões sem VPN": redes com página de
   login (escola, hotel) não abrem com o bloqueio ligado.

## ADB pela rede (porta 5555)

Com o cabo ligado uma vez: `python scripts\depuracao-sem-fio.py porta5555`. A partir daí:

- o **PC** alcança o celular em `IP-do-celular:5555` pela Tailscale (`python scripts\adb-remoto.py garantir`);
- o **Matrix** alcança o próprio celular em `127.0.0.1:5555`, em qualquer rede.

**Risco, dito às claras:** a porta 5555 aceita comandos de quem estiver na mesma rede e tiver a chave do
ADB autorizada. Ela cai quando o celular reinicia (o `cel` religa). Use só no seu aparelho.

## Segunda tela

`segunda-tela.cmd` (ou `python scripts\segunda-tela.py`) abre um menu:

| Opção | O que faz | Usa |
|---|---|---|
| 1 | O PC mostra e comanda o celular | scrcpy |
| 2 | Uma tela **extra** do celular numa janela do PC (outro app, sem mexer na tela do celular) | scrcpy `--new-display` |
| 3 | O celular vira monitor extra do Windows | Sunshine + Virtual Display Driver no PC, Moonlight no celular |
| 4 | Versão leve para dados móveis | scrcpy com menos qualidade |

A opção 3 precisa de uma instalação como administrador, uma vez: `segunda-tela-instalar.cmd`.

## Saída de internet pelo PC

O celular pode navegar "de dentro de casa" (exit node da Tailscale): `python scripts\vpn-celular.py saida
ligar` simula; com `--aplicar`, liga e confere em 45 s, e **desfaz sozinho** se a internet não vier. No
Termux, o comando `saida` deixa um guarda vigiando: se o PC sumir, a saída é suspensa (medido: 33 s).

## Webcam

`webcam-celular.cmd`: o celular vira câmera do PC (scrcpy + câmera virtual do OBS), com cabo ou sem.

Detalhes e medidas: [`memoria/VPN-SEMPRE-ATIVA.md`](memoria/VPN-SEMPRE-ATIVA.md),
[`memoria/WEBCAM-E-RECUPERACAO.md`](memoria/WEBCAM-E-RECUPERACAO.md).

Próximo: [5-TELA-SOM-E-VOZ.md](5-TELA-SOM-E-VOZ.md).
