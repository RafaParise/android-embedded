# Webcam pelo celular e recuperação de arquivos (03/11/2026)

Pedido do Rafael: transformar o telefone em webcam com o que ele já tem, e um recuperador de arquivos excluídos no PC que funcione de verdade; tudo de código aberto.

## Webcam

**Como usar:** dois cliques em `Webcam Frontal (aula)` ou em `Estudio - Webcam do Celular` (traseira), na área de trabalho. Na chamada, escolher a câmera "OBS Virtual Camera". Enter na janela preta desliga. Com a webcam ligada, a tela do celular fica escura e sem bloqueio desde 04/11 (`TELA-APAGADA.md`); o `keyevent 223` de antes bloqueava em 15 s. Provado em 04/11: 152 quadros em 1280x720, traseira, com a tela escura; frontal aberta a pedido do Rafael em aula, sem eu olhar a imagem.

**Com ou sem cabo, sozinho:** usa o cabo se estiver ligado; senão o Wi-Fi local; senão a Tailscale. Depois de reiniciar o celular, o sem fio pede o cabo uma vez.

**Como funciona:** scrcpy 5.0.1 abre a câmera direto pelo Android (sem app no celular) e a câmera virtual do OBS 32.1.2 entrega a imagem aos programas. Os dois já estavam no PC.

- **O Open Camera não entra:** ele não transmite vídeo. O scrcpy usa a mesma câmera, mas sem os ajustes do Open Camera [Certo: documentação do scrcpy]. A webcam virtual do próprio scrcpy só existe no Linux [Certo: `doc/v4l2.md`]; por isso o OBS.
- **Medido no aparelho em 03/11 [Certo], 720p:** cabo 28,5 fps; Wi-Fi local 28,7; Tailscale 28,3; com a tela do celular apagada 28,3. **O sem fio empatou com o cabo** nos testes curtos, com o Wi-Fi a -50 dBm. Prova de ponta a ponta lendo a câmera virtual como um programa de chamada: passou com cabo e sem fio. A imagem nunca foi olhada nem guardada.
- **Por que 720p a 30 fps:** cabe inteira no monitor de 1440x900, sem reduzir a imagem na captura, e pesa menos. 1080p também funciona (`--tamanho 1920x1080`), mas a janela segue limitada; **1440p falha** no encoder do A12.
- **Tela do celular apagada durante o uso**, porque poupa bateria e calor: o USB do PC nem sustenta a carga. Sem fio gasta a bateria toda.
- O OBS fica intacto: perfil e coleção próprios, e o `user.ini` volta ao que era ao desligar [Certo].

**Limites:**
- Porta 5555 do adb fica aberta até reiniciar o celular, em qualquer rede, inclusive na da escola. Só entra quem tem a chave deste PC ou for aceito na tela do celular; **se aparecer "Permitir depuração", recuse**. Fechar: `python scripts\webcam-celular.py fechar-sem-fio`.
- Nos dados móveis a câmera cai para 2 Mbit/s, cerca de 900 MB por hora, e avisa antes.
- Só vídeo: o som da chamada vem do microfone do JBL.
- A janela do scrcpy pode ficar atrás das outras, mas não minimizada. Open Camera e webcam não usam a câmera ao mesmo tempo.
- Não testado: uso longo sem fio com a tela apagada, em que a economia de energia do Android pode atrapalhar; e imagem com o celular em pé.
- O DroidCamX (`com.dev47apps.droidcamx`, fechado) segue instalado até o Rafael decidir.

## Recuperação de arquivos

**Como configurar na janela, alinhado a estes discos:** escolher o disco; a partição NTFS; opção **Free** (só o espaço livre: muito mais rápido e o certo para arquivo excluído); em File Formats, marcar só o tipo procurado (jpg, pdf, zip cobre docx, xlsx e pptx, mp4...), porque menos tipos dá menos lixo; e destino em OUTRO disco. Por comando em volume `\\.\D:` ele não reconhece o NTFS e varre o disco inteiro [Certo: testado por 60 s, só leitura]: use a janela.

