# VPN sempre ativa e saída de internet pelo PC (Tailscale) — 01/11/2026

**03/11/2026, escola:** o Rafael conectou e autenticou no Wi-Fi da escola com VPN, saída e DNS configurados: "deu tudo certo", com as restrições da rede [Certo pelo relato dele; não medido]. Relato do Rafael: não precisou desligar a Tailscale para logar, e ao abrir a Sala do Futuro por dados móveis apareceu um aviso do Android parecido com "será usado dados móveis, já que não se autenticou" (texto exato não anotado). **Medido: o PC foi desligado às 11:37 e ligado às 17:49** (eventos 1074 e 6005 do Windows). O guarda suspendeu a saída às 11:38 e religou às 17:52 (`saida log`), e o AdGuard ficou sem consultas do celular nesse intervalo: o "se desligou com tempo" foi o guarda fazendo o que devia, e a escola não teve culpa. Portanto o teste provou o login com a saída suspensa; a saída ligada com o PC ligado, na escola, segue sem teste. O celular também reiniciou duas vezes (guarda iniciado às 12:07 e 14:30; motivo gravado pelo Android nos dois: `reboot,userrequested`, ou seja, reinício pedido, não falha).

Pedido do Rafael: "deixar sempre a VPN ligada ... em qualquer rede Wi-Fi que eu conectar eu nunca ter limites de acesso com meu computador ligado servindo como servidor ... tudo gratuito". Aqui estão o que ficou configurado, os limites reais e como desfazer.

## Limites honestos (a premissa "nunca ter limite" não se garante)
- O PC precisa estar **ligado, acordado e online**; a velocidade do celular fora de casa é a do **upload do PC** (teste curto de hoje: ~181 Mbit/s de envio e ~244 de recebimento [Provável: 8 MB e 25 MB só]). O Wi-Fi do próprio A12 (2,4 GHz) já limita a ~40 a 70 Mbit/s.
- **Segurança melhora** em Wi-Fi aberto (as redes SEDUC são abertas): tráfego e DNS vão cifrados (WireGuard) até o PC. HTTPS já era cifrado. **Desempenho não melhora**: a saída pelo PC acrescenta um salto; só ajuda quando a rede local limita ou filtra.
- Rede que bloqueia a Tailscale (UDP 41641 e os servidores DERP em HTTPS) **derruba a saída e o celular fica sem internet** enquanto a saída estiver ligada: a Tailscale não volta sozinha para a rede normal. Portal cativo (login do Wi-Fi) precisa passar antes. [Provável: nada disso testado na escola.]
- Contornar o filtro de uma rede da SEDUC pode ferir a política de uso dela [não verifiquei a norma]; a decisão é do Rafael.

## Estado em 02/11/2026
| Item | Estado | Desfazer |
|---|---|---|
| Celular: "VPN sempre ativada" para o Tailscale (`always_on_vpn_app=com.tailscale.ipn`) | LIGADA | Configurações > Conexões > Mais configurações de conexão > VPN > engrenagem do Tailscale |
| Celular: "Bloquear conexões sem VPN" (`always_on_vpn_lockdown=0`) | DESLIGADO de propósito: ligado atrapalha o login do Wi-Fi da escola e, segundo usuários, o religamento depois do boot [Provável: fórum da Tailscale, só relatos] | — |
| PC: anuncia a saída (`tailscale set --advertise-exit-node`; rotas `0.0.0.0/0` e `::/0`) | FEITO | `tailscale set --advertise-exit-node=false` |
| PC: modo sem usuário (`tailscale set --unattended`) | FEITO (`ForceDaemon=True`) | `tailscale set --unattended=false` |
| Painel da Tailscale: aprovar o PC como saída | FEITO em 02/11 (AllowedIPs inclui 0.0.0.0/0) | login.tailscale.com/admin/machines > `rafaparise` > ⋯ > Edit route settings |
| Celular: saída pelo PC em uso | LIGADA, com o guarda `saida` vigiando | `saida desligar` no Termux, `python scripts\vpn-celular.py saida desligar --aplicar` ou app Tailscale > Exit node > None |
| Celular: guarda e partida (`~/bin/saida`, `~/.termux/boot/iniciar-a12`) | FEITO: reinício real provado (~2 min) | `saida desligar`; apagar o arquivo de `~/.termux/boot/` |

