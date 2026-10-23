# Evidência completa de chamadas entrantes

Continuidade autorizada do AXE PABX. Esta mudança complementa a PR #57;
não cria outro runner de DIDs. O runner existente verifica SIP, observadores
de ramais e CDR. A base já foi corrigida para exigir um novo CDR negativo;
esta mudança acrescenta prova do caminho completo e da causa de rejeição,
correlacionada ao mesmo registro da tentativa.

O implementador adota CEL (Channel Event Logging) no container privado para
exigir uma chamada completa, da criação ao último canal encerrado, com as
pernas correlacionadas por uniqueid/linkedid. Nas três chamadas conhecidas,
CEL deve apontar apenas para o destino correto e concordar com o mesmo CDR.
Nas três rejeições, deve haver causa 21, nenhuma resposta, ponte, destino,
fila, URA, voicemail ou gravação e um CDR não atendido da mesma tentativa.

Alternativas: manter somente sinalização, observadores e CDR não demonstraria
as aplicações executadas antes da rejeição;
AMI adicionaria credenciais/porta desnecessárias ao laboratório. CEL usa
módulos do Asterisk já existente, sem alterar as rotas de produção.

As configurações de CEL são efêmeras, privadas e ativadas apenas no modo
`--dids`. Os registros brutos nunca são exportados. O relatório contém
somente booleanos; entradas ausentes, truncadas, conflitantes ou de outra
chamada reprovam. Continua usando o isolamento, SHA e cleanup da #53/#54.

Não autoriza GO, merge ou implantação. Não conclui isolamento funcional
completo, URA, backup ou qualidade de áudio externo. O aceite de DIDs
depende de CI real e das correções/aceites da PR base #57.
