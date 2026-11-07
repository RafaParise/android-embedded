# Radar de desempenho do A12: o que se investigou em 01/11/2026 e o que sobrou

**03/11/2026, carga 21 não é sobrecarga:** o `uptime` marca carga de 21 mesmo sem o indexador, com CPU baixa no `top` e 20 processos em estado D (espera) [Certo: `ps -A -o S`, 20:08]. O valor conta quem espera, não quem usa CPU [Provável]: não usar esse número como prova de lentidão; olhar `saude.py`.

Pedido do Rafael: investigar a fundo o que ainda dá para fazer no celular, sem repetir o que já foi feito, sem deixar ferramenta ou técnica nova para trás.
Método: leitura do aparelho (dumpsys, /proc, logcat; nada alterado), servidor FOTA da Samsung, API do F-Droid e buscas na web.
Painel que nasceu disso: `python scripts\saude.py` (só leitura; `--online` confere firmware e apps).

## Veredito
O A12 está perto do teto prático **sem root** (root está fora, decisão de 29/10). Medido hoje, em repouso e carregando: RAM disponível 1,9 GB de 3,75 GB, pressão de memória baixa (PSI 60 s: espera 1–2 %, trava 0,5–1,4 %), térmica "leve", bateria com ~5,0 Ah estimados (100 % do projeto de 5000 mAh), Wi-Fi a −47/−51 dBm.
O que mais pesou no dia **não foi ajuste de sistema**: foi uma instalação do OmniRoute dentro do Termux (abaixo).

## 1. Achado: OmniRoute instalado dentro do Termux (pedido do Rafael ao Qwen do celular)
- 10:48 (hora local; o log do Qwen guarda em UTC): o Rafael digitou no celular "por favor automatize tudo e faça tudo por favor". O Qwen escreveu `instalar_completo_final.sh` (178 linhas, em `/storage/1A2B-3C4D/Projetos/qwen-celular/kit-ia-professor/scripts/`, 10:56) e o rodou. O script apaga `~/scripts/*`, `~/.omniroute`, `~/.hermes`, `~/.claude-mem` e o crontab; faz `pkg update -y` (o Node foi de 26.12.1 para 26.13.0 [Certo: `node -v`]); reinstala o Qwen Code; `npm install -g omniroute`; mexe no `.bashrc`; sobe um OmniRoute local com `OMNIROUTE_MEMORY_MB=1536`; abre o navegador para criar 4 chaves de cliente e grava `~/.omniroute/clientes.env`; registra cron (`@reboot` e diário às 12 h rodando `atualizar_combos.py`).
- Custo medido [Certo]: dois `npm install omniroute` somaram 749 + 414 MB de PSS; MemAvailable caiu a 692 MB; o gerenciador da Samsung (Chimera) matou apps em cache em rajada (36 mortes na hora, o Open Camera inclusive, 10:54:53). Disco: `omniroute` global chegou a 1.021 MB e o cache do npm está em 942 MB. Às 11:26 o npm já havia desfeito a instalação parcial (68 MB) e a RAM voltou a 1,95 GB; o cache de 942 MB ficou.
- Por que não ajuda o desempenho: (a) o OmniRoute do PC já atende o celular pela Tailscale (`ia`); no PC ele usa 527 MB de RAM [Certo: processo node, 01/11], no celular mediu 375 a 390 MB de PSS [Certo: 01/11 à tarde], 10 % da RAM, e por isso só liga sob demanda; (b) sem chave de provedor no celular (regra do projeto) o OmniRoute local não tem para onde rotear; (c) a porta 20128 já é do `socat` que liga ao PC; (d) `@reboot` do cron não roda: o Termux não inicia no boot (não há Termux:Boot); (e) guarda chaves de cliente no celular, que a regra só libera com o "sim" do dia.
- Não interferi: foi pedido dele. **Decisão dele (01/11, depois desta investigação): manter o OmniRoute no celular** ("para eu sempre ter uma IA capaz"). Feito como RESERVA sob demanda, instalada e medida pelo Claude do PC: `OMNIROUTE-CELULAR.md` (1.297 MB, cache do npm 947 → 7 MB, ~375 a 390 MB de RAM só enquanto o `ia` está aberto sem o PC, ~1 min para subir, só em 127.0.0.1:20129). Ela só liga com o arquivo `~/.omniroute/pronto`, que depende de chave de provedor no celular; **ativada em 01/11 ~17:20** com 3 chaves autorizadas pelo Rafael (ver `OMNIROUTE-CELULAR.md`), o arquivo existe. A causa do laço do Qwen NÃO foi falta de compilador: foi o limite de 300 s do shell dele mais o `postinstall` compilando o `better-sqlite3` (600 s); o Qwen foi alinhado (`QWEN-CELULAR.md`).
- Parte da queda de espaço livre (17,7 GB na noite anterior para 11,8 GB) vem daqui: o Termux subiu de 1,56 GB (diskstats, que é cache de até 24 h) para 4,0 GB (usr 1,5 + home 2,5; `du`). O resto não foi achado [Provável: atualizações do Play e do F-Droid]. O `saude.py` guarda o espaço a cada leitura (`diagnostico/saude-historico.jsonl`) e avisa quando cair 2 GB ou mais entre duas leituras.

