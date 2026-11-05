# Auditoria do script "Otimização Samsung A12.txt" (digerido em 27/10/2026)

O arquivo repete 9 versões do mesmo roteiro (v1 → Master → disable-user → SOP → v3.0 → v4.0 → Termux → Dashcam).
Rótulos: [Certo] fonte primária · [Provável] ≥ 2 fontes secundárias ou medido no aparelho · [Palpite] sem fonte boa · [Falso] a fonte contradiz.
"Aparelho" = medido por ADB em 27/10. "UAD" = lista UAD-ng (5.382 pacotes), baixada em 27/10. "Verificação" = workflow de 27/10 com fontes na web.

## A. Pacotes (de 52 nomes com 3+ partes extraídos do texto, 14 não existem no aparelho)
- NÃO existem neste A12 (o script os ignoraria): google.apps.photos, google.apps.wellbeing, samsung.android.app.spage, ardrawing, arzone,
  bixby.agent, bixby.visionui, ipsgeofence, sec.android.app.music, sec.android.app.sbrowser, sec.android.inputmethod (o teclado Samsung é
  com.samsung.android.honeyboard), wsmac.openapi, e os apps opencamera e ppsspp (não instalados). [Certo — aparelho]
- PERIGOSOS, não desativar [UAD + aparelho]:
  - com.osp.app.signin (Conta Samsung): "Configurações quebram no OneUI 3+".
  - com.sec.android.gallery3d: "dependência da câmera".
  - com.sec.android.app.myfiles: perde formatar/desmontar o SD nas Configurações.
  - com.android.bips: UAD "Expert", trava Configurações e deixa lento.
  - com.google.android.inputmethod.latin é o teclado em uso; com.samsung.android.honeyboard exige outro teclado com direct-boot.
  - com.samsung.android.fmm (achar celular) e com.google.android.apps.turbo ("quebra configurações de bateria").
- Sem ganho: wssyncmldm e soagent (OTA; patch 2024-10, provável fim de suporte [Palpite]) e samsungapps (UAD "Expert").
- Seguros (UAD "Recommended", presentes e ativos) estão no lote A do PLANO.md. UAD lista 121 "Recommended" instalados e ativos; muitos são apps
  do próprio Rafael (Instagram, YouTube, Office, Gmail…): decisão dele.
- Decisão do Rafael (perde função): googlequicksearchbox (≈ 325 MB de RAM em 3 processos; perde Assistente, widget e ditado do Google),
  mobileservice, forest, themestore, google.apps.maps. Já desativados hoje: 16 (inclui gamehome).

## B. Configurações (settings)
- Já no valor do script (não mudam nada): animações 0.0 · show_touches 1 · wifi/ble_scan_always_enabled 0 · mobile_data_always_on 0 ·
  assisted_gps_enabled 1 · low_power 0. [aparelho]
- Chaves que nem existem: upload_apk_enable, wifi_suspend_optimizations_enabled, activity_manager_constants (null). [aparelho]
- sem_enhanced_cpu_responsiveness existe (valor 0): único ajuste Samsung real; efeito não documentado [Palpite]; testar e medir.
- location_background_throttle_interval_ms hoje 600000 (script quer 3600000): ganho mínimo [Palpite]. Antes de qualquer mudança: `settings list global > backup`.
- DNS privado: o hostname certo é dns.adguard-dns.com (dns.adguard.com é antigo) [Provável]. Em rede de escola o modo estrito pode derrubar a
  internet ou o portal cativo: deixar "Automático" até testar lá [Provável]. Hoje: opportunistic.

## C. Memória (RAM Plus, processos em cache, freezer)
- max_cached_processes=4 via `settings ... activity_manager_constants`: [Falso] no Android 12 (vem do device_config; efetivo hoje 34). Se testar:
  `device_config put activity_manager max_cached_processes 16` (nunca 4); reverter com `device_config delete activity_manager max_cached_processes`.
- Desligar o RAM Plus (zRAM 4 GB lz4, ~2 GB em uso): [Palpite] que ajude; com 3,8 GB de RAM pode piorar. Medir antes e depois (A/B).
- Freezer: o caminho certo é `settings put global cached_apps_freezer enabled` + reiniciar, não `device_config use_freezer`. Pode não ter efeito se o
  kernel 4.19 não expõe cgroup freezer. Verificar com `dumpsys activity settings | grep use_freezer`. [Provável]

