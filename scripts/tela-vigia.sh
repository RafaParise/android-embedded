#!/system/bin/sh
# Roda no A12, como shell. Nao fica instalado: some ao reiniciar (depois disso, ligar de novo com o cabo: scripts/tela-apagada.py).
# Volume para baixo 3x escurece a tela. Quem acende e o proprio Tela (dois toques, volume para cima, botao, alarme, chamada).
# Se o Tela morrer, a camada preta some sozinha e este script devolve o brilho: nunca fica tela preta sem saida.
# Sem bloqueio (24/11/2026, pedido do Rafael): depois do gesto, o celular nunca bloqueia sozinho. Acendeu e ficou parado
# perto do tempo de apagar? A guarda escurece de novo em vez de deixar o Android dormir (dormir bloqueia). So o botao
# de ligar (ou o bloqueio pedido por ele) desliga a guarda.
# Uso: tela-vigia.sh vigiar|agora <no do volume para baixo> <no do toque> <nos das teclas...>
MODO=$1
DIR=${TELA_DIR:-/data/local/tmp}
if [ "$MODO" = turbo ]; then
  # Wi-Fi em alto desempenho com a tela em uso. Religa sozinho se o processo morrer. Desligar: tela-apagada.py turbo-desligar.
  echo $$ > "$DIR/tela-turbo.pid"
  while [ ! -e "$DIR/tela-vigia.sem-turbo" ]; do
    CLASSPATH=$DIR/tela.dex app_process / Tela wifi-turbo >/dev/null 2>&1
    sleep "${TELA_TURBO_ESPERA:-30}"
  done
  exit 0
fi
EV_VOL=$2
EV_TOQUE=$3
shift 3
TECLAS="$*"
JANELA=${TELA_JANELA:-3}
ESPERA_PIN=${TELA_ESPERA_PIN:-1}
TRAVA=$DIR/tela-escuro.trava
MOTIVO=$DIR/tela-vigia.motivo
HISTORICO=$DIR/tela-vigia.historico
PIDARQ=$DIR/tela-vigia.pid
GUARDA=$DIR/tela-guarda.ligada
GUARDA_S=${TELA_GUARDA_S:-20}
FOLGA_S=${TELA_GUARDA_FOLGA:-60}

tela() { CLASSPATH=$DIR/tela.dex app_process / Tela "$@" 2>/dev/null; }

escuro() {
  mkdir "$TRAVA" 2>/dev/null || return 0
  inicio=$(date +%H:%M:%S)
  m=$(tela escuro "$1" "$EV_TOQUE" $TECLAS)
  case "$m" in
    acendeu:*) ;;
    *)
      tela luz volta >/dev/null
      m="acendeu: encerrada (pelo PC, ou por falta de memoria)"
      ;;
  esac
  echo "$m" > "$MOTIVO"
  case "$m" in
    *energia*|*dormiu*|*bloqueou*) rm -f "$GUARDA" ;;
    *) : > "$GUARDA" ;;
  esac
  echo "$inicio -> $(date +%H:%M:%S) $m" >> "$HISTORICO"
  tail -n 20 "$HISTORICO" > "$HISTORICO.novo" && mv "$HISTORICO.novo" "$HISTORICO"
  case "$m" in
    *energia*|*dormiu*|*bloqueou*)
      # quem bloqueou foi o Rafael: a tela ja estava preta, entao mostra o PIN em vez de parecer que nada aconteceu
      sleep "$ESPERA_PIN"
      input keyevent 224
      ;;
  esac
  rmdir "$TRAVA" 2>/dev/null
}

pode_apagar() {
  e=$(dumpsys window 2>/dev/null | grep -m1 -oE 'isKeyguardShowing=[a-z]+')
  [ "$e" = "isKeyguardShowing=false" ]
}

# verdadeiro se o aparelho, aceso, esta parado perto do tempo de apagar sozinho (que bloquearia); sem dado = falso
parado_demais() {
  w=0 a=0 u=0 t=0 e=
  for c in $(dumpsys power 2>/dev/null | sed -nE \
      -e 's/.*mLastWakeTime=([0-9]+) \(([0-9]+) ms ago\).*/w=\1 a=\2/p' \
      -e 's/.*mLastUserActivityTime[^=]*=([0-9]+).*/u=\1/p' \
      -e 's/.*mScreenOffTimeoutSetting=([0-9]+).*/t=\1/p' \
      -e 's/.*mWakefulness=([A-Za-z]+).*/e=\1/p'); do
    case "$c" in
      w=*) [ "$w" = 0 ] && w=${c#w=} ;;
      a=*) [ "$a" = 0 ] && a=${c#a=} ;;
      u=*) [ "$u" = 0 ] && u=${c#u=} ;;
      t=*) [ "$t" = 0 ] && t=${c#t=} ;;
      e=*) [ -z "$e" ] && e=${c#e=} ;;
    esac
  done
  [ "$e" = Awake ] && [ "$w" -gt 0 ] && [ "$u" -gt 0 ] && [ "$t" -gt 0 ] || return 1
  limite=$((t - FOLGA_S * 1000))
  [ "$limite" -lt 20000 ] && limite=20000
  [ $((w + a - u)) -ge "$limite" ]
}

guarda() {
  pai=$1
  while kill -0 "$pai" 2>/dev/null; do
    sleep "$GUARDA_S"
    [ -e "$GUARDA" ] || continue
    [ -d "$TRAVA" ] && continue
    if ! pode_apagar; then
      rm -f "$GUARDA" # bloqueou com a tela acesa: foi ele (botao), a guarda sai
      continue
    fi
    parado_demais && escuro 0
  done
}

espera_gesto() {
  t0=0
  n=0
  while :; do
    l=$(getevent -lc 2 "/dev/input/$EV_VOL" 2>/dev/null)
    case "$l" in
      *KEY_VOLUMEDOWN*DOWN*) ;;
      *) [ -n "$l" ] || sleep 1; continue ;;
    esac
    agora=$(date +%s)
    if [ $((agora - t0)) -gt "$JANELA" ]; then
      t0=$agora
      n=1
    else
      n=$((n + 1))
    fi
    [ "$n" -ge 3 ] && return 0
  done
}

case "$MODO" in
  agora)
    escuro 0
    ;;
  vigiar)
    echo $$ > "$PIDARQ"
    rmdir "$TRAVA" 2>/dev/null
    guarda $$ &
    while :; do
      espera_gesto
      pode_apagar && escuro 3
    done
    ;;
  *)
    echo "uso: tela-vigia.sh vigiar|agora <volume> <toque> <teclas...>" >&2
    exit 2
    ;;
esac
