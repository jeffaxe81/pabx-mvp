# Manual 42 — Monitoramento de chamada (item #42)

## Leia isto primeiro — implicações legais reais
Monitoramento de chamada (escuta silenciosa, sussurro, intercalação)
é **vigilância de conversa de terceiros** — de um atendente, e em
alguns casos também do cliente do outro lado da linha. Isso não é só
uma questão técnica:

- No Brasil, a legislação trabalhista e o entendimento consolidado
  dos tribunais tratam monitoramento de ligação de empregado como uma
  prática que exige, no mínimo, **transparência com o funcionário**
  (política interna clara, ciência prévia de que as chamadas podem
  ser monitoradas) — monitoramento secreto e sistemático pode ser
  questionado juridicamente
- A LGPD também se aplica: a conversa monitorada envolve dados
  pessoais de quem está ligando
- **Este projeto não substitui orientação jurídica.** Antes de
  configurar isso em produção, consulte a área jurídica/RH da
  empresa sobre política de monitoramento, e certifique-se de que os
  atendentes tenham ciência formal (ex: contrato de trabalho,
  política interna assinada) de que isso pode acontecer

O código foi construído com controles técnicos (PIN, papel restrito a
admin) — mas controle técnico não substitui adequação legal.

## O que é
Três modos de monitoramento, todos usando o `ChanSpy()` nativo do
Asterisk:
- **Escuta silenciosa** (`*81` + ramal) — o supervisor ouve a
  conversa, ninguém nos dois lados percebe
- **Sussurro** (`*82` + ramal) — o supervisor fala só com o
  atendente; o cliente não ouve
- **Intercalação** (`*83` + ramal) — o supervisor entra na conversa
  de verdade, os três se ouvem (equivalente a uma "barge-in")

Exemplo: discar `*811010` faz escuta silenciosa na telefonista 1
(ramal `1010`).

## Proteção por PIN
Sem PIN configurado (por tenant), o monitoramento fica **bloqueado
por completo** — a chamada cai direto num aviso de "não configurado"
e desliga. Configurar o PIN é uma ação **admin-only** no painel (mais
restrita que o modo feriado, que supervisor também pode alterar) —
configurar vigilância é uma decisão de peso diferente de ligar uma
mensagem de feriado.

## Arquitetura
Mesmo padrão da URA/callback/atendente virtual: um contexto
**único e compartilhado** entre tenants (`[chamada-monitorada]`),
parametrizado por `${TENANT}`/`${MONITOR_MODE}`/`${MONITOR_TARGET}` —
não duplicado por tenant. O PIN é guardado por tenant no AstDB
(`monitoring-pin-{tenant}`), então cada tenant tem seu próprio PIN
independente.

```
*81/*82/*83 + ramal → [chamada-monitorada]
                         ↓ checa PIN (por tenant)
                       Read() + comparação
                         ↓ autorizado
                       mapeia ramal (1010/1011) → nome do endpoint real
                         ↓
                       ChanSpy(endpoint, opções do modo)
```

## Como configurar
1. Logue no painel como admin
2. Seção "PIN de monitoramento de chamada" (aviso legal já vem ali)
3. Configure um PIN de 4-10 dígitos pro tenant selecionado
4. Pra desativar depois: botão "Desativar monitoramento" (com
   confirmação)

## Como testar manualmente
1. Configure o PIN pro tenant de teste
2. Coloque a telefonista `t1-recepcao` (ramal `1010`) numa chamada
3. De outro ramal do mesmo tenant, disque `*811010`
4. Digite o PIN quando solicitado
5. Confirme que ouve a conversa silenciosamente (nem a telefonista
   nem o outro lado percebem)
6. Repita com `*821010` (sussurro) — fale, confirme que só a
   telefonista ouve
7. Repita com `*831010` (intercalação) — confirme que os três se ouvem
8. Desative o PIN pelo painel, tente monitorar de novo — confirme que
   cai direto no aviso de "não configurado"

## Teste automatizado
- `tests/test_extensions_conf.py` (5 testes): os 3 prefixos existem
  nos dois tenants com o modo certo, PIN vazio bloqueia antes de
  qualquer coisa, comparação de PIN acontece antes de autorizar,
  cada modo usa as opções certas do `ChanSpy` (trocar `w`/`B` seria
  um vazamento sério — o sussurro vazando pro cliente, por exemplo),
  destino inválido não tenta espionar canal nenhum
- `admin-api/tests/test_monitoring.py` (6 testes) — validação de PIN
- `admin-api/tests/test_server_security.py` — rotas exigem `admin`
  (não `supervisor`), PIN validado antes de escrever no AstDB, PIN
  nunca devolvido de volta pro navegador (só "configurado: sim/não")
- `tests/test_admin_html.py` — seção escondida de supervisor, aviso
  legal presente no texto, desativação exige confirmação

## Limitações conhecidas (honestidade técnica)
- **Só cobre as telefonistas** (`1010`/`1011`) — ramais dinâmicos
  criados pelo painel não têm mapeamento automático pro `ChanSpy`
  ainda (precisaria de uma tabela ramal→endpoint mais genérica)
- **PIN único compartilhado por tenant** — não há PIN individual por
  supervisor, nem log de quem usou o PIN pra monitorar o quê (uma
  auditoria completa exigiria capturar isso via evento AMI, não
  implementado)
- **Sem aviso sonoro pro atendente monitorado** — a escuta é
  deliberadamente silenciosa (é o propósito do recurso), o que reforça
  a importância da política/consentimento prévio mencionada no início
  deste manual, já que a pessoa não é avisada NAQUELE momento
- **Sem teste de integração real** contra `ChanSpy`/Asterisk rodando
  de verdade — mesma situação já documentada pro resto das partes que
  dependem do processo Asterisk real
