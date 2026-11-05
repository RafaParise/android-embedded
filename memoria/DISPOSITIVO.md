# Galaxy A12 — linha de base medida em 27/10/2026 (sem serial/IMEI)

| Item | Valor |
|---|---|
| Modelo / SO | SM-A125M · Android 12 (SDK 31) · One UI 4.1 (40100) · build A125MUBS6CXJ1 |
| Patch de segurança | 2024-10-01 (2 anos; provável fim de suporte [Palpite]) |
| SoC / kernel | MT6765 (Helio P35), PowerVR GE8320 (OpenGL ES 3.2 no `dumpsys SurfaceFlinger`, 29/10) · kernel 4.19.188 · userspace 64-bit (zygote64_32) · ABI arm64-v8a,armeabi-v7a,armeabi · sem AVF (`ro.virtualization.supported` vazio) · sem NFC (`pm list features`, 29/10) |
| Integridade | bootloader travado, verified boot green, Knox warranty 0, release-keys, sem root · 29/10: `ro.boot.flash.locked=1`, `vbmeta.device_state=locked`, `sys.oem_unlock_allowed=1` (Desbloqueio de OEM LIGADO), `ro.boot.bootloader=A125MUBS6CXJ1` |
| RAM | 3,84 GB; MemAvailable ≈ 1,19 GB; zRAM 4 GB (lz4) com ~2 GB em uso; ram_expand_size=4096, lista 2,4 |
| ActivityManager efetivo | max_cached_processes 34 · max_phantom_processes 32 (27/10; em 29/10 está em 2147483647, aplicado por `ajustes-script.py`) · use_freezer false (cached_apps_freezer=device_default) |
| /data | 51 GB, 6,1 GB livres (88%). App 14,1 · dados 19,7 · cache 7,1 · sistema 13,7 · outros 9,5 · fotos/vídeos < 1 GB · 29/10 ~15:55: 40 GB usados (79%), 11 GB livres; pastas do usuário: ARENA 6,5 GB (jogos 5,9), Android 2,0 GB (media 1,8), DCIM 0,5, Download 0,4 (a alta desde 28/10 04:10, quando eram 66% e 17,5 GB livres, não foi investigada) |
| Maiores caches | Chrome 1,4 GB · Mercado Livre 0,6 · Snaptube 0,6 · Instagram 0,6 · Galeria Samsung 0,5 · YouTube 0,4 · LarkPlayer 0,4 · app Google 0,4 |
| SD | 29/10 ~16:15: PORTÁTIL exFAT `1A2B-3C4D` (public:179,97), vazio, teste de gravação OK (64 MB, cache descartado); principal = INTERNA (ver "Armazenamento e cartão"). 28/10 ~18:32 a 29/10 ~16:15: ADOTADO e OCIOSO (private:179,98, UUID 00000000-0000-4000-8000-000000000001; corrompia gravação grande; apagado na formatação). 27/10 06:37: ADOTADO (UUID 00000000-0000-4000-8000-000000000002): 477 GB, 473 GB livres, depois revertido a PORTÁTIL exFAT (5E6F-7A8B); antes era "Cartao SDXC" exFAT (9C0D-1E2F, 419 GB usados, apagado); disk:179,96, flags ADOPTABLE\|SD; `sm has-adoptable` = false |
| Teclado | padrão Gboard; o da Samsung é com.samsung.android.honeyboard |
| Desativados na linha de base (27/10) | 16 pacotes (diagnostico/<data>/pacotes_desativados.txt); o estado de hoje (60 desativados, 105 removidos do usuário 0, FM Samsung ativo, Tailscale, ponte-pc) está em `ESTADO.md`, seção "Aparelho hoje" |
| Bateria | 18% (01:09) → 4% (04:55) ligada ao PC, ~3,7 pontos/h; Max charging current 0 → a porta USB não carrega: usar carregador de parede |

RAM por processo (RSS na sonda): Instagram 321 MB · system 218 · gms 186 · systemui 163 · YouTube 160 · app Google (3 processos) ≈ 325 ·
Teams 147 · launcher 131 · Samsung Cloud 84 · Conta Samsung 77 · Theme Store 55 · Facebook Services 40 · sdhms 40.

Reproduzir: `python scripts/sonda-a12.py` (somente leitura, ~1 min, grava em diagnostico/).

