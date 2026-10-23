# Manual 98 — Recuperação do catálogo após falha tardia de persistência

## Risco corrigido

A criação e a exclusão de empresas já tinham compensação dos arquivos
Asterisk e do DID no AstDB (Manuais 94–95). Entretanto, se
`save_tenants()` efetivasse `os.replace()` e uma falha fosse
reportada logo depois, a tentativa de compensação não restaurava
o cadastro `tenants.json`. Isso podia deixar o JSON divergente do
AstDB e das configurações recuperadas.

## Nova proteção

Antes de iniciar as operações destrutivas, a aplicação captura os
**bytes e as permissões** do catálogo; também registra se o arquivo
não existia. Só inicia a restauração se a gravação do catálogo tiver
sido tentada.

Em falha na criação ou remoção, o procedimento agora:

1. Restaura o estado anterior do catálogo por arquivo temporário e
   publicação atômica, ou remove o registro criado se o arquivo
   originalmente não existia.
2. Continua as compensações já existentes dos arquivos `.conf`,
   do cadastro de ramais e das associações DID via AMI.
3. Se qualquer restauração falhar, retorna
   `rollback_incomplete=true` para reconciliação manual.
4. Rejeita catálogos simbólicos ou que não sejam arquivos regulares,
   sem seguir links para outros dados.

Não exibe bytes do registro, DIDs ou segredos em logs de diagnóstico.

## Testes automatizados

```bash
(cd admin-api && python3 -m pytest -q \
  tests/test_tenant_registry_recovery.py \
  tests/test_tenant_provisioning.py tests/test_tenant_deprovisioning.py)
```

A suíte simula falha **depois** de salvar de verdade o JSON,
verificando restauração exata, ausência inicial do arquivo,
permissões e falha da própria compensação.

## Limites

A recuperação é compensatória, não uma transação ACID entre arquivos,
AstDB e Asterisk. Um encerramento abrupto, múltiplos processos
escritores ou falha do próprio volume pode exigir recuperação
controlada por backup. A sinalização `rollback_incomplete=false`
não comprova a convergência de todos os serviços em execução.
Toda migração e homologação exige evidências do Manual 73.
