# WSS e DTLS-SRTP reais no Webphone — plano

> **For agentic workers:** Use superpowers:executing-plans. Continuidade autorizada do marco 6, execução nesta sessão com revisão independente ao final.

**Goal:** Validar o telefone web real em Chromium contra Asterisk, com registro WSS, chamadas nos dois sentidos, DTLS-SRTP e áudio sintético recebido pela interface.

**Architecture:** Reusar o laboratório Docker, configurações versionadas, credenciais efêmeras e limpeza por propriedade. Playwright opera as telas reais; somente a entrada de microfone é um tom sintético. Verificar o certificado WSS por CA em Python e fixar no perfil Chromium somente a chave pública efêmera esperada. Bloquear requisições externas; nenhum STUN/TURN externo ou relatório com SDP, credenciais ou áudio.

**Tech Stack:** Python 3.12, Node, Playwright 1.56.1, JsSIP 3.10.1, esbuild 0.25.11 e Asterisk 22.11.0 fixado por digest.

**Spec:** docs/plano-16-semanas-pabx.json, marco 6; Manual 73 e Manual 102.

## Global Constraints

- Sem implantação ou GO; PR dependente da #54 e sujeita a revisão.
- Não alterar nem simular WebSocket, SIP, ICE, DTLS, RTP ou estatísticas de mídia.
- Entrada sintética em vez de microfone físico; não alegar qualidade acústica/headset ou redes externas.
- Chromium não usa `ignoreHTTPSErrors` nem bypass global de certificado; exceção restrita ao SPKI efêmero, com verificação de CA e hostname separada e controle negativo.
- Configurações/HTML extraídos do SHA; segredos em arquivo privado 0600, sem linha de comando, screenshot, trace ou console bruto.

## Review Focus

- Página deve carregar JsSIP real e versionado; dependência indisponível não pode virar aprovação por interceptação simulada.
- Confirmação de chamada não basta: exigir DTLS conectado, cifra SRTP, contadores RTP e tom remoto distinto.
- Evento `track` anterior à confirmação não pode deixar o áudio remoto desconectado.
- Campos/objetos malformados, relatório incompleto ou subprocesso com falha bloqueiam conclusão.
- Navegador/servidor/processos devem encerrar; não tocar containers de terceiros nem publicar material privado.

### Task 1: Dependência do telefone web e testes locais

**Files:** package.json, package-lock.json, scripts/build_webphone_sip.cjs, webphone/vendor/, webphone/index.html, tests/.

**Interfaces:** `npm ci --ignore-scripts`; `node scripts/build_webphone_sip.cjs [--check]` produz/compara um bundle local JsSIP, sem dependência de CDN durante chamadas.

- [x] Reproduzir disponibilidade da dependência atual; testes de carregamento e bundle real em navegador.
- [x] Gerar bundle com versão e licença, testar regressões da interface.

### Task 2: Laboratório WSS e WebRTC

**Files:** lab/webrtc_checks.py, lab/webrtc_browser.cjs, lab/asterisk_lab.py, scripts/tests/, .github/workflows/asterisk-lab.yml.

**Interfaces:** `--webrtc` exige `--calls`; acrescenta aceites explícitos de WSS/DTLS/áudio/CDR nas seis chamadas de t1/t2/t3. O runner Node recebe somente caminho privado e escreve JSON sanitizado; Python valida esse JSON antes de incorporá-lo ao relatório.

- [x] Escrever testes de verificação WSS/relatório incompleto/negação de certificado; observar RED→GREEN.
- [x] Operar a UI real, comparar tom remoto e obter estatísticas reais de transporte; executar em CI.
- [x] Corrigir causas comprovadas em runtime, preservando critérios de aceite e acrescentando regressões.

### Task 3: Revisão, evidências e entrega

**Files:** docs/manual-103-webrtc-real.md, docs/README.md, README.md, docs/plano-16-semanas-pabx.json.

- [x] Rodar oito suítes Python, Node/navegador e laboratório real no SHA publicado.
- [x] Revisão independente, corrigir achados importantes com regressões.
- [x] Registrar somente aceites comprovados, verificar árvore publicada e apresentar PR para revisão.

## Resultado verificado

- Código publicado em `27025101bc4a39e09d9d666b6afb093aedd090f4`.
- CI real 40008037655: 22/22 de registro, 70/70 de chamadas TLS/SDES e 138/138 do Webphone WSS/DTLS.
- CI estática 40008037783: oito suítes Python aprovadas (1.370 testes).
- CI de interface 40008037781: 19 Node e 24 Chromium aprovados.
- Revisão independente: quatro achados importantes corrigidos com regressões; nenhum crítico.
- Diagnóstico de execução: permissão nativa ICE, nomes IANA SRTP e certificado DER/SDP para estatística ausente.
- Marco 6 concluído, 6/16 (37,5%); revisão via PR #56, sem integração automática em main ou GO.
