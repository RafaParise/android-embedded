#!/usr/bin/env python3
"""Checklist do script original (Otimizacao Samsung A12.txt), item por item, lendo o estado REAL do aparelho pelo ADB.
Somente leitura. Cada item recebe um veredito:
  FEITO      o aparelho esta como o script manda (ou equivalente que cumpre o mesmo objetivo)
  DESVIO     decisao consciente de nao seguir o script, com o motivo
  RECUSADO   o script manda, mas e perigoso, falso ou fere regra do projeto; nada foi feito
  N.A.       o pacote ou a chave nao existe neste aparelho
  PENDENTE   falta aplicar ou depende do Rafael
Grava memoria/CHECKLIST-SCRIPT.md (sem dados pessoais) e imprime o resumo.

  python scripts/checklist-script.py            confere e grava o relatorio
  python scripts/checklist-script.py --so-pendentes
"""
import argparse
import datetime
import pathlib
import re
import subprocess
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ARENA = "io.github.rafaparise.arena"


def sh(cmd, timeout=60):
    r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    return (r.stdout + r.stderr).replace("\r", "").strip()


def lista(flag):
    return {l.split(":", 1)[1].strip() for l in sh(f"pm list packages {flag}").splitlines() if l.startswith("package:")}


E, D, U = lista("-e"), lista("-d"), lista("-u")


def estado(pkg):
    return "ativo" if pkg in E else "desativado" if pkg in D else "removido" if pkg in U else "ausente"


