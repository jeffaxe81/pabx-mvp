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

## Regra de manutenção

Toda vez que uma funcionalidade nova for implementada no projeto, um
novo manual numerado deve ser adicionado aqui **antes** de considerar
a funcionalidade concluída — não depois, "quando der tempo". Isso está
registrado como regra permanente no prompt master
(`prompt-base-pabx.md`).
