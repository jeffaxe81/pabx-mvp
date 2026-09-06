# Manual 21 — Busca de gravações e política de retenção (item #15)

## O que é
Duas melhorias na gravação de chamadas (manual 09): **buscar** por
número/atendente/período, e um **expurgo automático** configurável
(desligado por padrão, porque apagar gravação é irreversível).

## Como a busca funciona
O nome de cada arquivo gerado por este projeto já carrega a
informação: `AAAAMMDD-HHMMSS-numero-destino.wav`. A busca extrai isso
do próprio nome do arquivo — não precisa de banco de dados nem
metadado separado:
- `caller_number` — número de quem ligou
- `destination` — ramal/extensão que atendeu (`1000`, `1010`,
  `pickup`, etc.)
- `start_date`/`end_date` — intervalo de datas (formato `AAAAMMDD`)

Na interface web, o painel "Gravações" ganhou um campo de busca por
número. Pela API, todos os filtros:
```bash
curl "http://<ip>:8090/api/recordings?caller_number=5511999998888"
curl "http://<ip>:8090/api/recordings?destination=1010"
curl "http://<ip>:8090/api/recordings?start_date=20240101&end_date=20240131"
```

## Retenção automática
Desligada por padrão (`RECORDINGS_RETENTION_DAYS=0`). Pra ativar, no
`docker-compose.yml`:
```yaml
RECORDINGS_RETENTION_DAYS: "90"   # apaga gravações com mais de 90 dias
```
Uma thread roda em segundo plano no `queue-api`, checando uma vez por
dia, apagando o que passou do prazo. O log do container mostra o que
foi apagado.

## Como testar manualmente
1. `docker compose up -d`
2. Faça algumas chamadas de números diferentes
3. Na interface, busque por um dos números — confirme que só aparece
   a gravação daquele número
4. Pra testar retenção sem esperar dias de verdade: crie um arquivo
   de teste em `./recordings/` com uma data antiga
   (`touch -d "100 days ago" recordings/teste-antigo.wav` no Linux),
   configure `RECORDINGS_RETENTION_DAYS=90`, reinicie o `queue-api`, e
   confira o log — o arquivo antigo deve ter sido apagado dentro de
   um dia (ou reinicie o container de novo pra forçar a checagem)

## Teste automatizado
- `queue-api/tests/test_recordings.py` — parsing do nome do arquivo
  (inclusive quando o CALLERID vem vazio), filtro por
  número/destino/período, comportamento correto quando um arquivo não
  bate no padrão esperado (aparece sem filtro, some com filtro ativo),
  função de retenção (desligada por padrão, respeita o prazo, ignora
  arquivo não-áudio)
- `tests/test_docker_compose.py` — volume de gravações **gravável**
  (não `:ro`, senão o expurgo falharia sempre), retenção desligada
  por padrão
- `tests/test_webphone_html.py::test_recordings_search_sends_caller_number_filter`

## Limitações conhecidas (honestidade técnica)
- **Gravações da fila (monitor-type da fila, manual 09) usam outro
  padrão de nome** — vêm do próprio Asterisk, não do nosso
  `MixMonitor()` manual, então não têm número/destino extraíveis; elas
  aparecem na lista sem filtro, mas somem se você buscar por
  número/destino específico
- **Busca só por correspondência exata** — não tem busca parcial
  (ex: buscar só o DDD) nem por nome do atendente diretamente (só
  pelo número da extensão de destino)
- **Sem confirmação antes do expurgo automático** — uma vez habilitado
  e o prazo vencido, o arquivo é apagado sem aviso; a mensagem no log
  é o único registro de que aconteceu
- **Retenção verificada a cada 24h fixas**, não num horário
  configurável (ex: sempre de madrugada)
