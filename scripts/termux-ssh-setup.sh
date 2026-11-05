#!/data/data/com.termux/files/usr/bin/bash
# Prepara o Termux para SSH ao PC pela Tailscale. Este script so prepara o SSH e NAO instala IA
# (a IA do celular -- Qwen Code, comando ia, OmniRoute de reserva -- vem do celular-kit e esta em
# memoria/GUIA-IA-NO-CELULAR.md). Lembrete: "Claude Code nativo NAO roda no Termux"; para ele
# o celular e terminal (SSH) do Claude Code que roda no PC.
#
# So gera a chave do CELULAR e imprime a publica para voce copiar no PC; nunca toca na chave do
# PC nem em nenhuma credencial existente. Idempotente: rodar de novo nao sobrescreve nada.
#
# Uso (dentro do Termux, nao no PC):
#   bash scripts/termux-ssh-setup.sh [usuario_pc] [ip_tailscale_pc]
#   padrao: usuario_pc=passo, ip_tailscale_pc=100.64.0.1 (IP do PC na Tailscale; memoria/ESTADO.md)
set -euo pipefail

USUARIO_PC="${1:-passo}"
IP_PC="${2:-100.64.0.1}"
CHAVE="$HOME/.ssh/id_ed25519_pc"
CONFIG="$HOME/.ssh/config"

pkg install -y openssh

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

if [ -f "$CHAVE" ]; then
  echo "Chave ja existe em $CHAVE (nada sobrescrito; apague o arquivo a mao se quiser gerar outra)."
else
  echo "Gerando chave ed25519 (pode escolher uma frase secreta ou deixar vazia):"
  ssh-keygen -t ed25519 -f "$CHAVE" -C "termux@a12-$(date +%Y%m%d)"
fi

if [ -f "$CONFIG" ] && grep -q '^Host pc-tailscale$' "$CONFIG"; then
  echo "'pc-tailscale' ja existe em $CONFIG (nada sobrescrito)."
else
  {
    echo ""
    echo "Host pc-tailscale"
    echo "    HostName $IP_PC"
    echo "    User $USUARIO_PC"
    echo "    IdentityFile $CHAVE"
    echo "    IdentitiesOnly yes"
  } >> "$CONFIG"
  chmod 600 "$CONFIG"
  echo "Adicionado 'pc-tailscale' em $CONFIG. Depois de autorizar a chave no PC: ssh pc-tailscale"
fi

echo
echo "===================================================================="
echo "Copie A LINHA INTEIRA abaixo (chave PUBLICA, nunca a privada) para o PC:"
echo "  Se $USUARIO_PC for ADMINISTRADOR do Windows (confira: net user $USUARIO_PC):"
echo "    C:\\ProgramData\\ssh\\administrators_authorized_keys"
echo "    (o Windows OpenSSH IGNORA o authorized_keys da pasta do usuario para administradores)"
echo "  Se NAO for administrador:"
echo "    C:\\Users\\$USUARIO_PC\\.ssh\\authorized_keys (crie a pasta .ssh se nao existir)"
echo "So entra num desses dois arquivos no PC. Nao cole em outro lugar."
echo "===================================================================="
cat "$CHAVE.pub"