## 2. Esgotado, com prova de hoje (não repetir)
| Item | Resultado | Fonte |
|---|---|---|
| Firmware | `A125MUBS6CXJ1` é a **última** que a Samsung publica para SM-A125M/ZTO | [Certo] `fota-cloud-dn.ospserver.net/firmware/ZTO/SM-A125M/version.xml` (responde 403 sem User-Agent `Kies2.0`) |
| Fim do suporte | sem fonte oficial; SamMobile e fórum da Samsung apontam 2025; patch instalado 2024-10-01 | [Provável] buscas de 01/11 |
| Mainline / Play | módulos 2026-10-01, WebView 156.0.8078.47, Play Services 26.42.31, Play Store 53.8.11, 27 apex; `com.google.android.art` não está instalado (o ART vem no firmware) | [Certo] `dumpsys package` |
| Apps FOSS | 19 apps no F-Droid, todos na versão sugerida (VLC e Seal só mudam o código da ABI) | [Certo] API do F-Droid |
| Compactação de apps | `use_compaction=true`, `compact_action_1=file`, `compact_action_2=all`, 344 compactações; `/proc/<pid>/reclaim` existe | [Certo] `dumpsys activity settings` |
| Freezer de apps em cache | **não suportado**: `use_freezer=false` mesmo com `cached_apps_freezer=enabled` e `device_config activity_manager/use_freezer=true` (essa flag nem está no namespace certo, `activity_manager_native_boot`); só existe `/sys/fs/cgroup/uid_0` | [Certo] o valor; [Provável] a causa (cgroup v2 por app ausente no kernel 4.19.188) |
| GOS (Game Optimizing Service) | já desativado | [Certo] `pm list packages -d` |
| RAM Plus | zram de 4 GiB (lz4), taxa de compressão 4,4:1 a 6,8:1; manter | [Certo] `mm_stat` |
| Bateria | carga de 1185 mAh a 23 % e 5023 mAh estimados a 22 %: ~100 % do projeto; saúde "boa" | [Provável] estimativa pelo contador de carga |
| Térmica | `Thermal Status` 1; AP 45–47 °C, bateria 33 °C (carregando, tela ligada, Qwen ativo) | [Certo] `dumpsys thermalservice` |
| Rede | Wi-Fi só 2,4 GHz (A12 não tem 5 GHz), 802.11n, 78 Mbps a −47 dBm. **Corrigido em 04/11: o modo de alto desempenho GANHA, e é o que `tela-apagada.py` deixa ligado** (seção "Wi-Fi 2,4 GHz, medido em 04/11" de `TELA-APAGADA.md`) | [Certo] medida |
| Tela | 720×1600, 300 dpi, único modo 60 Hz; animações 0; `show_touches` 1 (do script) | [Certo] `dumpsys display` |
| TRIM e idle-maint | feitos em 27 e 28/10 (CHECKLIST-SCRIPT) | registro do projeto |
| Apps em segundo plano (01/11 ~19:30) | 78 apps de terceiros: ativo 7, conjunto 15, frequente 2, isento 8, raro 36, restrito 6, nunca 4. Desde a última carga (~22 h, 1.065 mAh): Termux em uso 131 mAh (tela 102 + CPU 30), sistema ~28, Play Store 8,4 (6,5 de wakelock), todo o resto abaixo de 1 mAh por app; nenhum app de terceiros entre os que mais acordam por alarme (só `android`, `networkstack`, `imsservice`). O Android 12 manda para "restrito" após 45 dias sem uso (Android 13: 8 dias); buckets "raro" e "restrito" cortam a rede em segundo plano e limitam alarmes e jobs | [Certo] `dumpsys batterystats`, `alarm`, `am get-standby-bucket`; [Certo] developer.android.com/topic/performance/appstandby e /power/power-details |
| Isenção do Doze para o SED e o Authenticator | estavam em "raro"; viraram "isento" (`dumpsys deviceidle whitelist +pkg`); os demais apps de notificação já estavam em "conjunto" ou "isento" | [Certo] `am get-standby-bucket` antes e depois |
| "Proteger bateria" (limite de 85%) | NÃO suportado: `SEC_FEATURE_BATTERY_LIFE_EXTENDER: false`; `protect_battery=0` existe e não faz nada | [Certo] `dumpsys battery` |
| Custo da VPN sempre ativada | Tailscale 0,37 mAh em ~22 h; app isento do Doze e do bucket "restrito" (apps de VPN são isentos) | [Certo] `dumpsys batterystats`, `deviceidle`, doc de standby |

