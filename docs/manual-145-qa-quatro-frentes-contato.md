# Manual 145 — Quatro frentes de isolamento e qualidade do Contact Center

## Escopo

A PR vinculada introduz quatro melhorias independentes em módulos já
existentes, com regressões negativas. Nenhuma pretende comprovar
homologação operacional sem chamadas reais adicionais.

### Frente 1 — Filas e captura simultânea Asterisk

A verificação da chamada de um tenant não aceita mais isolamento apenas
porque a linha do seu próprio canal está correta. O mesmo snapshot
\`core show channels concise\` é inspecionado em busca de **outros
canais na aplicação Queue**. Caso uma chamada de \`t2\` esteja em
\`fila-t1\` ou a origem tenha contexto distinto da própria empresa,
o check \`queue_no_foreign\` é reprovado. \`t1\` e \`t10\` são
tratados como empresas distintas, sem prefix-match.

Arquivo: \`lab/queue_tenant_checks.py\`. Testes de captura concorrente
em \`scripts/tests/test_queue_tenant_runtime.py\`.

### Frente 2 — Callback e destino AMI

A extração de destino de \`DialEnd\` passa a aceitar apenas uma
\`Dialstring\` completa e exata no formato
\`PJSIP/<8..20 dígitos>@gateway-tdm\`. Não aceita texto antes/depois,
caracteres de controle nem tipos arbitrários. Quando há \`Dialstring\`
inválida, não usa \`DestExten\` como fallback contraditório.
\`DestExten\` só é aceito isoladamente, com 8 a 20 dígitos.

Arquivo: \`queue-api/callbacks.py\`; regressões em
\`queue-api/tests/test_callbacks.py\`.

### Frente 3 — Voicemail e canais concorrentes

O laboratório \`*97\` já verificava a caixa exata e origem por
empresa. Agora também exige que **todo canal simultâneo** em
\`VoiceMailMain\` tenha contexto próprio, extensão \`*97\` e estado
\`Up\`, além de mailbox correta. Um canal suspeito reprova a
prova completa, mesmo que o canal original esteja correto.

Arquivo: \`lab/voicemail_checks.py\`; regressões em
\`scripts/tests/test_voicemail_concurrent_isolation.py\`.

Não comprova **PIN correto/incorreto** nem lockout ou leitura real
de mensagens; este marco permanece pendente.

### Frente 4 — Relatório SLA e integridade temporal

A consulta histórica de SLA agora rejeita datas inexistentes, valores
não textuais, datas fora de ISO \`YYYY-MM-DD\`, período invertido e
parâmetros duplicados. A API devolve **HTTP 400** em vez de calcular
um histórico incorreto ou deixar exceções escaparem ao chamador.
Limites válidos continuam inclusivos e são aplicados apenas depois
de escopo autenticado por tenant.

Arquivos: \`queue-api/queue_sla.py\`,
\`queue-api/server.py\`, \`queue-api/tests/test_queue_sla.py\`.

## Gate e aceite

Para realizar o merge, a mesma versão deve aprovar integralmente os
workflows estáticos, Asterisk/Docker real e pacote de release aplicável.
Evidências posteriores devem registrar IDs exatos das execuções.

As quatro alterações são **robustez e qualidade**, não homologação
completa do atendimento real WebRTC em Queue, callback fim a fim,
autenticação do voicemail por PIN ou SLA AMI fim a fim.
O percentual técnico **51,3%** e formal **7/16 (43,8%)** não devem
ser incrementados por este manual. **GO de produção permanece falso.**