# ---------------------------------------------------------------- pacotes: (fase, pacote, regra, nota)
# regra: "desativar" | "trocar:<pacote FOSS>" | "manter" (o script manda mexer, mas nao mexemos) | "foss"
PACOTES = [
    ("Etapa 1", "com.google.android.inputmethod.latin", "trocar:helium314.keyboard", "teclado Google (Gboard) trocado pelo HeliBoard, que e o padrao; o Gboard fica desativado"),
    ("Etapa 1", "com.sec.android.inputmethod", "desativar", "nome inexistente: o teclado Samsung e com.samsung.android.honeyboard"),
    ("Etapa 1", "com.samsung.android.honeyboard", "trocar:helium314.keyboard", "teclado Samsung trocado pelo HeliBoard (padrao)"),
    ("Etapa 1", "com.sec.android.app.camera", "trocar:net.sourceforge.opencamera", "regra v1 'NAO TOQUE'; trocado por pedido posterior do Rafael"),
    ("Etapa 1", "com.samsung.android.app.contacts", "trocar:org.fossify.contacts", "regra v1 'NAO TOQUE'; trocado por pedido posterior; dados ficam no provedor de contatos"),
    ("Etapa 1", "com.sec.android.app.popupcalculator", "trocar:org.fossify.math", "regra v1 'NAO TOQUE'; trocado por pedido posterior"),
    ("Etapa 1", "com.sec.android.app.clockpackage", "trocar:org.fossify.clock", "regra v1 'NAO TOQUE'; trocado por pedido posterior; alarmes recriados no Fossify"),
    ("Etapa 1", "com.samsung.android.app.notes", "trocar:org.fossify.notes", "regra v1 'NAO TOQUE'; trocado por pedido posterior; as 2 notas existentes foram copiadas para o Fossify Notas em 28/10 (originais ficam no app desativado)"),
    ("Etapa 1", "com.sec.android.app.fm", "manter", "radio FM usa o chip do aparelho: nao ha app livre equivalente sem root"),
    ("Etapa 1", "com.samsung.android.dialer", "manter", "telefone: continua instalado por seguranca (emergencia, VoLTE); o padrao pode ser o Fossify Telefone"),
    ("Etapa 1", "com.samsung.android.incallui", "manter", "tela de chamada do sistema; nao se desativa"),
    ("Etapa 1", "com.android.vending", "manter", "Play Store: bancos, Gov.br, SED e WhatsApp dependem"),
    ("Etapa 1", "com.google.android.gms", "manter", "Play Services: push e login de todos os apps"),
    ("Etapa 1", "com.google.android.webview", "manter", "WebView: bancos e Gov.br"),
    ("Fase 3", "com.wssyncmldm", "desativar", "OTA"),
    ("Fase 3", "com.sec.android.soagent", "desativar", "OTA"),
    ("Fase 3", "com.samsung.android.forest", "desativar", "Bem-estar Digital Samsung"),
    ("Fase 3", "com.google.android.apps.wellbeing", "desativar", ""),
    ("Fase 3", "com.sec.android.sdhms", "desativar", "Device Health Services"),
    ("Fase 3", "com.android.bips", "manter", "script manda desativar, mas UAD-ng 'Expert': trava as Configuracoes; regra do projeto"),
    ("Fase 3", "com.google.android.printservice.recommendation", "desativar", ""),
    ("Fase 4", "com.sec.android.app.samsungapps", "desativar", "Galaxy Store"),
    ("Fase 4", "com.osp.app.signin", "desativar", "Conta Samsung; UAD-ng avisa 'quebra as Configuracoes': testado, abrem normalmente; a conta em si ainda esta logada e so sai com a senha dele (Configuracoes > Contas > Samsung account > Remover)"),
    ("Fase 4", "com.samsung.android.mobileservice", "desativar", ""),
    ("Fase 4", "com.samsung.android.bixby.agent", "desativar", ""),
    ("Fase 4", "com.samsung.android.bixby.visionui", "desativar", ""),
    ("Fase 4", "com.samsung.android.ardrawing", "desativar", ""),
    ("Fase 4", "com.samsung.android.arzone", "desativar", ""),
    ("Fase 4", "com.sec.android.app.sbrowser", "desativar", "Samsung Internet"),
    ("Fase 4", "com.samsung.android.app.spage", "desativar", ""),
    ("Fase 4", "com.samsung.android.mdm", "desativar", ""),
    ("Fase 4", "com.samsung.android.knox.analytics.uploader", "desativar", "telemetria Knox"),
    ("Fase 4", "com.facebook.system", "desativar", ""),
    ("Fase 4", "com.facebook.appmanager", "desativar", ""),
    ("Fase 4", "com.facebook.services", "desativar", ""),
    ("Fase 4", "com.samsung.android.game.gos", "desativar", ""),
    ("Fase 4", "com.samsung.android.game.gamehome", "desativar", ""),
    ("Fase 4", "com.samsung.android.game.gametools", "desativar", ""),
    ("Fase 4", "com.samsung.android.kidsinstaller", "desativar", ""),
    ("Fase 4", "com.samsung.android.app.omcagent", "desativar", ""),
    ("Fase 4", "com.wsmac.openapi", "desativar", ""),
    ("Fase 4", "com.samsung.android.ipsgeofence", "desativar", ""),
    ("Fase 4", "com.samsung.android.rubin.app", "desativar", "Customization Service"),
    ("Fase 4", "com.sec.android.daemonapp", "desativar", "Clima Samsung"),
    ("Fase 4", "com.google.android.googlequicksearchbox", "desativar", "app Google: perde Assistente, widget e ditado Google"),
    ("Fase 4", "com.google.android.apps.maps", "trocar:app.organicmaps", "Maps trocado pelo Organic Maps"),
    ("Fase 4", "com.google.android.apps.photos", "desativar", ""),
    ("Fase 4", "com.sec.android.gallery3d", "trocar:org.fossify.gallery", "UAD-ng: 'dependencia da camera'; testado com o Open Camera"),
    ("Fase 4", "com.sec.android.app.myfiles", "trocar:org.fossify.filemanager", "UAD-ng: perde formatar/desmontar o SD nas Configuracoes (o PC formata)"),
    ("Fase 4", "com.sec.android.app.music", "desativar", "Samsung Music"),
    ("Apps", "org.videolan.vlc", "foss", "substituto do LarkPlayer"),
    ("Apps", "org.documentfoundation.libreoffice", "foss", "suite Office FOSS: LibreOffice Viewer (sem permissao de internet; abre docx, xlsx, pptx, odt; edicao so experimental)"),
    ("Apps", "com.gitlab.mudlej.MjPdfReader", "foss", "leitor de PDF"),
    ("Apps", "helium314.keyboard", "foss", "teclado (HeliBoard, derivado do OpenBoard)"),
    ("Apps", "com.junkfood.seal", "foss", "download de video/audio"),
    ("Apps", "com.tailscale.ipn", "foss", "rede Tailscale PC-celular"),
    ("Apps", "com.freerdp.afreerdp", "foss", "RDP livre no lugar do RD Client da Microsoft"),
    ("Dashcam", "net.sourceforge.opencamera", "foss", "camera"),
    ("Dashcam", "app.organicmaps", "foss", "mapas"),
    ("Termux", "com.termux", "foss", "terminal (F-Droid)"),
]

