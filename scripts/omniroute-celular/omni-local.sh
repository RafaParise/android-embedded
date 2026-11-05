#!/data/data/com.termux/files/usr/bin/bash
# omni-local - cuida do OmniRoute LOCAL do celular (a reserva do comando ia; memoria/OMNIROUTE-CELULAR.md).
# Quem chama e o PC (scripts/omniroute-celular.ps1, pelo ssh); no Termux tambem funciona na mao. Versao 2026-11-01.
#   omni-local ligar | desligar | status
#   omni-local provedor nvidia|gemini|openrouter   cria (ou atualiza) a conexao e testa; a chave vem pela ENTRADA PADRAO, nunca por argumento
#   omni-local combos [ARQ.json]                   cria codigo, auditoria e rapido so com os modelos dos provedores que existem aqui
#   omni-local testar [combo ...]                  uma pergunta curta por combo (padrao: codigo auditoria rapido)
#   omni-local pronto                              cria ~/.omniroute/pronto se o combo codigo respondeu agora (e o que liga a reserva no ia)
#   omni-local tirar nvidia|gemini|openrouter      apaga a conexao (e a chave) deste provedor
#   omni-local apagar-combos                       apaga os combos codigo, auditoria e rapido (nenhum outro)
# Nunca imprime chave nem senha. Variaveis: IA_GW_DIR, IA_GW_DADOS, IA_GW_PORTA, IA_GW_MB, IA_RUN (as mesmas do ia).

set -u
shopt -s lastpipe   # o ultimo comando de um pipe (a funcao api) roda neste shell e deixa o $COD aqui
GW_DIR="${IA_GW_DIR:-${PREFIX:-/data/data/com.termux/files/usr}/lib/node_modules/omniroute}"
D="${IA_GW_DADOS:-$HOME/.omniroute}"
PORTA="${IA_GW_PORTA:-20129}"; case "$PORTA" in ''|*[!0-9]*|20128) PORTA=20129 ;; esac
MB="${IA_GW_MB:-384}"; case "$MB" in ''|*[!0-9]*) MB=384 ;; esac
RUN="${IA_RUN:-$HOME/.cache/ia}"
mkdir -p "$RUN"
BASE="http://127.0.0.1:$PORTA"
PIDF="$RUN/omni-local.pid"; JAR="$RUN/omni-local.jar"; RESP="$RUN/omni-local.resp"
QUI="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
COD=""
trap 'rm -f "$JAR" "$RESP"' EXIT

no_ar() { [ "$(curl -s -o /dev/null -m 4 -w '%{http_code}' "$BASE/api/monitoring/health" 2>/dev/null)" = 200 ]; }
chave_local() { head -1 "$D/cliente-local.key" 2>/dev/null; }
limpa() { # nunca devolve nada que pareca chave: some com a chave conhecida (IA_K, so no ambiente do python) e com qualquer sequencia longa
  python3 -I -c 'import os,re,sys
t = sys.stdin.read().replace("\n", " ")
k = os.environ.get("IA_K", "")
if k:
    t = t.replace(k, "***")
print(re.sub(r"[A-Za-z0-9_.\-]{24,}", "***", t)[:200])'
}

