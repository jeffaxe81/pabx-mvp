# Manual 132 — Quatro frentes de robustez e isolamento do PABX

## Escopo e coordenação

Esta entrega reúne quatro frentes independentes de código, revisadas
sob o mesmo gate de integração. A execução em paralelo refere-se à
organização das frentes, **não** à contratação ou operação autônoma de
quatro programadores externos.

### Frente A — PIN de voicemail

O gerador do wizard de novas empresas descarta PINs triviais, repetitivos
e sequenciais, e limita a 64 as tentativas de obtenção de segredo seguro.
A renderização também nega PIN fornecido manualmente com padrão fraco.
Caixas já implantadas não são alteradas automaticamente.

### Frente B — Políticas de gravação

O catálogo JSON de autorização de gravações rejeita chaves repetidas
inclusive em objetos aninhados (tenant, credenciais, gravação) e números
não finitos. Duplicidade não pode sobrescrever silenciosamente uma
política de autorização.

### Frente C — Callback

Um resultado AMI desconhecido, malformado ou não mapeado não modifica
o callback em estado `discando`, não o conclui e não reabre rediscagem.
Apenas os cinco resultados de discagem previstos podem mudar o estado.
Isso exige reconciliação explícita em resultado inconclusivo.

### Frente D — SLA e filas

`AgentConnect` e `QueueCallerAbandon` com nome de fila ausente,
não textual, longo, de controle ou com espaços são descartados antes da
contagem do SLA. Eventos válidos da fila `fila-t10` continuam isolados
da identidade `fila-t1`.

## Regressão e implantação

Os testes automatizados respectivos estão em:

- `admin-api/tests/test_tenants.py`
- `queue-api/tests/test_recording_access.py`
- `queue-api/tests/test_callbacks.py`
- `queue-api/tests/test_queue_sla.py`

Antes do merge, todas as validações estáticas e o laboratório real
Asterisk precisam estar aprovados no **mesmo HEAD**. A integração
não comprova autenticação interativa de voicemail por PIN, isolamento
físico das gravações, callbacks fim a fim ou SLA real com chamadas
de produção. Os marcos 8/9 permanecem em andamento, e GO segue falso.