# ---------------------------------------------------------------- settings: (fase, ns, chave, valor_script, {atual: motivo do desvio}, nota)
SETS = [
    ("Fase 1", "global", "wifi_suspend_optimizations_enabled", "0", {}, "estabiliza Wi-Fi com a tela apagada"),
    ("Fase 1", "global", "mobile_data_always_on", "0", {}, ""),
    ("Fase 1", "global", "assisted_gps_enabled", "1", {}, ""),
    ("Fase 1", "global", "ble_scan_always_enabled", "0", {}, ""),
    ("Fase 1", "global", "wifi_scan_always_enabled", "0", {}, ""),
    ("Fase 3", "global", "send_action_app_error", "0", {}, ""),
    ("Fase 3", "secure", "upload_apk_enable", "0", {}, "o script usa o espaco 'secure'"),
    ("Fase 3", "global", "location_background_throttle_interval_ms", "3600000", {}, "localizacao em segundo plano a cada 1 h"),
    ("Fase 5", "global", "window_animation_scale", "0.0", {}, ""),
    ("Fase 5", "global", "transition_animation_scale", "0.0", {}, ""),
    ("Fase 5", "global", "animator_duration_scale", "0.0", {}, ""),
    ("Fase 5", "global", "ram_expand_size_list", "0,1,2,4,6,8", {"2,4": "RAM Plus mantido: o zram comprime ~4:1 e evita matar apps com 3,8 GB de RAM; so mudo com teste A/B"}, ""),
    ("Fase 5", "global", "ram_expand_size", "0", {"4096": "RAM Plus (4 GB) ligado de proposito; teste A/B exige 2 reinicios com PIN"}, ""),
    ("Fase 5", "global", "sem_enhanced_cpu_responsiveness", "1", {}, "unico ajuste Samsung real; efeito nao documentado"),
    ("Fase 5", "global", "low_power", "0", {}, ""),
    ("Fase 5", "global", "cached_apps_freezer", "enabled", {}, "caminho correto do freezer no Android 12 (o script usa device_config use_freezer)"),
    ("Fase 6", "global", "private_dns_mode", "hostname", {"opportunistic": "Automatico: o modo estrito derrubou a pagina de login do Wi-Fi da escola e travou o DNS"}, ""),
    ("Fase 6", "global", "private_dns_specifier", "dns.adguard-dns.com", {}, "hostname guardado; so vale com o modo 'hostname' (em casa)"),
    ("Fase 6", "system", "show_touches", "1", {}, ""),
    ("Fase 9", "global", "development_settings_enabled", "0", {"1": "ultimo passo: desligar as Opcoes do desenvolvedor pela interface so quando o Rafael encerrar o trabalho por ADB"}, "kill switch Gov.br/SEDUC"),
    ("Dashcam", "global", "force_resizable_activities", "1", {}, "tela dividida em qualquer app; vale depois de reiniciar"),
    ("Dashcam", "global", "enable_freeform_support", "1", {}, "janelas flutuantes; vale depois de reiniciar"),
]
RECUSADOS_SET = [
    ("Fase 5", "global", "activity_manager_constants", "max_cached_processes=4",
     "[Falso] no Android 12: a chave nao e lida (o valor vem do device_config) e 4 processos em cache mataria apps o tempo todo"),
]
# ---------------------------------------------------------------- appops: (fase, pacote, operacao, modo, nota, recusado?)
APPOPS = [
    ("Fase 2", "com.android.vending", "RUN_IN_BACKGROUND", "ignore", "a Play Store so atualiza com ela aberta", ""),
    ("Fase 2", "com.microsoft.teams", "RUN_IN_BACKGROUND", "ignore", "", ""),
    ("Termux", "com.termux", "RUN_IN_BACKGROUND", "ignore", "zero consumo ocioso. Atualizado em 02/11: nao impede o guarda `saida` nem o Termux:Boot (processo do Termux e servico em primeiro plano; 2 reboots reais provados com este ajuste)", ""),
    ("Dashcam", "net.sourceforge.opencamera", "PICTURE_IN_PICTURE", "allow", "", ""),
    ("Dashcam", "app.organicmaps", "PLAY_AUDIO", "allow", "", ""),
    ("Dashcam", "net.sourceforge.opencamera", "SYSTEM_ALERT_WINDOW", "allow", "",
     "sem efeito tecnico no que o script promete (prioridade na chamada) e abre permissao de sobreposicao; nao concedido"),
    ("Dashcam", "app.organicmaps", "SYSTEM_ALERT_WINDOW", "allow", "",
     "idem: permissao de sobreposicao desnecessaria; nao concedida"),
]
BUCKETS = [("Fase 2", "com.whatsapp.w4b", "30", "30 = FREQUENT (nao 'restrito'); push continua chegando")]
WHITELIST = [("Dashcam", "net.sourceforge.opencamera"), ("Dashcam", "app.organicmaps")]


