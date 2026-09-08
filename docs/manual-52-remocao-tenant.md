# Manual 52 — Remoção de tenant pelo wizard (item #52)

## O que fecha
O manual 39 (wizard de preparação de ambiente) documentou
explicitamente como limitação: **"sem remoção de tenant pelo wizard —
só criação"**. Este item fecha essa lacuna.

## Como funciona
Na tabela de tenants do painel, cada linha agora tem um botão
"Remover". Ao confirmar:
1. Desregistra o DID do tenant (AstDB, família `tenant-did`)
2. Apaga os 5 arquivos de infraestrutura gerados pelo wizard
   (`pjsip_tenants/{id}.conf`, `queues_tenants/{id}.conf`,
   `extensions_tenants/{id}.conf`, `voicemail_tenants/{id}.conf`,
   `parking_tenants/{id}.conf`)
3. Recarrega o Asterisk (`pjsip reload`, `dialplan reload`,
   `voicemail reload`, `queue reload all`, `parking reload`)
4. Remove o tenant da lista persistida (`tenants.json`)

## Proteção pros exemplos estáticos
`t1`/`t2` **nunca** podem ser removidos por aqui — são os exemplos
estáticos originais do projeto, configurados manualmente
(`pjsip.conf`, `queues.conf`, `extensions.conf`), não gerenciados
pelo wizard. `validate_tenant_removal` recusa explicitamente antes de
qualquer arquivo ser tocado.

## Ordem importa
A validação (`t1`/`t2` protegidos, tenant precisa existir de fato)
acontece **antes** de qualquer arquivo ser apagado — um pedido
malformado não pode apagar arquivo de um tenant que nem deveria ser
removido. Testado explicitamente
(`test_remove_tenant_validates_before_deleting_any_file`).

## Como usar
1. Logue no painel como admin
2. Seção "Preparar ambiente de um tenant novo" — a tabela de tenants
   já criados agora tem uma coluna de ação
3. Clique "Remover" no tenant desejado, confirme o popup (avisa que
   apaga dialplan, telefonistas, filas e vaga de estacionamento — não
   dá pra desfazer)

## Como testar manualmente
1. Crie um tenant de teste pelo wizard (manual 39)
2. Confirme que os 5 arquivos existem em `asterisk/*_tenants/`
3. Remova pelo painel
4. Confirme que os 5 arquivos sumiram
5. Confirme que discar o DID desse tenant não cai mais na URA dele
   (volta a cair no padrão, tenant 1)
6. Tente remover `t1`/`t2` diretamente pela API — confirme que é
   recusado

## Teste automatizado
- `admin-api/tests/test_tenants.py` (4 testes novos) —
  `validate_tenant_removal`: recusa t1/t2, recusa tenant desconhecido,
  aceita tenant existente, tolerante a maiúscula/espaço
- `admin-api/tests/test_server_security.py` (3 testes novos) —
  admin-only, validação antes de apagar qualquer arquivo, DID
  desregistrado e lista persistida só depois da tentativa de reload
- `tests/test_admin_html.py` (3 testes novos) — botão presente na
  tabela, exige confirmação, chama o endpoint `DELETE` certo
- **814 testes no total**, em 8 suítes

## Limitações conhecidas (honestidade técnica)
- **Sem confirmação em duas etapas** (tipo "digite o nome do tenant
  pra confirmar") — só um `confirm()` de navegador, mais simples que
  o padrão usado em ações destrutivas mais sensíveis (ex: desativar
  monitoramento de chamada, manual 42)
- **Ramais dinâmicos criados dentro daquele tenant (pelo painel,
  manual 38) não são limpos automaticamente** — o `#include` deles
  (`extensions_dynamic_dial-{tenant}.conf`) fica órfão, referenciando
  um contexto que não existe mais; não causa erro no Asterisk (arquivo
  vazio/simplesmente não é mais alcançável), mas fica como lixo no
  disco
- **Sem período de graça/soft-delete** — a remoção é imediata e
  definitiva, sem backup automático dos arquivos antes de apagar
- **Nunca testado contra um Asterisk real** — mesma situação já
  documentada pro resto das integrações AMI deste projeto
