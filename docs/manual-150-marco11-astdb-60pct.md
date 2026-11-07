# Manual 150 — Marco 11: recuperação AstDB real e avanço técnico a 60%

## Resultado esperado, condicionado à CI

Com três provas independentes do marco 11, o progresso técnico
ponderado alcança **60,0%** pela fórmula original de 16 semanas,
sem qualquer mudança nos pesos:

- **7** marcos formalmente encerrados;
- semana 8: **3/5** critérios de laboratório;
- semana 9: **4/5** critérios de laboratório;
- semana 10: **3/5** critérios de laboratório;
- semana 11: **3/5** critérios de laboratório.

Total: 7 + 0,6 + 0,8 + 0,6 + 0,6 = **9,6/16 = 60,0%**.

O indicador formal permanece **7/16 = 43,8%** e o GO de produção
permanece **falso**. A semana 11 entra apenas em andamento.

## Prova A — Arquivos restaurados via scripts de backup

O job existente "Docker | rollback de arquivos e volumes isolados"
executa de fato backup/backup.sh, backup/validate_archive.py e
backup/restore.sh em diretórios temporários. Usa arquivos
**sintéticos**, com bytes conhecidos. Primeiro recusa confirmação
negativa sem alterar dados; após confirmação positiva, exige que todos
os arquivos originais sejam restaurados exatamente.

Isso comprova **o mecanismo de restauração de arquivos**, não uma
restauração integral de perfis produtivos de PABX.

## Prova B — Volumes Docker restaurados

O mesmo job cria dois volumes Docker **efêmeros e isolados**,
escreve marcadores próprios, realiza backup, modifica ambos os
volumes e restaura os bytes originais, conferindo os dois volumes
antes de removê-los. Nenhum volume de produção é acessado.

## Prova C — AstDB lógico real t1, t2 e t3

O novo job "Asterisk | recuperacao logica AstDB real por empresa"
roda em Asterisk descartável, com identificadores temporários
e nenhum tronco público. Para cada tenant:

1. Verifica ausência inicial de duas chaves na família própria;
2. Escreve dois valores efêmeros com database put;
3. Obtém snapshot a partir de database get do runtime;
4. Remove as chaves com database del e verifica ausência;
5. Reimporta exclusivamente o snapshot observado;
6. Lê as chaves restauradas e confere bytes exatos;
7. Verifica isolamento cruzado de t1, t2 e t3 depois de
   restaurar todas as famílias;
8. Remove as chaves de laboratório e confirma a limpeza.

O relatório de CI contém apenas booleanos. Não exibe valores
temporários, ramais/telefones reais ou configurações confidenciais.
O processo **não** copia nem recupera o arquivo SQLite físico da
AstDB: a prova é de **exportação e restauração lógica de chaves**.

Comando: python3 -m lab.asterisk_lab --astdb-restore --report lab-results/astdb-restore.json

## Pendências que impedem conclusão formal

- **Perfis e ramais:** backup/restauração dos perfis reais PJSIP,
  autenticação e vínculos ao tenant.
- **Gravações:** recuperação de WAVs com checksum, permissões e
  autorização HTTP pós-restauração.

Os critérios anteriores de callback fim a fim, autenticação de
voicemail por PIN e gravação da Queue WebRTC também permanecem
pendentes, mesmo após 60% técnico.

## Gate de evidência

O registro de 60,0% só pode ser integrado após **8/8 CI estática**,
**17/17 Asterisk/Docker real** e **1/1 pacote RC** no mesmo HEAD.
Caso um job falhe, o indicador da main continua em **56,3%** até
que a correção seja validada. GO=false.
