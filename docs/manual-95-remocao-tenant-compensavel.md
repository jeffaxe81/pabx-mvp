# Manual 95 — Remoção compensável de tenant e ramais

## Alteração

O wizard anterior excluía arquivos e ramais antes de consultar
o Asterisk. Mesmo quando o AMI rejeitava a exclusão do DID,
a API confirmava a operação, deixando configurações e cadastro
possivelmente divergentes.

Agora a remoção utiliza um fluxo compensável:

1. Confirmar autorização, identidade e existência do tenant.
2. Bloquear outras criações/remoções de tenant e alterações de
   ramais realizadas no mesmo processo administrativo.
3. Guardar snapshots dos cinco arquivos de infraestrutura e dos
   três arquivos dinâmicos do tenant; recusar links simbólicos,
   arquivos ausentes ou configuração irregular.
4. Remover os oito arquivos e publicar uma nova versão do PJSIP
   dinâmico compartilhado, sem os endpoints da empresa excluída.
5. Solicitar `DBDel` do DID via AMI e validar recargas.
6. Persistir a exclusão dos ramais no JSON e depois atualizar
   o catálogo de tenants. Só então responder HTTP 200.

## Falhas e recuperação

Quando a remoção falha, a rotina tenta restaurar os arquivos do
Asterisk, o cadastro de ramais se já alterado, a associação do DID
via uma conexão AMI independente e o runtime da configuração anterior.

A API passa a responder HTTP 502 em caso de remoção não confirmada,
com `rollback_incomplete` sinalizando necessidade de reconciliação
manual. Ela não informa sucesso apenas por ter tentado uma operação.

## Testes

```bash
(cd admin-api && python3 -m pytest -q \
  tests/test_tenant_deprovisioning.py tests/test_server_security.py)
```

Os testes simulam recusa do DBDel, queda no login ou reload, erro ao
salvar o registro, arquivos incompletos, links simbólicos e falha da
compensação, preservando os dados de outra empresa.

## Limitações

As alterações são reversíveis por compensação, mas **não constituem
transação distribuída ACID**. Falhas elétricas, interrupção abrupta
do processo ou perda total do AMI podem exigir recuperação manual;
registros de voicemail já armazenados em outros volumes não são
apagados pelo wizard.

A trava vale dentro de um único `admin-api`, não entre réplicas.
A confirmação do AMI não substitui testes com chamadas SIP/RTP,
verificação de isolamento ou as evidências do Manual 73. Não houve
instalação nem execução contra Asterisk real nesta entrega.
