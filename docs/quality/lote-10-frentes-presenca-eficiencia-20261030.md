# AXE PABX — lote de 10 frentes: presença manual e estatísticas por ramal

**Registro:** 30/10/2026. Lote 3 após merges das PRs #179 e #181. Entrega **somente em código**, não operacional: `CODE_REGISTERED_PENDING_REAL_HOMOLOGATION`. CLI local passa de **80 a 90 indicadores de análise**, distribuídos em **18 áreas**. São funções de consulta e agregação, não dez novos módulos SIP, endpoints ou interfaces.

| Frente | Área | Função | Escopo |
|---:|---|---|---|
| 1 | presence | `presence_total_overrides` | Quantos ramais têm estado manual válido |
| 2 | presence | `presence_by_status` | Status manual disponível/ausente/reunião/férias |
| 3 | presence | `presence_updated_by_day` | Última atualização por dia UTC |
| 4 | presence | `presence_older_than_week` | Estados manuais com data válida há sete dias ou mais |
| 5 | presence | `presence_missing_valid_timestamp` | Entradas sem data confiável |
| 6 | agent_efficiency | `agent_answer_rate` | CDRs ANSWERED versus CDRs conhecidos por ramal |
| 7 | agent_efficiency | `agent_nonanswered_volume` | CDRs de não atendimento conhecidos por ramal |
| 8 | agent_efficiency | `agent_mean_talk_seconds` | Tempo médio faturável das atendidas com duração válida |
| 9 | agent_efficiency | `agent_median_talk_seconds` | Mediana dos tempos de chamada faturáveis |
| 10 | agent_efficiency | `agent_over_five_minutes` | Chamadas faturáveis acima de 300 segundos |

## Operação apenas local

Os seguintes comandos **consultam arquivos já presentes no container** e não iniciam chamadas nem modificam o PABX:

```bash
docker exec pabx-queue-api python3 /app/insights_cli.py --area presence --tenant t1 --file /app/data/presence.json
docker exec pabx-queue-api python3 /app/insights_cli.py --area agent_efficiency --tenant t1 --file /app/data/call_log.jsonl
```

Se o arquivo ainda não existir, o comando retorna erro; não fabrica métricas nem inicializa um histórico. O armazenamento `presence.json` é um mapa JSON por identificador de ramal, convertido para registros estritamente limitados a `extension`, `status`, `updated_at`. **As notas textuais não entram no pipeline de relatórios.** O arquivo `call_log.jsonl` usa o CDR já persistido.

## Limitações e segurança

- Uso somente em host autorizado. A CLI **não autentica operadores nem implementa RBAC**; nunca disponibilizá-la como API pública.
- Filtragem de `tN` exata (`t1` não acessa `t10`). Ramais inválidos não são computados; sem leitura de CallerID, números, nomes, mídia ou notas.
- Presença é um **override manual**, não indica registro SIP, BLF, pausa real ou disponibilidade efetiva. Atualizações sem data válida não recebem idade fictícia.
- Eficiência é calculada de **CDRs associados a ramais**, não produtividade humana; indisponibilidade, transferência e fila podem alterar os indicadores. CDR não é igual a abandono de fila.
- Não escreve dados, não dispara eventos AMI, não expõe novas APIs e não altera Asterisk, frontend, telefone, gravação ou credenciais.
- Não foi acrescentada suíte nova; **CI existente permanece obrigatória** antes de integrar. Não há teste em ambiente alvo nesta PR.
- **15 provas operacionais seguem pendentes** (issue #173); marcos formais continuam **7/16 = 43,8%**. `operational_go_authorized=false`; produção NO-GO.

**Arquivos:** `queue-api/insights_presence.py`, `queue-api/insights_agent_efficiency.py`, `queue-api/insights_common.py` e `queue-api/insights_cli.py`.
