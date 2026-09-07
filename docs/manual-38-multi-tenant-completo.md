# Manual 38 — Multi-tenant completo

## O que mudou
Até esta funcionalidade, o multi-tenant do projeto (manual 03) era só
isolamento de ramal e chamada interna — todas as ~30 funcionalidades
construídas depois (fila, URA, gravação, callback, pesquisa de
satisfação, transferência inteligente, grupos de toque, regras de
discagem, presença, multilíngue, painel de administração) só
existiam de verdade pro tenant 1. Esta funcionalidade estende **cada
uma delas** pro tenant 2, e formaliza o padrão pra adicionar um
tenant 3, 4, etc.

## Decisão de arquitetura: parametrizar, não duplicar
A abordagem ingênua seria duplicar cada contexto por tenant
(`ura-principal-t1`, `ura-principal-t2`, `horario-comercial-t1`,
`horario-comercial-t2`, ...) — isso dobraria (ou N-uplicaria) o
tamanho do dialplan a cada tenant novo, e qualquer correção de bug
precisaria ser replicada em N lugares.

Em vez disso, os contextos que fazem sentido serem compartilhados
(URA, seleção de idioma, VIP, callback, atendente virtual) usam uma
variável de canal `${TENANT}`, definida **antes** de entrar neles:

```
; from-tdm-gateway define o tenant baseado no DID:
exten => 5511900002222,1,Set(TENANT=t2)
 same => n,Goto(t2-internal,1001,1)

; ...mais adiante, dentro da URA (contexto ÚNICO, compartilhado):
exten => vip-direto,1,Goto(${TENANT}-internal,${VIP_DESTINO},1)
```

Isso significa: **um bug corrigido na URA é corrigido pra todos os
tenants de uma vez**, e adicionar um tenant novo não duplica lógica de
roteamento — só duplica o que genuinamente precisa existir por tenant
(ramais, filas, endpoints).

## O que cada camada ganhou

### Dialplan (`asterisk/extensions.conf`)
- `[t2-internal]` ganhou os mesmos recursos de `[t1-internal]`: fila
  (`exten 1000`), operadores diretos com retorno automático (`1010`/
  `1011`), extensões de teste (`700`/`800`/`650`)
- `[t2-hints]` criado, espelhando `[t1-hints]`
- `[ura-principal]`, `[selecionar-idioma]`, `[rotear-horario]`,
  `[horario-comercial]`, `[callback-connect]`, `[atendente-virtual]`
  — todos parametrizados com `${TENANT}`, contextos únicos
- `[pickup-target]` ganhou entradas pra `t2-recepcao`/`t2-recepcao-2`

### AstDB (bloqueio, VIP, modo feriado)
Famílias por tenant: `blocklist-t1`/`blocklist-t2`,
`vip-t1`/`vip-t2`, `config-t1`/`config-t2`. Bloquear um número no
tenant 1 não afeta o tenant 2, e vice-versa.

### Painel de administração (`admin-api`)
- `admin/index.html` ganhou um **seletor de tenant** no topo — troca
  o tenant recarrega ramais, lista de bloqueio, clientes VIP e modo
  feriado, todos filtrados pro tenant selecionado
- `store.py`: ramais dinâmicos agora têm campo `tenant`; números podem
  **repetir entre tenants** (contextos isolados), só precisam ser
  únicos dentro do mesmo tenant
- `conf_generator.py`: os arquivos de dial/hints/voicemail gerados
  pelo painel viraram **um arquivo por tenant**
  (`extensions_dynamic_dial-t1.conf`/`-t2.conf`, etc.) — um arquivo
  compartilhado colocaria ramal do tenant 2 dentro do dialplan do
  tenant 1, o que quebraria o isolamento

### queue-api
`PICKUP_ALLOWED_EXTENSIONS` e `CLICK_TO_CALL_ALLOWED_EXTENSIONS`
agora incluem ramais dos dois tenants por padrão. Campanhas, callback,
pesquisa de satisfação, detecção de fraude e monitoramento de
qualidade **já eram tenant-agnósticos** desde que foram construídos
(operam em cima do nome do canal/ramal, não de um tenant fixo) — não
precisaram de mudança nenhuma.

### Telefonistas do tenant 2 (novo)
`t2-recepcao` e `t2-recepcao-2`, endpoints WebRTC completos (mesmo
padrão de `t1-recepcao`), com fila (`fila-t2`, `fila-t2-en`,
`fila-t2-es`), hints combinados, e caixa de voz.