## D. Armazenamento
- O maior gargalo é /data a 88%: cache = 6,8 GB → `pm trim-caches` é o ganho imediato. [aparelho + skill kit-turbo:android-a12]
- `compile -m speed -f` e `bg-dexopt-job` com 88% cheio: custo de espaço e ganho pequeno em emuladores nativos [Palpite]; só com ≥ 12 GB livres
  e só nos apps-alvo.
- SD como interno: criptografa e prende o cartão ao celular; o PC deixa de ler; se o cartão falhar, os apps nele se perdem [Provável — AOSP, não reaberto].
  Adotar NÃO libera /data por si só: só o que for movido, e a maioria dos apps não deixa [Provável].
- `sm set-force-adoptable true` não foi necessário: o disco já vem com a flag ADOPTABLE (apesar de `sm has-adoptable` = false).

## E. AppOps e standby
- `am set-standby-bucket <pkg> 30` é FREQUENT, não "restrito" (RESTRICTED = 45) [Provável]. `appops RUN_IN_BACKGROUND ignore` só em apps sem
  notificação importante; nunca banco, Gov.br ou SEDUC; anotar `cmd appops get` antes e reverter com `... default`.

## F. "Kill switch" Gov.br (development_settings_enabled 0)
- Gov.br bloquear com opções do desenvolvedor ligadas: [Palpite] (nenhuma fonte oficial). Bancos: [Provável] (BMG confirma; Caixa Tem relatado).
- development_settings_enabled e adb_enabled são chaves independentes [Provável]: desligar uma não derruba a outra. Qualquer app instalado
  lê as duas [Certo — AOSP Settings.java].
- "Indetectável para Play Integrity/SafetyNet": [Palpite] e enganoso. A doc do Play Integrity não cita opções do desenvolvedor; o SafetyNet
  foi descontinuado (desligado em jan/2025). Fontes: developer.android.com/google/play/integrity/verdicts ·
  developer.android.com/privacy-and-security/safetynet/deprecation-timeline
- Jeito certo: ao terminar, desligar as Opções do desenvolvedor pela interface e testar cada app (Gov.br, banco, SEDUC).

## G. Tela dividida (dashcam)
- force_resizable_activities / enable_freeform_support: provavelmente desnecessários [Provável]; testar antes a tela dividida pelos Recentes, sem
  alterar nada. Open Camera e Organic Maps ainda não estão instalados. PLAY_AUDIO e PICTURE_IN_PICTURE via appops: sem efeito conhecido [Palpite].

## H. Termux / IA no celular
- `npm i -g @anthropic-ai/claude-code` no Termux: [Falso] desde a 2.1.113 (binário glibc; process.platform=android). Alternativas: proot-distro
  Ubuntu, ou fixar 2.1.112 com DISABLE_AUTOUPDATER=1 (versão antiga). Fontes: code.claude.com/docs/en/setup ·
  github.com/anthropics/claude-code/issues/50270 (lido num espelho).
- Melhor: o celular como terminal SSH do PC via Tailscale (já instalado); o Claude Code roda no PC. [Palpite razoável]
- Phantom Process Killer do Android 12 (limite 32, efetivo hoje) mata o Termux em segundo plano: `device_config set_sync_disabled_for_tests persistent`
  + `device_config put activity_manager max_phantom_processes 2147483647`, reiniciar, conferir; voltar o sync para `none` antes de atualizar o sistema.
  [Provável] Fonte: github.com/agnostic-apollo/Android-Docs (phantom-cached-and-empty-processes.md).
- `adb shell input text` no Termux é frágil (espaço = %s; & $ e aspas) [Palpite]; usar `adb push` de um .sh ou o sshd do Termux (porta 8022).
- NÃO copiar ~/.claude.json nem credenciais para /sdcard/Download (outros apps e MTP leem). Login direto no Termux ou SSH ao PC.
  A conta Claude em uso pode ser emprestada.

## I. Processo
- As 9 versões repetem os mesmos comandos e cerca de 40% das configurações já estavam aplicadas: ler o estado antes (sonda) evita executar e narrar o que não muda nada.