def verifica_pacote(pkg, regra):
    e = estado(pkg)
    if regra == "desativar":
        return ("N.A.", e) if e == "ausente" else ("FEITO", e) if e in ("desativado", "removido") else ("PENDENTE", e)
    if regra == "manter":
        return ("RECUSADO", e) if e == "ativo" else ("PENDENTE", e + " (devia estar ativo)")
    if regra == "foss":
        return ("FEITO", e) if e == "ativo" else ("PENDENTE", e)
    if regra.startswith("trocar:"):
        novo = regra.split(":", 1)[1]
        en = estado(novo)
        if e == "ausente":
            return "N.A.", f"{e}; FOSS {en}"
        if en != "ativo":
            return "PENDENTE", f"{e}; FOSS {en}"
        return ("FEITO", f"{e}; FOSS {en}") if e in ("desativado", "removido") else ("PENDENTE", f"{e}; FOSS {en}")
    return "PENDENTE", e


def opmodo(pkg, op):
    m = re.search(rf"{op}: (\w+)", sh(f"cmd appops get {pkg} {op}"))
    return m.group(1) if m else "?"


def compilacao(pkg):
    m = re.search(r"\[status=([\w-]+)\]", sh(f"dumpsys package {pkg} | grep -m1 'status='"))
    return m.group(1) if m else "?"


