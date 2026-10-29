# Manual 134 — Expurgo de gravações com diretório ancorado

## Objetivo

O expurgo de retenção foi alinhado à proteção de arquivos já adotada
no download e listagem do AXE PABX. A versão anterior percorria
`Path.iterdir()` e `Path.unlink()`; embora evitasse symlinks no arquivo
final, um **diretório pai** renomeado ou trocado por um link poderia
redirecionar as operações para fora do volume esperado.

## Quatro frentes entregues

1. **Diretório seguro:** a limpeza usa `_recording_directory_fd()`,
   que abre cada ancestral via `O_DIRECTORY|O_NOFOLLOW`, e opera
   com `stat(..., dir_fd=..., follow_symlinks=False)` e
   `unlink(..., dir_fd=...)`, sem fallback inseguro.
2. **Filtros e concorrência:** somente arquivos regulares com extensão
   permitida, nome sem controles e data anterior ao corte são
   elegíveis. A identidade do inode/dispositivo é verificada novamente
   antes de remover; entradas substituídas ou ausentes são ignoradas.
3. **Privacidade:** o serviço registra **apenas a quantidade** de
   gravações expurgadas, nunca nomes com números telefônicos.
4. **Regressão:** testes cobrem symlink no diretório raiz, no ancestral
   intermediário e no áudio, FIFO, subdiretórios, relógio inválido,
   período não inteiro e fluxo normal.

## Restrições

- `retention_days <= 0` continua desabilitando a remoção, como
  originalmente. A mudança não habilita retenção automaticamente.
- A pasta de gravações precisa permanecer restrita a processos
  autorizados. POSIX não oferece `unlink` condicional ao inode;
  validar identidade antes de remover não elimina uma corrida se
  outro processo não confiável tiver escrita concorrente na pasta.
- Esta entrega **não prova** gravação física Asterisk, vinculação CDR,
  autenticação SSO, restauração de backup ou isolamento de volumes
  em produção. O marco 8 continua `in_progress`, sem GO.

## Executar

```bash
cd queue-api
python3 -m pytest -q tests/test_recordings.py
```

Somente integrar na `main` após CI estática e laboratório Asterisk
aprovados integralmente no HEAD exato.
