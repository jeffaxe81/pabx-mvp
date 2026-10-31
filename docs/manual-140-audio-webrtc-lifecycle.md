# Manual 140 — Ciclo de vida do áudio WebRTC e cache PWA

## Objetivo
Registrar o reforço de segurança de sessão do áudio remoto do AXE PABX. A interface compartilha um único elemento `<audio>` entre duas linhas e a consulta/transferência assistida. O encerramento de uma chamada não pode apagar o som de uma chamada diferente nem reabrir uma mídia antiga.

## Mudanças
- A referência da trilha anexada pertence à sua sessão. Em `ended` ou `failed`, somente o áudio daquela trilha é liberado.
- Um evento `track` que chega após encerramento ou de uma conexão substituída não reconecta a mídia.
- Uma trilha que dispara `ended` remove sua própria reprodução somente se ainda estiver vinculada ao elemento; uma substituta é preservada.
- O cache de app shell passa a `telefonista-shell-v4` para substituir a versão antiga de `remote-audio.js`.
- O service worker passa a interceptar apenas as URLs completas do shell via `GET`. Endpoints da API, URLs de outra origem, POST e recursos com query string ficam fora do cache.

## Evidência automatizada
```bash
npm ci --ignore-scripts --no-audit --no-fund
npm run test:node
python3 -m pytest tests/test_service_worker.py
```

Os testes de Node exercitam a liberação por sessão, `track.ended`, eventos atrasados de peer connections antigas e o cache PWA. A validação de CI comprova somente regressões simuladas, **não** mídia SIP/DTLS em operação real.

## Homologação pendente
A issue #61 continua aberta até que o laboratório WebRTC no SHA corrente execute e comprove DTLS, SRTP, mídia nos dois sentidos, CDR e limpeza; repetir após atualização da PWA em navegador real. As 15 provas do gate de produção da issue #173 permanecem pendentes. Não existe autorização de produção.