## 3. Avaliado e rejeitado, ou que depende do Rafael
- **Root, Magisk, bootloader**: decidido não fazer. Sem root não se troca o compressor do zram, o escalonador de E/S nem o LMK.
- **Shizuku, Hail, Brevent, wireless ADB no Termux**: exigem Opções do desenvolvedor ligadas, o que briga com o F8; o ganho já está coberto por appops, standby e Doze.
- **Desativar `com.samsung.android.privacydashboard`** (34 MB residentes): UAD marca "Advanced" (tela de Privacidade das Configurações); não compensa.
- **`com.google.android.apps.turbo`**: já avaliado, quebra as configurações de bateria (AUDITORIA-SCRIPT).
- **Ferramentas conhecidas e dispensadas** [Provável: conhecimento geral, não testei cada uma]: Canta e Shizuku (pedem ADB/Opções do desenvolvedor ligados; o `lote-pacotes.py` já faz o mesmo com simulação e desfazer), SD Maid SE (o `pm trim-caches 100G` e a limpeza de 31/10 cobrem; as funções fortes pedem root ou Shizuku), Obtainium (repete o F-Droid, que já confere 19 apps), Aurora Store (cliente alternativo do Play, sem ganho), Brevent e Hail (appops `RUN_IN_BACKGROUND`, standby e Doze do `ajustes-script.py` já fazem o mesmo sem serviço residente), Tasker, MacroDroid e Modos e rotinas da Samsung (este foi removido; o `modos.py` faz por ADB o que se precisa).
- **Reduzir resolução (`wm size`), `debug.hwui.renderer` (Vulkan), desligar sobreposições de hardware**: sem ganho útil no GE8320 ou piora a bateria.
- **Atraso de toque** (`long_press_timeout` 500 → 300 ms): conforto, não desempenho; mexe no feeling do teclado, não apliquei. Desfazer: `settings put secure long_press_timeout 500`.
- **Recompilar `speed` os 8 apps** (Fossify ×5, Open Camera, HeliBoard, ARENA): as atualizações do F-Droid voltaram os 7 primeiros para `speed-profile` (só o ARENA segue em `speed`). Ganho marginal; só vale com 12 GB livres ou mais (hoje 11,8).
- **Tela sempre ligada no cabo**: `stay_on_while_plugged_in` = 7 e `screen_off_timeout` = 1.800.000 (30 min). Esquenta e gasta o painel; é a opção "Permanecer ativo" do desenvolvedor. Ao deixar o celular parado no cabo: `settings put global stay_on_while_plugged_in 0`.
- **App pair do dashcam** (Mapas + Open Camera em um toque): precisa da tela. One UI 4.1: Painel lateral → Apps → Editar → "Criar par de apps" (rótulos podem variar) [Provável: página de suporte da Samsung; a mesma fonte diz que versões novas mudaram o caminho]. Fica para quando o celular estiver livre.
- **Teste térmico do dashcam** (20 min de gravação com tela dividida, `saude.py` a cada 5 min): fica para quando o celular estiver livre.

