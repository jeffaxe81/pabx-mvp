# Manual 101 — Laboratório real de registro SIP/TLS

O workflow `asterisk-lab.yml` sobe um Asterisk 22.11.0 real e executa
REGISTER SIP sobre TLS, com autenticação Digest. O laboratório usa o
código do checkout da CI e as configurações exportadas diretamente do commit Git, incluindo o
gerador de empresas do painel para criar t3. Ele não precisa de conta
SIP, tronco de operadora ou segredo de produção.

## O que comprova

- Processo Asterisk em execução, versão, ID e digest da imagem fixada.
- Montagem somente leitura da configuração e SHA do checkout limpo
  associado ao container.
- Transportes TLS e WSS carregados; certificado TLS validado pela CA
  efêmera e pelo nome `localhost`.
- Contextos separados t1-internal, t2-internal e t3-internal.
- Registro autenticado, presença do contato, desregistro e rejeição
  de senha incorreta para t1-1001, t2-1001 e t3-recepcao.
- Remoção do container e de seus volumes anônimos ao finalizar.

A existência do contexto correto não comprova isolamento funcional
completo de chamadas, filas, gravações e caixas de voz. O registro
TLS de um endpoint WebRTC não testa o transporte WSS nem sua mídia DTLS.

## Execução

Em Linux com Docker e OpenSSL disponíveis, na raiz de um checkout limpo:

```bash
python3 -m lab.asterisk_lab --report /diretorio/relatorio-sip.json
```

Na CI, o workflow executa automaticamente nas PRs e também pode ser
iniciado manualmente. Só o JSON sanitizado é publicado como artefato,
com retenção de 14 dias. Não são publicados logs SIP, senhas, certificados
privados, arquivos de configuração gerados ou gravações.

O laboratório cria recursos descartáveis com nome aleatório `axe-lab-*`
e um token exclusivo de propriedade. A limpeza verifica o token e remove
somente o ID imutável correspondente; colisões de nome preservam o
container preexistente. A imagem é fixada por versão e digest. Não sobe
o `docker-compose.yml` do operador, não altera seus arquivos e não usa
containers de produção. Utiliza rede host com serviços em loopback;
portas locais 5060, 5061, 8088 e 8089 devem estar livres. O container
executa com capabilities removidas, exceto DAC_OVERRIDE, necessário
para ler a cópia privada do UID do runner; a montagem permanece somente
leitura e o socket Docker não é montado no container.

## Resultado e segurança

Exit code 0 exige todas as 22 verificações previstas positivas; ausência,
falha, dependência indisponível ou conjunto incompleto produz exit code 1.
O resultado sempre mantém `operational_go_authorized=false`.

As senhas são geradas em cada execução, em diretório 0700 e arquivos
0600. A chave TLS dura um dia e é eliminada junto da pasta temporária após
confirmar a remoção do container. Se o Docker ficar indisponível e a
limpeza não puder ser confirmada, a execução falha e preserva a pasta
privada, indicada por `private_staging_retained=true`. Logs indisponíveis
não impedem a tentativa de remoção. Arquivos locais não versionados,
inclusive ignorados pelo Git, não são copiados para o laboratório.
O cliente aceita somente destino 127.0.0.1, exige o desafio de registro,
correlaciona Call-ID/CSeq e trata NOTIFY/OPTIONS assíncronos. Nenhum
resultado positivo é inferido apenas porque um módulo foi importado.

## Falha corrigida em configuração real

O Asterisk recusava `endpoint-base!` como nome de template e, com isso,
não carregava os ramais. A configuração agora usa a sintaxe
`[endpoint-secure](!,endpoint-base)`, também aplicada aos templates
plain e WebRTC. O parser dos testes foi corrigido para rejeitar a
sintaxe anterior. A regra vem da documentação oficial de
[templates Asterisk](https://docs.asterisk.org/Fundamentals/Asterisk-Configuration/Asterisk-Configuration-Files/Templates/Using-Templates/).

A execução real que reproduziu o problema foi
[39967057738](https://github.com/jeffaxe81/pabx-mvp/actions/runs/39967057738).

## Limites da entrega

Este laboratório não realiza chamadas, áudio RTP/SRTP, DTLS, URA/fila,
transferência, gravações, recuperação ou carga prolongada. Essas provas
permanecem nos marcos seguintes do programa e na matriz do Manual 73.
Carregar o transporte WSS não significa homologar o Webphone. O resultado
não autoriza implantação em produção nem substitui o aceite operacional.

A primeira validação completa dos registros passou em
[39967937669](https://github.com/jeffaxe81/pabx-mvp/actions/runs/39967937669):
22 de 22 verificações aprovadas. As regressões de recuperação cobrem
colisão de nome, timeout de criação, timeout de logs e configuração
não versionada/ignorada.
