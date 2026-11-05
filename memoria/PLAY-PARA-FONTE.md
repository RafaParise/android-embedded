# Apps da Play Store: o que dá para trocar pela fonte (03/11/2026)

Pedido do Rafael: "o que puder tirar da playstore e baixar da fonte eu quero", para evitar rastreio e ter apps melhores.

**Medido em 03/11 [Certo: `pm list packages -3 -i` e índice assinado do F-Droid, 4.933 pacotes]:** 74 apps de terceiros: 38 da Play, 27 instalados pelo cabo, 7 pelo F-Droid e 2 pelo instalador do sistema. Dos 38, **só o Tailscale existe no F-Droid**.

## Limite que precisa ficar claro

Baixar de outro lugar não tira o rastreio que está dentro do próprio app: um banco fechado rastreia igual. E para app fechado, "a fonte" costuma ser site espelho de APK, risco maior que o da Play. Banco e governo ainda podem recusar rodar fora da Play [Provável: verificação de integridade; não testei app a app]. Por isso esses ficam.

## Os 38

| Grupo | Apps | O que fazer |
|---|---|---|
| Existe na fonte | Tailscale (`com.tailscale.ipn`) | Decisão do Rafael, abaixo |
| Banco, pagamento, benefício | Bradesco next, Santander, Caixa Tem, Mercado Pago, Pluxee/Sodexo, Raízen Acelera | Ficam: sem fonte confiável |
| Governo e serviço | Gov.br, CNH, Carteira de Trabalho, e-Título, Poupatempo, Sou SP, SP190, Sala do Futuro (2), Jacad, MK Solutions, Sabesp, Elektro, Vivo, MobileBus, Piracicabana, 99 | Ficam: sem fonte confiável |
| Fechados que ele usa | WhatsApp Business, Claude, GitHub, Google Docs, Teams | Ficam; Teams e similares seguem sem permissões |
| Sem uso, já desativados | Maps Go, Gemini, Contact Keys, Steam, entre outros (`pm list packages -d`) | Podem sair de vez com o sim dele |
| Têm substituto | DroidCamX (scrcpy), Gboard (HeliBoard, já em uso) | Decisão do Rafael. O `lote-pacotes.py` protege todo teclado: Gboard exige o sim dele |
| Google sem pedido | SafetyCore, Android Device Policy (sem dono no aparelho, parado) | Podem ser desativados com o sim dele |
| Sistema | Verificador do Google (`com.google.android.verifier`) | Fica |

Os nomes de apps vêm dos pacotes; "Pluxee", "Jacad" e "MK Solutions" foram deduzidos [Provável].

## Tailscale: as opções

- **F-Droid** 1.104.4, BSD-3-Clause, marcado com a antifunção `Tracking` no próprio índice [Certo]. Assinatura diferente da instalada [Certo: comparada]: exige desinstalar, entrar de novo na conta (só ele) e refazer VPN sempre ativa e saída pelo PC. O F-Droid atualiza sozinho.
- **Site oficial** `pkgs.tailscale.com/stable` 1.104.5: não se atualiza sozinho, e a própria página recomenda a Play [Certo]. Não vale a pena.
- **Recomendação:** F-Droid, porque é o pedido dele, com o celular em casa, no cabo, e sem chamada em andamento. O ganho é pequeno: é o mesmo cliente e também com aviso de rastreio.
- **04/11:** ele perguntou qual a vantagem. Resposta: é o mesmo programa, com o mesmo aviso de rastreio; o único ganho é não depender da Play, que fica de qualquer jeito por causa dos bancos. Recomendo não trocar; troca só se ele pedir. Isto substitui a recomendação acima.

Sem a Play de todo: inviável, porque os apps de banco e governo dependem dela. E `com.android.vending` está na lista do que nunca se desativa.
