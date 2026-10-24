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
40. [Aviso de gravação / conformidade LGPD](manual-40-aviso-gravacao-lgpd.md)
41. [Estacionamento de chamada](manual-41-estacionamento-chamada.md)
42. [Monitoramento de chamada](manual-42-monitoramento-chamada.md)
43. [Sala de conferência ad-hoc](manual-43-sala-conferencia.md)
44. [Motivo de pausa do agente](manual-44-motivo-pausa-agente.md)
45. [Overflow entre filas](manual-45-overflow-filas.md)
46. [SLA de fila](manual-46-sla-fila.md)
47. [Migração faster-whisper → whisper.cpp](manual-47-migracao-whisper-cpp.md)
48. [Síntese de voz / TTS (Piper padrão, XTTS opcional)](manual-48-tts-piper-xtts.md)
49. [Confirmação falada do atendente virtual (fase 2 do TTS)](manual-49-confirmacao-falada-atendente-virtual.md)
50. [Geração de segredos fortes antes do deploy](manual-50-geracao-segredos.md)
51. [Verificação pós-deploy](manual-51-verificacao-pos-deploy.md)
52. [Remoção de tenant pelo wizard](manual-52-remocao-tenant.md)
53. [Lista de áudios existentes no painel](manual-53-lista-audios.md)
54. [Limpeza de ramais órfãos ao remover tenant](manual-54-limpeza-ramais-orfaos.md)
55. [Monitoramento de ramais dinâmicos](manual-55-monitoramento-ramais-dinamicos.md)
56. [Overflow entre filas configurável por tenant](manual-56-overflow-por-tenant.md)
57. [Histórico de tempo em pausa por motivo](manual-57-historico-pausa.md)
58. [Histórico de SLA por dia](manual-58-historico-sla.md)
59. [Interface do histórico de SLA no painel](manual-59-interface-historico-sla.md)
60. [Reprodução de áudio na lista do painel](manual-60-reproducao-audio.md)
61. [Correção de vazamento de memória no player de áudio](manual-61-correcao-vazamento-audio.md)
62. [Limpeza de mapeamento ao renumerar ramal](manual-62-limpeza-renumeracao.md)
63. [Filtro de intervalo de datas nos relatórios](manual-63-filtro-data-relatorios.md)
64. [Integração de voz na URA principal](manual-64-integracao-voz-ura.md)
65. [Rodando o projeto a partir do Windows via WSL2](manual-65-windows-wsl2.md)

66. [CI e validação das entregas](manual-66-ci-e-validacao.md)
67. [Interface AXE PABX no padrão do Despacho](manual-67-interface-despacho.md)

68. [Rejeitar chamadas com DID desconhecido](manual-68-did-sem-tenant.md)

69. [Diagnóstico somente leitura do SIP/Asterisk](manual-69-diagnostico-sip.md)

70. [Segurança da verificação AMI](manual-70-verificador-ami.md)

71. [Validação defensiva do wizard multiempresa](manual-71-validacao-wizard-tenants.md)

72. [Credenciais SIP seguras no wizard de tenants](manual-72-segredos-sip-wizard.md)

73. [Matriz de homologação e critérios de GO](manual-73-gates-homologacao.md)

74. [PINs seguros de correio de voz por tenant](manual-74-voicemail-pins-seguros.md)

75. [Prevenir conflito de DID estático entre empresas](manual-75-did-estatico-colisao.md)

76. [Proteção XSS nas tabelas administrativas](manual-76-xss-tabelas-admin.md)


77. [Arquivos críticos obrigatórios no verificador de deploy](manual-77-arquivos-segredos-obrigatorios.md)

78. [Listagem segura de gravações](manual-78-indice-gravacoes-seguro.md)

79. [Validação segura de ramais e credenciais SIP](manual-79-ramais-validacao-segredos.md)

80. [Credenciais e isolamento de gravações por tenant](manual-80-acesso-gravacoes-tenant.md)

