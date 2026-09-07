# Manuais do projeto

Um manual por funcionalidade implementada, na ordem em que foram
construídas. Cada manual explica: o que a funcionalidade faz, como
configurar, como testar manualmente, e limitações conhecidas.

0. [Roteiro de implantação (primeiros passos em servidor real)](manual-00-roteiro-implantacao.md)
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
22. [E-mail de correio de voz](manual-22-email-correio-voz.md)
23. [URA / IVR](manual-23-ura.md)
24. [Grupos de toque](manual-24-grupos-de-toque.md)
25. [Permissões e perfis](manual-25-permissoes-perfis.md)
26. [Autenticação em dois fatores (2FA)](manual-26-2fa.md)
27. [Detecção de fraude](manual-27-deteccao-fraude.md)
28. [Alta disponibilidade e backup](manual-28-backup-disponibilidade.md)
29. [Monitoramento de qualidade de chamada](manual-29-monitoramento-qualidade.md)
30. [Discador automático / campanhas](manual-30-discador-campanhas.md)
31. [Chamada de retorno / callback](manual-31-callback.md)
32. [Pesquisa de satisfação pós-atendimento](manual-32-pesquisa-satisfacao.md)
33. [Transferência inteligente por regra](manual-33-transferencia-inteligente.md)
34. [Presença corporativa avançada](manual-34-presenca-avancada.md)
35. [Atendimento multilíngue](manual-35-multilingue.md)
36. [Transcrição, resumo automático e análise de sentimento](manual-36-transcricao-resumo-sentimento.md)
37. [Atendente virtual com IA](manual-37-atendente-virtual.md)
38. [Multi-tenant completo](manual-38-multi-tenant-completo.md)
39. [Wizard de preparação de ambiente por tenant](manual-39-wizard-tenant.md)

## Regra de manutenção

Toda vez que uma funcionalidade nova for implementada no projeto, um
novo manual numerado deve ser adicionado aqui **antes** de considerar
a funcionalidade concluída — não depois, "quando der tempo". Isso está
registrado como regra permanente no prompt master
(`prompt-base-pabx.md`).
