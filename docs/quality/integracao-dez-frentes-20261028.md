# AXE PABX — Integração das dez frentes do marco 8 / avanço do marco 9

Registro de integração da árvore após as PRs #105–#112, #115 e #114.
A configuração e os testes estão na `main`; esta alteração de
documentação permite executar novamente a matriz CI sobre a árvore
**com todas as entregas em conjunto**, em vez de confiar apenas nos
resultados individuais anteriores.

## Matriz técnica

| Frente | Entrega integrada | Evidência automatizada |
| --- | --- | --- |
| 1 | #105 — voicemail exige canal ativo em VoiceMailMain | laboratório SIP/voicemail |
| 2 | #106 — proveniência de gravação estritamente validada | pytest gravações |
| 3 | #107 — fonte CDR compartilhada entre empresas rejeitada | pytest catálogo |
| 4 | #108 — CDR malformado não cria candidatos de gravação | pytest entradas negativas |
| 5 | #109 — HTTP t1/t10 e catálogo atualizado em tempo real | HTTP loopback |
| 6 | #110 — seis combinações cruzadas de pickup negadas | HTTP loopback / AMI simulado |
| 7 | #111 — pacote de evidência recusa chaves JSON duplicadas | pytest release |
| 8 | #112 — status de homologação contraditório é negado | pytest QA |
| 9 | #115 (substitui #113) — gravações HTTP por agente e revogação | HTTP loopback |
| 10 | #114 — snapshot de callback inconsistente bloqueia FIFO | pytest callbacks |

## Gate de integração

Exigir na PR desta verificação:
- `AXE PABX | validação estática`: todos os jobs aprovados;
- `AXE PABX | laboratório Asterisk real`: todos os jobs aprovados;
- mesmo SHA e nenhum job falho, pendente ou dispensado;
- nenhum atalho que altere as regras de segurança para obter verde.

Mesmo com este gate aprovado, **não confundir integração com
homologação completa**. O programa tem 16 marcos e ainda mantém
7 concluídos (43,8%). Os marcos 8 e 9 estão em andamento.

## Faltas de homologação que impedem marcar 50% ou 56,3%

- Entrada DTMF e PIN válido/inválido no voicemail real; tentativa de
  acesso a mensagens de outra empresa, política de bloqueio.
- Proveniência, proteção e leitura negativa de arquivos gerados
  de chamadas reais no volume Asterisk e integração de identidade/SSO.
- Cenário completo de URA, espera, transbordo, callback,
  correlação de resultado AMI e apuração de SLA.
- Aprovação de evidência por responsável e aceite operacional
  conforme `docs/modelo-homologacao-pabx.json`.

Esta verificação não altera a porcentagem formal ou autoriza
implantação/GO; `operational_go_authorized` permanece `false`.