## Como testar
1. Registre um softphone como `t2-recepcao` (console da telefonista
   web funciona igual ao do tenant 1)
2. De um ramal do tenant 2, disque `700` (teste de URA) — confirme que
   funciona igual ao tenant 1, mas mostra "(tenant t2)" nos logs
3. Bloqueie um número pelo painel com o seletor em "Tenant 2" —
   confirme que ligar desse número **só** é bloqueado quando discado
   por dentro do tenant 2, não do tenant 1
4. Crie um ramal novo pelo painel com "Tenant 2" selecionado, número
   `1150` — depois troque pro tenant 1 e crie outro ramal, também
   número `1150` — confirme que os dois coexistem sem conflito
5. Ligue pro DID `5511900002222` (ou simule via `700` internamente) e
   confirme que a URA, a fila, e a pesquisa de satisfação depois da
   chamada funcionam de ponta a ponta pro tenant 2

## Bugs reais encontrados durante este trabalho (fora do escopo original, mas corrigidos)
Ao mexer em `ami_client.py`, encontrei um **erro de sintaxe real**
(dois métodos colados sem quebra de linha) que quebrava a importação
do módulo inteiro desde o commit do item #28 — e um segundo bug
idêntico em `queue-api/server.py`. Nenhum teste pegava isso porque os
testes de segurança desses arquivos (`test_server_security.py`/
`test_server_routes.py`) só leem o código como **texto** (pra
verificar decisões como "checa papel antes de mutar"), nunca fazem
`import server` de verdade. Também encontrei `self._lock` usado sem
nunca ter sido definido no `__init__`.

Corrigidos, e adicionei `test_module_importability.py` em **todas as
7 suítes** do projeto — importa cada módulo Python de verdade,
fechando esse buraco de cobertura permanentemente.

## Teste automatizado
- `tests/test_extensions_conf.py` — mais de 10 testes novos: tenant 2
  tem fila/operadores/retorno automático/extensões de teste, hints
  espelham o tenant 1, `from-tdm-gateway` define `${TENANT}` antes de
  entrar em contexto compartilhado, VIP/bloqueio usam família por
  tenant
- `tests/test_pjsip_conf.py::test_tenant2_telephonist_endpoints_use_webrtc_template`
- `tests/test_ami_config.py::test_language_specific_queues_exist` (e
  equivalente novo pro tenant 2)
- `tests/test_voicemail_conf.py` — caixas de voz das telefonistas dos
  dois tenants
- `admin-api/tests/test_store.py` — números repetem entre tenants,
  rejeitam tenant desconhecido
- `admin-api/tests/test_conf_generator.py` — arquivos gerados
  corretamente separados por tenant
- `admin-api/tests/test_server_security.py` — tenant validado antes
  de qualquer mutação AstDB, listagem de ramais filtra por tenant
- `tests/test_admin_html.py` — seletor de tenant recarrega tudo,
  todas as chamadas incluem o tenant certo
- **606 testes no total**, em 7 suítes

## Limitações conhecidas (honestidade técnica)
- **`from-tdm-gateway` não tem tabela real de faixas de DID por
  tenant** — o "pega-tudo" pra números não mapeados assume tenant 1.
  Em produção de verdade com múltiplos tenants recebendo ligação
  externa sem DID específico, isso precisaria de uma tabela real
  (DID → tenant), não implementada aqui
- **Fora de horário e feriado continuam só em português** (mesma
  limitação já aceita no manual 35, atendimento multilíngue) — vale
  pros dois tenants igualmente
- **Sem painel de gerenciamento de tenants em si** — adicionar um
  tenant 3 ainda exige editar `.conf` na mão (pjsip.conf, queues.conf,
  extensions.conf, voicemail.conf) seguindo o padrão documentado aqui;
  não há uma tela "criar tenant novo" no painel de administração
- **Nomes de ramal dinâmico continuam globalmente únicos**, não
  prefixados por tenant — dois tenants não podem ter um ramal
  dinâmico com o mesmo `name` (só o `number` pode repetir)
- **Detecção de fraude, monitoramento de qualidade, backup e
  transcrição/IA são tenant-agnósticos por natureza** (operam sobre
  todas as chamadas/gravações igualmente) — não fazem distinção nem
  precisam fazer, já que essas funcionalidades fazem sentido
  aplicadas ao PABX inteiro, não a um tenant isolado
