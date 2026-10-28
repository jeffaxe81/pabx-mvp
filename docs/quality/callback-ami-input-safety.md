# Marco 9 — Higienização de pedidos de callback por evento AMI

Um evento `UserEvent: CallbackRequest` pode conter `CallerIDNum`
e `CallerIDName` fornecidos pelo chamador. Sem validação na entrada,
números inválidos ficavam no arquivo de callbacks e só eram rejeitados
ao tentar originar uma chamada.

A partir desta correção:

- O número precisa ter de 8 a 20 dígitos ASCII, com `+` inicial
  opcional; ele é armazenado apenas como dígitos.
- Nomes não textuais, com caracteres de controle ou acima de 80
  caracteres são substituídos por string vazia.
- O método de persistência valida novamente o número e o tenant,
  antes de ler ou escrever o catálogo.
- Entradas inválidas não geram callback pendente ou chamada AMI.

Os testes unitários não representam callback completado em operadora.
Ainda faltam entrada real, espera, transbordo, retorno, evento de
desfecho e apuração de SLA integrados no laboratório. Não declarar
o marco 9 como concluído por esta entrega.
