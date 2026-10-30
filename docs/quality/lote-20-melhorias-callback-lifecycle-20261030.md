# AXE PABX — 20 melhorias reais no ciclo operacional de callbacks

**Data:** 30/10/2026. **Tipo:** melhorias de segurança e integridade do subsistema existente de callback; não são vinte produtos independentes. **Status operacional:** somente código/CI; não homologado no cliente.

## Alterações no código

| Nº | Especialidade | Melhoria implementada |
|---:|---|---|
| 01 | AMI | Captura opcional do `Uniqueid` do `CallbackRequest` |
| 02 | Segurança | Rejeição de `Uniqueid` malformado, excessivo ou com controle |
| 03 | Idempotência | Replay do mesmo UserEvent na mesma empresa reutiliza o pedido original |
| 04 | Idempotência | Replay da mesma origem com número conflitante não gera callback |
| 05 | Multiempresa | Chaves de origem isoladas entre `t1` e `t10` |
| 06 | Armazenamento | Catálogo precisa ser arquivo regular e não link simbólico |
| 07 | Resiliência | Tamanho máximo do catálogo: 8 MiB |
| 08 | Resiliência | Limite de até 20.000 pedidos no catálogo antes de aceitar novas entradas |
| 09 | Segurança | Estado deve ser texto, não lista/dicionário arbitrário |
| 10 | Identidade | ID dos pedidos acionáveis precisa ter formato hex de 12 caracteres |
| 11 | Discagem | Número ativo exige formato exclusivamente numérico canônico |
| 12 | Privacidade | Nome de chamador limitado e sem caracteres de controle |
| 13 | Multiempresa | Tenant de pedido ativo deve ter formato integral válido |
| 14 | Ordenação | Timestamp de criação precisa ser numérico finito e não negativo |
| 15 | Controle de chamadas | Pendente não pode ter contador esgotado (2 tentativas) |
| 16 | Controle de chamadas | `discando` precisa ter ao menos uma tentativa registrada |
| 17 | AMI | `attempt_id` em `discando` deve ser hexadecimal de 32 caracteres |
| 18 | AMI | `channel_id` precisa corresponder exatamente ao `attempt_id` |
| 19 | AMI | Timestamp da tentativa e metadados de `OriginateResponse` são validados |
| 20 | Concorrência | `attempt_id` ativo não pode pertencer a dois pedidos, mesmo entre empresas |

## Arquivos alterados

- `queue-api/callbacks.py`: validação do catálogo, restrições de estado, limites e persistência do identificador de origem.
- `queue-api/server.py`: integra o `source_uniqueid` de eventos AMI na criação persistente dos callbacks.
- `queue-api/tests/test_callback_lifecycle_security.py`: cenários de idempotência, estado e tenant.
- `queue-api/tests/test_campaign_tenant_http.py`: rejeição HTTP 503 sem nova ação AMI para catálogo corrompido em `discando`.
- `queue-api/tests/test_callbacks.py`: regressão ajustada para falha antecipada em catálogo inválido.

## Contratos operacionais

O identificador AMI é **opcional**. Sem ele, o módulo não consegue provar que dois UserEvents são o mesmo pedido; portanto a deduplicação por evento não é garantida. O número telefônico **não** é tratado como chave global de identidade, para não unir solicitações legítimas distintas.

Snapshots válidos de histórico concluído/cancelado podem manter campos legados, mas pedidos **acionáveis** (`pendente` e `discando`) seguem as regras estritas. A API existente protege a listagem e o `dial-next` com credencial Bearer e tenant, retornando 503 caso o catálogo esteja inválido. O sistema não faz rediscagem automática a partir de respostas AMI ambíguas.

O catálogo é local ao volume compartilhado e protegido pelo `outbound_lock` nos caminhos de escrita já existentes. O projeto ainda requer provas reais de SIP, áudio, CDR e gravação, além de restauração/failover. As **15 provas operacionais** continuam pendentes, o progresso formal do projeto continua **7/16 marcos (43,8%)**, e a liberação para produção permanece **NO-GO**.

A PR só poderá ser integrada à `main` depois de **100% dos checks e workflows aprovados**. Não foi feito deployment em ambiente de cliente.
