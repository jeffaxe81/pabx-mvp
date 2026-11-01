# AXE PABX — Controle de 1.000 funcionalidades inéditas

Status: auditoria inicial; **nenhuma das 1.000 funcionalidades foi declarada implementada por este documento**.

## Escopo
PABX puro (Asterisk/PJSIP): ramais, chamadas, troncos, discagem, transferência, grupos de toque, conferência, voicemail, gravação, segurança, multiempresa, administração, provisionamento, WebRTC, disponibilidade, backup, observabilidade, CDR, APIs e desempenho. Contact Center e IA excluídos.

## Regra de não duplicação
Antes de abrir qualquer implementação:
1. Conferir README, código, docs, issues e PRs do repositório.
2. Registrar ID único `AXEF-0001` até `AXEF-1000`, descrição e critérios de aceite.
3. Comparar comportamento esperado e assinaturas de cenários, não apenas nomes.
4. Classificar como EXISTENTE, PARCIAL, NOVA ou BLOQUEADA; somente NOVA pode contar como entrega inédita.
5. Não reexecutar testes históricos como se fossem inéditos; referenciar seus IDs.
6. Registrar commit, PR, evidência de CI e homologação real separadamente.

## Achados iniciais confirmados no README
Já documentados: isolamento lógico por tenant, SIP TLS/SRTP, provisionamento Yealink, webphone WebRTC, transferência cega e assistida, BLF, gravação, grupos de toque, voicemail, 2FA, antifraude, backup e CDR. **Não cadastrar essas capacidades genéricas como novas sem identificar um incremento funcional específico.**

## Frentes de triagem (50 candidatas por frente)
01 Ramais SIP; 02 Chamadas; 03 Troncos; 04 Dialplan; 05 Transferências; 06 Grupos de toque; 07 Conferência; 08 Voicemail; 09 Gravação; 10 Segurança; 11 Multiempresa; 12 Administração web; 13 Provisionamento; 14 WebRTC; 15 Disponibilidade; 16 Backup; 17 Monitoramento; 18 CDR; 19 APIs; 20 Escalabilidade.

Total: 20 × 50 = 1.000 **vagas de análise**, não 1.000 entregas concluídas.

## Primeiro lote de auditoria
- AXEF-0001: bloqueio de chamadas internacionais por tenant — verificar se já existe regra equivalente.
- AXEF-0002: janela de horários por ramal para chamadas externas — verificar regras atuais.
- AXEF-0003: lista de destinos permitidos por tronco — verificar controle atual.
- AXEF-0004: limite de chamadas simultâneas por ramal — verificar PJSIP/dialplan.
- AXEF-0005: rotação de credenciais SIP sem interromper chamadas ativas — verificar API.
- AXEF-0006: diagnóstico de falha de registro SIP por motivo — verificar observabilidade.
- AXEF-0007: auditoria de alterações de rota por administrador — verificar logs.
- AXEF-0008: expiração programada de ramais temporários — verificar provisionamento.
- AXEF-0009: exportação de inventário SIP por tenant — verificar painel.
- AXEF-0010: teste de restauração de configuração sem escrita em produção — verificar backup.

Esses itens são **candidatos**, sujeitos a deduplicação no código antes da implementação.
