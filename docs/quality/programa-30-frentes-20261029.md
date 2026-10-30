# AXE PABX — Programa de 30 frentes de desenvolvimento

Entrega organizada em **seis PRs independentes** de cinco melhorias
mensuráveis. Estes itens são critérios de código/testes; **não**
representam trinta homologações operacionais de cliente.

## A. SLA / histórico (1–5)
1. Impedir limiar SLA inválido ou booleano.
2. Rejeitar JSONL de histórico não objeto ou excessivamente longo.
3. Validar datas de calendário e nomes de fila.
4. Validar `offered` e `within_sla` sem tipos ambíguos.
5. Recalcular percentuais a partir dos contadores e agregar linhas
   repetidas da mesma fila/dia.

## B. CDR / métricas (6–10)
6. Não contabilizar `Disposition` malformada.
7. Validar `Uniqueid` quando informado.
8. Deduplicar reenvio do mesmo CDR por AMI.
9. Preservar CDRs de pernas distintas com destino/início diferentes.
10. Limitar janela em memória de deduplicação e zerá-la no novo dia.

## C. Callback / supervisão (11–15)
11. Contagem de pendentes por empresa.
12. Contagem de chamadas em discagem por empresa.
13. Contagem de retornos concluídos por empresa.
14. Contagem de cancelamentos separada de conclusão.
15. Idade do pedido pendente mais antigo, sem revelar telefone.

## D. Chamadas perdidas (16–20)
16. Validar capacidade do histórico em memória.
17. Rejeitar entradas não objeto sem erro.
18. Higienizar campos de origem/destino também na gravação interna.
19. Limitar listagem e não tratar limite inválido como acesso amplo.
20. Entregar cópias para impedir mutação externa dos registros.

## E. Qualidade RTCP (21–25)
21. Não criar alarme a partir de objeto inválido.
22. Não usar limiar NaN, negativo, infinito ou fora da faixa.
23. Validar capacidade do histórico RTCP.
24. Rejeitar registros/flags malformados no log.
25. Aplicar limites e cópias defensivas na listagem de qualidade.

## F. Painel do supervisor (26–30)
26. Quantidade atual de chamadas em espera.
27. Maior tempo de espera.
28. Tempo médio de espera.
29. Quantidade de filas com chamadas aguardando.
30. Chamadas acima de 60 segundos na espera.

**Critérios gerais:** manter isolamento por empresa, não adicionar PII
aos KPIs, negar dados antigos na troca do token, testes sintéticos de
código/HTTP/navegador e gate de CI antes de integrar.

As **15 provas operacionais externas** seguem
`DEFERRED_NOT_EXECUTED` no registro versionado. O marco 9 não é
formalmente concluído nesta etapa; `operational_go_authorized=false`.
