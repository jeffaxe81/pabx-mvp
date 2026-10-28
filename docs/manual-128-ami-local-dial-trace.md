# Manual 128 — Observação de DialBegin e DialEnd em Asterisk real descartável

## Objetivo e limite da entrega

Esta etapa prolonga o Manual 127: o laboratório executa uma chamada
**exclusivamente interna** entre canais `Local/` em um Asterisk Docker
descartável, com AMI restrito a `127.0.0.1` e credencial efêmera.
Não existe chamada para cliente, gateway, ramal real ou operadora.

O laboratório captura somente em memória os eventos AMI
`OriginateResponse`, `DialBegin` e `DialEnd`. Publica apenas o campo
`ami_local_dial_observation` com indicadores booleanos sem números de
telefone, IDs de canal, dados de autenticação ou eventos brutos.

O verificador observa: presença dos dois tipos de evento, par
`Uniqueid/DestUniqueid/Linkedid` consistente, `AccountCode`
correspondente ao tenant de laboratório, presença do `ChannelId` da
originação na trilha e resultado `ANSWER` quando o par é comprovado.

**Esses indicadores são diagnósticos, não critérios de GO.**
A evidência `live_ami_dialend_correlated` continua **false**, porque
o cenário `Local/` não prova campanhas ou callbacks PJSIP reais e não
confirma dois cenários de resultado por categoria.

## Execução isolada

```bash
python3 -m lab.asterisk_lab --ami --report lab-results/ami-originate.json
python3 -m pytest -q scripts/tests/test_ami_local_dial_trace.py
```

O relatório exige o sucesso dos controles existentes de
`OriginateResponse`; as novas observações não são transformadas em
aprovação de campanhas/callbacks. Resultados ausentes ou inconclusivos
não são tratados como atendimento.

## Próxima fase — issue #79

1. Criar cenário PJSIP autenticado inteiramente em loopback.
2. Executar tentativa real de **campanha** e **callback**, cada uma
   atendida e não atendida, com `ActionID` e `ChannelId` únicos.
3. Confirmar o vínculo entre `OriginateResponse`, `DialBegin`,
   `DialEnd`, `Linkedid`, `AccountCode`, CDR e resultado.
4. Rejeitar duplicidades, IDs divergentes e tentativas entre tenants
   sem concluir ou rediscar por erro.
5. Exigir CI/laboratório verde no SHA da PR e revisão antes do merge.
   Nenhum merge isolado equivale a homologação ou implantação em produção.