81. [PIN seguro de voicemail para novos ramais](manual-81-pins-voicemail-ramais.md)

82. [Ramais de tenants dinâmicos t3+](manual-82-ramais-tenants-dinamicos.md)

83. [Importação assistida e auditável de gravações](manual-83-catalogo-gravacoes.md)

84. [Emissão e revogação de credenciais de gravações](manual-84-credenciais-gravacoes.md)

85. [Persistência atômica do cadastro de ramais](manual-85-cadastro-ramais-atomico.md)

86. [Limites de requisição JSON administrativa](manual-86-limites-json-admin.md)

87. [Publicação recuperável de arquivos Asterisk e migração de volume](manual-87-publicacao-asterisk-rollback.md)

88. [Pré-check de arquivos gerados do Asterisk](manual-88-precheck-gerados-asterisk.md)

89. [Conciliação CDR com propostas de gravações](manual-89-conciliacao-cdr-gravacoes.md)

90. [Framing TCP e respostas AMI correlacionadas](manual-90-ami-tcp-framing.md)

91. [Leitura completa de listas AstDB pelo AMI](manual-91-ami-dbgettree-eventos.md)

92. [Verificação semântica de reload AMI](manual-92-validacao-semantic-reload-ami.md)

93. [Confirmação obrigatória de alterações AstDB no AMI](manual-93-confirmacao-astdb-ami.md)

94. [Criação de tenant com compensação de DID e arquivos](manual-94-tenant-create-compensation.md)

95. [Remoção compensável de tenants e ramais](manual-95-remocao-tenant-compensavel.md)

96. [Auditoria somente leitura do Asterisk em execução](manual-96-auditoria-runtime-asterisk.md)

97. [Compatibilidade do CLI PJSIP na auditoria de laboratório](manual-97-pjsip-cli-compat.md)

98. [Rollback do catálogo de tenants após falha tardia](manual-98-tenant-registry-compensation.md)

99. [Programa AXE PABX de 16 semanas e progresso verificável](manual-99-plano-16-semanas-pabx.md)

100. [Pacote de evidências vinculado ao SHA de release](manual-100-release-evidence.md)

## Regra de manutenção

Toda vez que uma funcionalidade nova for implementada no projeto, um
novo manual numerado deve ser adicionado aqui **antes** de considerar
a funcionalidade concluída — não depois, "quando der tempo". Isso está
registrado como regra permanente no prompt master
(`prompt-base-pabx.md`).


101. [Laboratório real de registro SIP/TLS](manual-101-laboratorio-sip-real.md)
102. [Chamadas internas reais com SRTP](manual-102-chamadas-srtp-reais.md)
103. [Webphone real com WSS e DTLS-SRTP](manual-103-webrtc-real.md)
104. [Números de entrada e encerramento dos marcos 6 e 7](manual-104-webrtc-dids-reais.md)
105. [Trilha CEL e CDR correlacionado no aceite de DIDs](manual-105-cel-dids.md)
106. [Gate estático inicial de isolamento multiempresa](manual-106-isolamento-estatico.md)
107. [Gravações: isolamento ACL por tenant](manual-107-gravacoes-isolamento-acl.md)
108. [Roteamento seguro de filas por empresa](manual-108-filas-por-tenant.md)
109. [Negativas SIP reais entre empresas](manual-109-negativas-sip-entre-empresas.md)
110. [Catálogo ACL aberto atomicamente, sem symlink](manual-110-catalogo-acl-atomico.md)
111. [Listagem de gravações segura por descritor de diretório](manual-111-listagem-gravacoes-fd.md)
112. [Pickup de chamadas restrito à empresa](manual-112-pickup-isolamento-tenant.md)
113. [Filas: autenticação Bearer e visibilidade por tenant](manual-113-autenticacao-filas-tenant.md)
114. [Presença, pausa e estados por empresa](manual-114-presenca-pausa-isoladas.md)
