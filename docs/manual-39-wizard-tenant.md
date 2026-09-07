# Manual 39 — Wizard de preparação de ambiente por tenant

## O que é
No manual 38 (multi-tenant completo), documentei como limitação
conhecida: "adicionar um tenant 3 ainda exige editar `.conf` na mão".
Este épico fecha essa lacuna — um assistente guiado no painel de
administração que cria um tenant novo **de ponta a ponta**, sem
precisar editar nenhum arquivo de configuração.

## O que o wizard cria
Pra um tenant novo (ex: `t3`), com só três informações (ID, DID, nome
de exibição):
1. **Duas telefonistas web** (`t3-recepcao`, `t3-recepcao-2`) — mesmo
   padrão WebRTC das existentes
2. **Três filas** (`fila-t3`, `fila-t3-en`, `fila-t3-es`) — padrão,
   inglês e espanhol, mesma estrutura do tenant 1/2
3. **Dialplan completo** (`[t3-internal]`, `[t3-hints]`) — fila,
   operadores diretos com retorno automático, extensões de teste
   (700/800/650), tudo espelhando t1/t2
4. **Caixas de voz** das duas telefonistas
5. **Mapeamento de DID** — registrado no AstDB, pra chamadas de
   entrada pro número informado caírem automaticamente na URA desse
   tenant

## Decisão de arquitetura: `#include` com wildcard
Em vez de gerar um arquivo e pedir pra alguém adicionar uma linha
`#include` no `.conf` estático (o que ainda seria "editar arquivo na
mão", só que uma vez em vez de sempre), os quatro arquivos estáticos
(`pjsip.conf`, `queues.conf`, `extensions.conf`, `voicemail.conf`) já
têm, desde sempre:
```
#include pjsip_tenants/*.conf
#include queues_tenants/*.conf
#include extensions_tenants/*.conf
#include voicemail_tenants/*.conf
```

Cada tenant criado pelo wizard vira **um arquivo novo** dentro dessas
pastas (`pjsip_tenants/t3.conf`, etc.) — o wildcard pega
automaticamente, sem precisar tocar em nenhum arquivo estático de
novo. Criar um tenant 4, 5, 6... nunca muda esses quatro arquivos.

## Roteamento de DID dinâmico
`from-tdm-gateway` (manual 38) já checava `${TENANT}` antes de entrar
na URA. Agora, pra DIDs não mapeados explicitamente (os dois exemplos
manuais de t1/t2 continuam como estão), o dialplan consulta o AstDB:
```
exten => _X.,1,Set(TENANT=${DB(tenant-did/${EXTEN})})
 same => n,Set(TENANT=${IF($["${TENANT}" = ""]?t1:${TENANT})})
 same => n,Goto(ura-principal,s,1)
```
O wizard registra `tenant-did/<DID> = <tenant_id>` via AMI no momento
da criação — é isso que faz uma chamada pro DID novo cair na URA do
tenant certo, sem editar dialplan.

## Como usar
1. Logue no painel como admin
2. Seção "Preparar ambiente de um tenant novo"
3. Preencha ID (ex: `t3`), DID, nome de exibição
4. Clique "Revisar" — confirme os dados
5. Clique "Criar tenant" — os arquivos são gerados, o DID é
   registrado, e o Asterisk recarrega automaticamente
6. Registre `t3-recepcao`/`t3-recepcao-2` nos softphones das novas
   telefonistas

## Como testar manualmente
1. `docker compose up -d`
2. Crie um tenant `t3` pelo wizard, com um DID de teste
3. Confirme que os arquivos apareceram:
   `asterisk/pjsip_tenants/t3.conf`, `queues_tenants/t3.conf`,
   `extensions_tenants/t3.conf`, `voicemail_tenants/t3.conf`
4. Registre um softphone como `t3-recepcao`
5. De qualquer ramal, disque `700` (não vai funcionar direto — essa
   extensão é interna a cada tenant; disque um ramal DENTRO do t3, ou
   simule via `Originate` no AMI pro contexto `t3-internal,700,1`)
6. Confirme que a fila, a URA, e o dialplan completo do t3 funcionam
   exatamente como t1/t2

## Teste automatizado
- `admin-api/tests/test_tenants.py` (19 testes) — validação completa
  (ID reservado t1/t2 rejeitado, DID duplicado rejeitado, formato de
  ID, normalização de maiúsculas), e geração de texto pros 4 arquivos
- `admin-api/tests/test_server_security.py` — criação de tenant exige
  admin, valida antes de escrever qualquer arquivo, registra o DID e
  persiste só depois do sucesso
- `tests/test_extensions_conf.py`, `test_pjsip_conf.py`,
  `test_ami_config.py`, `test_voicemail_conf.py` — os 4 `#include`
  com wildcard estão presentes
- `tests/test_docker_compose.py` — as 4 pastas dinâmicas estão
  montadas no container do Asterisk
- `tests/test_admin_html.py` — wizard escondido de supervisor, fluxo
  de dois passos (revisão antes de criar), reporta falha de reload
  sem escondê-la
- **639 testes no total**, em 7 suítes

## Limitações conhecidas (honestidade técnica)
- **Sem remoção de tenant pelo wizard** — só criação. Remover um
  tenant exigiria apagar os 4 arquivos manualmente e desregistrar o
  DID (`DBDel` na família `tenant-did`) — não implementado
- **IDs só seguem o padrão `tN`** (`t3`, `t4`, ...) — não dá pra usar
  nomes de tenant mais descritivos (ex: "empresa-c")
- **Senha SIP das telefonistas geradas é sempre a mesma string
  previsível** (`troque_esta_senha_web_{tenant}`) — precisa trocar
  manualmente antes de produção, mesma limitação já aceita nos
  exemplos estáticos t1/t2 desde o início do projeto
- **Nenhuma configuração de horário comercial customizada por
  tenant** — todos usam o mesmo horário fixo (08:00-18:00, seg-sex)
  definido em `[horario-comercial]`, que é compartilhado
- **Não valida se o reload de verdade aplicou tudo** — só reporta se
  os comandos AMI de reload retornaram sucesso; não confirma de fato
  que a chamada de teste funciona
