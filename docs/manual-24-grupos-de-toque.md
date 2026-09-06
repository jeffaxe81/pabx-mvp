# Manual 24 — Grupos de toque (item #18)

## O que é
Uma chamada toca em **vários ramais** — todos ao mesmo tempo, ou um
de cada vez em sequência — sem as funcionalidades de fila (sem música
de espera, sem posição, sem estatística). É a ferramenta certa pra
"qualquer um da equipe pode atender isso", quando a fila (manual 08)
seria over-engineering.

## Diferença entre grupo de toque e fila
| | Grupo de toque | Fila (Queue) |
|---|---|---|
| Música de espera | Não | Sim |
| Posição/tempo de espera | Não | Sim (painel, manual 08) |
| Gravação automática | Não | Sim (`monitor-type`, manual 09) |
| Pickup dirigido de chamada específica | Não faz sentido (não há espera) | Sim (manual 08) |
| Uso típico | Grupos pequenos, informal | Atendimento formal com métricas |

## Os dois exemplos incluídos
- **Ramal `900` — grupo simultâneo**: `Dial(PJSIP/t1-1001&PJSIP/t1-1002&PJSIP/t1-recepcao,20)`
  — todos tocam juntos, quem atender primeiro fica com a chamada
- **Ramal `901` — grupo em sequência**: `Dial()` separado por membro,
  10 segundos cada, na ordem definida — tenta o primeiro, se não
  atender tenta o próximo

Os dois têm BLF (presença) combinado — dá pra ver o estado do grupo
inteiro como hint.

## Como adicionar/remover membros
Edite diretamente `asterisk/extensions.conf`, contexto `[t1-internal]`:
- **Simultâneo**: adicione `&PJSIP/nome-do-ramal` na lista do `Dial()`
- **Sequência**: adicione uma linha `Dial(PJSIP/nome-do-ramal,10)` na
  ordem que quiser

E atualize o hint correspondente em `[t1-hints]` pra refletir os
mesmos membros (senão o BLF mostra gente que não está mais no grupo).

## Como testar manualmente
1. `docker compose up -d`
2. Registre 2-3 softphones nos ramais que estão no grupo (`t1-1001`,
   `t1-1002`, `t1-recepcao`)
3. De outro ramal, disque `900` — todos devem tocar ao mesmo tempo;
   atenda em qualquer um e confirme que os outros param de tocar
4. Disque `901` — confirme que toca primeiro só em `t1-1001` por 10s,
   depois `t1-1002`, depois `t1-recepcao`, nessa ordem
5. Não atenda nenhum dos dois — confirme que cai na caixa de voz

## Teste automatizado
`tests/test_extensions_conf.py`:
- `test_simultaneous_ring_group_dials_all_members_at_once` — confirma
  que é um `Dial()` só com `&`, não vários separados
- `test_sequential_ring_group_dials_members_one_at_a_time` — confirma
  o oposto: 3 `Dial()` separados, sem `&`
- `test_ring_groups_have_combined_hints`

## Limitações conhecidas
- **Gerenciamento manual** — diferente dos ramais (que têm painel de
  administração, manual 16), grupos de toque são editados direto no
  `extensions.conf`; não tem CRUD pelo painel
- **Só 2 grupos de exemplo** (900 simultâneo, 901 sequência) — pra
  mais grupos, é copiar o padrão com um número de ramal novo
- **Sem gravação automática** — se quiser gravar chamadas de um grupo
  de toque, precisa adicionar `MixMonitor()` manualmente, seguindo o
  mesmo padrão usado nos ramais diretos da telefonista (manual 09)
- **Só tenant 1** — mesma limitação de escopo já aceita em outras
  partes do projeto
