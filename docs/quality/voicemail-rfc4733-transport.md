# Voicemail: transporte DTMF RFC4733 no laboratório Asterisk

## Escopo comprovado pelo pipeline

O job de laboratório `voicemail-runtime` executa SIP/TLS, SDES-SRTP e chamada autenticada `*97` nos tenants `t1`, `t2` e `t3`. O cliente sintético negocia `telephone-event/8000` (PT 101) no SDP, confere resposta remota e envia um evento DTMF sintético com 3 pacotes finais (RFC4733) no canal SRTP. A implementação exige mídia e contexto de canal exatos antes de transmitir.

O relatório fornece apenas verificações booleanas de negociação e transmissão; **não grava nem imprime dígitos ou PINs**. O áudio usa loopback e o container é descartado após a execução.

## O que este teste NÃO comprova

- Que o Asterisk reconheceu ou processou o evento como um dígito, nem que a aplicação VoiceMailMain aceitou um PIN.
- Login correto, PIN incorreto, tentativas e bloqueio de acesso, nem isolamento de mensagens ou de diretórios de spool.
- Sessão/SSO unificada, segregação dos volumes e gravações operacionais, restauração ou GO.

Para concluir o Marco 8 ainda são necessários testes reais com PIN efêmero válido e inválido, prova de negação cruzada (incluindo t1/t10), mensagem persistida e consulta/descarga autorizada sob isolamento de cada empresa. Vincular o relatório final ao SHA da instalação efetivamente testada e à revisão humana de evidência.

O progresso formal permanece **7/16 = 43,8%** até que a homologação integral seja comprovada. `operational_go_authorized=false`.