## Como usar (sem digitar nada no celular)
- **Em casa**: deixe a saída desligada (não precisa).
- **Fora de casa / Wi-Fi aberto**: já fica ligada. Para ligar de novo: `saida ligar` no Termux (confere o PC e a internet, liga e deixa o guarda vigiando) ou app Tailscale > **Exit node** > `rafaparise`, com **Allow LAN access**. Pelo PC: `python scripts\vpn-celular.py saida ligar --aplicar` (confere em 45 s e **desfaz sozinho** se a internet não passar; não liga o guarda: o `status` e a saída do comando avisam).
- **Se a internet sumir** (PC desligado, rede que bloqueia a Tailscale): o guarda desliga a saída sozinho em ~33 s (medido em 02/11, com a tela ligada; com a tela apagada ele age quando o aparelho acorda, ou o tempo todo com `saida vigilia ligar`, que gasta bateria). Manual: app Tailscale > Exit node > **None**.
- **Login do Wi-Fi da escola**: com a saída desligada entra normalmente (172.30.0.1 se a página não abrir). Com a saída ligada o Android faz o teste do portal fora da VPN [Certo: Mullvad, "Android leaks connectivity check traffic"], então a página de login deve abrir; se não abrir, desligue a saída, entre, e ligue de novo.
- `python scripts\vpn-celular.py status` mostra o que falta (usa só leitura).

## Medido hoje [Certo, salvo marca]
- Tailscale 1.104.4 (Play Store) no celular e 1.104.2 no PC; a Tailscale do celular gastou **0,37 mAh em ~22 h** (batterystats), está isenta do Doze e no bucket "isento"; o Android isenta apps de VPN do bucket "restrito".
- `netcheck` do PC: UDP ok, NAT sem variação por destino, DERP mais próximo São Paulo (8,6 ms); IPv6 sem; sem portal cativo. Caminho PC–celular em casa: direto pela LAN.
- O app aceita 3 intenções (`am broadcast -n com.tailscale.ipn/.IPNReceiver -a ...`): `com.tailscale.ipn.CONNECT_VPN`, `...DISCONNECT_VPN` e `...USE_EXIT_NODE` com os extras `exitNode` (nome do PC na Tailscale; **vazio = sem saída**) e `allowLanAccess` (booleano) [Certo: commit 864cc35 do tailscale-android e o APK instalado]. Funcionam pelo ADB.
- Com "sempre ativada" ligada, um **desligamento deliberado NÃO é desfeito sozinho** (24 s sem religar); o "sempre ativada" cobre boot e queda do serviço. `CONNECT_VPN` religa em ~2 s.
- O app tem divisão de túnel por app (`addDisallowedApplication`, `split_tunneling` no APK) [Provável: o caminho de menu não foi aberto]: serve para tirar da VPN apps que reclamam dela.
- Na tela de VPN do Android há também **Sala do Futuro** e **Sala do Futuro Professor** (apps da SEDUC com serviço de VPN). O Android só mantém uma VPN por vez: usar a VPN deles derruba o Tailscale. [Provável: não testei.]
- Plano grátis da Tailscale (Personal): até 6 usuários, dispositivos ilimitados, saída de internet incluída [Certo: tailscale.com/pricing em 01/11].

## Medido em 02/11 com a saída de verdade [Certo]
- Pelo PC 1,47 MB/s e 43 ms; direto 1,71 MB/s e 10,6 ms (em casa, Wi-Fi fraco do aparelho).
- Com `allowLanAccess=true` o app NÃO usa a rota `0.0.0.0/0`: divide em ~132 rotas que deixam a rede local de fora, e a interface pode ser `tun1`. O `vpn-celular.py` soma as rotas (`rota_de_saida`): sem isso desfaria sozinho uma saída boa.
- O nome da saída é o da Tailscale (`rafaparise`, do `DNSName`), não o do Windows (`RafaParise`).
- Queda real (serviço Tailscale do PC parado): internet de volta em 33 s; PC de volta: saída religada em 62 s.
- DNS e anúncios: `ADGUARD-PC.md`.

