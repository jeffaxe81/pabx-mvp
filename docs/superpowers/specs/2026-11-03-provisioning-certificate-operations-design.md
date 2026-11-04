# Gestão local de certificados de provisionamento

Continuidade da issue #344 e das PRs #367/#368, no escopo de PABX puro.
O cadastro v2 já é consultado a cada GET; falta operar a revogação sem
editar JSON manualmente. A entrega oferece inventário por tenant e
revogação exata por tenant/MAC, sem certificados, fingerprints ou segredos
na saída. Estados: active, pending, expired e revoked.

Usar o servidor Python existente e uma CLI local, sem dependências novas.
Uma tela remota exigiria identidade administrativa ainda não homologada;
edição manual não protege alterações simultâneas. A escolha desta entrega
é a CLI, executada apenas por quem já possui acesso ao cadastro privado.

Reutilizar a validação v2 tanto para leitura quanto para alterações. Ler
arquivos por descritor, com O_NOFOLLOW, tamanho limitado e permissões
validadas no mesmo descritor. Revogar sob lock estável, exigir diretório
privado, gravar temporário 0600 e substituir atomicamente. Manter todas
as outras entradas e rejeitar tenant/MAC divergentes antes de gravar.
Falha anterior à publicação preserva o arquivo original; falha de fsync
do diretório posterior à publicação é reportada sem desfazer a revogação.

Não emitir certificados, não reativar credenciais, não alterar `.cfg`,
não publicar serviço e não mudar o RC nem o aceite operacional.
Compatibilidade Yealink físico e as 13+15 provas seguem pendentes.