## 4. Como ler o painel `saude.py`
OK / ATENCAO / ALERTA por linha; saída 0 sem alerta, 1 com alerta, 2 sem aparelho. Só o `Thermal Status` e o estado da bateria vêm do Android; **os demais limites são palpites** razoáveis para 3,8 GB de RAM (constantes `LIM_*` no topo do script):
| Linha | Atenção | Alerta |
|---|---|---|
| Bateria | capacidade estimada < 80 % do projeto ou ≥ 40 °C ou saúde ≠ boa | < 60 % ou ≥ 45 °C |
| Térmica | status 2 (moderada) | status ≥ 3 |
| RAM | disponível < 500 MB, swap > 85 % | disponível < 300 MB |
| Pressão (PSI 60 s) | memória "trava" ≥ 2 %, espera ≥ 15 %, CPU ≥ 40 %, disco "trava" ≥ 10 % | memória "trava" ≥ 10 % |
| Processos | algum com PSS ≥ 450 MB | PSS ≥ 700 MB |
| Espaço | livre < 15 % ou queda ≥ 2 GB desde a leitura anterior | livre < 10 % |
| Mortes (1 h) | serviço/último app morto por memória, ou ≥ 30 mortes por memória | app visível ou audível morto por memória |
| Wi-Fi | sinal < −75 dBm | — |
Só contam como falta de memória os motivos Chimera, ML_Kill e lmkd. "isolated not needed", "stop <pacote>" e "empty" são faxina normal: o app Vivo criou e recolheu um processo isolado por minuto (31 mortes entre 10:21 e 10:50 de hoje, adj 0, ou seja, com o app aberto [Provável]) e isso **não** é falta de RAM.

## 5. Varredura dos projetos de Android modificado (06/11/2026 ~22:45)
Pedido do Rafael: revisar hardware e software a fundo e trazer o melhor dos projetos de Android modificado.
**Premissa:** quase tudo o que esses projetos ganham vem de root ou de bootloader desbloqueado (decidido NÃO fazer; desbloquear apaga o aparelho). Abaixo, o que se transfere por ADB, medido no A12.

**Hardware lido hoje** [Certo: sonda só de leitura, 22:27]:
- SoC MT6765V/CB (8 núcleos) e GPU PowerVR GE8320 (GLES 3.2).
- zram de 4 GiB em lz4. O kernel também oferece zstd, mas trocar exige root.
- Governador, frequência, vida útil do eMMC e swappiness não são legíveis sem root ("Permission denied").
- Disco: escrita de 512 B em 1 ms; escrita recente de 13,5 MB/s; 14,0 GB livres (27%).
- Térmica 0; PSI 0%; RAM disponível de 1,37 GB, com o Organic Maps aberto (625 MB).
- **Bateria: a Samsung estima a saúde em 86%** (`mSavedBatteryAsoc` do `dumpsys battery`) [Provável: campo próprio da Samsung, sem documentação pública]. A conta do charge counter dá cerca de 100% porque o medidor escala esse contador. Desde 06/11 o `saude.py` mostra os dois e usa os limites 80/60 também no ASOC.
- Proteção contra inchaço e limite de carga: não suportados (`SEC_FEATURE_PREVENT_SWELLING: false`, `SEC_FEATURE_BATTERY_LIFE_EXTENDER: false`).

