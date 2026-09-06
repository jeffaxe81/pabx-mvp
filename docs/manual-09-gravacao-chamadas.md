# Manual 09 — Gravação de chamadas (backlog #3)

## O que é
Toda chamada em que a telefonista fala com alguém é gravada
automaticamente (formato wav), e fica disponível pra ouvir direto na
interface web, num player de áudio embutido — sem precisar baixar
arquivo nem acessar o servidor por fora.

## Como funciona
Duas fontes de gravação, cobrindo os três caminhos possíveis de uma
chamada chegar até a telefonista:

1. **`queues.conf`** (`monitor-format=wav` + `monitor-type=mixmonitor`
   na fila `fila-t1`): grava automaticamente qualquer chamada que
   passa pela fila e é atendida - cobre o fluxo normal (chamada sem
   DID mapeado, ou extensão de teste `800`)
2. **`MixMonitor()` explícito no dialplan**, em dois pontos que ficam
   *fora* do controle da fila:
   - `[t1-internal]` extensão `1000` (alguém disca direto pro ramal da
     telefonista, sem passar pela fila)
   - `[pickup-target]` (a chamada puxada manualmente da fila pelo
     painel web - uma vez que sai da fila via `Redirect`, o
     `monitor-type` da fila não se aplica mais a ela)

Os arquivos vão para `/var/spool/asterisk/monitor/` dentro do
container, que é montado no host em `./recordings/` (fora do Git - são
conversas reais).

O **`queue-api`** (o mesmo serviço da fila) ganhou dois endpoints
novos:
- `GET /api/recordings` — lista as gravações (nome, tamanho, data)
- `GET /recordings/<nome>` — serve o arquivo de áudio pra tocar

## Como configurar
Nada a configurar além do que já existe — a gravação já vem
habilitada por padrão nos pontos acima. Se quiser desabilitar
temporariamente, comente as linhas `monitor-format`/`monitor-type` em
`queues.conf` e as chamadas `MixMonitor(...)` em `extensions.conf`.

## Como testar manualmente
1. `docker compose up -d`
2. Faça uma chamada até a telefonista (direto no `1000`, ou via fila
   discando `800` de outro ramal)
3. Fale alguma coisa, encerre a chamada
4. Confira se apareceu um arquivo `.wav` em `./recordings/` no host
5. Na interface web, clique "Atualizar" no painel "Gravações" — a
   chamada deve aparecer na lista, com um player de áudio funcional

## Teste automatizado
- `queue-api/tests/test_recordings.py` — listagem (ordenação, limite,
  filtro por extensão) e proteção contra path traversal no nome do
  arquivo pedido
- `tests/test_ami_config.py::test_queue_records_calls_automatically`
- `tests/test_extensions_conf.py::test_receptionist_calls_are_recorded`
- `tests/test_docker_compose.py::test_recordings_volume_shared_between_asterisk_and_queue_api`
- `tests/test_webphone_html.py::test_recordings_panel_uses_embedded_audio_player`

## Limitações conhecidas (honestidade técnica)
- **Sem teste de integração real** — nenhum teste automatizado grava
  uma chamada de verdade e confere o áudio resultante; isso exigiria
  um Asterisk rodando de fato (mesma limitação já documentada para o
  tronco TDM e o AMI)
- **Sem autenticação** no endpoint de gravações — qualquer um que
  alcançar a porta do `queue-api` na rede pode listar e ouvir
  gravações. Aceitável só em rede interna confiável; precisa de
  camada de auth antes de qualquer exposição maior
- **Sem exclusão automática** — as gravações se acumulam
  indefinidamente em `./recordings/`; não há rotina de limpeza/retenção
  configurada
- Chamadas puramente internas entre ramais (ex: `1001` ligando pra
  `1002`) **não** são gravadas — só as que envolvem a telefonista, que
  é o escopo original do pedido
- Sem indicação sonora "esta chamada está sendo gravada" pro cliente -
  dependendo da legislação aplicável, isso pode ser exigido
  legalmente; vale verificar antes de usar em produção