**Instalado:** TestDisk e PhotoRec 7.2 em `C:\Projetos\ferramentas\testdisk\testdisk-7.2` (76 MB), licença GPL-2.0, do site oficial, com SHA-256 conferido contra `cgsecurity.org/testdisk_sha256.txt` [Certo]. Abrir: dois cliques em `scripts\recuperar-arquivos.cmd` (pede administrador; é a interface gráfica do PhotoRec).

**Por que este:** é o recuperador aberto mais citado, ativo no GitHub (2,6 mil estrelas, commit em 10/2026) [Certo: API do GitHub]. Mas as listas de "melhores" são quase todas de vendedores de software, e a análise mais neutra achada, da [TechRadar](https://www.techradar.com/reviews/testdisk-and-photorec), diz que nenhum dos dois recuperou tudo. Não há como garantir recuperação.

- **PhotoRec** acha arquivos pelo conteúdo, mesmo com sistema de arquivos danificado: **perde nomes e pastas**, e devolve muita coisa.
- **TestDisk** recupera partição perdida e, em NTFS, lista excluídos com nome (menu Advanced > Undelete) [Provável: documentação; não testei].

**Prova em 03/11 [Certo]:** imagem de disco com PNG, PDF e ZIP soltos, sem sistema de arquivos: os 3 voltaram com md5 igual. `testdisk_win /list` enxerga os 5 discos. Não testado: disco de verdade e Undelete com nomes.

**Limite que nenhum programa resolve:**
- `C:` é SSD com TRIM ligado [Certo: `fsutil`] e sem cópias de sombra [Certo: `vssadmin`]: arquivo excluído ali costuma ser apagado de fato pelo próprio disco logo depois, e a chance é baixa [Provável: comportamento conhecido do TRIM; não medi].
- `D:` e `G:` são HD: chance boa se nada foi gravado por cima [Provável]. `E:` é externo, tipo não identificado.
- **Regra de ouro:** parar de usar o disco e salvar o recuperado em OUTRO disco. Hoje há pouco espaço: `C:` 50 GB, `D:` 15 GB, `E:` 31 GB, `G:` 0 GB livres [Certo]; uma recuperação grande pode não caber.

**Ordem ao perder um arquivo:** Lixeira; `Backup-PC` no Google Drive (nunca apaga nada); GitHub; só depois o PhotoRec.

## Antivírus

Em `ANTIVIRUS.md`.

## 06/11: aula, gravação e live, de perto ou de longe
- Atalho "Celular no OBS" (área de trabalho, serve pelo aFreeRDP) ou, do celular, `cel obs camera|frontal|tela|gravar|gravar-tela|parar-gravacao|live|parar-live|desligar|status`.
- A câmera virtual liga sozinha, também com o OBS do Estúdio aberto (05/11 ela estava desligada na aula e o site só mostrava o logo).
- Site da aula sem câmera ou sem compartilhar a tela: `pwsh -File scripts\pc-permissoes-aula.ps1` (estado) e `-Aplicar` como administrador.
- A TELA do celular: `--tela` (scrcpy `--video-source=display`, sem controle pelo PC); `--som` leva o som do aparelho (na câmera, o microfone, que fica mudo sem fone).
- Gravações em `D:\Vídeos\Celular OBS` (MP4 híbrido, AMF). Live: destino e chave no OBS do PC, perfil "Webcam Celular" (o Rafael configura uma vez).
- Aviso fixo na barra do celular enquanto estiver no OBS (câmera, tela, GRAVANDO, AO VIVO), com botões Desligar e Parar gravação.
- Limites: o OBS 32.1.2 cai ao fechar (o script já contorna); nos dados, ~900 MB por hora a 2 Mbit/s.
