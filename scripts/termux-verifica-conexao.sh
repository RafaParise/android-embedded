#!/usr/bin/env bash
# Confere se o Termux tem internet de verdade (nao so Wi-Fi conectado sem saida): mesmo
# padrao do Project NOMAD (memoria/nuvem/projeto-nomad.md) -- tenta o endpoint da
# Cloudflare primeiro, com um 2o endpoint como reserva, timeout curto para nao prender
# um script de IA offline esperando. So leitura (GET que descarta o corpo; nao e HEAD); nunca muda nada no aparelho.
#
# Saida: 0 = online, 1 = offline, 2 = nem curl nem ping disponiveis (nao deu pra testar).
# Uso: bash scripts/termux-verifica-conexao.sh [--timeout N]
set -u

TIMEOUT=3
if [ "${1:-}" = "--timeout" ] && [ -n "${2:-}" ]; then
    TIMEOUT="$2"
    case "$TIMEOUT" in
        ''|*[!0-9]*|0)
            echo "Uso: bash scripts/termux-verifica-conexao.sh [--timeout N]  (N = segundos, inteiro maior que zero)" >&2
            exit 2 ;;
    esac
fi

testa_com_curl() {
    curl -fsS --max-time "$TIMEOUT" -o /dev/null "$1"
}

testa_com_ping() {
    ping -c 1 -W "$TIMEOUT" "$1" >/dev/null 2>&1
}

if command -v curl >/dev/null 2>&1; then
    for alvo in "https://1.1.1.1" "https://8.8.8.8"; do
        if testa_com_curl "$alvo"; then
            echo "ONLINE (curl, $alvo)"
            exit 0
        fi
    done
    echo "OFFLINE (curl sem resposta nos 2 alvos)"
    exit 1
elif command -v ping >/dev/null 2>&1; then
    for alvo in 1.1.1.1 8.8.8.8; do
        if testa_com_ping "$alvo"; then
            echo "ONLINE (ping, $alvo)"
            exit 0
        fi
    done
    echo "OFFLINE (ping sem resposta nos 2 alvos)"
    exit 1
else
    echo "NAO TESTADO: nem curl nem ping disponiveis no Termux"
    exit 2
fi
