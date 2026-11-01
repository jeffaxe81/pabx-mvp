# AXE PABX — 100 funcionalidades candidatas ao roadmap

**Status:** 100 itens registrados para triagem; não significa implementação, teste ou homologação.
**Escopo:** PABX puro. Contact Center e IA fora deste lote.
**Deduplicação:** cada item deve ser comparado ao código, documentação e PRs antes de receber status NOVA. Itens já existentes serão marcados EXISTENTE/PARCIAL e substituídos antes de contar como novas entregas.

## Ramais e identidades

- [ ] **AXEF-0001** — Expiração automática de ramal temporário. **Status:** A AUDITAR.
- [ ] **AXEF-0002** — Reserva de numeração por departamento. **Status:** A AUDITAR.
- [ ] **AXEF-0003** — Importação de ramais com validação prévia. **Status:** A AUDITAR.
- [ ] **AXEF-0004** — Exportação de inventário por tenant. **Status:** A AUDITAR.
- [ ] **AXEF-0005** — Histórico de alterações de ramal. **Status:** A AUDITAR.
- [ ] **AXEF-0006** — Suspensão programada de ramal. **Status:** A AUDITAR.
- [ ] **AXEF-0007** — Rotação de senha SIP com janela de transição. **Status:** A AUDITAR.
- [ ] **AXEF-0008** — Bloqueio de registro por dispositivo não autorizado. **Status:** A AUDITAR.
- [ ] **AXEF-0009** — Limite de dispositivos simultâneos por perfil. **Status:** A AUDITAR.
- [ ] **AXEF-0010** — Identificação de ramais sem registro prolongado. **Status:** A AUDITAR.

## Discagem e políticas

- [ ] **AXEF-0011** — Bloqueio internacional por tenant. **Status:** A AUDITAR.
- [ ] **AXEF-0012** — Permissão internacional por ramal. **Status:** A AUDITAR.
- [ ] **AXEF-0013** — Janela horária de chamadas externas por ramal. **Status:** A AUDITAR.
- [ ] **AXEF-0014** — Lista de destinos permitidos por tronco. **Status:** A AUDITAR.
- [ ] **AXEF-0015** — Limite de simultaneidade de chamadas externas por ramal. **Status:** A AUDITAR.
- [ ] **AXEF-0016** — Roteamento por menor custo configurável. **Status:** A AUDITAR.
- [ ] **AXEF-0017** — Normalização E.164 antes do roteamento. **Status:** A AUDITAR.
- [ ] **AXEF-0018** — Bloqueio de números premium por categoria. **Status:** A AUDITAR.
- [ ] **AXEF-0019** — Fallback de tronco por código de falha SIP. **Status:** A AUDITAR.
- [ ] **AXEF-0020** — Auditoria de alterações das regras de discagem. **Status:** A AUDITAR.

## Troncos e operadoras

- [ ] **AXEF-0021** — Health check ativo de tronco SIP. **Status:** A AUDITAR.
- [ ] **AXEF-0022** — Circuit breaker por falhas consecutivas de tronco. **Status:** A AUDITAR.
- [ ] **AXEF-0023** — Limite CPS por tronco. **Status:** A AUDITAR.
- [ ] **AXEF-0024** — Controle de canais ocupados por tronco. **Status:** A AUDITAR.
- [ ] **AXEF-0025** — Alerta de registro de tronco expirado. **Status:** A AUDITAR.
- [ ] **AXEF-0026** — Troca controlada de tronco em manutenção. **Status:** A AUDITAR.
- [ ] **AXEF-0027** — Diagnóstico de respostas 4xx/5xx/6xx por operadora. **Status:** A AUDITAR.
- [ ] **AXEF-0028** — Validação de cabeçalhos SIP recebidos por tronco. **Status:** A AUDITAR.
- [ ] **AXEF-0029** — Inventário de DIDs vinculados a troncos. **Status:** A AUDITAR.
- [ ] **AXEF-0030** — Simulação de roteamento sem originar chamada. **Status:** A AUDITAR.

## Transferência e mobilidade

