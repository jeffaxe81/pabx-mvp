# AXE PABX — 20 frentes técnicas de especialistas em PABX (30/10/2026)

**Status:** `CODE_REGISTERED_PENDING_REAL_HOMOLOGATION` — nenhuma execução no ambiente real do cliente foi feita. **Tipo de entrega:** evolução de lógica de fila AMI, API multiempresa e testes. São vinte frentes de implementação/fortalecimento **num subsistema existente**, e não vinte produtos ou instâncias de agentes especialistas executadas separadamente.

## Escopo

A implementação reforça o rastreador `QueueStateTracker` que já existia. Ele recebe eventos Asterisk Manager Interface (AMI) por meio de `server.handle_ami_event` e alimenta a API Webphone. O backend continua somente refletindo os eventos, sem criar chamadas adicionais ou mudar o roteamento em Asterisk.

### 20 frentes tratadas

| # | Especialidade | Alteração implementada |
|---:|---|---|
| 1 | Filas / Asterisk | Limpeza de chamada abandonada por `QueueCallerAbandon` |
| 2 | Filas / Asterisk | Remoção de chamada atendida por `AgentConnect` |
| 3 | Filas / Asterisk | Limpeza conservadora pelo evento `AgentDump` |
| 4 | Filas / Asterisk | Limpeza conservadora residual por `AgentComplete` |
| 5 | AMI | Correlação de `Hangup` pelo `Uniqueid` |
| 6 | AMI | Correlação de `QueueCallerLeave` pelo `Uniqueid` |
| 7 | AMI | Conferência da fila exata nos eventos finais, inclusive abandono e atendimento |
| 8 | Segurança | Rejeição de `Uniqueid` com formato inválido ou caracteres de controle |
| 9 | Segurança | Rejeição de canal inválido ou com espaço/caracteres não imprimíveis |
| 10 | Multiempresa | Entrada somente nas filas com padrão integral `fila-tN`, `fila-tN-en` ou `fila-tN-es` |
| 11 | AMI | Deduplicação de `QueueCallerJoin` para não reiniciar o tempo em reentrega |
| 12 | Multiempresa | Troca de empresa no mesmo canal somente com `Uniqueid` distinto e verificável |
| 13 | Concorrência | Proteção com `RLock` de leitura, escrita, limpeza e contadores |
| 14 | Resiliência | Expurgo de chamadas antigas por TTL máximo configurável (padrão 6h) |
| 15 | Resiliência | Teto global de 10.000 chamadas monitoradas em memória |
| 16 | Resiliência | Teto por fila (padrão 3.000 chamadas) com rejeição contada |
| 17 | Webphone / Tenant | Seleção de chamadas em espera já filtrada por tenant no próprio tracker |
| 18 | Pickup | Remoção após redirect condicionada à fila exata observada |
| 19 | Observabilidade | Snapshot local por tenant sem BINA, canal, nomes ou `Uniqueid` |
| 20 | Segurança HTTP | Novo `GET /api/supervision/queue-health` com Bearer, papel supervisor/admin, CORS seguro e `no-store` |

**Observação:** frentes como deduplicação e remoção após `Hangup` já tinham proteção básica; este lote **amplia ou reforça** esses controles, em vez de alegar funcionalidades inteiramente inéditas.

## Contratos HTTP

O endpoint `GET /api/queue` preserva o esquema `{"waiting": [...]}`, agora com `waiting_list(tenant=identity["tenant"])`. Cada linha continua trazendo canal, fila, identificador de chamada e tempo, e por isso **continua restrita à credencial Bearer da empresa**. O `Uniqueid` é usado apenas internamente, não adicionado à resposta.

O novo endpoint `GET /api/supervision/queue-health` retorna somente contadores e indicadores agregados: chamadas aguardando, quantidade de filas, maior espera e contadores de eventos AMI/remoções/descartes desde o início do processo. O tenant é retirado **exclusivamente do Bearer**, nunca da query. A rota é negada a agentes, clientes não autenticados ou origem não autorizada. Não exibe CallerID, canais, `Uniqueid`, endereço IP, nomes ou mídia.

## Limites e riscos

- Asterisk AMI é assíncrono: pode duplicar, atrasar ou reordenar eventos. O `Uniqueid` correlaciona o **canal de quem liga**, não o `DestUniqueid` do atendente. Eventos finais sem `Uniqueid` não removem uma chamada previamente identificada por `Uniqueid`, para não apagar chamadas substitutas.
- O tracker é uma **estrutura em memória**, não um mecanismo transacional distribuído. Reiniciar o processo zera contadores/espera, e múltiplas réplicas exigem fonte de estado compartilhada. Não substituir por isso CDR, QueueLog ou auditoria de gravação.
- Expurgo após 6h evita chamadas fantasmas, porém uma chamada efetivamente esperando por mais de 6h deixa de aparecer no espelho. O controle deve ser revisado com a operação antes de produção.
- Ao exceder os limites, novos registros são rejeitados no **espelho**; isso não rejeita chamadas reais no Asterisk. Há contadores de descartes por tenant.
- O esquema `queue-health` é apenas de diagnóstico operacional; `real_environment_homologated=false` sempre. Não provar disponibilidade, desempenho, faturamento, failover ou isolamento efetivo de mídia em cliente.
- Os testes novos usam cenários AMI sintéticos, concorrência em threads, TTL e t1/t10, mais a API HTTP local. A regressão automatizada e o laboratório Asterisk do CI **devem concluir 100% verde** antes de qualquer merge.
- Os **15 cenários de prova operacional real** da issue #173 continuam diferidos, e o cronograma formal permanece em **7/16 marcos (43,8%)**. `operational_go_authorized=false`; implantação em produção não autorizada.

## Arquivos

- `queue-api/queue_state.py`
- `queue-api/server.py`
- `queue-api/tests/test_queue_lifecycle_hardening.py`
- `queue-api/tests/test_monitoring_tenant_http.py`
- `docs/quality/lote-20-frentes-ciclo-filas-ami-20261030.md`

## Uso do diagnóstico HTTP (apenas em laboratório autorizado)

```bash
curl --fail --silent --show-error \
  -H "Authorization: Bearer $QUEUE_SUPERVISOR_TOKEN" \
  https://pabx.exemplo.invalid/api/supervision/queue-health
```

O endereço `pabx.exemplo.invalid` é ilustrativo, não um ambiente existente nem validado. Nunca colocar token em URL, histórico do terminal ou controle de versão. A aprovação das regras de código/laboratório **não é homologação operacional**.
