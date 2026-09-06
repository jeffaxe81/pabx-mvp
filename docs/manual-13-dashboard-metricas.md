# Manual 13 — Dashboard de métricas do dia (backlog #7)

## O que é
Painel "Métricas de hoje" na interface web, com 5 números que dão uma
visão rápida do dia: chamadas totais, atendidas, perdidas, tempo médio
de atendimento (TMA) e taxa de perdidas. Atualiza sozinho a cada 15
segundos, e zera automaticamente na virada do dia.

## Como funciona
A fonte de dados é o **CDR** (Call Detail Record) do Asterisk — um
registro que o próprio Asterisk gera automaticamente pra cada chamada
finalizada, já com o status (`ANSWERED`, `NO ANSWER`, `BUSY`,
`FAILED`) e a duração calculados. Em vez de tentar somar isso na mão a
partir de vários eventos separados (o que já fizemos pra chamada
perdida no manual 11), aqui é mais confiável usar a fonte que o
próprio Asterisk já consolida.

Dois arquivos habilitam isso:
- **`asterisk/cdr.conf`**: liga o CDR (`enable=yes`) e garante que
  chamadas **não atendidas** também gerem registro (`unanswered=yes`)
  — sem isso, só chamadas atendidas apareceriam, e "taxa de perdidas"
  não faria sentido
- **`asterisk/cdr_manager.conf`**: faz o Asterisk mandar cada CDR como
  um evento `Cdr` via AMI — é esse evento que o `queue-api` escuta

O cálculo (`queue-api/metrics.py`) é só contagem simples: cada evento
`Cdr` com `Disposition=ANSWERED` soma 1 chamada atendida e some seu
`BillableSeconds` (tempo de conversa) pro total; qualquer outro
disposition soma 1 chamada perdida. TMA = tempo total / atendidas.
Taxa de perdidas = perdidas / total.

## Como configurar
Nada a configurar além do que já vem no `docker-compose.yml` — os
dois arquivos de CDR já são montados junto com o resto.

## Como testar manualmente
1. `docker compose up -d`
2. Conecte a telefonista web — o painel "Métricas de hoje" aparece na
   barra lateral, começando zerado
3. Faça uma chamada e atenda — depois de alguns segundos (até 15s de
   polling), "Chamadas hoje" e "Atendidas" devem subir pra 1, e o TMA
   deve refletir a duração da ligação
4. Faça uma chamada e **não atenda** (deixe cair) — "Perdidas" deve
   subir, e "% perdidas" deve recalcular

## Teste automatizado
- `queue-api/tests/test_metrics.py` — contagem, cálculo de TMA e taxa
  de perdidas, tratamento de eventos malformados, e a virada do dia
  (usando um relógio injetável, sem precisar esperar meia-noite de
  verdade)
- `tests/test_ami_config.py::test_cdr_enabled_including_unanswered_calls`
- `tests/test_ami_config.py::test_cdr_manager_enabled`
- `tests/test_docker_compose.py::test_cdr_config_files_mounted_for_metrics`
- `tests/test_webphone_html.py::test_metrics_polling_starts_and_stops_with_connection`

## Limitações conhecidas (honestidade técnica)
- **Sem teste de integração real** — assim como AMI, tronco TDM e
  notificações, só dá pra validar que o Asterisk realmente emite o
  evento `Cdr` no formato esperado contra uma instância de verdade
- **Métricas globais, não por tenant** — hoje soma tudo num contador
  só; separar por tenant (t1/t2) exigiria olhar o campo
  `AccountCode`/`Context` do CDR e manter contadores separados —
  ainda não implementado
- **Sem histórico** — só "hoje". Não guarda métricas de dias
  anteriores nem gera relatório semanal/mensal
- **Em memória, não sobrevive a restart** do `queue-api` — se o
  container reiniciar no meio do dia, as métricas voltam a zero
- TMA considera só chamadas atendidas pela telefonista via `Dial()`
  direto ou fila — chamadas puramente internas entre ramais também
  entram na contagem geral, já que qualquer CDR conta
