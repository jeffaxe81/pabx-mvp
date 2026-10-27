# Manual 120 — Correlação de tentativas e diagnóstico WebRTC

## Cinco frentes de evolução nesta entrega

1. **Fencing de reservas:** cada contato de campanha ou callback recebe
   `attempt_id` aleatório de 128 bits no momento da reserva para
   `discando`. Tentativas de reservar uma entrada que já não esteja em
   `pendente` falham; não incrementam o contador.
2. **Rastreabilidade AMI:** a ação `Originate` inclui
   `ActionID=<attempt_id>`. Esse identificador é gravado
   no snapshot e disponibilizado na CLI de revisão (Manual 119).
   **Importante:** `DialEnd` nativo do Asterisk não garante que o
   `ActionID` será enviado. A atualização automática não deve presumir
   essa propagação.
3. **Correlação segura:** quando mais de um registro `discando`
   do mesmo tenant usa o mesmo número, o evento AMI sem uma chave
   inequívoca não altera nenhuma campanha nem callback. Isso vale
   inclusive quando o mesmo número consta nas duas categorias.
   Se um evento AMI confiável contiver `AttemptID`, aplica-se
   somente à tentativa correspondente. As duas coleções são
   protegidas com travas na mesma ordem para evitar deadlock.
   A deduplicação de contatos também evita números repetidos dentro
   da mesma campanha nova.
4. **Diagnóstico WebRTC:** o navegador precisa de **duas amostras
   consecutivas completas** de DTLS, SRTP, RTP bidirecional, ICE,
   áudio remoto e frequências corretas, dentro de 30 segundos.
   Não se reduz nenhum critério de segurança para aprovar o teste.
   O laboratório continua verificando CDR, canais e contatos até
   15 segundos, mesmo se o navegador falhar; esses resultados passam
   a ser registrados independentemente do problema de mídia.
5. **Regressões:** novos testes cobrem duplo claim, IDs únicos,
   campanhas com número repetido, duas campanhas com mesmo número,
   callbacks duplicados, conflito campanha/callback e ActionID
   idêntico ao ID duravelmente persistido.

## Limitações explícitas

O `ActionID` permite diagnosticar pedidos de Originate e eventos
que efetivamente carreguem `AttemptID`, mas **não é uma correlação
ponta a ponta garantida pelo DialEnd nativo**. O comportamento seguro
para eventos ambíguos é manter `discando` até auditoria (Manual 119).
Não reprocessar automaticamente a chamada ao reiniciar.

Os testes reais do WebRTC estavam falhando na PR #73, sobretudo
mídia/DTLS intermitente no Chromium; resultados posteriores de CDR
e encerramento também permaneciam incompletos após a falha antecipada
do navegador. Esta entrega altera limites de espera e coleta de
evidências, mas **não se declara correção ou GO antes do laboratório
real passar**. O laboratório de 26/10 no SHA desta PR é o
critério verificável.

O travamento cross-process da PR #73 requer que todas as instâncias
usem o mesmo volume compatível com `flock`. Para cluster com
volumes independentes, ainda é necessário banco transacional e
fencing distribuído.

Sem merge, deploy ou GO até a revisão de todos os gates.

```bash
cd queue-api
python3 -m pytest -q tests/test_outbound_attempt_fencing.py \
  tests/test_campaign_tenant_http.py tests/test_outbound_safety.py
```
