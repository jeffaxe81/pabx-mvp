# Manual 33 — Transferência inteligente por regra (item #28)

## O que é
Roteamento de chamada que decide o destino considerando **quem está
ligando** (cliente VIP), **quando** (horário/feriado, manual 23) e
**assunto** (opção do menu, manual 23) — com **retorno automático**
de verdade se o destino escolhido não atender, em vez de simplesmente
desistir da chamada.

Essa funcionalidade formaliza e completa peças que já existiam
(URA por horário e por assunto), e adiciona duas coisas novas:
**identificação de cliente VIP** e o **retorno automático correto**.

## Regra por cliente (novo: clientes VIP)
Um número de cliente pode ser associado a um **ramal de destino
específico** — a chamada dele pula a URA e a fila geral inteiramente,
indo direto pro ramal configurado. Guardado no AstDB (família `vip`),
mesmo banco já usado pra lista de bloqueio (manual 20) e modo feriado
(manual 23), gerenciável pelo painel de administração.

**Prioridade das regras** (checadas nessa ordem em `[ura-principal]`):
1. Cliente VIP (número bate na família `vip`) → vai direto, ignora
   até o modo feriado
2. Modo feriado ligado → mensagem de feriado
3. Fora do horário comercial → mensagem de fora de expediente
4. Horário comercial normal → menu da URA (regra por assunto)

## Regra por horário e por assunto (já existiam, aqui formalizadas)
- **Horário**: `GotoIfTime()` na URA (manual 23)
- **Assunto**: dígito 1 (vendas → fila geral) ou 2 (suporte → ramal
  direto) no menu da URA (manual 23)

## Retorno automático (corrigido de verdade)
Antes desta funcionalidade, se um ramal direto (1010, 1011, ou a
chamada puxada da fila) **não fosse atendido**, o dialplan
simplesmente seguia pra pesquisa de satisfação — o que não fazia
sentido pra uma conversa que nunca aconteceu. Agora:

```
exten => 1010,1,...
 same => n,Dial(PJSIP/t1-recepcao,20,g)
 same => n,GotoIf($["${DIALSTATUS}" = "ANSWER"]?pesquisa-satisfacao,s,1)
 same => n,Goto(t1-internal,1000,1)   ; RETORNO AUTOMÁTICO pra fila geral
```

Se `t1-recepcao` não atender (`DIALSTATUS` diferente de `ANSWER`), a
chamada **volta pra fila geral** (ramal `1000`) em vez de cair na
pesquisa de satisfação ou simplesmente ser perdida. O mesmo vale pra
`1011` e pro pickup dirigido. Pra `1000` (a própria fila), a checagem
equivalente usa `${QUEUESTATUS}` — só vai pra pesquisa se
`CONTINUE` (alguém atendeu e depois desligou); qualquer outro
resultado cai na caixa de recado.

## Como configurar clientes VIP
Pelo painel de administração, seção "Clientes VIP": número do
cliente + ramal de destino (ex: `1010`). Ou pela API:
```bash
curl -X POST http://<ip>:8091/api/vip \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"number": "11999998888", "target_extension": "1010"}'
```

## Como testar manualmente
1. Cadastre um número de teste como VIP, apontando pro ramal `1010`
2. Ligue desse número (ou simule o Caller ID) — confirme que cai
   direto no ramal `1010`, sem passar pela URA
3. Ligue de um número comum pro `1000` e não deixe ninguém atender —
   confirme que, depois do timeout, cai na caixa de recado (não na
   pesquisa de satisfação)
4. Ligue pro `1010` diretamente e não atenda — confirme que a chamada
   **volta pra fila geral** automaticamente em vez de simplesmente
   cair

## Teste automatizado
- `admin-api/tests/test_vip.py` — validação de número/ramal de destino
- `admin-api/tests/test_server_security.py` — rota de VIP também
  admin-only, checada antes de mexer na AMI
- `tests/test_extensions_conf.py`:
  - `test_vip_check_has_priority_over_holiday_and_business_hours`
  - `test_vip_route_uses_dynamic_extension_from_astdb`
  - `test_no_answer_falls_back_automatically_instead_of_giving_up`
  - `test_queue_only_surveys_if_actually_answered`
- `tests/test_admin_html.py::test_vip_section_exists_and_manages_target_extension`

## Limitações conhecidas (honestidade técnica)
- **"Assunto" continua sendo só a opção digitada na URA** — não há
  reconhecimento de assunto por voz nem histórico do cliente
- **VIP é só número → ramal fixo** — não dá pra combinar regra de VIP
  com horário (ex: "VIP de dia vai pro ramal X, à noite vai pra
  caixa de voz VIP") neste MVP
- **Retorno automático sempre vai pra fila geral (`1000`)**, não pra
  um "ramal de origem" specífico no sentido de quem transferiu — pra
  chamadas de entrada não existe literalmente uma pessoa "de origem"
  como haveria numa transferência feita por um humano; a interpretação
  usada aqui é "volta pro ponto de entrada geral", documentada assim
  de propósito
- **Sem teste de integração real** do fluxo completo (checagem AstDB
  real, `DIALSTATUS`/`QUEUESTATUS` de verdade) — mesma situação já
  documentada pro resto das integrações que dependem do Asterisk de
  verdade rodando
