# Programas de terceiros

O repositório **não inclui** nenhum programa de terceiros. Os scripts usam ou baixam, das fontes
oficiais, os programas abaixo; cada um tem a sua licença.

| Programa | Para quê | Licença | Fonte |
|---|---|---|---|
| Android SDK Platform-Tools (adb) | falar com o celular | Termos do Android SDK | Google / winget |
| scrcpy | espelhar e comandar o celular, tela extra, webcam | Apache-2.0 | github.com/Genymobile/scrcpy |
| Tailscale | rede particular entre PC e celular | BSD-3-Clause (cliente) | tailscale.com |
| Termux, Termux:API, Termux:Boot | o Linux do celular | GPL-3.0 | F-Droid |
| Qwen Code | o agente do parise-core | Apache-2.0 | github.com/QwenLM/qwen-code |
| OmniRoute | roteador das IAs grátis | ver o projeto | npm / GitHub do autor |
| Ollama | modelos locais no PC | MIT | ollama.com |
| ClamAV | motor do antivírus `guarda` | GPL-2.0 | clamav.net |
| WhisperIME | ditado offline no celular | ver o projeto (código aberto) | F-Droid |
| Handy | ditado offline no PC | MIT | github.com/cjpais/Handy |
| HeliBoard | teclado | GPL-3.0 | F-Droid |
| Fossify (Telefone, Mensagens, Galeria...) | substitutos livres dos apps de fábrica | GPL-3.0 | F-Droid |
| Sunshine e Moonlight | celular como monitor do PC | GPL-3.0 | GitHub dos autores |
| Virtual Display Driver | monitor virtual no Windows | MIT | winget |
| Organic Maps | mapas offline | Apache-2.0 | F-Droid |
| PhotoRec | recuperar arquivos | GPL-2.0+ | cgsecurity.org |
| OBS Studio | estúdio e câmera virtual | GPL-2.0 | obsproject.com |

## Dados de terceiros (não incluídos)

- **Listas de lugares dos mapas**: geradas no seu PC a partir do Censo Escolar do INEP e do Overture
  Maps (licenças por registro). `scripts/mapas-lugares.py` e `scripts/mapas-overture/` baixam e montam.
- **Ícones dos apps**: `scripts/icones-parise-core.py` redesenha no seu PC os ícones instalados no seu
  celular; o resultado tem marcas de terceiros e não é distribuído.
- **Lista de apps perigosos de desativar**: baseada nas listas comunitárias do UAD-ng, que o script
  `cruzar-uad.py` baixa do projeto original.

As versões de cada programa usadas nos testes estão nos documentos de `memoria/`.