## Depois das fases F1/F2 (27/10, medido)
| Item | Valor |
|---|---|
| /data | 74% usado, 13,4 GB livres (era 88% e 6,1 GB) depois de `pm trim-caches 999G`. O "App Cache" do `dumpsys diskstats` fica velho (6,6 GB) por horas: confiar no `df` |
| Desativados por mim (12) | A1: facebook.appmanager/services/system, omcagent, rubin.app, kidsinstaller, mapsagent, sec.spp.push, app.updatecenter · A1b: com.dti.samsung · A2: game.gametools, game.gos |
| Já vinham desativados (16, não por mim) | br.com.conectcar, br.gov.caixa.tem, br.gov.sp.detran.consultas, br.gov.sp.prodesp.pptdigital, google.apps.restore, google.apps.tachyon (Meet), google.projection.gearhead (Android Auto), opera.max.oem, samsung clipboardedge, cmfa.framework, cmfa.AuthTouch, game.gamehome, samsung.android.messaging, emergencylauncher, sec.usermanual, steam.community |
| Memória | RAM Plus = zram0 de 4 GiB: 1,43 GB trocados usando ~346 MB de RAM; swappiness 160; 11 processos em cache (limite 34); `use_freezer=false` |
| Abertura a frio (ms, mediana de 3), referência ~06:51 | ARENA 740 · Chrome 3778 · Configurações 1027 · Gov.br 1144; MemAvailable 1020 MB |
| Apps do Rafael (teste de fumaça) | ARENA io.github.rafaparise.arena · Gov.br br.gov.meugovbr · SED br.gov.sp.educacao.sed.android · Sala do Futuro (professores) · Termux · teclado Gboard |

## Armazenamento e cartão (27/10 medido; 28/10 corrigido)
- **Estado atual (28/10, após as 22:00):** principal = memória INTERNA (`sm get-primary-storage-uuid` = null), restaurada do backup e conferida por md5 (fora de `Android/`): a quente, logo após o envio (22:09), 5.006 de 5.006 iguais; a frio (29/10 01:37, depois do `teste-gravacao.py` na interna), 4.901 iguais, 0 corrompidos e 105 ausentes, todos dentro de `.thumbnails` (miniaturas que o Android poda sozinho: Pictures 95, Movies 10) [Certo];
  `Android/media`: 9.926 de 9.926 iguais ao tar (29/10 01:12). `Android/data` (sem backup): validado só por amostra (137 arquivos baixados; 18 verificáveis, 14 corrompidos, 13 apagados por serem cache); o app 99 (`com.taxis99`, 1.455 arquivos) e 109 arquivos de outros formatos não foram validados (se um app estranhar: Limpar dados). Cartão ADOTADO e OCIOSO (`private:179,98`, UUID 00000000-0000-4000-8000-000000000001): 0 apps, nada gravado.
  Não mover nada entre volumes. Voltar a PORTÁTIL exFAT (o que funcionava) apaga o cartão: só com o "sim" do Rafael; depois, `python scripts\teste-gravacao.py --alvo /storage/<UUID do cartão>`.
  Dashcam e NewPipe dependiam do cartão portátil (backup do Dashcam no PC em `Backups\A12-20261028\sd-Dashcam`, 18 arquivos; `sd-NewPipe` está VAZIO: não sei se a pasta do cartão estava vazia ou se a cópia falhou, então downloads do NewPipe que estivessem no cartão podem ter sido apagados na adoção das 18:32).
- **Regra:** nunca `pm move-package` nem `pm move-primary-storage`. Operação em massa no armazenamento: backup no PC antes e md5 DEPOIS, com o cache descartado entre gravar e conferir (`scripts/teste-gravacao.py` faz isso).
  "Success", `du` e contagem de arquivos não provam integridade.
- 27/10 (medido): cartão SD de 512 GB adotado como privado (`private:179,98`, f2fs sobre dm-crypt em /mnt/expand/<uuid>): escrita sequencial 55 MB/s contra 64 MB/s da interna (dd 128 MB com fsync; mede velocidade, não integridade).
  O volume emulado `emulated:179,98;0` fica `unmounted` (só monta sozinho se for o armazenamento principal); montado à mão por `sm mount` não aparece no seletor de arquivos.