def conferir():
    L = []  # (fase, item, script_pede, agora, veredito, nota)
    for fase, pkg, regra, nota in PACOTES:
        v, agora = verifica_pacote(pkg, regra)
        pede = {"desativar": "pm disable-user", "manter": "(script manda mexer)", "foss": "instalar substituto"}.get(regra, "trocar por FOSS")
        if regra == "manter":
            nota = "RECUSADO: " + nota
        L.append((fase, pkg, pede, agora, v, nota))
    for fase, ns, k, valor, aceita, nota in SETS:
        atual = sh(f"settings get {ns} {k}")
        if atual == valor:
            v, n = "FEITO", nota
        elif atual in aceita:
            v, n = ("PENDENTE", aceita[atual]) if k == "development_settings_enabled" else ("DESVIO", aceita[atual])
        elif atual == "null":
            v, n = "N.A.", "chave nao existe neste aparelho"
        else:
            v, n = "PENDENTE", nota
        L.append((fase, f"settings {ns} {k}", valor, atual, v, n))
    for fase, ns, k, valor, motivo in RECUSADOS_SET:
        L.append((fase, f"settings {ns} {k}", valor, sh(f"settings get {ns} {k}"), "RECUSADO", motivo))
    L.append(("Fase 5", "device_config activity_manager use_freezer", "true", sh("device_config get activity_manager use_freezer"),
              "DESVIO", "kernel 4.19 do MT6765 pode nao expor o freezer; o caminho certo e cached_apps_freezer (acima)"))
    for fase, pkg, op, modo, nota, recusa in APPOPS:
        if estado(pkg) != "ativo":
            L.append((fase, f"appops {pkg} {op}", modo, estado(pkg), "N.A.", "app nao instalado"))
            continue
        atual = opmodo(pkg, op)
        if recusa:
            # recusa = decisao de NAO conceder; "RECUSADO" so vale enquanto o estado real confirma isso
            # (atual != modo). Se, por outra via, o appop foi concedido mesmo assim, isso e uma pendencia
            # de verdade (igual ao padrao de "manter" acima), nunca "FEITO" (nao foi essa decisao que fez).
            L.append((fase, f"appops {pkg} {op}", modo, atual, "RECUSADO" if atual != modo else "PENDENTE", recusa))
        else:
            L.append((fase, f"appops {pkg} {op}", modo, atual, "FEITO" if atual == modo else "PENDENTE", nota))
    for fase, pkg, b, nota in BUCKETS:
        atual = sh(f"am get-standby-bucket {pkg}")
        if atual == b:
            v, n = "FEITO", nota
        elif atual in ("10", "20"):  # o Android promove o app pelo uso; e melhor para receber mensagem do que o 30 pedido
            v, n = "DESVIO", f"{nota}. O Android recalcula o bucket pelo uso e o app muito usado fica em {atual} (melhor que 30 para receber mensagens); forcar 30 se desfaz sozinho"
        else:
            v, n = "PENDENTE", nota
        L.append((fase, f"standby-bucket {pkg}", b, atual, v, n))
    idle = sh("dumpsys deviceidle whitelist")
    for fase, pkg in WHITELIST:
        ok = f",{pkg}," in idle
        L.append((fase, f"deviceidle whitelist {pkg}", "+", "na lista" if ok else "fora da lista", "FEITO" if ok else "PENDENTE", ""))
    st = compilacao(ARENA)
    L.append(("Fase 8", f"compile -m speed -f {ARENA}", "speed", st, "FEITO" if st == "speed" else "PENDENTE",
              "AOT so nos apps-alvo (ARENA); o resto fica em speed-profile"))
    vols = sh("sm list-volumes all")
    # "private" tambem aparece no volume INTERNO ("private mounted null"): o cartao adotado e "private:<major>,<minor>"
    adotado = re.search(r"^private:", vols, re.M) is not None
    L.append(("Fase 7", "sm set-force-adoptable + sm partition private", "cartao como memoria interna",
              "adotado (volume private: em sm list-volumes agora); apps e dados nele NAO foram medidos aqui" if adotado else "portatil exFAT",
              "PENDENTE" if adotado else "DESVIO",
              "depende da decisao do Rafael (deixar adotado e ocioso, voltar a portatil exFAT ou trocar o cartao); nao mover nada entre volumes. "
              "27/10: apps sumiam do teclado/SMS/relogio apos o boot, VLC e Seal apareceram corrompidos [Provavel: desmontagem suja] e o `pm move-package` derrubou o Android; voltou a portatil. "
              "28/10: voltou a aparecer adotado (autor nao comprovado) e a unificacao (`pm move-primary-storage`) corrompeu 1.412 de 5.006 arquivos (md5 contra o backup do PC); revertida e restaurada. "
              "Licao: 'Success', du e contagem nao provam integridade, so o md5 apos descartar o cache (scripts/teste-gravacao.py)"
              if adotado else
              "o cartao portatil aparece como 'Cartao SD' e o PC le; o adotado foi testado em 27/10 e 28/10 e revertido (ver PLANO.md); em 29/10 o portatil exFAT novo (formatado com o 'sim' do Rafael) passou no teste-gravacao.py (64 MB, cache descartado); Dashcam e NewPipe ainda precisam que o Rafael escolha a pasta no cartao novo"))
    L.append(("Apps", "com.onlyoffice.documents (ONLYOFFICE)", "instalar", "nao instalado", "DESVIO",
              "o ONLYOFFICE nao esta na F-Droid, empurra a nuvem dele e envia estatisticas; o LibreOffice Viewer (F-Droid, MPL-2.0, sem internet) cumpre o pedido de Office livre e sem telemetria"))
    L.append(("Fase 8", "pm trim-caches", "limpar caches", "historico (28/10), nao lido agora: executado", "FEITO", "cache de apps liberado ate 8 GB livres (28/10)"))
    L.append(("Fase 8", "sm fstrim", "executar", "historico (28/10), nao lido agora: executado", "FEITO", "TRIM rodado em 27/10 e de novo em 28/10 antes da medicao final"))
    L.append(("Fase 8", "cmd package bg-dexopt-job", "executar", "historico (28/10), nao lido agora: executado", "FEITO", "compilacao em segundo plano rodada em 28/10; apps FOSS recompilados em speed-profile"))
    L.append(("Termux", "empacotar ~/.claude.json e chaves em ai_workspace.tar.gz e copiar para /sdcard/Download", "migrar credenciais", "nada copiado", "RECUSADO",
              "token em /sdcard/Download e legivel por outros apps e pelo MTP; regra do projeto: sem credenciais no celular"))
    L.append(("Termux", "npm install -g @anthropic-ai/claude-code", "instalar no Termux", "nao instalado", "RECUSADO",
              "[Falso] desde a 2.1.113 (binario glibc, process.platform=android); alternativa: proot-distro ou SSH ao PC"))
    L.append(("Termux", "pkg update/upgrade; pkg install python nodejs rust; Hermes pip; aliases ai-up/ai-kill", "instalar Hermes no Termux",
              "pkg update feito; Hermes ainda nao instalado", "PENDENTE", "Hermes + OmniRoute + perfil Claude no celular (pedido #31) ficou para depois do checklist; plano sem chaves no celular esta no claude-mem e em PLANO-DE-ACAO.md"))
    L.append(("Dashcam", "Open Camera: 720p, 30 fps, fonte de audio 'Otimizado para voz'", "configurar no app", "historico (28/10), nao lido agora: 720p, 30 fps, audio otimizado para voz", "FEITO",
              "configurado e testado em 28/10 00:08 (MP4 verificado: 1280x720, ~30 fps, AAC, legenda .srt)"))
    L.append(("Dashcam", "Open Camera em HEVC (H.265)", "HEVC", "H.264", "DESVIO",
              "o MT6765 so tem encoder de hardware AVC/MPEG4/H263; HEVC por software seria lento e esquentaria; H.264 e o correto neste chip"))
    L.append(("Dashcam", "Tela dividida: Recentes > Organic Maps > Abrir em tela dividida > Open Camera", "uso manual", "historico (28/10), nao lido agora: testado, funciona", "FEITO",
              "os dois apps ficam 'resumed' e a camera continua gravando com o foco no mapa (28/10); force_resizable vale para outros apps so apos reiniciar"))
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--so-pendentes", action="store_true")
    a = ap.parse_args()
    if "SM-A125" not in sh("getprop ro.product.model"):
        sys.exit("ABORTADO: aparelho nao encontrado ou inesperado")
    L = conferir()
    cont = Counter(x[4] for x in L)
    quando = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    md = [f"# Checklist do script original, item por item (gerado em {quando}; o que o script le do aparelho vem do ADB agora, itens marcados 'historico' sao registro de execucoes passadas)",
          "Fonte dos itens: `Otimização Samsung A12.txt` (9 versões repetidas; 52 pacotes, ~25 chaves, appops, buckets, whitelist, compilação, armazenamento, kill switch, Termux, tela dividida).",
          "Veredito: FEITO = como o script manda · DESVIO = decisão consciente com motivo · RECUSADO = perigoso, falso ou fere regra do projeto · N.A. = não existe neste aparelho · PENDENTE = falta aplicar ou depende do Rafael.",
          "", "Resumo: " + " · ".join(f"{k} {cont[k]}" for k in ("FEITO", "DESVIO", "RECUSADO", "N.A.", "PENDENTE")) + f" · total {len(L)}", ""]
    fase = None
    for f, item, pede, agora, v, nota in L:
        if f != fase:
            fase = f
            md += ["", f"## {f}", "", "| Item | Script pede | Agora | Veredito | Observação |", "|---|---|---|---|---|"]
        md.append(f"| `{item}` | {pede} | {agora} | **{v}** | {nota} |")
    (RAIZ / "memoria" / "CHECKLIST-SCRIPT.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print(f"itens: {len(L)} | " + " | ".join(f"{k} {cont[k]}" for k in ("FEITO", "DESVIO", "RECUSADO", "N.A.", "PENDENTE")))
    for f, item, pede, agora, v, nota in L:
        if v == "PENDENTE" or not a.so_pendentes and v in ("DESVIO",):
            print(f"  [{v}] {f}: {item} | pede {pede} | agora {agora} | {nota[:110]}")
    print("relatorio: memoria/CHECKLIST-SCRIPT.md")


if __name__ == "__main__":
    main()
