# AdGuard Home no PC e escolha de anúncios por site (02/11/2026)

Pedido do Rafael: bloqueador de anúncios no PC para o celular, "que eu possa escolher quais sites teriam ou não esse bloqueador", porque um site de que ele gosta só abre os filmes com os anúncios.

## A premissa que muda o desenho
**Bloqueio por DNS não sabe em que site você está.** Ele só vê o nome de cada endereço pedido, então "liberar um site" no AdGuard libera aquele domínio em todo o celular. Escolher **site a site** só existe no navegador. [Certo: é como o DNS funciona.] Por isso ficaram duas camadas:

| Onde | Escolhe por | Como |
|---|---|---|
| **uBlock Origin no Fennec** (o certo para "este site sim, aquele não") | site | no site: ícone do uBlock → botão grande de energia; vale só para aquele site e fica guardado |
| **AdGuard Home no PC** (apps e todo o aparelho) | domínio, em todo o celular | `liberar`, `bloquear`, `tirar`, `pausar` abaixo |

O Fennec usa DNS seguro próprio (DoH, modo 2), então **não passa pelo AdGuard**: o site escolhido abre com anúncios ao desligar o uBlock nele, sem precisar mexer no AdGuard. Site de filmes com anúncio costuma trazer anúncio malicioso: com o uBlock desligado nele, não instale nada que a página oferecer.

## O que está instalado [Certo: testado neste PC em 02/11]
- AdGuard Home v0.107.79, serviço do Windows em LOCAL SERVICE, `C:\Program Files\AdGuardHome`, dados em `C:\ProgramData\AdGuardHome`, início automático atrasado e religamento em caso de falha. Versão fixa e SHA-256 conferido no `scripts\adguard-pc.ps1`.
- DNS **só** em `100.64.0.1:53` (a tailnet); painel **só** em `127.0.0.1:3000`; firewall "AdGuard Home DNS (somente tailnet)" (remoto 100.64.0.0/10).
- Acesso em `C:\Projetos\adguard-home\acesso.json` (fora do git, ACL só do usuário `passo`, senha gerada e nunca impressa). As regras e os domínios liberados ficam só no AdGuard: nome de site nunca entra em arquivo versionado.
- DNS criptografado de 3 empresas (Cloudflare, Google, Quad9), 2 listas (194.573 regras), histórico de 24 h, 68 MB de RAM.
- Comportamento conferido: do celular resolve em milissegundos; bloqueio devolve 0.0.0.0; sobrevive a reiniciar a Tailscale; se subir antes da Tailscale, para e volta sozinho em ~25 s.

## Comandos (`python scripts\adguard-pc.py ...`, o Claude roda por você)
`status` · `liberar <dominio>` (aceita colar a URL) · `bloquear <dominio>` · `tirar <dominio>` · `listar` · `testar <dominio>` (diz por qual regra) · `pausar [min]` (padrão 15; volta sozinho) · `retomar` · `top` (o que mais foi bloqueado: acha o domínio que quebrou um site). Serviço: `pwsh -File scripts\adguard-pc.ps1 -Status|-Reiniciar|-Desinstalar`.

## Falta o clique dele: DNS no painel da Tailscale
Sem isso o AdGuard está pronto, mas **o celular ainda não o usa**. Conferido em 02/11: `tailscale dns status --all` diz "Nameservers: none were provided", e `doubleclick.net` no celular resolve para IP real.
Em login.tailscale.com/admin/dns > Nameservers:
1. Add nameserver > Custom > `100.64.0.1`, ligar **Use with exit node**, Save.
2. Add nameserver > Custom > `1.1.1.1`, **Use with exit node** desligado, Save.
3. Ligar **Override DNS servers**.

O PC está com `tailscale set --accept-dns=false`, para não depender de si mesmo.

| Situação | DNS que o celular usa | Anúncios |
|---|---|---|
| Saída pelo PC ligada | só o AdGuard [Certo: tailscale.com/kb/1054/dns, com exit node o aparelho só usa nameserver marcado "Use with exit node"] | bloqueados |
| PC cai | o guarda `saida` desliga a saída (medido: internet de volta em 33 s) e o 1.1.1.1 assume | passam |
| Saída desligada e PC no ar | AdGuard e 1.1.1.1 em paralelo, vence o mais rápido [Certo: mesma página] | **pode vazar** |

Por que 1.1.1.1 junto: só com o AdGuard, um PC desligado derrubaria o DNS do celular. A alternativa sem vazamento é manter a saída ligada.

## Testado e não testado
- Testado: todos os comandos contra o servidor real; a instalação; 71 testes e 24 de 24 defeitos plantados pegos.
- **Não testado até o clique**: bloqueio de verdade no celular, liberar e pausar vistos do celular, a queda do PC com o DNS configurado, o vazamento medido nos dois modos.
- **Não testado**: login do Wi-Fi da escola com esse DNS. Se a página de login não abrir, desligue a saída no app Tailscale, entre e ligue de novo; se ainda assim não abrir, desligue a Tailscale para logar (regra antiga do projeto).

## Desfazer
Tirar os dois nameservers e o "Override" no painel; depois `pwsh -File scripts\adguard-pc.ps1 -Desinstalar` e `tailscale set --accept-dns=true`.

Fontes: tailscale.com/kb/1054/dns · github.com/AdguardTeam/AdGuardHome (releases, wiki "Configuration" e openapi) · HostlistsRegistry da AdGuard (listas).