- `pm move-package` derrubou o system_server em 27/10 18:43 (ver DECISOES). O PackageManager só enxerga apps do cartão depois do vold montar o volume. Ainda em 27/10 o cartão voltou a PORTÁTIL exFAT (`/storage/5E6F-7A8B`), com todos os apps na INTERNA.
- 28/10 [Certo]: ~18:32 o cartão apareceu ADOTADO de novo, com UUID novo; quem adotou não foi provado. a pedido do Rafael ("cartão unificado e não portátil", ~21:00), o Claude rodou, de 21:21:23 a 21:31:19 (9 min 55 s),
  `pm move-primary-storage` para o cartão: "Success", com `du` e contagem de arquivos iguais. O md5 contra o backup do PC mostrou 1.412 de 5.006 arquivos corrompidos (fora de `Android/`:
  ARENA, DCIM, Pictures...): os primeiros 32 KB (às vezes 128 KB) batem e o resto difere. `Android/media` também foi atingido (6.374 de 9.926 arquivos divergentes ou ausentes na conferência das 22:11).
- Prova [Certo]: gravar 64 MB aleatórios, ler vários GB de /system para expulsar o cache e reconferir o md5. O volume do cartão adotado devolve arquivo DIFERENTE; a interna (controle), IGUAL. Conferir logo depois de gravar engana
  (o dado sai do cache de páginas): foi assim que o Claude afirmou por engano que "escrever no cartão funcionava".
- Causa [Palpite]: cartão com defeito (capacidade falsa ou flash ruim) OU limitação do armazenamento adotado da Samsung neste aparelho; nenhum teste separou as duas.
  [Provável] a Samsung não suporta oficialmente o armazenamento adotado (fóruns; fonte oficial não verificada).
- Desfeito [Certo], 28/10 21:54 a 22:09: cópias corrompidas apagadas do cartão; `pm move-primary-storage internal` (para desfazer) terminou com "Success" (5 min 50 s); 4.939 arquivos restaurados do backup por `adb push`.
- Versões: Termux 0.118.3 (targetSdk 28), HeliBoard 4.2, VLC 3.7.2, Seal 1.13.1 + yt-dlp 2026.10.26, Fossify Relógio 10 (aceita o intent SET_ALARM).

## Depois da revisão final (28/10, medido com `scripts/medir.py`)
| Item | Valor |
|---|---|
| /data | 66% usado, 17,5 GB livres (F2FS com `background_gc` e `discard`); início do projeto 88% e 6,1 GB |
| Pacotes | 262 ativos; 155 desativados em 22 lotes (eram 16 no início) |
| Cartão | na revisão final (madrugada de 28/10): portátil exFAT `/storage/5E6F-7A8B`, 477 GB livres; nenhum app nele. Às ~18:32 apareceu ADOTADO de novo: estado atual em "Armazenamento e cartão" |
| Abertura a frio (ms, mediana de 3) | ARENA 733 · Configurações 861 · Gov.br 834 · SED 417 · Fennec 868 · Termux 408 · WhatsApp B. 695 · Telefone Fossify 760 · Contatos Fossify 671 · Relógio Fossify 683 · Mensagens Fossify 839 · Organic Maps 458 |
| Memória | MemAvailable 2182 MB logo após matar processos em cache (1562 MB com mais apps vivos); swap 1039 MB (aparelho ligado há 8h50) |
| CPU em repouso | calmo: 13% de 800% (1,6% do total), nenhum processo acima de 0,0%; o medidor pegou 27,4% por um pico de 198% do WhatsApp Business logo após reiniciar |
| Pressão (PSI, média 60 s) | cpu 1,0% · memória 0,26% · disco 0,16% (calmo) |
| Rolagem das Configurações | 254 quadros, 0,39% lentos, p90 19 ms, p99 21 ms |
| Compilação | ARENA, Fossify Telefone, Mensagens, Contatos, Galeria, Relógio, Open Camera e HeliBoard em `speed`; demais apps livres em `speed-profile`; TRIM e `sm idle-maint run` feitos |
Arquivos: `diagnostico/20261027-230938/medicao-agora.json` e `diagnostico/20261028-041321/medicao-depois.json` (comparar: `python scripts\medir.py --comparar A.json B.json`).
