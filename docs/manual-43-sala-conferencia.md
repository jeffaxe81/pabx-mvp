# Manual 43 — Sala de conferência ad-hoc (item #43)

## O que é
Uma sala de conferência de verdade — várias pessoas conversando ao
mesmo tempo — diferente do **grupo de toque** (manual 24), que toca
em vários ramais até *um* atender. Usa o módulo nativo `ConfBridge`
do Asterisk.

## Como funciona
Disque `40` + 4 dígitos (o número da sala) pra entrar ou criar a
conferência — ex: `400001`. Se a sala ainda não existe, o Asterisk
cria na hora; se já existe (alguém já entrou), você se junta a ela.

```
Discar 400001 → ConfBridge("sala-t1-0001", ...)
```

Durante a chamada, aperte `*` pra alternar mudo/áudio.

## Isolamento por tenant
O nome interno da sala já embute o tenant (`sala-t1-0001` vs
`sala-t2-0001`) — dois tenants discando exatamente o mesmo número de
sala **nunca** caem na mesma conferência. Isso é essencial: `ConfBridge`
por padrão vive num namespace único e global no Asterisk (não é
isolado por contexto automaticamente), então sem esse prefixo dois
tenants diferentes discando "0001" cairiam juntos na mesma sala — um
vazamento grave de isolamento entre empresas diferentes.

## Perfis compartilhados, isolamento pelo nome
Diferente da lista de bloqueio/VIP/feriado (que têm família AstDB
separada por tenant), aqui os **perfis de conferência**
(`default_bridge`/`default_user`/`default_menu` em
`asterisk/confbridge.conf`) são compartilhados entre todos os
tenants — não há nada sensível neles (limite de participantes, avisos
de entrada/saída), então não precisam ser duplicados. O isolamento
de verdade acontece só no nome da sala, que já é montado
dinamicamente com `${TENANT}`.

## Tenants criados pelo wizard
Qualquer tenant novo criado pelo wizard (manual 39) já nasce com a
mesma capacidade de sala de conferência — o padrão de dial (`_40XXXX`)
é gerado automaticamente no dialplan desse tenant, sem precisar de
configuração extra.

## Como testar manualmente
1. `docker compose up -d`
2. De três ramais diferentes do mesmo tenant, disque `400001`
3. Confirme que os três se ouvem, e que há aviso sonoro de
   entrada/saída conforme cada um entra
4. Aperte `*` num dos ramais — confirme que ele fica mudo pros outros
5. De um ramal do **outro tenant**, disque `400001` também — confirme
   que cai numa sala **diferente** (não ouve os três do primeiro teste)

## Teste automatizado
- `tests/test_confbridge_conf.py` (5 testes) — perfis existem,
  limite de participantes configurado, gravação desligada por padrão,
  aviso de entrada/saída ativo, mudo vinculado à tecla `*`
- `tests/test_extensions_conf.py`:
  - `test_both_tenants_have_conference_room_dial_pattern`
  - `test_conference_room_name_embeds_tenant_for_isolation` — o
    teste que garante que o vazamento entre tenants descrito acima
    nunca acontece por acidente numa mudança futura
  - `test_conference_room_uses_the_configured_profiles`
- `admin-api/tests/test_tenants.py::test_render_extensions_includes_conference_room_pattern`
- `tests/test_docker_compose.py::test_confbridge_conf_mounted`

## Limitações conhecidas (honestidade técnica)
- **Sem gravação de conferência** — `record_conference = no` de
  propósito; isso seria uma funcionalidade própria (com os mesmos
  cuidados de aviso/LGPD do manual 40), não implementada ainda
- **Sem PIN de acesso à sala** — qualquer ramal do tenant que souber
  o número entra direto; diferente do monitoramento de chamada
  (manual 42), aqui não há a mesma natureza de vigilância que
  justificaria essa fricção extra, mas empresas que quiserem PIN
  precisariam adicionar isso manualmente (ex: `Read()` antes do
  `ConfBridge()`, seguindo o mesmo padrão já usado no monitoramento)
- **20 participantes no máximo** por sala (`max_members`) — fixo,
  precisaria editar `confbridge.conf` pra mudar
- **Sem lista de salas ativas na interface** — não há um painel
  mostrando quais salas existem no momento nem quem está em cada uma
- **Sem teste de integração real** contra `ConfBridge`/Asterisk
  rodando de verdade — mesma situação já documentada pro resto das
  partes que dependem do processo Asterisk real
