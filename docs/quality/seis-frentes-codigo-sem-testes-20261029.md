# PABX AXE — seis frentes registradas em código (29/10/2026)

Escopo: implementação em branch isolada, sem execução de testes, laboratório,
homologação, deploy ou publicação. A anotação [skip ci] no commit solicita
não iniciar workflows GitHub Actions neste envio.

1. **Isolamento multiempresa/relatórios:** rejeitar CDR cujo AccountCode,
   contexto e operador apontem para tenants divergentes; preservar o
   caminho legado exclusivamente quando AccountCode estiver ausente.
2. **Métricas por tenant:** deduplicação de CDR por UniqueID/Uniqueid,
   com limite de memória e reset diário. A ausência do ID mantém legado.
3. **SLA:** gravação de histórico privado (0600), append seguro sem
   symlinks e leitura em fluxo com descarte de entradas malformadas.
4. **Presença:** leitura regular sem symlink, teto de 1 MiB, conferência
   de estrutura e salvamento atômico com teto de dados.
5. **Pausas:** ramal obrigatório com prefixo do tenant, validação dos
   valores AMI de Paused e rejeição de razões malformadas/duração negativa.
6. **Gravações/CDR:** impedir proposta automática quando duas gravações
   compartilham a mesma referência de origem; exigir revisão humana.

Limitações: código criado, NÃO testado e NÃO homologado. Revisão, CI e
provas operacionais continuam obrigatórias antes de incorporação à main.
O progresso formal permanece 7/16 (43,8%) e o indicador ponderado
registrado permanece 51,3%, sem autorizar GO de produção.

## Continuidade — segundo incremento das seis frentes

- **Voicemail:** PINs numéricos não podem repetir o número da própria caixa
  na abertura/final do segredo; gerador aplica também essa regra.
- **Callbacks:** leitura por descritor ancorado, limite de 4 MiB e
  20 mil registros; escrita é recusada quando excede limite.
- **Gravações:** uma mesma evidência de CDR não é reutilizável em
  múltiplos arquivos, inclusive entre lotes diferentes.
- **SLA:** atualizações e leituras protegidas por RLock, alias de
  UniqueID reconciliado e teto diário de IDs para deduplicação.
- **Presença:** rejeição de chaves JSON duplicadas, valores não finitos
  e concorrência entre requisições HTTP dentro do mesmo processo.
- **Relatórios:** identificação estrita do canal, deduplicação de CDR
  por tenant/UniqueID na consulta e leitura de linhas em fluxo.

**Situação:** alterações persistidas em branch de código, sem executar
testes, simulações, CI, laboratório ou deploy. Ainda não homologadas;
requerem revisão especializada antes de incorporação na main.

## Quarto incremento — 6 frentes de implementação (sem testes)

1. **Multiempresa** — validação de integridade do registro: nenhum
   tenant ou DID poderá aparecer duas vezes no cadastro já persistido.
2. **Gravações** — política de autorização recusa a utilização de
   um único identificador CDR/AMI para dois arquivos, mesmo tenant.
3. **SLA** — leitura por descritor de arquivo com proteção contra
   symlink e limite de tamanho do histórico.
4. **Presença** — serialização das operações de alteração entre
   threads e processos que compartilham o mesmo filesystem.
5. **Relatórios** — persistência em arquivo regular, sem seguir
   symlink final, com flush e fsync do histórico CDR.
6. **Callbacks** — estados inválidos e tenants incorretos em registros
   históricos deixam de ser aceitos no snapshot persistido.

**Estado:** código registrado apenas na branch de desenvolvimento.
Sem execução de testes, homologação, CI solicitada manualmente,
deploy ou integração na `main`. A anotação `[skip ci]` foi usada
nos commits, mas não substitui a checagem posterior dos workflows.
Homologação e GO de produção continuam bloqueados.

## Quinto incremento — continuidade em seis frentes

1. **Cadastro multiempresa:** leitura limitada a 1 MiB de arquivo
   regular sem symlink final, rejeição de chaves JSON duplicadas e
   números não finitos, validação do registro antes de salvar e
   persistência atômica com fsync do diretório.
2. **Callbacks:** tamanho calculado com a mesma indentação do
   serializador persistente; FIFO rejeita status desconhecido ou tenant
   inválido inclusive em registros históricos.
3. **Presença:** validação explícita do tipo do ramal e status antes
   do acesso ao regex; leitura ancorada que recusa symlinks ancestrais.
4. **Relatórios CDR:** leitura ancorada por descritor e descarte de
   registros com identificadores de empresa inválidos ou conflitantes.
5. **SLA:** histórico rejeita percentuais não finitos, contadores
   negativos ou inconsistentes, tanto na leitura quanto na escrita.
6. **Gravações:** importação recusa arquivo de áudio com múltiplos
   hardlinks e arquivo de lock com mais de um link de inode.

### Condições desta rodada
- Sem testes, builds, lint, simulações, homologação ou deploy.
- Código mantido em branch separada, sem merge na main.
- Progresso de homologação formal não muda por registro de código.
- A main e a branch estão divergentes, exigindo integração
  cuidadosa e avaliação posterior dos conflitos.
