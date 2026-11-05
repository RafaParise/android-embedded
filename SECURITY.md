# Política de segurança

## Versões com suporte

Só a versão mais recente (a da página [Releases](https://github.com/RafaParise/android-embedded/releases/latest))
recebe correções.

## Como relatar uma falha de segurança

**Não abra uma issue pública** para falha de segurança. Use o relato particular do GitHub: aba
**Security** > **Report a vulnerability**. A mensagem chega só ao responsável pelo projeto.

Conte, se possível: o script e a versão, o que um atacante consegue fazer e de onde (o mesmo PC, a mesma
rede, a tailnet, a internet) e o passo a passo para reproduzir. O projeto é mantido por uma pessoa: a
primeira resposta pode levar alguns dias.

## Como o projeto se protege (para quem vai testar)

- **Ponte do PC** (`scripts/ponte-pc.py`, porta 20130): escuta só no próprio PC e é exposta apenas à
  tailnet (Tailscale). Exige token; o pareamento usa código de uso único que vence em 1 hora;
  `-NovoToken` revoga. As ações remotas são uma **lista fechada** (`ACOES_PC`), sem argumento livre, e
  as entregas do celular chegam marcadas "NÃO REVISADO", nunca gravadas direto no projeto.
- **OmniRoute (20128) e Ollama (11434)**: abertos só para a tailnet, nunca para a internet.
- **ADB pela porta 5555**: aceita só chaves já autorizadas no aparelho; cai ao reiniciar. Risco
  documentado no guia 4.
- **Matrix** (Qwen Code no Termux): lista de negados no `settings.json` que bloqueia o irreversível
  mesmo no modo sem confirmação; o `cel tocar` recusa botões sem volta.
- **Navegador de teste** (`scripts/navegador.py`): recusa endereço interno, inclusive por redirecionamento.
- **Publicação** (`scripts/publicar.py`): só uma lista permitida sai, com troca dos dados pessoais e
  varredura de segredos; se sobrar qualquer coisa, nada é publicado.
