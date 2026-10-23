# Chamadas internas SIP/TLS com SRTP — plano de implementação

> **For agentic workers:** Use superpowers:executing-plans; continuar o programa já autorizado, com testes antes do código e revisão independente ao concluir.

**Goal:** Comprovar o marco 5 do programa: chamadas internas com estabelecimento, desligamento e CDR em dois tenants, nas duas direções.

**Architecture:** Estender o laboratório descartável validado na PR #53 com o modo opt-in `--calls`. Ramais adicionais serão gerados pelo gerador real do painel a partir do mesmo commit. Dois clientes SIP/TLS trocam mídia PCMU protegida por SDES/SRTP através do Asterisk; o relatório contém somente verificações e contadores.

**Tech Stack:** Python 3.12, stdlib, pylibsrtp 0.12.0 (somente testes), Docker, Asterisk 22.11.0 fixado por digest.

**Spec:** docs/plano-16-semanas-pabx.json, marco 5; comprovação parcial de RTP/SRTP do marco 6, que continua pendente de WSS/DTLS.

## Global Constraints

- Servidor e mídia somente em loopback; TLS verifica CA/nome; sem chaves, SDP, áudio ou segredos nos artefatos públicos.
- Não alterar arquivos do operador nem implantar em produção; manter operational_go_authorized=false.
- Ramais t1/t2 usam a mesma numeração e geradores existentes; testar 1202→1201 e 1201→1202 em cada tenant.
- Sucesso exige sinalização positiva, encerramento dos dois lados, CDR ANSWERED com tenant/contexto corretos e mídia verificada nos dois sentidos.
- SDES/SRTP não equivale à homologação DTLS/WebRTC nem de isolamento funcional completo.

## Review Focus

- SDP sem criptografia, chave inválida, múltiplas mídias e destino fora de loopback devem ser recusados.
- Nenhum contador ou chave SDP isolado pode aprovar áudio sem pacotes recebidos e autenticados.
- ACK de 401 e de 200, CSeq e Call-ID corretos, NOTIFY assíncrono, BYE e prazos limitados.
- Falha de thread/cliente não pode deixar sockets, containers ou gravações persistentes.
- CDR/gravação de outro teste não podem aprovar a chamada atual.

### Task 1: Mídia segura

**Files:** lab/srtp_media.py; scripts/tests/test_srtp_lab.py; lab/requirements.txt; tests/requirements.txt.
**Interfaces:** SrtpMedia.offer() -> bytes; negotiate(sdp: bytes) -> None; exchange(expected_payload, barrier) -> dict; close().

- [ ] Escrever e observar RED para SDP inválido/inseguro e troca real SRTP em sockets UDP locais.
- [ ] Implementar perfil AES_CM_128_HMAC_SHA1_80, PCMU, validação de destino/chave e métricas sem material de chave.
- [ ] Verificar tráfego real nos dois sentidos e rejeição criptográfica de chave incorreta.

### Task 2: Sinalização e chamada completa

**Files:** lab/call_peer.py; lab/call_lab.py; lab/asterisk_lab.py; scripts/tests/test_sip_call_lab.py.
**Interfaces:** CallPeer.invite(number, media), answer(media), hangup(), wait_for_bye(); exercise_calls(container_id, prepared, source) -> relatório.

- [ ] Escrever testes de ACK/autenticação/dialog e de reconhecimento estrito de CDR.
- [ ] Gerar dois ramais por tenant, realizar quatro chamadas com Asterisk real e correlacionar CDR e arquivos criados no teste.
- [ ] Incluir modo --calls sem alterar os aceites do laboratório de registro padrão.

### Task 3: CI e entrega

**Files:** .github/workflows/asterisk-lab.yml; docs/manual-102-chamadas-reais.md; docs/plano-16-semanas-pabx.json.

- [ ] Rodar oito suítes Python e laboratório real de chamadas, corrigindo causas de falhas observadas.
- [ ] Revisão independente e correções importantes com regressões RED→GREEN.
- [ ] Publicar PR empilhada sobre #53, evidências CI e somente os marcos efetivamente comprovados.
