#!/system/bin/sh
# Roda no A12, como shell. Nao fica instalado: some ao reiniciar (depois disso, ligar de novo com o cabo: scripts/tela-apagada.py).
# Volume para baixo 3x escurece a tela. Quem acende e o proprio Tela (dois toques, volume para cima, botao, alarme, chamada).
# Se o Tela morrer, a camada preta some sozinha e este script devolve o brilho: nunca fica tela preta sem saida.
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
