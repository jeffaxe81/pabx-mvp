# Manual 104 — Trilha CEL e CDR da mesma chamada de DID

## Finalidade

Complementa o laboratório da PR #57 com Channel Event Logging (CEL) do
Asterisk real. Um SIP 403 e a ausência de toque nos outros ramais são
conferidos junto ao ciclo completo e ao CDR da mesma tentativa. Isso
impede aprovar uma rejeição a partir de eventos ausentes ou de chamadas
diferentes.

O teste preserva os DIDs estáticos de t1/t2, o DID dinâmico de t3 e os
casos negativos desconhecido, removido e associado a empresa inexistente.
O tronco TLS, os contextos, os observadores e a mídia SRTP são os da #57.

## Execução e critérios

Em Linux com Docker e OpenSSL, checkout limpo e portas de laboratório livres:

```bash
python3 -m pip install -r lab/requirements.txt
python3 -m lab.asterisk_lab --calls --dids --report /diretorio/resultado-dids.json
```

O modo exige **113 verificações**: 70 de registros/chamadas/SRTP, 36 de
roteamento DID e sete de CEL. Resultado ausente, incompleto ou negativo
retorna código de saída 1. Os outros modos não habilitam CEL.

| Prova | Aceite exigido |
|---|---|
| Ciclo | CHAN_START, HANGUP, CHAN_END e LINKEDID_END presentes |
| Correlação | Uniqueid/linkedid coerentes, canal constante por uniqueid |
| DID conhecido | Somente duas pernas, ponte e destino 1001 da empresa correta |
| DID rejeitado | Causa 21, nenhuma resposta, ponte ou nova perna |
| Efeitos da rejeição | Nenhum Dial, Queue, URA, voicemail, reprodução ou gravação |
| CDR | Um registro da mesma origem CEL, empresa/contexto/destino coerentes |
| Cursor | Somente novos eventos; truncamento ou substituição do histórico reprova |

CDR negativo deve ter empresa vazia, destino de rejeição/DID original,
nenhum canal de destino, duração tarifada zero e disposição não atendida.
CDR conhecido deve estar atendido, com duração positiva e ambos os canais
da trilha. Evidências de linhas diferentes nunca são combinadas.

## Isolamento e dados

`cel.conf` e `cel_custom.conf` são criados apenas na cópia privada do
laboratório, com modo 0600. CEL acompanha as aplicações de roteamento, atendimento, gravação e execução
de scripts nessa execução descartável; isso não altera a configuração ou as rotas da
produção. O diretório de saída é criado antes das primeiras chamadas.

A leitura é limitada a 1 MiB e os CSVs são validados antes do uso. Os
registros, identificadores, argumentos de aplicação, SDP, chaves e áudio
permanecem no container/memória e não são anexados. O relatório e o console
contêm somente nomes fixos de cenário e diagnósticos booleanos. O container
é removido pelo procedimento de propriedade do Manual 101, inclusive em falha.

## Histórico e validação

- O primeiro protótipo verificava novos CDRs negativos por lista; a #57
  passou a exigir uma linha nova válida antes desta integração.
- Esta entrega acrescenta a correlação do CDR com CEL e prova as aplicações
  efetivamente executadas. Trilha vazia, parcial, cruzada ou causa ambígua
  são cobertas por regressões.
- A primeira execução real, [40008169936](https://github.com/jeffaxe81/pabx-mvp/actions/runs/40008169936),
  aprovou 110/113 verificações: as três rejeições tiveram causa 21, ciclo
  completo, CDR correlacionado e nenhum atendimento ou efeito lateral.
  O diagnóstico composto dos três caminhos conhecidos ainda reprovou;
  foi detalhado em booleanos para investigar o formato real do CEL.
- A causa foi `apps=all`: o código de Asterisk 22.11.0 armazena `all`
  como um nome literal. A preparação agora lista explicitamente as
  aplicações auditadas e confere sua presença em `cel show status`.
  `events=ALL` continua habilitando todos os tipos de evento. A prova
  negativa exige também o evento real de `Hangup(21)` e recusa aplicações
  inesperadas, como Record, AGI, EAGI e System. Referência de implementação:
  [main/cel.c — Asterisk 22.11.0](https://github.com/asterisk/asterisk/blob/22.11.0/main/cel.c).
- Um teste herdado de cleanup iniciava seu timeout antes de o processo Node
  instalar o handler de sinal. A fixture agora confirma prontidão antes do
  timeout, com atraso de partida simulado; processos e sinais continuam reais.
- A revisão independente e a execução final serão registradas após a
  aprovação dos critérios. Nenhum marco é promovido por testes de fixture.

## Limites

O tráfego de teste usa loopback, números sintéticos e um tronco autenticado.
O caminho VIP configurado para t3 permite chegar ao ramal controlado pela
URA real; não homologa todas as opções do menu, gateway físico, operadora,
SIP de outras redes ou qualidade acústica. Isolamento funcional completo,
filas, transferência, gravações, restauração e carga continuam sujeitos
aos aceites próprios. `operational_go_authorized` permanece `false`.

PR complementar: [#58](https://github.com/jeffaxe81/pabx-mvp/pull/58),
dependente da [#57](https://github.com/jeffaxe81/pabx-mvp/pull/57).
