# Marco 9 — Tratamento conservador do SLA quando o AMI falha

## Regra

O campo `HoldTime` do evento `AgentConnect` do Asterisk representa
segundos inteiros de espera. Antes desta correção, a ausência, valores
negativos ou texto inválido podiam virar `0`, fazendo o atendimento
ser contado como dentro do limiar (por exemplo, 20 segundos) sem prova.

A partir desta entrega:

- `HoldTime` inteiro não negativo, ou representação decimal ASCII
  integral, é considerado no cálculo.
- Espera ausente, inválida, negativa, fracionária ou excessivamente
  longa é tratada como **desconhecida**: o evento válido continua a
  contar no denominador das chamadas oferecidas, mas **não** no
  numerador dos atendimentos dentro do SLA.
- `QueueCallerAbandon` continua sempre fora do SLA.
- As filas `fila-t1`, `fila-t2` e `fila-t10` são acompanhadas
  separadamente, sem comparação por prefixo.

## Provas e limites

Regressões unitárias em `queue-api/tests/test_queue_sla.py`.
Execução da CI estática e do laboratório Asterisk é obrigatória para
integrar. Ainda faltam ensaios reais conjuntos de fila, URA,
transbordo, callback e relatório de SLA sobre chamadas controladas.

Um SLA conservador não é uma prova de qualidade operacional. **Marco 9
permanece em andamento**, não marcado como concluído neste ajuste.