| Técnica (projeto de origem) | Neste A12 | Prova |
|---|---|---|
| ROM própria, GSI, kernel, governador, escalonador de E/S, LMK, swappiness, zram zstd (LineageOS, crDroid, FDE.AI, YAKT, Uperf, LKT) | fora: root/bootloader | decisão de 29/10 e 04/11 |
| Debloat (UAD-ng, Canta, listas Samsung) | feito | `lote-pacotes.py`, `cruzar-uad.py` |
| Restringir segundo plano (Brevent, Hail, Greenify, smart-restrict do Aatricks) | feito | appops, buckets, Doze em `ajustes-script.py` |
| Limite de processos fantasma (comunidade do Termux) | feito | `max_phantom_processes` |
| **Doze mais cedo (Naptime, ForceDoze, Aatricks "experimental")** | **APLICADO 06/11** | `device_config device_idle` com `inactive_to` e `idle_after_inactive_to` de 30 min para 10 min; conferido no `dumpsys deviceidle`; a auditoria confere e o `ajustes-script.py` reaplica. Quem está na lista do Doze (Termux, Tailscale, SED, Relógio, Agenda, Open Camera, Organic Maps) não muda. Desfazer: `device_config delete device_idle inactive_to` e `... idle_after_inactive_to` |
| Compilar tudo em `speed` (módulos Dex2OAT) | **MEDIDO PIOR, desfeito** | abertura a frio de 3 a 4 medidas por app; `speed-profile` → `speed` → `speed-profile`. Mensagens 521 → 597 → 518 ms; Contatos 579 → 671 → 566; Firefox 725 → 1.133 → 737; Arquivos 768 → 879 → 766. Código AOT maior pesa no eMMC. O ARENA ficou igual nos dois modos (cerca de 720 ms) e segue em `speed` |
| GMS fora da lista do Doze (Universal GMS Doze) | possível sem root, **não aplicado** | `dumpsys deviceidle sys-whitelist -com.google.android.gms` (volta com `+` ou `reset`). O próprio projeto ensina a consertar "mensagens que chegam atrasadas" e o FCM das notificações passa pelo GMS: risco ao WhatsApp e ao SED. Só se o Rafael pedir |
| Modo de desempenho fixo (`cmd power set-fixed-performance-mode-enabled`) | rejeitado | trava o clock alto; esquenta, e o SDHMS fecha app visível no calor |
| Buffers de log menores ou desligados (ROMs) | rejeitado | ganho de cerca de 7 MB (main 5 MiB, system 2 MiB); o `saude.py` lê as mortes (`am_kill`) do buffer de eventos |
| Hibernação de apps sem uso (Android 12) | já ligada pelo sistema | `app_hibernation_enabled=true` |
| Tela sempre ligada, levantar para acordar, gesto de pegar | já desligados | `aod_mode`, `lift_to_wake` e `motion_pick_up` = 0 |
| Processamento aprimorado da Samsung | já ligado | `sem_enhanced_cpu_responsiveness=1` |
| `device_idle_constants` em `settings global` (scripts antigos) | inerte no Android 12 | o `dumpsys` mostra outros valores. Fica como está: não é do projeto e não faz nada |

Fontes:
- [Provável] github.com/gloeyisk/universal-gms-doze, README;
- [Provável] github.com/Aatricks/android-battery-optimization, README (perfis safe, experimental e Samsung);
- [Palpite] para FDE.AI, YAKT e Dex2OAT: só changelogs e READMEs, sem ler o código dos módulos.
