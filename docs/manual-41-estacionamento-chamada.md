# Manual 41 — Estacionamento de chamada (item #41)

## O que é
"Estacionar" uma chamada é diferente de transferir pra um ramal
específico: a telefonista coloca a chamada numa "vaga" numerada, e
**qualquer ramal do mesmo tenant** pode recuperá-la depois discando
o número da vaga — útil quando quem vai atender não está no próprio
ramal, ou quando a chamada precisa esperar alguém ficar disponível em
outro lugar da empresa.

Usa o módulo nativo `res_parking` do Asterisk — não é uma
funcionalidade construída do zero, é configuração de um recurso já
existente no Asterisk, exposta corretamente pro nosso desenho
multi-tenant.

## Como funciona
- **Estacionar**: durante uma chamada, a telefonista clica
  "Estacionar chamada" (ou qualquer ramal pode discar `75` durante
  uma transferência cega) — a chamada vai pra uma vaga livre
  (76 a 95)
- **Recuperar**: qualquer ramal do mesmo tenant disca o número da
  vaga (ex: `76`) pra reconectar com a chamada estacionada
- **Se ninguém recuperar a tempo**: a chamada toca de volta pra quem
  estacionou (`comebacktoorigin=yes`) — não fica esquecida no limbo

## Isolamento por tenant
Cada tenant tem sua própria vaga de estacionamento
(`asterisk/res_parking.conf`, seções `[parkinglot-t1]`/
`[parkinglot-t2]`), com o mesmo número (`75`/`76-95`) mas em contextos
diferentes (`t1-internal`/`t2-internal`) — uma chamada estacionada no
tenant 1 **nunca** aparece pro tenant 2, mesmo discando o mesmo
número de vaga. Tenants criados pelo wizard (manual 39) ganham a
própria vaga automaticamente — o `#include` com wildcard já
estabelecido nos outros arquivos (`pjsip.conf`, `queues.conf`, etc.)
também se aplica aqui.

## Como usar
Durante uma chamada ativa no console da telefonista, clique
"Estacionar chamada". Anuncie o número da vaga (76-95) pra quem vai
atender — no Asterisk de verdade, isso normalmente é anunciado por
voz de volta pra quem estacionou; nossa interface web ainda não capta
e mostra esse número automaticamente (ver limitação abaixo).

## Como testar manualmente
1. `docker compose up -d`
2. Ligue entre dois ramais, atenda a chamada
3. Clique "Estacionar chamada" (ou transfira cegamente pro número `75`)
4. De um terceiro ramal do mesmo tenant, disque `76` — confirme que
   reconecta com a chamada estacionada
5. Repita sem recuperar — confirme que, depois do tempo padrão, a
   chamada toca de volta pra quem estacionou
6. Confirme que um ramal do **outro tenant** discando `76` não
   consegue recuperar a chamada estacionada (contextos isolados)

## Teste automatizado
- `tests/test_res_parking_conf.py` (7 testes) — vagas existem pros
  dois tenants, cada uma isolada no próprio contexto, mesmo número
  reutilizado sem conflito, retorno automático configurado, BLF
  habilitado, nada dinâmico implícito, `#include` com wildcard
- `admin-api/tests/test_tenants.py` — o wizard gera a vaga de
  estacionamento certa pra tenant novo
- `tests/test_webphone_html.py::test_park_button_does_blind_transfer_to_parking_extension`
- `tests/test_docker_compose.py` — arquivo e diretório dinâmico
  montados no container do Asterisk

## Limitações conhecidas (honestidade técnica)
- **A interface web não mostra o número da vaga automaticamente** —
  quem estacionou precisa saber/ouvir o anúncio de voz do Asterisk
  (não capturado programaticamente na nossa UI) e informar
  manualmente pra quem vai recuperar
- **20 vagas fixas** (76-95) por tenant — não escala automaticamente,
  precisaria editar `parkpos` se um tenant precisar de mais
- **Sem teste de integração real** contra um Asterisk rodando de
  verdade — mesma situação já documentada pro resto das partes que
  dependem do processo Asterisk real
- **`comebacktoorigin` volta pra quem estacionou**, não pra quem
  estava na linha originalmente antes de várias transferências — se
  a chamada já passou por múltiplas mãos, "origem" é só o último
  estacionamento
