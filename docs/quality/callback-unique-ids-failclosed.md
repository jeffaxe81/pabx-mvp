# AXE PABX — Callback com identificadores únicos (Marco 9)

## Risco corrigido

O arquivo `callbacks.json` pode conter dois pedidos com o mesmo
identificador, inclusive pertencentes a empresas distintas (`t1`
e `t10`). Antes, uma pesquisa retornava a primeira ocorrência e a
rotina de discagem podia reservar ou alterar o registro errado.

## Regras

- O catálogo de callbacks só é elegível para seleção FIFO, pesquisa
  e mutação quando seus identificadores são textos não vazios e
  globalmente únicos.
- Pedidos novos tentam gerar outro ID em caso de colisão; depois de
  vinte tentativas sem ID livre, a operação falha sem gravar o arquivo.
- A reserva para discagem aceita somente contagem inteira de
  tentativas no intervalo de zero até `MAX_ATTEMPTS - 1`.
- Um evento AMI de desfecho não altera callbacks com contagem
  corrompida ou status diferente de `discando`.
- As negativas não substituem nem salvam o snapshot, preservando
  evidências para correção administrativa.

As regressões em `queue-api/tests/test_callbacks.py` incluem
duplicidade entre `t1` e `t10`, mesmo quando uma ocorrência já
está concluída; IDs malformados; colisão gerada; tentativas inválidas
e integridade dos bytes persistidos.

## Limites do aceite

Os testes demonstram comportamento do backend e da API simulada,
não um fluxo real de URA, transbordo, retorno por operadora ou SLA.
A conclusão formal do marco 9 requer os ensaios de ponta a ponta
previstos no plano. Nenhuma autorização de produção é concedida.
