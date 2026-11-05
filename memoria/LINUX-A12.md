# Linux no A12, sem interface (04/11/2026)

Pedido de 28/10, ajustado em 04/11: "não precisa de interface, apenas o linux mesmo como um subsistema", leve e sem consumo quando parado.

**Instalado:** Debian 13 pelo `proot-distro` do Termux, sem root. Comando `linux`, em `~/bin` (fonte: `scripts/celular-kit/bin/linux`).

| Medida (04/11) | Valor |
|---|---|
| Espaço | 184 MB, mais 48 MB do pacote guardado |
| Abrir, rodar um comando e sair | 1,5 s |
| Processos depois de sair | 0 [Certo: `ps` no aparelho] |
| Memória e CPU parado | nada: não fica processo |

## Uso, no Termux
- `linux`: abre o terminal do Debian (`exit` sai).
- `linux -c "comando"`: roda um comando e sai.
- Instalar programa, dentro dele: `apt update` e `apt install <nome>`. Testado com o `file`.
- `linux status`: espaço e o que está rodando. `linux remover`: apaga tudo, pedindo a palavra `APAGAR`.

## Limites
- É `proot`: sem kernel próprio, sem serviços do sistema (`systemd`) e sem Docker. Programa pesa um pouco mais que nativo, porque cada chamada ao sistema passa pelo proot.
- Aberto, conta como processo do Termux: o Android pode encerrá-lo em segundo plano se a memória apertar.
- Interface gráfica não foi instalada, a pedido dele. A pesquisa do Hermes sobre isso segue na pasta dele (`saida\memoria-proposta\05-linux-grafico-a12-atualizado.md`).
- Restauração: `pkg install proot-distro`, `proot-distro install debian`; os programas instalados dentro dele não entram na cópia (`COPIA-E-RESTAURAR.md`).