- [ ] **AXEF-0031** — Estacionamento de chamadas com tempo máximo. **Status:** A AUDITAR.
- [ ] **AXEF-0032** — Recuperação de chamada estacionada por código. **Status:** A AUDITAR.
- [ ] **AXEF-0033** — Desvio condicional por indisponibilidade SIP. **Status:** A AUDITAR.
- [ ] **AXEF-0034** — Desvio temporário com data de expiração. **Status:** A AUDITAR.
- [ ] **AXEF-0035** — Transferência com política de destino permitido. **Status:** A AUDITAR.
- [ ] **AXEF-0036** — Retorno de transferência não atendida ao originador. **Status:** A AUDITAR.
- [ ] **AXEF-0037** — Siga-me com sequência configurável de dispositivos. **Status:** A AUDITAR.
- [ ] **AXEF-0038** — Hotdesking com expiração de sessão. **Status:** A AUDITAR.
- [ ] **AXEF-0039** — Bloqueio de hotdesking simultâneo no mesmo terminal. **Status:** A AUDITAR.
- [ ] **AXEF-0040** — Registro de trilha de transferência por CDR. **Status:** A AUDITAR.

## Grupos e conferências

- [ ] **AXEF-0041** — Grupos de toque por calendário. **Status:** A AUDITAR.
- [ ] **AXEF-0042** — Estratégia de toque por ordem de prioridade. **Status:** A AUDITAR.
- [ ] **AXEF-0043** — Limite de participantes em grupo de conferência. **Status:** A AUDITAR.
- [ ] **AXEF-0044** — PIN de conferência com expiração. **Status:** A AUDITAR.
- [ ] **AXEF-0045** — Bloqueio de entrada tardia em conferência. **Status:** A AUDITAR.
- [ ] **AXEF-0046** — Modo somente escuta para participantes de conferência. **Status:** A AUDITAR.
- [ ] **AXEF-0047** — Expulsão administrativa de participante. **Status:** A AUDITAR.
- [ ] **AXEF-0048** — Conferência com sala agendada. **Status:** A AUDITAR.
- [ ] **AXEF-0049** — Registro de entrada e saída de conferência. **Status:** A AUDITAR.
- [ ] **AXEF-0050** — Limite de duração configurável por conferência. **Status:** A AUDITAR.

## Correio de voz e gravações

- [ ] **AXEF-0051** — Cota de armazenamento de voicemail por ramal. **Status:** A AUDITAR.
- [ ] **AXEF-0052** — Expurgo seletivo de voicemail por idade. **Status:** A AUDITAR.
- [ ] **AXEF-0053** — Bloqueio de voicemail por excesso de cota. **Status:** A AUDITAR.
- [ ] **AXEF-0054** — Notificação de caixa postal cheia. **Status:** A AUDITAR.
- [ ] **AXEF-0055** — Política de retenção de gravação por tenant. **Status:** A AUDITAR.
- [ ] **AXEF-0056** — Proteção de gravação contra expurgo por retenção legal. **Status:** A AUDITAR.
- [ ] **AXEF-0057** — Checksum de integridade de arquivo de gravação. **Status:** A AUDITAR.
- [ ] **AXEF-0058** — Exportação de gravação com trilha de auditoria. **Status:** A AUDITAR.
- [ ] **AXEF-0059** — Alerta de falha na escrita de gravações. **Status:** A AUDITAR.
- [ ] **AXEF-0060** — Mascaramento de número em listagens de gravações. **Status:** A AUDITAR.

## Segurança e isolamento

- [ ] **AXEF-0061** — Allowlist de IPs para registro SIP por tenant. **Status:** A AUDITAR.
- [ ] **AXEF-0062** — Limite de tentativas de autenticação por origem. **Status:** A AUDITAR.
- [ ] **AXEF-0063** — Quarentena temporária de endpoint suspeito. **Status:** A AUDITAR.
- [ ] **AXEF-0064** — Auditoria de permissões administrativas por tenant. **Status:** A AUDITAR.
- [ ] **AXEF-0065** — Validação de contexto de origem em chamadas internas. **Status:** A AUDITAR.
- [ ] **AXEF-0066** — Bloqueio de alteração de tenant em sessão ativa. **Status:** A AUDITAR.
- [ ] **AXEF-0067** — Alerta de pico de tentativas REGISTER. **Status:** A AUDITAR.
- [ ] **AXEF-0068** — Detecção de varredura de ramais SIP. **Status:** A AUDITAR.
- [ ] **AXEF-0069** — Rotação programada de chaves de API administrativas. **Status:** A AUDITAR.
- [ ] **AXEF-0070** — Revogação de sessão administrativa em todos os dispositivos. **Status:** A AUDITAR.

