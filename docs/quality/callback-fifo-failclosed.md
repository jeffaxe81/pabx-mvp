# Marco 9 — Callback FIFO rejeita catálogos pendentes corrompidos

A API lê um snapshot JSON de pedidos de retorno. Antes desta entrega,
o seletor FIFO confiava que todo item continha `status` e
`requested_at` comparáveis. Um arquivo antigo ou adulterado podia
provocar exceção ou uma seleção indevida.

Agora a seleção falha fechado (sem Originates) se um registro pendente
possuir identificador inválido, timestamp não numérico, negativo, NaN,
infinito, telefone fora do padrão ou tenant malformado. Os registros
válidos continuam obedecendo à ordem de solicitação.

**Limites:** esta validação não substitui a proteção do arquivo em
disco, um fluxo real de callback com SIP/AMI, nem homologação de URA,
espera, transbordo e SLA. O marco 9 continua `in_progress`.
