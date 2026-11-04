# Arquivos privados de provisionamento

Continuidade da issue #344 após a PR #369. O gerador ainda produz `.cfg`
0644 em pasta criada com o umask do processo, e o servidor mTLS aceita
arquivos públicos. Esses arquivos contêm as senhas SIP.

Adotar diretório 0700 e arquivos 0600 por padrão. A pasta deve pertencer
ao operador. Antes de publicar, validar os `.cfg` existentes sem seguir
links, recusar symlinks, hardlinks e objetos não regulares, e restringir
as permissões dos arquivos antigos sem alterar seu conteúdo. Não excluir
arquivos antigos nem alterar pastas superiores.

Usar descritor de diretório, O_NOFOLLOW, lock no diretório e replace
relativo ao descritor. Temporários devem ser privados antes de receber
dados. Assegurar nomes MAC em minúsculas, como exige o endpoint mTLS.
Cada arquivo é publicado atomicamente; não prometer transação do lote.

O servidor mTLS deve verificar no descritor aberto que pasta e arquivo
pertencem à sua identidade local, não são acessíveis por grupo/outros,
e que o arquivo é regular e sem hardlinks. Retornar 404 genérico quando
esses controles falharem. Testar geração real seguida de GET HTTPS/mTLS.

A escolha é proteger a saída por padrão. Um modo público opcional
reintroduziria o risco já mitigado; uma API remota de migração exigiria
identidade e homologação fora deste lote. O operador local executa a
geração no diretório dedicado. O Nginx legado permanece desabilitado por
padrão e não deve receber permissões para ler credenciais reais.

Escopo PABX puro: sem emissão de certificados, deploy, alteração de
contas ou mudanças nos segredos SIP de origem. O catálogo de entrada com
credenciais reais deve ser protegido pelo operador. Homologação Yealink
físico, RC, 13 cenários e 15 provas operacionais permanecem inalterados.