aquece() { # a 1a chamada a /v1/models depois de subir leva ~8 s (medido em 01/11)
  local k; k=$(chave_local); [ -n "$k" ] || return 0
  printf 'header = "Authorization: Bearer %s"\n' "$k" | curl -s -K - -m 90 -o /dev/null "$BASE/v1/models" >/dev/null 2>&1
}
ligar() {
  no_ar && { echo "OmniRoute do celular: ja estava ligado"; return 0; }
  [ -f "$GW_DIR/bin/omniroute.mjs" ] || { echo "OmniRoute nao esta instalado em $GW_DIR"; return 1; }
  command -v node >/dev/null 2>&1 || { echo "Falta o node (pkg install nodejs)"; return 1; }
  ( trap '' HUP; cd "$GW_DIR" && DATA_DIR="$D" OMNIROUTE_SERVER_HOST=127.0.0.1 OMNIROUTE_MEMORY_MB="$MB" exec node bin/omniroute.mjs serve --port "$PORTA" --no-open --no-tray --headless --no-recovery ) >"$RUN/omniroute.log" 2>&1 &
  local gp=$!; echo "$gp" > "$PIDF"
  local i; for i in $(seq 1 120); do no_ar && break; kill -0 "$gp" 2>/dev/null || { echo "O servidor morreu ao subir: veja $RUN/omniroute.log"; return 1; }; sleep "${IA_ESPERA:-2}"; done
  no_ar || { echo "O servidor nao respondeu a tempo: veja $RUN/omniroute.log"; return 1; }
  aquece
  echo "OmniRoute do celular: ligado em 127.0.0.1:$PORTA"
}
desligar() {
  local p; p=$(cat "$PIDF" 2>/dev/null)
  if [ -n "$p" ] && grep -qa omniroute "/proc/$p/cmdline" 2>/dev/null; then kill "$p" 2>/dev/null; fi
  local i; for i in 1 2 3 4 5 6 7 8; do no_ar || break; sleep "${IA_ESPERA:-1}"; done
  if no_ar; then echo "OmniRoute do celular: continua ligado (nao foi este comando que o ligou? use: ia parar)"; return 1; fi
  echo "OmniRoute do celular: desligado"
}
precisa_no_ar() { no_ar || { echo "O OmniRoute do celular esta desligado: rode  omni-local ligar"; return 1; }; }

