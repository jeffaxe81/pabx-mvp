# Manual 147 — Seis frentes de integridade do AXE PABX

## Objetivo

Reforçar seis caminhos do PABX e Contact Center com provas negativas,
sem aumentar os percentuais de homologação antes de um novo fluxo
fim a fim comprovado. As mudanças seguem as salvaguardas do
laboratório Asterisk e do servidor HTTP autenticado.

### 1. WebRTC — canais SIP independentes

As seis chamadas Chromium (t1/t2/t3, ambas as direções) devem
ter **CDR e canais PJSIP distintos**. Um CDR completo mas
reutilizando uma perna SIP de outra chamada não conta como prova.
O relatório de validação continua sanitizado, sem expor canal,
número ou credenciais. Código: \`lab/webrtc_checks.py\`.

### 2. Filas — mesma chamada durante toda a espera

A prova de 1 segundo em \`Queue\` agora identifica o canal PJSIP
completo e reinicia a janela se aparecer uma nova instância do mesmo
ramal. Uma observação de encaminhamento cruzado registrada depois
de um snapshot correto não pode ser ocultada pelo sucesso anterior.
Código: \`lab/queue_tenant_checks.py\`.

### 3. Callback — ActionID AMI inequívoco

Um evento \`DialEnd\` pode não conter \`ActionID\`. Quando o campo
está presente, porém, deve apontar para a **mesma tentativa** do
callback/campanha. Um \`Uniqueid\` aparentemente correto não mascara
ActionID diferente nem a prova de outra tentativa AXE.
Código: \`queue-api/outbound_correlation.py\`.

### 4. Voicemail — seções de autenticação não ambíguas

O preflight do Asterisk recusa \`[general]\` repetida, cabeçalhos
de seção malformados e outros \`maxlogins\` inconsistentes. Segue
exigindo \`maxlogins\` único entre 1 e 3; não expõe PIN de usuário.
Código: \`lab/voicemail_pin_checks.py\`.

**Limitação:** é validação de configuração, não prova de autenticação
real com PIN válido, incorreto, lockout e leitura do spool.

### 5. SLA — defesa também no agregador

A consolidação diária valida individualmente os registros de
histórico em memória, mesmo quando não vieram do armazenamento
JSONL previamente auditado. Datas inválidas, contadores booleanos,
\`within_sla > offered\` e filas com caracteres de controle
reprovam a consolidação. O percentual é recalculado com os
contadores, inclusive para \`fila-t1\` e \`fila-t10\` separadamente.
Código: \`queue-api/queue_sla.py\`.

### 6. Gravações — autorização antes do limite de página

O endpoint \`GET /api/recordings\` deriva os nomes autorizados do
catálogo autenticado, **antes** de classificar e selecionar as
50 gravações mais recentes. Assim, um excesso de arquivos de t2
ou t10 não impede t1 de listar seus próprios arquivos antigos.
A rotina de listagem recebe um conjunto explícito de nomes
permitidos; symlinks/arquivos não regulares continuam recusados.
Sem ACL não há resultado. Códigos: \`queue-api/server.py\` e
\`queue-api/recordings.py\`.

## Critérios de aceite

- Regressões próprias por frente, incluindo CDR e canais repetidos,
  PJSIP de chamada distinta, ActionID conflitante, seções
  \`[general]\` duplicadas, linhas SLA inválidas e mais de 100
  arquivos de outras empresas competindo com gravações próprias.
- CI estática, Asterisk/Docker real e pacote RC totalmente
  aprovados **sobre o mesmo SHA** antes do squash merge.
- Nenhum dado privado, arquivo de áudio ou senha nos logs.

## Escopo de homologação

Esses refinamentos **não** constituem gravação real de chamada
atendida por Queue via WebRTC com leitura HTTP, resultado de
callback real, login em voicemail por PIN correto/incorreto ou
relatório SLA de evento AMI gerado por atendimento real.
\`recordings_real\`, \`voicemail_messages\`, \`callback_outcome\` e
\`sla_report\` continuam pendentes. Avanço técnico ponderado:
**51,3%**; formal: **7/16 (43,8%)**. **GO=false**.