## Provisionamento e terminais

- [ ] **AXEF-0071** — Provisionamento de telefone Grandstream. **Status:** A AUDITAR.
- [ ] **AXEF-0072** — Provisionamento de telefone Snom. **Status:** A AUDITAR.
- [ ] **AXEF-0073** — Inventário de firmware de telefone IP. **Status:** A AUDITAR.
- [ ] **AXEF-0074** — Política de firmware mínimo por modelo. **Status:** A AUDITAR.
- [ ] **AXEF-0075** — Associação segura de MAC a tenant. **Status:** A AUDITAR.
- [ ] **AXEF-0076** — Revogação remota de provisionamento por MAC. **Status:** A AUDITAR.
- [ ] **AXEF-0077** — Expiração de URL de provisionamento. **Status:** A AUDITAR.
- [ ] **AXEF-0078** — Assinatura de arquivos de configuração distribuídos. **Status:** A AUDITAR.
- [ ] **AXEF-0079** — Validação de template antes de publicar. **Status:** A AUDITAR.
- [ ] **AXEF-0080** — Histórico de provisionamento por terminal. **Status:** A AUDITAR.

## Operação e disponibilidade

- [ ] **AXEF-0081** — Verificação periódica de integridade do dialplan. **Status:** A AUDITAR.
- [ ] **AXEF-0082** — Validação pré-reload de configuração Asterisk. **Status:** A AUDITAR.
- [ ] **AXEF-0083** — Rollback automático de configuração inválida. **Status:** A AUDITAR.
- [ ] **AXEF-0084** — Backup incremental de configuração. **Status:** A AUDITAR.
- [ ] **AXEF-0085** — Teste de restauração em ambiente isolado. **Status:** A AUDITAR.
- [ ] **AXEF-0086** — Alerta de uso de disco de gravações. **Status:** A AUDITAR.
- [ ] **AXEF-0087** — Monitoramento de perda RTP por chamada. **Status:** A AUDITAR.
- [ ] **AXEF-0088** — Detecção de jitter acima de limite por tenant. **Status:** A AUDITAR.
- [ ] **AXEF-0089** — Painel de consumo de canais simultâneos. **Status:** A AUDITAR.
- [ ] **AXEF-0090** — Modo de manutenção com drenagem de chamadas. **Status:** A AUDITAR.

## CDR, APIs e desempenho

- [ ] **AXEF-0091** — Exportação incremental de CDR por cursor. **Status:** A AUDITAR.
- [ ] **AXEF-0092** — Conciliação de CDR com eventos de chamadas. **Status:** A AUDITAR.
- [ ] **AXEF-0093** — API de consulta de estado de ramal com escopo tenant. **Status:** A AUDITAR.
- [ ] **AXEF-0094** — Webhook de mudança de estado de tronco. **Status:** A AUDITAR.
- [ ] **AXEF-0095** — Idempotência em comandos de criação de ramal. **Status:** A AUDITAR.
- [ ] **AXEF-0096** — Rate limit por credencial de API. **Status:** A AUDITAR.
- [ ] **AXEF-0097** — Paginação estável em listagens de CDR. **Status:** A AUDITAR.
- [ ] **AXEF-0098** — Métrica de tempo de estabelecimento de chamada. **Status:** A AUDITAR.
- [ ] **AXEF-0099** — Teste de capacidade sem chamadas externas reais. **Status:** A AUDITAR.
- [ ] **AXEF-0100** — Relatório de chamadas recusadas por política. **Status:** A AUDITAR.

## Critérios de aceite por item

- Evidência de inexistência ou lacuna funcional específica no código atual.
- Especificação de comportamento, segurança e isolamento entre tenants.
- PR com código e testes inéditos identificados, sem repetir casos históricos.
- Homologação local registrada separadamente; implantação em produção somente com autorização e evidências.
