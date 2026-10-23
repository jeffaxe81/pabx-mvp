# Laboratório real Asterisk — plano de implementação

> **For agentic workers:** Use superpowers:executing-plans. Continuar o plano aprovado de 16 semanas, sem novas perguntas de escopo.

**Goal:** Executar o próximo aceite pendente do programa: Asterisk real isolado e registros SIP/TLS autenticados de t1, t2 e t3+.

**Architecture:** Manter Python 3.12 e os geradores/configurações existentes. Um laboratório descartável copia as configurações para uma pasta privada, gera certificados e senhas efêmeros e sobe somente um Asterisk Docker no runner CI. O cliente SIP fala TLS e Digest com o servidor real; os relatórios públicos contêm somente resultados, versão, SHA e digest da imagem.

**Tech Stack:** Python stdlib, pytest, OpenSSL, Docker e GitHub Actions.

**Spec:** docs/plano-16-semanas-pabx.json, marcos 3–4; docs/manual-73-gates-homologacao.md.

## Global Constraints

- Sem alterar arquivos de configuração do operador, implantar em produção ou conceder GO.
- Sem publicar credenciais, chaves privadas, áudio ou mensagens SIP completas.
- Nenhum marco real será concluído sem execução CI verificável.
- TLS verifica a CA e o nome do servidor; o laboratório escuta somente loopback.
- WSS/DTLS e homologação física continuam sujeitos aos seus aceites específicos.

## Review Focus

- Fragmentação e agrupamento de mensagens SIP no mesmo fluxo TCP/TLS.
- Desafio de autenticação recusado, usuário incorreto e respostas de outra transação.
- Falha de inicialização, timeout e limpeza sem afetar containers preexistentes.
- Relatórios não podem transformar ausência de dependência ou teste em aprovação.
- Configurações copiadas devem manter a herança Asterisk real e contextos dos tenants.

### Task 1: Protocolo e preparação privados

**Files:** lab/sip_tls.py; lab/asterisk_lab.py; scripts/tests/test_real_lab_helpers.py.

**Interfaces:** SipTLS(host, port, ca_file, username, password).register() retorna código final e challenge verificado; prepare(root, destination) retorna credenciais em memória e caminhos privados.

- [ ] Escrever testes de framing, Digest e preparação; observar RED.
- [ ] Implementar cliente limitado ao laboratório loopback, com timeout e framing limitado.
- [ ] Rodar testes focados e verificar segredos/arquivo original preservado.

### Task 2: Runtime e registros reais

**Files:** lab/asterisk_lab.py; .github/workflows/asterisk-lab.yml.

**Interfaces:** python3 -m lab.asterisk_lab --report PATH inicia runtime isolado, verifica CLI e registros t1/t2/t3+, sempre limpa e sai 1 se qualquer cenário falhar.

- [ ] Configurar a execução CI real, sem simular Asterisk.
- [ ] Executar no Asterisk; reproduzir erros de configuração antes de corrigi-los.
- [ ] Corrigir a causa comprovada e rodar novamente.

### Task 3: Evidências e entrega

**Files:** docs/manual-101-laboratorio-sip-real.md; docs/README.md; docs/plano-16-semanas-pabx.json.

- [ ] Rodar as oito suítes Python, Node e CI real.
- [ ] Revisar o diff e corrigir falhas importantes com regressões.
- [ ] Publicar PR e registrar apenas aceites comprovados; demais cenários continuam pendentes.
