# Pré-verificação de PINs do voicemail (issue #88)

Esta verificação offline evita declarar isolamento entre empresas quando
persistem PINs fracos ou repetidos, contextos errados e cadastros
malformados. **Não altera segredos nem acessa mensagens.**

Exemplo com arquivo estático de referência:

```bash
python3 scripts/voicemail_pin_audit.py asterisk/voicemail.conf
```

Para conferir o ambiente em preparação, inclua os arquivos gerados
`voicemail_dynamic_*.conf` e `voicemail_tenants/*.conf` explicitamente
na lista de argumentos. Um resultado favorável para um arquivo apenas
**não abrange outros arquivos ausentes**.

O resultado JSON contém só contagens: total de mailboxes, PINs fracos,
PINs reutilizados, vínculos entre empresas inválidos e linhas
malformadas. Não imprime PIN, nome de caixa, e-mail nem mensagem.
A verificação retorna status não zero para qualquer erro encontrado.

**Limitações:** PIN forte no arquivo não comprova isolamento de acesso
por SIP, bloqueio após erros, autorização por tenant, proteção do
volume de mensagens nem funcionamento em produção. A configuração
versionada ainda usa PINs de exemplo (1234), portanto a auditoria
reprova o arquivo estático de referência. Não substituir esses
exemplos por PINs privados diretamente no Git; seguir implantação
segura, rotação individual e provas reais da issue #88.

Marco 8 permanece aberto, sem GO operacional.
