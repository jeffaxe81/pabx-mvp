# Manual 68 — Rejeitar chamadas entrantes com DID desconhecido

## Objetivo e risco

Em plataformas multiempresa, uma chamada recebida no tronco TDM/SIP sem DID
associado a uma empresa **não pode** ser encaminhada por padrão ao tenant t1.
Esse comportamento anterior permitiria que números não cadastrados fossem
atendidos e eventualmente gravados no ambiente da empresa errada.

A regra no contexto `[from-tdm-gateway]` foi alterada para **falhar fechado**.

## Comportamento

- Os DIDs estáticos de exemplo `5511900001111` (t1) e
  `5511900002222` (t2) continuam com seu roteamento explícito.
- DIDs dinâmicos registrados pelo wizard em `tenant-did/<DID>` no
  AstDB continuam sendo roteados à URA do tenant cadastrado.
- Para DID sem entrada no AstDB, o dialplan não entra na URA: emite
  `NoOp` de diagnóstico e finaliza com `Hangup(21)`, correspondente a
  *call rejected* (cause 21). Nenhum tenant é presumido.

O Asterisk pode traduzir a causa de desligamento conforme o tronco,
a operadora ou o gateway. Não presumir código SIP exato sem validação real.

## Pré-requisitos para o laboratório

1. Salvar um backup validado dos arquivos e da base AstDB antes de mudar
   qualquer configuração, conforme os manuais de backup/restauração.
2. Confirmar os DIDs de teste e seu mapeamento por empresa; não usar
   chamadas reais de clientes em testes destrutivos.
3. Subir o Asterisk num ambiente de homologação isolado; verificar
   `asterisk -rx "dialplan show from-tdm-gateway"`.
4. Verificar os DIDs dinâmicos com
   `asterisk -rx "database show tenant-did"`.

## Testes de aceite em laboratório

| Cenário | Resultado esperado |
|---|---|
| DID estático de t1 | Roteia apenas para t1 |
| DID estático de t2 | Roteia apenas para t2 |
| DID dinâmico mapeado para t3 | Entra na URA de t3 |
| DID sem mapeamento | Chamada rejeitada; não cai em t1 |
| Mapeamento removido do AstDB | A próxima chamada é rejeitada |
| Recuperação do mapeamento correto | Roteamento para empresa correta |

A simulação deve ser feita por um gerador SIP ou gateway de testes.
Consultar o CLI do Asterisk e confirmar, com rastreio de canais e CDR
do laboratório, que a chamada desconhecida **não chegou** às filas,
ramais, URAs e gravações de outro tenant. Validar sinalização e mídia
real com duas pontas SIP distintas.

## Testes automatizados

```bash
python3 -m pytest -q tests/test_extensions_conf.py
```

Os testes são **estáticos** e garantem a existência e a ordem do lookup,
da condição de rejeição e do roteamento conhecido. Eles não provam
o resultado de uma ligação real nem substituem a homologação SIP.

## Operação e rollback

- Risco: DIDs antes aceitos implicitamente por t1 passam a ser rejeitados.
  Identificar e cadastrar explicitamente esses DIDs **antes de promover**
  a configuração ao ambiente produtivo.
- Não criar uma regra de fallback global para t1 como forma de rollback:
  ela reintroduziria o problema de isolamento. Para restaurar serviço,
  corrigir o mapeamento de DID do tenant afetado, com auditoria.
- Registrar o DID, o tenant escolhido, o horário do teste e as
  evidências do CLI/operadora. Não registrar credenciais SIP/AMI.
