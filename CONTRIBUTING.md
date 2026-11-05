# Como contribuir

Obrigado por querer ajudar! Leia também o [código de conduta](CODE_OF_CONDUCT.md).

## Relatar um problema

1. Rode `python scripts/auditoria.py` (só lê) e `python scripts/saude.py`: muitas vezes eles já dizem
   o que está errado.
2. Abra uma issue com o modelo **Relatar um problema**: modelo do celular e versão do Android, o script
   e o comando, o que esperava e o que aconteceu.

**Nunca cole** nas issues: e-mail, número de telefone, nomes de contatos, nome da sua rede Wi-Fi, o seu
IP da Tailscale, chaves ou tokens. As issues são públicas. Mascare antes (`***`).

## Sugerir uma melhoria

Modelo **Sugerir uma melhoria**: o que você quer, por que ajuda e como imagina. Antes, procure em
`memoria/RADAR-DESEMPENHO.md`: muita ideia de desempenho já foi testada, com o resultado.

## Contribuir com código

| Regra | Por quê |
|---|---|
| **Sem root** | O projeto existe para quem não pode ou não quer desbloquear o aparelho |
| **Simular é o padrão** (`--aplicar` para agir) | Ninguém perde nada por rodar um script para ver |
| **Todo passo tem desfazer**, escrito no comentário do topo | Celular de trabalho não pode ficar quebrado |
| **Python com a biblioteca padrão** sempre que der | Roda em qualquer PC e no Termux sem instalar nada |
| **Teste com ADB falso** em `scripts/tests/` | Ninguém precisa de um celular para conferir a mudança |
| **Português do Brasil** em código, comentários e textos | O projeto também é material de estudo |
| **Fonte oficial e hash conferido** para todo download | Segurança de quem usa |

Antes de enviar: `python -m pytest scripts/tests -q` sem falhas, e o guia da função atualizado.
