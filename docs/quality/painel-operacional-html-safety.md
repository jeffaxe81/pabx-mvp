# AXE PABX — Proteção de renderização do painel operacional

O painel de supervisão usa as APIs autenticadas de filas, extensões, SLA,
pausas e CDR. Valores de `CallerID`, campos AMI e textos de presença
não devem ser inseridos como marcação HTML.

## Regra aplicada

A função `escapeHtml` do `webphone/painel-operacional.html` codifica
`&`, `<`, `>`, aspas simples e duplas antes de preencher templates
`innerHTML`. Foi aplicada a identificadores de fila, relatórios SLA,
motivos de pausa, métricas, estados de ramais e observações de presença.
A classe visual do estado de ramal usa apenas estados conhecidos,
sem permitir texto AMI arbitrário como atributo de classe.

O rendering já feito com `textContent` para CallerID da fila e
notificações de fraude/qualidade é preservado. Tokens de autenticação
não são incluídos em URL, DOM estático nem armazenamento persistente.

## Regressão automatizada

`tests/ui_browser.test.cjs` injeta, via endpoints HTTP simulados, um
valor HTML com `<img onerror=...>` em fila, SLA, motivo de pausa,
ramal e indicador diário. O teste usa Chromium real em CI para confirmar
que o texto continua visível, mas nenhum elemento `img` é criado e o
código malicioso não executa.

Esta etapa **não** executa provas operacionais externas. As 15 pendências
continuam registradas em `docs/quality/provas-operacionais-diferidas.json`.
O marco 9 segue em andamento; não há GO de produção.
