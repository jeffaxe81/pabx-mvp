# Manual 119 — Reservas de discagem duráveis e revisão auditável

## Alterações entregues

Campanhas e callbacks agora compartilham dois mecanismos para reduzir
disparos duplicados quando múltiplos processos `queue-api` usam
**o mesmo volume persistente**:

1. `outbound_lock(path)`: trava de processo/thread e `fcntl.flock`
   em `campaigns.json.lock` ou `callbacks.json.lock`. Abrir o arquivo
   exige 0600, arquivo regular, sem symlinks. A trava abrange a
   operação **ler → reservar → gravar → enviar Originate** e também
   os eventos AMI que alteram resultados.
2. `atomic_write_json`: escreve o JSON completo em arquivo temporário
   no mesmo diretório, `fsync`, `os.replace` e sincroniza o diretório.
   Em falha anterior ao rename, o snapshot antigo permanece intacto.
   Arquivos são criados com permissão 0600.

A trava **não garante** ausência de chamadas repetidas caso uma
instância use outro volume, caminho ou backend incompatível com `flock`.
Utilize volume compartilhado com semântica POSIX verificada e nunca
sincronize réplicas por cópias assíncronas dos arquivos JSON.
Recomendação para clusters: migrar para banco com transação,
fencing de proprietário, lease, idempotência AMI e registro de
tentativas com IDs imutáveis. A solução presente é intermediária.

## Recuperação manual sem nova discagem

O utilitário `queue-api/reconcile_outbound.py` identifica contatos
e callbacks com status `discando` há pelo menos 10 minutos.
Exibe **hash SHA-256 do telefone** na listagem, nunca números reais.
Ele não reenvia chamadas, nem redefine `pendente` automaticamente.

Consultar suspeitos do tenant t1:

```bash
cd queue-api
python3 reconcile_outbound.py \
  --path /app/data/callbacks.json --kind callbacks --tenant t1
```

Após verificar CDR, AMI e logs reais, colocar um callback em revisão:

```bash
python3 reconcile_outbound.py \
  --path /app/data/callbacks.json --kind callbacks --tenant t1 \
  --quarantine-id ID_CONFIRMED \
  --actor supervisor-responsavel \
  --evidence "Conferidos CDR, canal AMI e tickets relacionados"
```

Para campanhas, acrescentar `--kind campaigns`,
`--path /app/data/campaigns.json` e
`--number NUMERO_EXATO_DO_CONTATO`, junto com o ID da campanha.

A operação é restrita a instância com acesso ao volume de dados;
**não há rota HTTP** para alterar esses estados. Ela exige identidade
do operador, texto de evidência e tenant exatos, grava
`requested` e `committed` em `*.audit.jsonl` (0600) e atualiza
o registro para `revisao_manual`. A atualização tardia de DialEnd
não devolve a entrada para `pendente`. Divergência entre as duas
fases do log exige investigação antes de qualquer outra alteração.

Se a comunicação AMI teve retorno incerto, manter `discando` ou
`revisao_manual` até prova documental. Nenhuma etapa autoriza
automaticamente uma segunda tentativa.

## Testes e verificação

```bash
cd queue-api
python3 -m pytest -q tests/test_outbound_safety.py \
  tests/test_campaign_tenant_http.py tests/test_campaigns.py \
  tests/test_callbacks.py
```

Inclui concorrência com **dois processos Python distintos**,
permissões/symlinks, simulação de falha antes do rename, isolamento
`t1` versus `t10`, quarentena com evidências e proibição de
atualizações tardias após revisão.

## Bloqueios de homologação

A PR #72 teve validação estática aprovada, mas seu laboratório
Chromium/WebRTC terminou **com falha** em cenários CDR, encerramento
de canais e negociação DTLS. Os quatro demais jobs Asterisk
passaram. Registrar e corrigir/validar antes de GO, sem atribuir
automaticamente o incidente ao novo código de filas.

Esta PR não implanta, não mescla a main nem concede GO.
O portfólio mantém 7/16 marcos concluídos (43,8%), com o
marco de segurança multiempresa ainda em andamento.
