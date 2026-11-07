# Manual 140 — Armazenamento seguro do histórico de SLA

## Objetivo

Endurecer a persistência em JSONL do `SLAHistoryStore` da
`queue-api` para que o histórico de atendimento não seja redirecionado
por links, não aceite arquivos especiais e não seja sobrescrito por
registros de SLA adulterados.

A mudança preserva o cálculo do `QueueSLATracker` e a API atual:
eventos AMI `AgentConnect` e `QueueCallerAbandon` continuam
alimentando os indicadores da fila.

## Segurança implementada

- **Proteção de caminho completo:** cada diretório ancestral é aberto
  por descritor `openat`, com `O_NOFOLLOW` e `O_DIRECTORY`.
  Links simbólicos intermediários e no nome final são recusados.
- **Arquivos regulares exclusivamente:** FDs para FIFO, diretórios,
  hardlinks (mais de um link para o mesmo inode) ou arquivos acima de
  **32 MiB** são recusados; nenhum fallback inseguro é permitido.
- **Privacidade:** novos diretórios são criados com modo `0700` e
  arquivo `0600`; um arquivo legado de permissões amplas é
  restringido a `0600` antes da escrita.
- **Integridade do histórico:** todas as linhas novas contêm
  data válida, fila sem caracteres de controle, contadores inteiros
  não negativos e `within_sla <= offered`. O percentual é
  **recalculado**, nunca aceito do JSON de entrada.
- **Escrita verificável:** `O_APPEND` e operação única de
  `os.write` para uma linha delimitada por `\n`, com `fsync`
  após a gravação. Falha de escrita não é reportada como sucesso.
- **Leitura limitada:** no máximo 32 MiB, linhas até 4 KiB e
  rejeição de chaves JSON duplicadas ou constantes não finitas.
  Linhas legadas malformadas continuam ignoradas.

## Testes

```bash
cd queue-api
python3 -m pytest -q tests/test_queue_sla.py tests/test_sla_history_secure_storage.py
```

Regressões obrigatórias cobrem criação de diretório, permissões,
cálculo de percentual, `t1` e `t10`, links simbólicos no arquivo
e em pasta ancestral, hardlink, FIFO, limites de armazenamento,
JSON com chaves duplicadas e arquivo inexistente.

## Limitações e implantação

Este reforço não comprova ainda SLA a partir de chamadas
**reais com operadores WebRTC**, e não conclui o critério
`sla_report` da semana 9. Não altera o status formal, não habilita
GO de produção e não substitui backup, retenção, políticas de
acesso HTTP ou proteção do host. Em sistemas sem os recursos de
`openat` necessários, a operação falha de forma segura.

Arquivos legados com hardlinks ou localizados sob diretórios
simbólicos precisam ser migrados para caminhos regulares antes
da adoção.
