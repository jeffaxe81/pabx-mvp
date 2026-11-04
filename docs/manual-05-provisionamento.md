# Manual 05 — Auto-provisionamento

O gerador prepara a configuração de cada telefone pelo MAC. Os arquivos
contêm senhas SIP e são privados por padrão. A distribuição para aparelho
físico depende de homologação; o HTTP legado está desativado por padrão.

## Geração em laboratório local

1. Prepare um catálogo com MAC, `vendor`, `ramal`, `nome`, `senha` e
   `servidor`. Os dados versionados em `provisioning/devices.json` são
   exemplos; não gravar credenciais reais no Git. O catálogo real também
   exige controle local de acesso e backup privado.
2. Em Linux/POSIX, execute `python3 provisioning/generate.py` com os
   caminhos locais configurados para o laboratório. O template do
   fabricante fica em `provisioning/templates/`.
3. A saída é `provisioning/files/<mac-minusculo>.cfg`, com modo 0600,
   em diretório 0700 pertencente ao operador. A senha não aparece no log.

O umask deve preservar o acesso do próprio proprietário, como nas máscaras
usuais 0022/0077. Uma máscara como 0777 pode criar a pasta sem acesso e
bloquear a geração antes do ajuste de permissões. Nesse caso, revisar a
configuração local; a operação falha sem publicar configurações.

MACs maiúsculos na entrada são normalizados no nome do arquivo; o manifesto
usado pelo servidor mTLS continua exigindo MACs em minúsculas. Os arquivos
de empresas distintas mantêm as credenciais separadas por MAC. Isso não
substitui a autorização de distribuição por tenant/certificado.

## Arquivos existentes

O gerador valida os `.cfg` antigos antes de publicar e restringe suas
permissões, inclusive os que não pertencem ao lote atual, sem excluir
arquivos. Recusa symlinks, hardlinks, objetos não regulares, nomes `.cfg`
inválidos ou arquivos de outra identidade. Não altera pastas superiores.
Uma entrada inválida no catálogo não modifica a pasta de saída.

Cada arquivo é publicado atomicamente por descritor de diretório,
com temporário privado e lock entre geradores cooperantes. Uma falha
posterior pode deixar parte do lote atualizada e permissões já restritas;
não há transação ou rollback global do lote.

## Distribuição autenticada

O [laboratório HTTPS/mTLS](security/provisioning-mtls-laboratorio.md)
exige certificado cliente vinculado ao tenant/MAC. Execute o servidor
com a mesma identidade local do gerador. Arquivo ou pasta com acesso por
grupo/outros, propriedade divergente ou hardlink recebe 404 genérico.
O serviço permanece em loopback e a compatibilidade com firmware Yealink
físico continua pendente.

O perfil HTTP `insecure-lab-provisioning` não inicia com o Compose
padrão. Não usar URL HTTP para provisionar aparelhos reais e não tornar
arquivos públicos para acomodar o Nginx legado.

## Verificação automatizada

```bash
python3 -m pytest -q tests/test_provisioning.py tests/test_provisioning_30_guardas.py tests/test_provisioning_private_files.py tests/test_provisioning_mtls.py
```

Os testes executam geração isolada, permissões, links, falha de escrita,
troca de pasta, lock e HTTPS/mTLS com certificados efêmeros.

Somente o fabricante Yealink possui template. Adicionar outro fabricante
requer template próprio, entrada em `TEMPLATE_EXT` e homologação. Os
modelos atuais não constituem prova de configuração aceita por telefone
físico. Produção permanece NO-GO (issue #344).