## Não testado ainda
- A rede da escola (portal cativo + Tailscale + saída).
- Desligar o adaptador Wi-Fi do PC da economia de energia ("Permitir que o computador desligue este dispositivo": está ligado); o PC nunca suspende na tomada (suspensão e hibernação em CA = nunca), então o risco é pequeno; o `Set-NetAdapterPowerManagement` deste Windows não tem esse parâmetro (só pelo Gerenciador de Dispositivos).

Fontes: tailscale.com/kb/1103/exit-nodes · tailscale.com/pricing · developer.android.com/topic/performance/appstandby e /power/power-details · github.com/tailscale/tailscale/issues/8143 e tailscale-android commit 864cc35 · mullvad.net/blog/android-leaks-connectivity-check-traffic · forum.tailscale.com (Android + AlwaysOn).

## Hotspot do celular com a saída pelo PC (05/11)
- O Tailscale só deixa fora do túnel a rede do Wi-Fi em uso; a rede do hotspot cai no túnel. Conexão que chega do hotspot volta certo; conexão que um app do celular inicia para um aparelho do hotspot se perde.
- 05/11: o guarda `saida` passou a PAUSAR a saída com o hotspot ligado. **06/11 (na escola) isso virou o problema:** o Rafael ligou o hotspot, a saída pausou e o celular caiu no filtro da SEDUC; os alunos na VPN dele saíam livres [Provável: ícone do hotspot na foto das 07:33].
- **Desde 06/11 o padrão é MANTER:** com o hotspot ligado a saída pelo PC continua. `saida hotspot pausar` volta ao jeito de 05/11 (pausa e religa sozinho), `saida hotspot manter` desfaz, `saida hotspot status` mostra. Com a saída mantida, o que um app do celular INICIA para um aparelho do hotspot pode falhar; o ScreenStream e o `link` funcionam, porque quem conecta é o aparelho do hotspot.
- **O hotspot NÃO passa pela VPN** (o Android manda o tráfego dele direto pela rede em uso) [Provável: comportamento do Android, conferido com o que ele viu]. Por isso: hotspot com o Wi-Fi da escola = notebook com filtro; hotspot com os dados móveis = notebook livre (é a rede da operadora). Para o notebook sair pelo PC usando o Wi-Fi da escola: `link internet` (proxy do celular, abaixo).
- ScreenStream: Filtro de interface com VPN e Filtro de endereço com Público = abre também em `http://100.64.0.2:8080` (Tailscale, de qualquer lugar). KDE Connect: o celular tem o PC por IP (`100.64.0.1`).

## Notebook do hotspot sem o filtro da escola: `link internet` (06/11; feito sem o celular, falta provar na escola)
- O que é: um proxy (app do Termux) que escuta SÓ no endereço do hotspot (porta 3128), SÓ atende quem está no hotspot, SÓ abre sites públicos (recusa 10.x, 192.168.x, 172.16-31.x, 127.x, 169.254.x e a Tailscale 100.64/10) e SÓ nas portas web (CONNECT 443/8443, HTTP 80/8080). Como é um app do celular, a navegação do notebook sai pela VPN, pelo PC.
- No celular: hotspot ligado, notebook conectado nele, `link internet` (para sozinho em 120 min; `--minutos N`; `link parar`).
- No notebook (Windows): Configurações > Rede e Internet > Proxy > Configuração manual > Configurar: Ativado, endereço que o comando mostrar, porta 3128, Salvar. Ao terminar, DESATIVAR (fora do hotspot o notebook fica sem internet). Notebook da escola com o proxy travado pela TI: não funciona; aí só o hotspot com os dados.
- Limites: só passa o que usa o proxy do Windows (navegador sim; jogos e alguns apps não). A internet sem filtro depende da saída pelo PC ligada (`saida status`).
- Risco que o Rafael precisa pesar: quem estiver no hotspot e configurar o proxy também sai sem o filtro da SEDUC. Hotspot com senha só dele; não deixar aluno no hotspot com o proxy ligado.