entrar() { # login na API com a senha inicial do .env (o CLI nao autentica no Termux: falta /etc/machine-id)
  local pw; pw=$(grep -m1 '^INITIAL_PASSWORD=' "$D/.env" 2>/dev/null | cut -d= -f2-)
  [ -n "$pw" ] || { echo "Sem a senha inicial em $D/.env"; return 1; }
  ( umask 077; : > "$JAR" )
  local cod; cod=$(printf '%s' "$pw" | python3 -I -c 'import json,sys;print(json.dumps({"password":sys.stdin.read()}))' | curl -s -m 20 -c "$JAR" -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' --data-binary @- "$BASE/api/auth/login")
  [ "$cod" = 200 ] || { echo "Login recusado pelo OmniRoute (HTTP $cod)"; return 1; }
}
api() { # METODO CAMINHO [sim]: com "sim" o corpo JSON vem da entrada padrao. Corpo da resposta em $RESP, codigo HTTP em $COD
  local m="$1" c="$2" com="${3:-nao}"
  if [ "$com" = sim ]; then COD=$(curl -s -m 90 -b "$JAR" -o "$RESP" -w '%{http_code}' -X "$m" -H 'Content-Type: application/json' --data-binary @- "$BASE$c")
  else COD=$(curl -s -m 90 -b "$JAR" -o "$RESP" -w '%{http_code}' -X "$m" "$BASE$c" </dev/null); fi
}
conexoes() { # guarda em $CONEX "id provedor" por conexao existente; devolve 1 se a listagem falhou (nao confundir falha com lista vazia)
  CONEX=""
  api GET '/api/providers?limit=5000'
  [ "$COD" = 200 ] || { echo "Nao consegui listar as conexoes do OmniRoute (HTTP $COD)"; return 1; }
  CONEX=$(python3 -I -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    d = {}
rows = d if isinstance(d, list) else (d.get("connections") if isinstance(d.get("connections"), list) else d.get("providers")) if isinstance(d, dict) else []
for r in rows or []:
    if isinstance(r, dict) and r.get("id") and r.get("provider"):
        print(r["id"], r["provider"])' < "$RESP")
}

provedor() {
  local id="${1:-}" pre pre2 chave
  case "$id" in
    # Gemini: o Google passou a emitir chaves "AQ.xxxx" (53 caracteres, 01/11/2026) alem das antigas "AIza..." (39)
    nvidia) pre='nvapi-' ;; gemini) pre='AIza'; pre2='AQ.' ;; openrouter) pre='sk-or-' ;;
    *) echo "Provedor desconhecido: '$id' (use nvidia, gemini ou openrouter)"; return 2 ;;
  esac
  if [ -t 0 ]; then printf 'Cole a chave de %s (nao aparece na tela) e aperte Enter: ' "$id" >&2; IFS= read -rs chave; echo >&2
  else IFS= read -r chave || true; fi
  chave=$(printf '%s' "$chave" | tr -d '[:space:]')
  case "$chave" in "$pre"*|"${pre2:-$pre}"*) ;; *) echo "A chave de $id tem que comecar com $pre${pre2:+ ou $pre2} (nada foi guardado)"; return 2 ;; esac
  { [ "${#chave}" -ge 20 ] && [ "${#chave}" -le 200 ]; } || { echo "Tamanho da chave fora do esperado (nada foi guardado)"; return 2; }
  case "$chave" in *[!A-Za-z0-9_.-]*) echo "A chave tem caractere estranho (nada foi guardado)"; return 2 ;; esac
  precisa_no_ar || return 1
  entrar || return 1
  conexoes || return 1
  local cid; cid=$(printf '%s\n' "$CONEX" | while read -r a b; do [ "$b" = "$id" ] && { echo "$a"; break; }; done)
  local acao
  if [ -n "$cid" ]; then
    printf '%s' "$chave" | python3 -I -c 'import json,sys;print(json.dumps({"apiKey":sys.stdin.read()}))' | api PATCH "/api/providers/$cid" sim
    acao=atualizada
  else
    printf '%s' "$chave" | python3 -I -c 'import json,sys;print(json.dumps({"provider":sys.argv[1],"name":sys.argv[2],"apiKey":sys.stdin.read()}))' "$id" "celular-$id" | api POST /api/providers sim
    acao=criada
    cid=$(python3 -I -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    d = {}
c = d.get("connection") if isinstance(d, dict) else None
print(c.get("id", "") if isinstance(c, dict) else "")' < "$RESP")
  fi
  case "$COD" in 200|201) ;; *) echo "OmniRoute recusou a conexao de $id (HTTP $COD): $(IA_K="$chave" limpa < "$RESP")"; return 1 ;; esac
  [ -n "$cid" ] || { echo "OmniRoute respondeu sem o id da conexao de $id"; return 1; }
  api POST "/api/providers/$cid/test"
  local veredito
  veredito=$(IA_K="$chave" python3 -I -c '
import json, os, re, sys
cod = sys.argv[1]
try:
    d = json.load(sys.stdin)
except ValueError:
    d = {}
txt = json.dumps(d, ensure_ascii=False)
k = os.environ.get("IA_K", "")
if k:
    txt = txt.replace(k, "***")
positivo = isinstance(d, dict) and (d.get("valid") is True or d.get("success") is True or d.get("ok") is True)   # corpo vazio ou que nao e JSON nao valida chave nenhuma
ok = cod == "200" and positivo and not d.get("error") and d.get("valid") is not False and d.get("success") is not False and d.get("ok") is not False
msg = re.sub(r"[A-Za-z0-9_.\-]{24,}", "***", txt)[:160]
print(("OK" if ok else "FALHOU") + " " + msg)' "$COD" < "$RESP")
  echo "$id: conexao $acao; teste do OmniRoute: $veredito"
  case "$veredito" in OK*) return 0 ;; *) return 1 ;; esac
}
tirar() {
  local id="${1:-}"; [ -n "$id" ] || { echo "Diga o provedor (nvidia, gemini ou openrouter)"; return 2; }
  precisa_no_ar || return 1; entrar || return 1
  conexoes || return 1
  local n=0 a b rc=0
  while read -r a b; do
    [ "$b" = "$id" ] || continue
    api DELETE "/api/providers/$a"
    case "$COD" in
      200|204) echo "$id: conexao apagada (HTTP $COD)"; n=$((n + 1)) ;;
      *) echo "$id: NAO apagou a conexao (HTTP $COD): a chave continua no celular"; rc=1 ;;
    esac
  done <<< "$CONEX"
  [ "$n" -gt 0 ] || [ "$rc" -ne 0 ] || echo "$id: nao havia conexao"
  return $rc
}

