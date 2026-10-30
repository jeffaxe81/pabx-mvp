# AXE PABX — 20 frentes de diagnóstico operacional (30/10/2026)

**Status:** `CODE_REGISTERED_PENDING_REAL_HOMOLOGATION`.

## Objetivo da entrega

A PR acrescenta **20 regras independentes de atenção operacional**, em vez de repetir os 20 indicadores da entrega anterior. O painel `webphone/painel-operacional.html` agora interpreta os números do resumo `GET /api/supervision/summary` e apresenta `Normal`, `Atenção` ou `Sem dados` para cada regra. A avaliação ocorre no servidor em `supervision_diagnostics.py`. Não há novas chamadas, bloqueios, eventos AMI, manutenção automática ou endpoint público.

## Vinte verificações entregues

| ID | Domínio | Condição ilustrativa de atenção |
|---|---|---|
| OP-01 | Filas | Pelo menos 10 chamadas esperando |
| OP-02 | Filas | Pelo menos 3 filas com espera |
| OP-03 | Filas | Pelo menos 3 chamadas acima do limiar de espera configurado |
| OP-04 | Filas | Ao menos uma chamada espera mais de 60 segundos |
| OP-05 | Filas | Espera máxima registrada de pelo menos 180 segundos |
| OP-06 | Ramais | Nenhum ramal monitorado no contexto BLF da empresa |
| OP-07 | Ramais | Nenhum ramal livre, desde que haja ramais monitorados |
| OP-08 | Ramais | Pelo menos 5 ramais tocando |
| OP-09 | Ramais | 80% ou mais de ocupação, com amostra mínima de 5 ramais |
| OP-10 | Ramais | Pelo menos 3 ramais indisponíveis |
| OP-11 | SLA | Verificação da existência de amostra; sem chamadas = sem dados, não situação normal |
| OP-12 | SLA | SLA ponderado inferior a 80%, com pelo menos 10 ofertas |
| OP-13 | SLA | Pelo menos 10 chamadas fora do limiar de SLA |
| OP-14 | SLA | Pelo menos 2 filas abaixo da referência de 80% |
| OP-15 | SLA | 30% ou mais das chamadas fora do SLA, com no mínimo 10 ofertas |
| OP-16 | Ocorrências | Pelo menos 10 eventos de chamadas perdidas no buffer |
| OP-17 | Ocorrências | Pelo menos um alerta de fraude no buffer |
| OP-18 | Ocorrências | Pelo menos 3 amostras classificadas como qualidade ruim |
| OP-19 | Ocorrências | Pelo menos 5 agentes atualmente pausados |
| OP-20 | Ocorrências | Pelo menos 5 overrides manuais de presença ausente |

Esses limites são **referências fixas de diagnóstico**, não metas contratuais, nem base para avaliação disciplinar de funcionários. O status "normal" não é garantia de disponibilidade. Campos ausentes, NaN, infinito, tipo inesperado ou falta da amostra mínima resultam em **Sem dados**, nunca em sucesso fictício.

## Isolamento, proteção de dados e apresentação

1. A API existente continua autenticando o Bearer por catálogo privado, deriva o tenant **da credencial** e permite **somente supervisor/admin**; o frontend não escolhe tenant nem armazena tokens em URL, LocalStorage ou código.
2. A avaliação consome apenas os 20 números do `build_supervision_summary`, já filtrados por `fila-tN`, contexto BLF do tenant e vínculo exato do ramal. Exemplo: `t1` não inclui `t10`.
3. São devolvidos IDs fixos, nome de campo técnico, situação, valor numérico e referência ilustrativa. Não se retorna CallerID, telefone, nome, canal, nota, gravação, mídia nem token.
4. O painel usa uma tabela de títulos fixa e elementos DOM com `textContent`. Respostas atrasadas são descartadas quando a credencial muda; a limpeza inclui a nova seção de regras, evitando retenção de dados de outra sessão.
5. A origem do navegador respeita `QUEUE_CORS_ORIGINS`, o status HTTP restringe papéis e a resposta aplica `Cache-Control: no-store` como no resumo anterior.
6. Falhas de esquema rejeitam o resumo (503 genérico no servidor); nenhuma exceção revela caminhos ou conteúdos internos.
7. As verificações correm sob demanda no ciclo de consulta existente. Não existe novo agendador de alarmes, notificador externo ou automação de correção.

## Homologação, CI e decisão de produção

Foi adicionada cobertura unitária para as 20 regras, amostra insuficiente, valores adversariais e ausência de dados sensíveis, além de assertivas HTTP em `test_monitoring_tenant_http.py`. A CI já existente **deve concluir integralmente em verde** antes do merge. **Nenhuma prova em ambiente real do cliente foi realizada por esta entrega.**

O programa formal permanece em **7/16 marcos = 43,8%**, com **15 provas operacionais diferidas** (issue #173), inclusive isolamento real de identidade, gravações, failover, carga e go/no-go. `operational_go_authorized=false`. **Produção NO-GO** até evidência e aceite humano.

## Arquivos

- `queue-api/supervision_diagnostics.py` — 20 regras de estado
- `queue-api/server.py` — incorpora diagnóstico ao endpoint autenticado
- `webphone/painel-operacional.html` — exibe as vinte avaliações
- `queue-api/tests/test_supervision_diagnostics.py` — regressão das vinte regras
- `queue-api/tests/test_monitoring_tenant_http.py` — checagem HTTP/tenant
- `docs/quality/lote-20-frentes-diagnosticos-supervisao-20261030.md` — este registro
