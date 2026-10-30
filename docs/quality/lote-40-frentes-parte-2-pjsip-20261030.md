# AXE PABX — Lote 2 de 2: 20 frentes PJSIP e provisionamento multiempresa

**Data:** 30/10/2026 — **Status:** CODE_REGISTERED_PENDING_REAL_HOMOLOGATION.

Esta PR completa o lote de 40 frentes de desenvolvimento solicitado, com **20 verificações de configuração Asterisk aplicadas no fluxo real de criação de tenant**, antes de publicar arquivos `.conf` e antes de registrar DID no AstDB/AMI. Complementa as 20 melhorias de discagem CTI da PR #188. Não muda comportamento da telefonia existente e não gera novos serviços.

## Controles incluídos (TP-01 a TP-20)

| ID | Especialista | Critério de validação pré-publicação |
|---|---|---|
| TP-01 | Multiempresa | Identificador de tenant elegível (a partir de t3) |
| TP-02 | Release | Lote precisa de 8 arquivos de configuração completos |
| TP-03 | Segurança | Nomes e subdiretórios devem corresponder exclusivamente ao tenant |
| TP-04 | Segurança | Tamanho e conteúdo de cada arquivo limitados, sem NUL ou CR |
| TP-05 | PJSIP | Endpoint WebRTC da primeira recepcionista presente |
| TP-06 | PJSIP | Endpoint WebRTC da segunda recepcionista presente |
| TP-07 | Dialplan | Ambos endpoints associados ao contexto interno correto |
| TP-08 | PJSIP / Auth | Autenticação SIP individual para os dois endpoints |
| TP-09 | PJSIP / AOR | AOR exclusivo para cada endpoint |
| TP-10 | Voicemail | Cada endpoint vinculado à própria caixa postal |
| TP-11 | Filas | Filas geral, inglês e espanhol geradas |
| TP-12 | Filas | Ambos os ramais da recepção são membros da fila geral |
| TP-13 | Gravações | Declaração de MixMonitor nas três filas |
| TP-14 | Dialplan | Contextos internos e hints BLF exclusivos |
| TP-15 | Filas | Seleção de fila correta na extensão de recepção |
| TP-16 | Segurança / Voicemail | Verificação de contexto de endpoint no acesso à caixa postal |
| TP-17 | Segurança / Saída | Consulta à lista de números bloqueados específica do tenant |
| TP-18 | Dialplan | Includes dinâmicos de ramais e hints vinculados ao tenant |
| TP-19 | Voicemail | Três caixas postais locais e inclusão dinâmica previstas |
| TP-20 | Call Parking | Estacionamento de chamadas em contexto e faixa isolados |

## Integração e proteção

O módulo `admin-api/tenant_config_invariants.py` verifica conteúdo renderizado e retorna **somente IDs TP-nn e estados booleanos**, sem fornecer senhas SIP, PINs de voicemail, ramais individuais ou gravações.

O fluxo `build_tenant_files`, em `admin-api/tenant_provisioning.py`, executa `validate_generated_tenant_files` **antes de publicar qualquer arquivo e antes do contato AMI**. Se uma verificação reprovar, interrompe o processo com IDs genéricos dos controles, sem expor credenciais.

Os novos testes usam o gerador de configuração real e modificam um campo por vez. Incluem alterações de tenant `t3` para `t30`, alteração de autenticação e AOR, ausência de fila, remoção do isolamento de voicemail e troca de faixas de estacionamento. Esse conjunto cobre **regressão estrutural de texto**, não prova que Asterisk carregou ou executou essas configurações corretamente.

## Limites de segurança e homologação

- Este gate valida **templates gerados pelo próprio código** e não analisa todos os tipos de sintaxe Asterisk ou conflitos de runtime/AstDB já existentes.
- Não corrige manualmente rotas, configurações antigas, troncos, certificados SIP/TLS, SRTP, codecs ou NAT.
- Não comprova autenticação SIP real, simultaneidade, áudio, gravação nem isolamento físico de clientes.
- A próxima camada deve executar testes de registro, SIP, RTP, CDR e acesso às gravações em ambiente de homologação devidamente autorizado.
- As **15 provas operacionais** registradas no projeto seguem diferidas e os marcos formais permanecem **7/16 (43,8%)**. Sem autorização de produção.
- Exigir CI 100% verde antes do merge. Nenhum deploy automático ou alteração remota de PABX operacional.

Arquivos: `admin-api/tenant_config_invariants.py`, `admin-api/tenant_provisioning.py`, `admin-api/tests/test_tenant_config_invariants.py`.

**Nota:** as 40 frentes correspondem a 20 melhorias na originação CTI (PR #188) e 20 verificações pré-publicação do provisionamento nesta PR. Isso não equivale a 40 módulos de telefonia prontos nem a 40 homologações operacionais.