combos() {
  local arq="${1:-$QUI/omni-local.combos.json}"
  [ -f "$arq" ] || { echo "Sem o arquivo de combos: $arq"; return 1; }
  precisa_no_ar || return 1; entrar || return 1
  conexoes || return 1
  local provs; provs=$(printf '%s\n' "$CONEX" | cut -d' ' -f2 | sort -u | tr '\n' ' ')
  [ -n "${provs// /}" ] || { echo "Nenhum provedor configurado: rode  omni-local provedor nvidia  (e gemini, openrouter)"; return 1; }
  echo "Provedores daqui: $provs"
  api GET /api/combos
  local plano; plano=$(python3 -I -c '
import json, sys
provs = set(sys.argv[2].split())
combos = json.load(open(sys.argv[1], encoding="utf-8"))
try:
    atual = json.load(sys.stdin)
except ValueError:
    atual = []
atual = atual if isinstance(atual, list) else (atual.get("combos") or atual.get("data") or [])
ids = {c.get("name"): c.get("id") for c in atual if isinstance(c, dict)}
for c in combos:
    modelos = [m for m in c.get("models", []) if isinstance(m, dict) and m.get("providerId") in provs]
    if not modelos:
        print("PULA", c["name"], "sem modelo dos provedores daqui")
        continue
    if ids.get(c["name"]):
        velho = {k: v for k, v in next(x for x in atual if isinstance(x, dict) and x.get("name") == c["name"]).items() if k not in ("id", "createdAt", "updatedAt", "created_at", "updated_at")}
        print("APAGA", ids[c["name"]], c["name"], json.dumps(velho, separators=(",", ":")))   # o antigo vai junto: se a criacao do novo for recusada, ele volta
    cfg = {k: v for k, v in (c.get("config") or {}).items() if k != "compressionMode"}   # a compressao nao foi testada no celular
    corpo = {"name": c["name"], "strategy": c.get("strategy") or "priority", "enabled": True, "models": modelos, "config": cfg}
    print("CRIA", c["name"], len(modelos), json.dumps(corpo, separators=(",", ":")))' "$arq" "$provs" < "$RESP")
  local acao a b c rc=0 velho="" velho_nome="" travado=""
  while IFS= read -r linha; do
    acao=${linha%% *}; resto=${linha#* }
    case "$acao" in
      PULA) echo "combo $resto" ;;
      APAGA) a=${resto%% *}; resto=${resto#* }; velho_nome=${resto%% *}; velho=${resto#* }
             api DELETE "/api/combos/$a"
             case "$COD" in 200|204) ;; *) echo "combo $velho_nome: nao apagou o antigo (HTTP $COD); mantido como estava"; travado="$velho_nome"; velho=""; rc=1 ;; esac ;;
      CRIA) b=${resto%% *}; resto=${resto#* }; c=${resto%% *}
            if [ "$b" = "$travado" ]; then continue; fi
            printf '%s' "${resto#* }" | api POST /api/combos sim
            case "$COD" in
              200|201) echo "combo $b: criado com $c modelo(s)" ;;
              *) echo "combo $b: recusado (HTTP $COD): $(limpa < "$RESP")"; rc=1
                 if [ "$b" = "$velho_nome" ] && [ -n "$velho" ]; then
                   printf '%s' "$velho" | api POST /api/combos sim
                   case "$COD" in 200|201) echo "combo $b: restaurado como era antes" ;; *) echo "combo $b: NAO consegui restaurar o antigo (HTTP $COD)" ;; esac
                 fi ;;
            esac ;;
    esac
  done <<< "$plano"
  return $rc
}

apagar_combos() { # so os tres que este script cria
  precisa_no_ar || return 1; entrar || return 1
  api GET /api/combos
  python3 -I -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    d = []
d = d if isinstance(d, list) else (d.get("combos") or d.get("data") or [])
for c in d:
    if isinstance(c, dict) and c.get("id") and c.get("name") in ("codigo", "auditoria", "rapido"):
        print(c["id"], c["name"])' < "$RESP" | while read -r a b; do api DELETE "/api/combos/$a"; echo "combo $b: apagado (HTTP $COD)"; done
}

