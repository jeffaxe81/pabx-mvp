# Manual 88 — Pré-check de migração dos arquivos gerados do Asterisk

## Objetivo

Após o Manual 87, os arquivos dinâmicos do Asterisk passaram para
`asterisk/generated/`, montado como diretório no container Asterisk.
Na atualização de instalações existentes, é essencial conferir
que todos os arquivos foram copiados corretamente **antes** de
recriar os containers.

`scripts/check_generated_migration.py` é uma verificação
**somente leitura** dos arquivos locais. Não se conecta ao Docker,
não inicia Asterisk, não dispara AMI, não faz mudanças nem exibe
senhas ou conteúdo dos arquivos.

## Uso

No repositório atualizado:

```bash
python3 scripts/check_generated_migration.py
```

Para conferir também os tenants dinâmicos registrados:

```bash
python3 scripts/check_generated_migration.py \
  --asterisk-dir ./asterisk \
  --tenant-registry /caminho/privado/tenants.json
```

**Somente antes da primeira atualização/migração**, comparar o estado
antigo com os arquivos copiados para a pasta `generated`:

```bash
python3 scripts/check_generated_migration.py \
  --asterisk-dir ./asterisk --compare-legacy
```

Não use `--compare-legacy` como verificação periódica após a
migração, porque os arquivos antigos deixarão de ser atualizados
e divergirão legitimamente dos novos.

## Verificações

- Presença dos sete arquivos iniciais: PJSIP, dial/hints e voicemail
  de t1/t2.
- Includes estáticos de `pjsip.conf`, `extensions.conf` e
  `voicemail.conf` apontando ao novo diretório.
- Para cada `t3+` presente no cadastro informado, os três
  arquivos adicionais do dialplan, hints e correio de voz.
- Rejeição de diretório `generated` com symlink e arquivos de
  configuração ausentes, vazios ou inseguros.
- Opcionalmente, comparação exata com arquivos legados na raiz,
  para identificar cópias incompletas, sem imprimir os segredos.

O relatório inclui um progresso percentual de verificações que
passaram, nunca um percentual de homologação do PABX.

## Códigos de retorno

- `0`: validações locais concluídas, pronto para revisar a execução
  das próximas etapas de migração;
- `1`: arquivos ausentes, includes errados ou cópias divergentes;
- `2`: entradas/registry/diretórios inválidos.

## Testes

```bash
(cd scripts && python3 -m pytest -q tests/test_check_generated_migration.py)
```

## Limites

**100% neste script não significa GO operacional.** Ainda precisam
ser conferidos os bind mounts reais, o estado dos containers,
a autenticação dos endpoints, chamadas SIP/RTP, voicemail, isolamento,
backup, restauração e rollback de release. Para isso, siga os
Manuais 73 e 87 e recolha evidências do laboratório.
