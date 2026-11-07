# Manual 149 — Marco 10: provas parciais de transferência, autorização e retenção

## Escopo

O marco 10 deixa de ser `planned` e passa a `in_progress`; **não** foi
formalmente concluído. Três critérios, cada um com evidência distinta:

1. **SIP REFER cego real**: job Asterisk | REL-13 transferencia SIP REFER em t1/t2.
   Dois tenants, chamada original atendida, REFER 202 e INVITE ao destino
   no próprio tenant. Não equivale a transferência assistida nem retorno.
2. **Gravação e autorização HTTP reais**: job Asterisk | chamadas, CDR e SRTP
   bidirecional. MixMonitor grava WAV de áudio sintético e produz CDR;
   GET autorizado retorna bytes originais; outro tenant e t10 são
   bloqueados; revogação de token tem efeito imediato.
3. **Retenção de WAV do MixMonitor real**: o MESMO job exercita
   `lab/recording_retention_checks.py`. Copia os WAVs reais para um
   filesystem privado do runner, com **arquivo fonte fora da pasta
   expurgada**. Prova não expurgar quando o recurso está desabilitado,
   apagar somente a cópia com mais de 30 dias, preservar áudio recente,
   bloquear link simbólico, preservar metadados do original e arquivo
   não-áudio. O sistema de produção não é alterado.

Os dois critérios **não homologados** são:

- `assisted_transfer_and_return`: consulta, transferência assistida,
  retorno à chamada original e áudio posterior.
- `queue_recording_full`: áudio efetivo da **chamada atendida pela
  aplicação Queue**, segregação física e download HTTP vinculado ao CDR.

## Cálculo de progresso

A fórmula anterior continua igual, sem novos pesos artificiais:
7 marcos formais concluídos + 3/5 da semana 8 + 4/5 da semana 9 +
3/5 da semana 10 = 9,0/16 = **56,3% técnico** (arredondamento a 1 casa).

O avanço é condicionado a **8/8 estático**, **16/16 Asterisk/Docker**
e **1/1 pacote RC** sobre o mesmo SHA da PR. Não confundir
com homologação formal: **7/16 = 43,8%**, GO=false.

## Próximos passos para 60%

Provas faltantes: callback AMI correlacionado fim a fim, autenticação real
do voicemail por PIN, gravação da Queue com áudio/HTTP e transferência
assistida com retorno. Não é permitido mudar `pending` somente com
testes sintéticos de parser.