testar() {
  local lista=("$@") c k cod t0 saida rc=0 rc2
  [ "${#lista[@]}" -gt 0 ] || lista=(codigo auditoria rapido)
  precisa_no_ar || return 1
  k=$(chave_local); [ -n "$k" ] || { echo "Sem a chave local em $D/cliente-local.key"; return 1; }
  for c in "${lista[@]}"; do
    t0=$(date +%s)
    cod=$(printf 'header = "Authorization: Bearer %s"\n' "$k" | curl -s -K - -m 150 -o "$RESP" -w '%{http_code}' -H 'Content-Type: application/json' \
      -d "$(python3 -I -c 'import json,sys;print(json.dumps({"model":sys.argv[1],"max_tokens":200,"messages":[{"role":"user","content":"Responda so com a palavra: ok"}]}))' "$c")" "$BASE/v1/chat/completions")
    saida=$(IA_K="$k" python3 -I -c '
import json, os, re, sys
cod, nome, seg = sys.argv[1], sys.argv[2], sys.argv[3]
chave = os.environ.get("IA_K", "")
def lim(t):
    t = str(t).replace("\n", " ")
    if chave:
        t = t.replace(chave, "***")
    return re.sub(r"[A-Za-z0-9_.\-]{24,}", "***", t)[:140]
try:
    d = json.load(sys.stdin)
except ValueError:
    d = {}
ch = d.get("choices") if isinstance(d, dict) else None
txt = ""
if cod == "200" and isinstance(ch, list) and ch and isinstance(ch[0], dict):
    m = ch[0].get("message")
    txt = (m.get("content") if isinstance(m, dict) else "") or ""
if txt.strip():
    print("OK " + nome + " em " + seg + " s, respondeu: " + lim(txt.strip())[:40] + " (modelo: " + lim(d.get("model", "?"))[:60] + ")")
    sys.exit(0)
e = d.get("error") if isinstance(d, dict) else None
print("FALHOU " + nome + " (HTTP " + cod + "): " + lim(e.get("message") if isinstance(e, dict) else (e or "sem texto na resposta")))
sys.exit(1)' "$cod" "$c" "$(( $(date +%s) - t0 ))" < "$RESP"); rc2=$?
    echo "$saida"
    [ "$rc2" -eq 0 ] || rc=1
  done
  return $rc
}
pronto() {
  if testar codigo; then : > "$D/pronto"; chmod 600 "$D/pronto"; echo "pronto: criado ($D/pronto): o ia passa a usar o OmniRoute do celular quando o PC nao responder"
  else rm -f "$D/pronto"; echo "pronto: NAO criado (o combo codigo nao respondeu); a reserva fica desligada no ia (qualquer arquivo pronto antigo foi apagado)"; return 1; fi
}
status() {
  echo "Instalado: $([ -f "$GW_DIR/bin/omniroute.mjs" ] && echo sim || echo NAO) | ligado: $(no_ar && echo sim || echo nao) | pronto: $([ -f "$D/pronto" ] && echo sim || echo NAO)"
  if no_ar && entrar; then
    if conexoes; then echo "Provedores: $(printf '%s\n' "$CONEX" | cut -d' ' -f2 | sort | tr '\n' ' ')"; fi
    api GET /api/combos
    echo "Combos: $(python3 -I -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    d = []
d = d if isinstance(d, list) else (d.get("combos") or d.get("data") or [])
print(" ".join(sorted(str(c.get("name")) for c in d if isinstance(c, dict))))' < "$RESP")"
  fi
}

case "${1:-ajuda}" in
  ligar) ligar ;;
  desligar) desligar ;;
  status) status ;;
  provedor) shift; provedor "$@" ;;
  tirar) shift; tirar "$@" ;;
  combos) shift; combos "$@" ;;
  apagar-combos) apagar_combos ;;
  testar) shift; testar "$@" ;;
  pronto) pronto ;;
  *) sed -n '2,/^$/{/^#/s/^# \{0,1\}//p}' "$0" ;;
esac
