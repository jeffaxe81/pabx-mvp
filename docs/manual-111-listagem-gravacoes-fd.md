# Manual 111 — Listagem segura de gravações (Marco 8)

## Objetivo

Evitar exposição de metadados de gravações por troca de symlink no caminho da
pasta ou entre enumeração e consulta de atributos do arquivo.

## Implementação

- `_recording_directory_fd`: abre desde a raiz (ou diretório corrente), ancorando
  cada componente da pasta com `O_DIRECTORY | O_NOFOLLOW` e `dir_fd`.
  Componentes `..` são rejeitados; em ambiente incompatível, falha fechado.
- `list_recordings`: `os.scandir(directory_fd)` e `os.stat(name,
  dir_fd=directory_fd, follow_symlinks=False)`. Somente arquivos regulares,
  com extensão aceita e nome seguro, entram na resposta. Ordenação por data
  decrescente com critério estável por nome; filtros anteriores preservados.
- `open_recording_file`: reutiliza a mesma ancoragem de diretório do catálogo
  de listagem e mantém `O_NOFOLLOW | O_NONBLOCK` no áudio.
- Testes temporários: links simbólicos em ancestral, troca no momento do stat,
  remoção concorrente, recusa de `..`, ordenação, filtros e leitura ancorada.

## Critérios de aceite

1. Todas as suítes Python estáticas precisam aprovar no HEAD da PR.
2. Laboratório Asterisk descartável precisa aprovar sem retirar verificações.
3. PR deve permanecer em rascunho até revisão das dependências #59 e #62.
4. Isolamento completo, carga, API/AMI/AstDB, fila, voicemail e acesso HTTP em
   infraestrutura alvo **não estão comprovados por esses testes**.
5. Sem merge automático, publicação em produção ou GO operacional.

## Limitações

- O diretório de gravações deve ser controlado pelo serviço e não gravável por
  tenants. Esta mudança impede seguir symlinks; não implementa verificação
  criptográfica de integridade do conteúdo.
- Retenção/expurgo e catálogos administrativos são fluxos distintos; não ficam
  automaticamente homologados por este incremento.
