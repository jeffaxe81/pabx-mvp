# Aceite real de números de entrada

Continuação do marco 7 do programa de 16 semanas: comprovar, com o
Asterisk versionado, os DIDs estáticos de t1/t2 e o cadastro dinâmico de
t3. DIDs desconhecidos, removidos e com empresa inexistente devem ser
negados antes de atender a chamada.

O laboratório usa um tronco SIP/TLS autenticado exclusivamente em
loopback, credenciais descartáveis e os contextos de produção sem
substituí-los. Para t3, o cadastro VIP real leva a chamada ao ramal 1001
sem depender de prompts ou do horário comercial. Outros ramais são
observados durante cada tentativa para detectar encaminhamento cruzado.

Abordagens: testes apenas de texto não comprovam sinalização; um tronco
externo dependeria de operadora e autorização operacional. A escolha
técnica é estender o laboratório Docker já existente, com testes reais
na CI e verificações unitárias do protocolo e dos aceites.

O relatório contém somente métricas e booleanos. Não publica senhas,
SDP, chaves ou CDR bruto. Não conclui o marco 8 (isolamento completo),
nem autoriza produção. Se um mapeamento órfão chegar à URA, será
corrigido o desvio na origem antes de atualizar o progresso.
