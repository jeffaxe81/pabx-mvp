# AXE PABX — arquivos privados de provisionamento

Base: `5a085e228923458da26a058c3a1c512bf50020f7`. Continuidade da issue #344.

## Entrega

- Geração com pasta 0700, temporários e arquivos 0600; MAC no nome da
  saída sempre em minúsculas, compatível com a rota mTLS.
- Validação e restrição dos `.cfg` antigos, inclusive MACs fora do lote,
  sem exclusão nem alteração do conteúdo desses arquivos antigos.
- Recusa de symlinks, hardlinks, FIFOs, nomes `.cfg` inválidos, outros
  objetos não regulares e arquivos pertencentes a outra identidade.
- Diretório ancorado por FD, lock e publicação com replace relativo.
- GET mTLS recusa pasta/arquivo públicos ou de outra identidade, mesmo
  com certificado válido. Mantém 404 genérico e limites de tamanho.

## Evidências locais

Antes da correção, 14 casos novos reproduziram permissões públicas,
aceitação de legado inseguro, escrita redirecionada após troca da pasta,
nome MAC incompatível e entrega mTLS de arquivos públicos/hardlinks.
Após a correção, os cenários passaram. Um caso também confirma o contrato
preexistente de não publicar quando o catálogo é inválido.

O teste HTTPS usa a saída do gerador real e CA/certificados OpenSSL
efêmeros. Confirma 200 para arquivo privado, 404 após abrir permissões
da pasta ou arquivo, 200 após restaurar a proteção e 404 após revogação.
Um segundo tenant conserva acesso. O lock é exercitado por um processo
Python real bloqueado enquanto o processo pai mantém o lock de diretório.

| Suíte | Aprovados |
| --- | ---: |
| Configurações/web/provisioning | 642 |
| admin-api | 7.663 |
| queue-api | 1.221 |
| ai-worker (somente regressão existente) | 94 |
| asterisk/agi | 19 |
| asterisk/scripts | 8 |
| backup | 1.025 |
| scripts | 3.584 |
| **Total Python** | **14.256** |
| Node | 25 |

São 19 casos novos: 13 no gerador privado e seis na recusa mTLS por
permissão, hardlink ou identidade. A prova HTTPS preexistente foi ampliada.
Comandos: `python -m pytest -q tests` em cada diretório da matriz
`quality-gates.yml`, `npm run test:node`, `git diff --check` e
`python -m compileall -q provisioning`.

Revisão independente não identificou achados críticos ou importantes.
A limitação reproduzida com umask 0777 (pasta 0000, falha fechada na
abertura) está documentada; máscaras usuais 0022/0077 preservam o acesso
do proprietário. A CI e os laboratórios devem estar verdes no SHA final
da PR antes de integrar.

## Limites operacionais

Este código não foi executado para migrar pasta ou credenciais reais.
Requer Linux/POSIX, mesma identidade local no gerador/servidor e umask
que preserve acesso do proprietário. Não protege catálogo de origem,
chaves, backups, cópias já obtidas ou acesso privilegiado de administrador.
Cada arquivo é atômico; não há transação nem rollback global do lote.

Não modifica o RC, os 13 cenários ou as 15 provas operacionais.
Homologação de firmware Yealink físico e aceite operacional permanecem
pendentes. Nenhuma funcionalidade de Contact Center/IA foi criada.
Issue #344 permanece aberta; **produção NO-GO**.
