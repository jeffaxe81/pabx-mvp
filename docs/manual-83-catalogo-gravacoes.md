# Manual 83 — Importação assistida e auditável do catálogo de gravações

## Objetivo

Importar múltiplas gravações para o catálogo privado criado no
Manual 80 sem editar JSON manualmente. A **origem do tenant deve ter
sido comprovada por um operador autorizado** em CDR, registro do
Asterisk ou evidência interna confiável.

**Importante:** o importador não associa empresas automaticamente.
Nomes de arquivos, DID e caller ID isolados não comprovam tenant.
Uma referência de evidência no manifesto é um identificador para
auditoria, **não uma prova criptográfica**.

## Formato de entrada

Um objeto JSON por linha em um arquivo privado UTF-8, sem senha,
hash de token ou dados completos das chamadas:

\`\`\`json
{"filename":"20261022-120000-551199998888-1010.wav","tenant":"t1","owner_extension":"t1-recepcao","source_ref":"CDR-T1-20261022-01"}
{"filename":"20261022-120001-551199998887-1010.wav","tenant":"t1","source_ref":"CDR-T1-20261022-02"}
\`\`\`

Os arquivos precisam existir em \`RECORDINGS_DIR\`, ser áudio regular
e não ser links simbólicos. Nenhum campo extra é aceito. O campo
\`owner_extension\` é opcional; sem ele um agente não poderá acessar
a gravação, mesmo tendo um token do tenant. Administradores e
supervisores continuam sujeitos ao isolamento por empresa.

## Operação

\`\`\`bash
# Primeiro conferência, que não escreve na política:
python3 queue-api/recording_catalog.py \
  --policy /local/privado/recording_access.json \
  --recordings-dir /local/recordings \
  --manifest /local/privado/lote.jsonl

# Somente depois de revisar as evidências e a simulação:
python3 queue-api/recording_catalog.py \
  --policy /local/privado/recording_access.json \
  --recordings-dir /local/recordings \
  --manifest /local/privado/lote.jsonl --apply
\`\`\`

O catálogo deve **existir**, conter \`credentials\` e \`recordings\`
válidos, e ter permissões privadas (modo \`0600\`). Em Docker,
execute o script num contexto autorizado com acesso ao volume
\`queue_api_data\`; não copie o catálogo para o repositório.

Cada lote é todo validado antes da escrita. O programa usa lock
entre processos, grava arquivo temporário com modo \`0600\` e
troca atômica. Registros idênticos são idempotentes; alterações
na classificação prévia, conflitos entre empresas e duplicatas
são recusados. A política de credenciais é preservada.

Limites: 1000 linhas e 1 MiB de manifesto por execução, e tamanho
final do catálogo de no máximo 1 MiB. A saída apresenta contagens
de novos, repetidos idênticos e total, sem imprimir os tokens.

## Testes

\`\`\`bash
(cd queue-api && python3 -m pytest -q tests/test_recording_catalog.py)
\`\`\`

Cobrem simulação sem escrita, atomicidade, preservação das
credenciais, idempotência, conflitos, entradas inválidas,
arquivo inexistente, symlinks e permissões inseguras.

## Limitações e GO

A conferência da evidência ainda é responsabilidade de um operador
autorizado; o importador não assina nem certifica o CDR. Ainda não
há integração com identidade/SSO ou produção automática de vínculo
de tenant por evento no Asterisk. Para GO, homologar a origem,
retensão, revogação, acesso cross-tenant e backup/restore reais.
