# Chamadas internas reais — plano de implementação

> **For agentic workers:** Use superpowers:executing-plans. Continuidade do programa aprovado de 16 semanas; execução nesta sessão.

**Goal:** Comprovar chamadas internas, desligamento e CDR em dois tenants, com mídia SRTP bidirecional verificada.

**Architecture:** Estender o laboratório descartável e o cliente TLS existentes. Usar o gerador real para ramais seguros adicionais de t2/t3; manter os contextos e dialplans do repositório. Um cliente limitado a loopback negocia SDES e verifica pacotes PCMU por libsrtp, sem exportar chaves, mensagens SIP ou áudio.

**Tech Stack:** Python 3.12, pylibsrtp 1.0.0 (somente laboratório), OpenSSL, Asterisk Docker fixado por digest, GitHub Actions.

**Spec:** docs/plano-16-semanas-pabx.json, marco 5 e parte SRTP do marco 6; docs/manual-73-gates-homologacao.md.

## Global Constraints

- Sem implantar em produção ou conceder GO; propostas continuam sujeitas a revisão.
- Configuração exportada do Git; segredos efêmeros somente em memória/diretório privado.
- Todas as mensagens SIP correlacionadas por diálogo/transação; prazos limitados.
- Mídia somente em loopback, AES_CM_128_HMAC_SHA1_80; sem implementação criptográfica própria.
- Não concluir o marco 6 sem WSS/DTLS; nem o marco 8 com apenas tentativas de discagem cruzada.

## Review Focus

- SDP sem criptografia, host externo, porta inválida ou chave malformada deve falhar.
- SIP final de outra transação e BYE de outro diálogo devem falhar.
- Pacote adulterado, repetido ou de outra chamada nunca comprova mídia.
- CDR deve concordar com origem, destino, contexto, canais e tenant; somente ANSWERED é aprovação.
- Falhas de chamada devem continuar limpando sockets e container, sem divulgar conteúdo privado.

### Task 1: Negociação e mídia SRTP

**Files:** lab/srtp_media.py; scripts/tests/test_srtp_media.py.

**Interfaces:** SrtpMedia().offer(), .negotiate(sdp), .exchange(other), .close(); parse_sdp(sdp) valida endereço, perfil, codec e chave.

- [ ] Testar SDP seguro/recusas, troca UDP real bidirecional e rejeição de adulteração/replay; observar RED.
- [ ] Implementar negociação SDES e envio/recebimento com pylibsrtp; verificar GREEN.

### Task 2: Diálogos e execução Asterisk

**Files:** lab/sip_calls.py; lab/call_checks.py; lab/asterisk_lab.py; scripts/tests/test_sip_calls.py; scripts/tests/test_call_checks.py; .github/workflows/asterisk-lab.yml.

**Interfaces:** CallPeer(SipTLS) inicia/atende/desliga diálogo autenticado; exercise_calls(container, prepared, report) retorna verificações sanitizadas; summarize(checks, calls=False) exige conjunto completo.

- [ ] Testar INVITE/Digest/ACK/BYE em socket real com servidor controlado e correlação negativa; observar RED.
- [ ] Gerar ramais privados via conf_generator; executar seis chamadas (ida/volta em t1/t2/t3), comparar CDR e mídia; verificar GREEN.
- [ ] Publicar branch e PR dependente da #53; executar CI real e corrigir causas observadas.

### Task 3: Evidências e revisão

**Files:** docs/manual-102-chamadas-srtp-reais.md; docs/README.md; README.md; docs/plano-16-semanas-pabx.json.

- [ ] Rodar as oito suítes Python e Node, obter CI real do SHA publicado.
- [ ] Revisão independente do conjunto, corrigir achados importantes com regressão.
- [ ] Registrar somente marcos aceitos, evidências e limites; atualizar PR com resultado concreto.
