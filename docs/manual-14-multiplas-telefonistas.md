# Manual 14 — Múltiplas telefonistas simultâneas (backlog #8)

## O que é
Duas (ou mais) telefonistas podem estar logadas ao mesmo tempo na
interface web, cada uma com seu próprio ramal. As chamadas que chegam
pela linha de recepção (`1000`) são distribuídas **em round-robin**
entre quem estiver livre — não é sempre a mesma pessoa atendendo tudo.

## O que mudou estruturalmente
Essa foi a funcionalidade que mais mexeu na arquitetura já existente:

1. **`1000` deixou de ser um ramal fixo** e virou a entrada da fila
   (`Queue(fila-t1)`). Antes discava direto pra `t1-recepcao`; agora
   qualquer telefonista logada pode atender
2. **Dois ramais diretos novos**: `1010` (telefonista 1, mesma pessoa
   que era `t1-recepcao`) e `1011` (telefonista 2, `t1-recepcao-2`) —
   uso interno da equipe, pra falar com uma pessoa específica em vez
   da recepção em geral
3. **`queues.conf`**: `strategy` mudou de `ringall` pra `rrmemory`
   (round-robin com memória — lembra quem atendeu por último, não
   sempre bate na primeira da lista)
4. **Pickup dirigido ficou por-operador**: antes o Redirect sempre
   mandava a chamada puxada pra um ramal fixo; agora o webphone manda
   **qual ramal está pedindo** (`extension` no corpo da requisição),
   validado contra uma allowlist (`PICKUP_ALLOWED_EXTENSIONS`)
5. **Hint combinado**: `1000` no BLF agora reflete o estado das duas
   telefonistas juntas (`PJSIP/t1-recepcao&PJSIP/t1-recepcao-2`) — só
   aparece "ocupado" se as duas estiverem em chamada

## Como adicionar uma 3ª telefonista
1. `pjsip.conf`: duplique o bloco `t1-recepcao-2`, trocando pra
   `t1-recepcao-3` (endpoint + auth + aor)
2. `queues.conf`: adicione `member => PJSIP/t1-recepcao-3`
3. `extensions.conf`:
   - Ramal direto: `exten => 1012,1,MixMonitor(...)` + `Dial(PJSIP/t1-recepcao-3,20)`
   - Hint: `exten => 1012,hint,PJSIP/t1-recepcao-3`
   - Atualize o hint combinado de `1000` pra incluir o terceiro:
     `PJSIP/t1-recepcao&PJSIP/t1-recepcao-2&PJSIP/t1-recepcao-3`
   - `[pickup-target]`: adicione a entrada `exten => t1-recepcao-3,1,...`
4. `docker-compose.yml`: adicione `t1-recepcao-3` em
   `PICKUP_ALLOWED_EXTENSIONS`
5. `webphone/index.html`: adicione `{ ext: '1012', label: 'Telefonista 3' }`
   no array `COLLEAGUES`

## Como testar manualmente
1. `docker compose up -d`
2. Abra a interface web em **duas abas/dispositivos diferentes**,
   logando uma como `t1-recepcao` e outra como `t1-recepcao-2`
3. De outro ramal, disque `1000` várias vezes seguidas (uma chamada
   de cada vez, desligando entre elas) — confirme que a distribuição
   alterna entre as duas telefonistas, não bate sempre na mesma
4. Com as duas telefonistas ocupadas em chamadas diferentes, disque
   `1000` de novo — a chamada deve esperar na fila e aparecer no
   painel "Fila de espera" de **ambas** as interfaces
5. Uma das telefonistas clica "Atender" nessa chamada em espera — a
   chamada deve tocar **só na interface de quem clicou**, não na outra
6. Disque `1010` diretamente — deve tocar só na telefonista 1,
   ignorando se ela está livre ou não (é dial direto, não fila)

## Teste automatizado
- `queue-api/tests/test_pickup.py` — validação de qual ramal pode
  puxar (allowlist), rejeição de ramal não autorizado
- `tests/test_ami_config.py::test_queue_uses_round_robin_strategy_for_multiple_operators`
- `tests/test_ami_config.py::test_queue_fila_t1_exists_with_receptionist_as_member`
  (agora confere os dois membros)
- `tests/test_extensions_conf.py::test_pickup_target_context_dials_receptionist`
  (agora confere as duas entradas por operador)
- `tests/test_extensions_conf.py::test_direct_operator_extensions_are_recorded`
- `tests/test_webphone_html.py::test_pickup_sends_own_extension_along_with_channel`
- `tests/test_webphone_html.py::test_my_extension_is_captured_on_registration`

## Limitações conhecidas (honestidade técnica)
- **Número fixo de operadoras configuradas manualmente** — não existe
  cadastro dinâmico; adicionar uma nova telefonista é editar 4-5
  arquivos manualmente (ver seção acima), não um formulário
- **`rrmemory` não é perfeitamente justo sob carga concorrente** — é
  o comportamento padrão do Asterisk, adequado pra este MVP, mas não
  é um scheduler sofisticado
- **A troca de round-robin real só é visível com Asterisk de
  verdade** — como sempre, esse é o tipo de comportamento que só um
  teste de integração contra um Asterisk rodando validaria de fato
- **Sem noção de "capacidade" por telefonista** — todas são tratadas
  como iguais; não há prioridade nem peso diferente por operadora
  (o `weight` do `queues.conf` existe pra isso, mas não é usado aqui)
