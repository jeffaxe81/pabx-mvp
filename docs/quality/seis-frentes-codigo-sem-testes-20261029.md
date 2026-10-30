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
