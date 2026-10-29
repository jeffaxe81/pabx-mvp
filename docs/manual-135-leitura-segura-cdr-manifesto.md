# Manual 135 — Origem segura de arquivos CDR e gravações

## Contexto

A importação de evidências de gravações usa arquivos locais JSONL e
reconcilia CDR com os áudios. Até esta entrega, `lstat()` antecedia
`read_bytes()` por caminho, permitindo troca entre verificação e leitura.
Da mesma forma, `Path.iterdir()/is_file()` não fixava cada ancestral do
diretório de áudio durante a conciliação.

## Quatro frentes

1. **Manifesto:** `load_manifest` abre uma única vez um descritor seguro
   de arquivo e faz `fstat` no descritor antes de ler dados limitados.
2. **CDR:** `load_raw_cdr` usa o mesmo leitor, recusando FIFO, symlink no
   arquivo ou em qualquer pasta ancestral, e arquivos fora do limite de 4 MiB.
3. **Áudio:** `preview_batch` e `propose_candidates` ancoram a pasta de
   gravações por `dir_fd`; cada `stat` usa `follow_symlinks=False`,
   sem dedução de tenant pelo nome do arquivo.
4. **Regressões:** testes de documento válido, ancestrais simbólicos,
   arquivos simbólicos, FIFO, subdiretórios e arquivo não regular.
   Uma entrada negativa não pode mutar o catálogo.

## Limites

As alterações não tornam a origem do CDR automaticamente confiável
e não eliminam uma troca concorrente no conteúdo de arquivo regular
que um processo externo possa editar enquanto estiver aberto. A pasta
e os manifestos ainda precisam de permissões de escrita restritas.

**Não equivale** à prova de MixMonitor em chamada real nem ao isolamento
físico do spool por empresa; a issue #30 e o marco 8 permanecem abertos.
O aceite operacional e o GO continuam bloqueados.

## Reproduzir

```bash
cd queue-api
python3 -m pytest -q \
  tests/test_recording_catalog.py \
  tests/test_recording_cdr_candidates.py
```

Merge permitido somente quando todas as suítes estáticas e o laboratório
Asterisk estiverem aprovados para o mesmo HEAD da PR.
