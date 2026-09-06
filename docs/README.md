# Manuais do projeto

Um manual por funcionalidade implementada, na ordem em que foram
construídas. Cada manual explica: o que a funcionalidade faz, como
configurar, como testar manualmente, e limitações conhecidas.

1. [Core: ramais e chamadas internas](manual-01-core-ramais.md)
2. [Criptografia (TLS + SRTP)](manual-02-criptografia.md)
3. [Multi-tenant](manual-03-multi-tenant.md)
4. [Tronco TDM (gateway)](manual-04-tronco-tdm.md)
5. [Auto-provisionamento](manual-05-provisionamento.md)
6. [Telefonista web (WebRTC + presença/BLF)](manual-06-telefonista-web.md)
7. [Transferência assistida (com consulta)](manual-07-transferencia-assistida.md)
8. [Fila de atendimento (pickup dirigido)](manual-08-fila-atendimento.md)
9. [Gravação de chamadas](manual-09-gravacao-chamadas.md)
10. [Multi-chamada (segunda linha)](manual-10-multi-chamada.md)
11. [Notificação de chamada perdida](manual-11-notificacao-chamada-perdida.md)
12. [Discagem por clique a partir do CRM](manual-12-click-to-call.md)
13. [Dashboard de métricas do dia](manual-13-dashboard-metricas.md)
14. [Múltiplas telefonistas simultâneas](manual-14-multiplas-telefonistas.md)
15. [PWA instalável com notificação nativa](manual-15-pwa-notificacao.md)
16. [Painel de administração web](manual-16-painel-administracao.md)
17. [Painel operacional consolidado](manual-17-painel-operacional.md)
18. [Relatórios por atendente, tenant e período](manual-18-relatorios.md)
19. [Integração CRM: screen-pop PABX→CRM](manual-19-crm-screen-pop.md)
20. [Regras de discagem externa](manual-20-discagem-externa.md)
21. [Busca de gravações e política de retenção](manual-21-busca-retencao-gravacoes.md)

## Regra de manutenção

Toda vez que uma funcionalidade nova for implementada no projeto, um
novo manual numerado deve ser adicionado aqui **antes** de considerar
a funcionalidade concluída — não depois, "quando der tempo". Isso está
registrado como regra permanente no prompt master
(`prompt-base-pabx.md`).
