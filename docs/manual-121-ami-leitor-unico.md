# Manual 121 — Canal AMI com leitor único e correlação de respostas

## Problema corrigido

O `queue-api/ami_client.py` anterior tinha dois consumidores de
`recv()` no mesmo socket TCP: a thread de eventos e o envio HTTP de
comandos `Originate`, `Redirect`, `DBPut` e `QueuePause`.
Sob concorrência, um consumidor podia ler a resposta do outro,
descartar um `DialEnd`, aceitar um evento como resposta ou aguardar
indefinidamente um fragmento TCP. Isso gera resultados incertos,
especialmente ao usar campanhas e callbacks paralelos.

## Comportamento novo

- Há **um único leitor** do socket AMI. Ele conserva bytes entre
  chamadas de `recv()`, reconstrói blocos completos delimitados por
  `CRLF CRLF` e rejeita buffer acima de 128 KiB.
- Cada solicitação possui `ActionID` único; os retornos são
  correlacionados **exclusivamente** por esse campo, incluindo o ID
  previamente gerado para cada tentativa de campanha/callback (Manual 120).
  Respostas anônimas ou com IDs não reconhecidos jamais autorizam uma
  chamada.
- Pedidos HTTP aguardam seu próprio evento de conclusão com timeout
  finito (5 segundos, padrão). Fechamento de socket, excesso de dados e
  resposta ausente falham sem confirmação positiva; **não há rediscagem
  automática**.
- Eventos assíncronos são entregues a uma fila limitada de 1024
  entradas e consumidos por outra thread. Um evento AMI que precise
  originar outra ação pode fazê-lo sem disputar leitura ou travar
  o leitor. Excesso de eventos interrompe a conexão em vez de
  continuar após perder eventos silenciosamente.
- O banner do Asterisk admite fragmentação e bytes posteriores já
  recebidos, preservados para o leitor.

## Testes automatizados

```bash
cd queue-api
python3 -m pytest -q tests/test_ami_client_framing.py \
  tests/test_ami_protocol.py tests/test_campaign_tenant_http.py
```

O arquivo `test_ami_client_framing.py` usa sockets Python reais
conectados localmente em `socketpair()` e verifica: pacotes
fragmentados, eventos intercalados, respostas de comandos simultâneos
fora de ordem, callback que envia outro comando, resposta com ActionID
incorreto, desconexão, limite de tamanho, login e tentativa de reusar
um ActionID ainda pendente.

**Limites:** confirmações de `Originate` por AMI indicam aceite da
ação, **não** comprovação de estabelecimento da chamada ou do
`DialEnd`. Reconciliação ponta a ponta depende de correlação
auditável com canais/Uniqueid do Asterisk. Não há reconnect automático,
replicação transacional entre hosts independentes ou liberação de GO.

A entrega fica em PR draft baseada na #74, que passou os três
pipelines, inclusive laboratório Asterisk 5/5. Nenhuma alteração desta
PR é automaticamente implantada na produção.
