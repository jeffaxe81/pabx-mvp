# REL-13 — Regressão SIP real (PABX puro)

## Escopo do novo laboratório

- **Chamadas internas:** reutiliza `lab/call_checks.py`, com SIP TLS, SRTP autenticado, CDR e desconexão nos tenants t1/t2/t3.
- **Decisão de saída:** executa `lab/outbound_route_checks.py` com dialplan Asterisk verdadeiro e interceptação do `Dial()` exclusivamente na cópia temporária dos testes; não chama operadora.
- **Transferência:** novo `lab/transfer_checks.py` faz A (1001) chamar B (1002), B emitir SIP REFER para 1103 e verifica recebimento e atendimento real do novo INVITE pelo terminal C, nos tenants t1 e t2.
- **Isolamento:** credenciais e ramais 1103 são gerados somente no sandbox, não publicados no PABX real. A CI remove o container de teste usando token de propriedade.

## Critérios de aceite

O job `Asterisk | REL-13 transferencia SIP REFER em t1/t2` precisa aprovar os checks obrigatórios de ambos os tenants, a suíte de chamadas internas com SRTP, as decisões de saída local e a limpeza do runner. O REFER 202 sozinho é insuficiente: o INVITE do novo ramal precisa ser atendido com ACK. O relatório inclui somente flags e informações sintéticas.

## Limites

Não comprova mídia renegociada após REFER, transferência assistida, dispositivos reais, tronco externo ou produção. REL-14 permanece separada. Não contar REL-13 no percentual antes de CI completa e revisão. GO operacional continua proibido.
