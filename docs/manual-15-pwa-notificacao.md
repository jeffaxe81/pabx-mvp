# Manual 15 — PWA instalável com notificação nativa (backlog #9)

## O que é
A interface web do telefonista agora pode ser **instalada** como um
app (ícone na área de trabalho/tela inicial, abre em janela própria
sem barra de endereço do navegador), e toca uma **campainha de
verdade** + mostra uma **notificação nativa do sistema operacional**
quando uma chamada chega — mesmo que a aba esteja em segundo plano.

## O que foi adicionado
- **`webphone/manifest.json`**: nome, ícones, `display: standalone` —
  é isso que faz o navegador oferecer "Instalar aplicativo"
- **`webphone/icons/`**: ícones PNG gerados (192px, 512px, e uma
  versão "maskable" pra não cortar feio em launchers Android)
- **`webphone/service-worker.js`**: cacheia o essencial da interface
  (HTML/manifest/ícones — nunca dados dinâmicos como fila ou
  gravações) e é quem tem permissão de mostrar notificação do sistema
  operacional quando a página avisa de uma chamada recebida
- **Campainha via Web Audio** (`startRingtone`/`stopRingtone` em
  `index.html`): dois beeps a cada 2 segundos, gerados por código —
  sem depender de nenhum arquivo de áudio externo. Toca em **qualquer**
  chamada recebida (linha 1 ou linha 2), para assim que atendida ou
  recusada

## Como instalar
No Chrome/Edge (desktop ou Android), abra a interface web e:
- **Desktop**: ícone de instalação na barra de endereço, ou menu → 
  "Instalar Telefonista..."
- **Android**: menu do navegador → "Adicionar à tela inicial" /
  "Instalar app"
- **iOS/Safari**: compartilhar → "Adicionar à Tela de Início" (Safari
  tem suporte mais limitado a PWA, especialmente notificações — ver
  limitações abaixo)

## Como habilitar a notificação nativa
Na primeira vez que a telefonista conecta (clica "Conectar"), o
navegador pede permissão de notificação automaticamente. Se ela negar
por engano, precisa liberar manualmente nas configurações do site no
navegador — não tem como pedir de novo programaticamente depois de
uma negação.

## Como testar manualmente
1. `docker compose up -d`, acesse a interface, conecte normalmente
2. Aceite a permissão de notificação quando o navegador perguntar
3. De outro ramal, disque `1000` (ou o ramal direto da telefonista)
4. Confirme: toca a campainha (dois beeps repetidos) e aparece uma
   notificação do sistema operacional com "Chamada recebida"
5. Coloque a aba em segundo plano (troque de aba) **antes** de
   atender — confirme que a notificação aparece mesmo assim
6. Clique na notificação — deve focar a aba/janela da interface
7. Atenda ou recuse — confirme que a campainha para imediatamente
8. Teste a instalação: instale como app (ver seção acima), feche e
   reabra pelo ícone instalado — deve abrir sem a barra de endereço

## Teste automatizado
- `tests/test_pwa_manifest.py` — campos obrigatórios do manifest,
  ícone de 512px presente, ícone maskable presente, arquivos de ícone
  existem de verdade no disco
- `tests/test_service_worker.py` — ciclo de vida install/activate,
  cache restrito ao app shell (não intercepta fila/gravações/métricas
  em tempo real), listener de mensagem da página, notificação com
  `requireInteraction`/`tag`/`renotify` corretos, clique foca a janela
- `tests/test_webphone_html.py` — manifest e service worker linkados
  no HTML; toda chamada recebida dispara campainha + notificação;
  campainha para ao atender ou recusar

## Limitações conhecidas (honestidade técnica)
- **Service worker exige HTTPS** (ou `localhost`) pra registrar. Com
  o certificado self-signed deste projeto (manual 02), o navegador
  pode continuar bloqueando o registro do service worker mesmo depois
  de você aceitar o aviso de certificado da página — nesse caso, a
  interface funciona normalmente, só sem PWA/notificação nativa, até
  trocar por um certificado válido
- **Isso não é Push (não funciona com o navegador fechado)** — a
  notificação só aparece com a aba/app aberto em segundo plano, não
  com o navegador completamente fechado. Notificação de verdade com
  app fechado exigiria a Push API com um servidor de push e chaves
  VAPID — fora do escopo deste MVP
- **iOS/Safari tem suporte bem mais limitado** a service worker e
  notificação em PWA instalado — funciona de forma mais confiável em
  Chrome/Edge (desktop ou Android)
- **Nenhum teste automatizado executa o service worker de verdade**
  (isso exigiria um navegador real) — os testes são verificação
  estática do código-fonte, no mesmo padrão já usado pra outras partes
  que dependem de ambiente externo (AMI, tronco TDM)
- A campainha usa Web Audio, que em alguns navegadores só toca depois
  de alguma interação prévia do usuário na página (política de
  autoplay) — como a telefonista já precisou clicar "Conectar" antes,
  isso normalmente já é suficiente, mas vale testar no navegador real
  que for usar
